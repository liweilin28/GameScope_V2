"""
来源：学生 + AI
作用：生成 Steam 游戏分析需要的衍生字段。
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from backend.services.utils import split_multi_value, to_numeric


def _extract_release_year(df: pd.DataFrame) -> pd.Series:
    if "release_date" not in df.columns:
        return pd.Series([np.nan] * len(df), index=df.index)
    parsed = pd.to_datetime(df["release_date"], errors="coerce")
    year = parsed.dt.year
    fallback = df["release_date"].astype(str).str.extract(r"(\d{4})", expand=False)
    return year.fillna(pd.to_numeric(fallback, errors="coerce"))


def _price_level(value: float | int | None) -> str:
    if pd.isna(value):
        return "Unknown"
    if value == 0:
        return "Free"
    if 0 < value < 5:
        return "Low"
    if 5 <= value < 20:
        return "Medium"
    if value >= 20:
        return "High"
    return "Unknown"


def _review_level(value: float | int | None) -> str:
    if pd.isna(value):
        return "Unknown"
    if value < 100:
        return "Low"
    if value < 1000:
        return "Medium"
    if value < 10000:
        return "High"
    return "Very High"


def add_derived_features(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """生成 total_reviews、positive_rate、release_year 等分析字段。"""
    output = df.copy()
    report = {"generated_fields": [], "warnings": []}

    if "positive_reviews" not in output.columns:
        output["positive_reviews"] = 0
        report["warnings"].append("缺少 positive_reviews，已按 0 处理。")
    if "negative_reviews" not in output.columns:
        output["negative_reviews"] = 0
        report["warnings"].append("缺少 negative_reviews，已按 0 处理。")

    output["positive_reviews"] = to_numeric(output["positive_reviews"], 0)
    output["negative_reviews"] = to_numeric(output["negative_reviews"], 0)

    if "total_reviews" not in output.columns:
        output["total_reviews"] = output["positive_reviews"] + output["negative_reviews"]
        report["generated_fields"].append("total_reviews")
    else:
        output["total_reviews"] = to_numeric(output["total_reviews"], 0)

    if "positive_rate" not in output.columns:
        total = output["total_reviews"].replace(0, np.nan)
        output["positive_rate"] = output["positive_reviews"] / total
        report["generated_fields"].append("positive_rate")
    else:
        output["positive_rate"] = to_numeric(output["positive_rate"])
        output.loc[output["total_reviews"] == 0, "positive_rate"] = np.nan

    if "release_year" not in output.columns:
        output["release_year"] = _extract_release_year(output)
        report["generated_fields"].append("release_year")
    else:
        output["release_year"] = to_numeric(output["release_year"])

    if "price" in output.columns:
        output["price"] = to_numeric(output["price"])
    else:
        output["price"] = np.nan
        report["warnings"].append("缺少 price，价格相关分析将受限。")

    for field in ["genres", "tags"]:
        if field not in output.columns:
            output[field] = "Unknown"
            report["warnings"].append(f"缺少 {field}，已填充 Unknown。")
        output[field] = output[field].fillna("Unknown").replace("", "Unknown")

    output["genre_list"] = output["genres"].map(split_multi_value)
    output["tag_list"] = output["tags"].map(split_multi_value)
    report["generated_fields"].extend(["genre_list", "tag_list"])

    if "is_indie" not in output.columns:
        output["is_indie"] = output.apply(
            lambda row: any(item.lower() == "indie" for item in row["genre_list"] + row["tag_list"]),
            axis=1,
        )
        report["generated_fields"].append("is_indie")
    else:
        output["is_indie"] = output["is_indie"].astype(bool)

    if "price_level" not in output.columns:
        output["price_level"] = output["price"].map(_price_level)
        report["generated_fields"].append("price_level")

    if "review_level" not in output.columns:
        output["review_level"] = output["total_reviews"].map(_review_level)
        report["generated_fields"].append("review_level")

    report["generated_fields"] = sorted(set(report["generated_fields"]))
    return output, report
