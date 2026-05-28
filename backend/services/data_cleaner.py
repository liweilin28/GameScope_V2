"""
来源：学生 + AI
作用：清洗 Steam CSV 数据，生成清洗报告，并调用特征工程补齐分析字段。
"""

from __future__ import annotations

import pandas as pd

from backend.services.feature_engineering import add_derived_features
from backend.services.utils import standardize_columns, to_numeric


def clean_steam_data(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """清洗 Steam 游戏数据，并返回清洗后的 DataFrame 与可展示报告。"""
    report = {
        "raw_rows": 0,
        "cleaned_rows": 0,
        "raw_columns": [],
        "cleaned_columns": [],
        "renamed_columns": {},
        "dropped_missing_name": 0,
        "dropped_duplicates": 0,
        "filled_fields": [],
        "derived": {},
        "warnings": [],
        "errors": [],
    }

    if df is None:
        report["errors"].append("输入数据为空。")
        return pd.DataFrame(), report

    try:
        output, renamed = standardize_columns(df)
        report["raw_rows"] = int(len(output))
        report["raw_columns"] = list(df.columns)
        report["renamed_columns"] = renamed

        output = output.copy()
        if "name" not in output.columns:
            report["errors"].append("缺少关键字段 name，无法完成清洗。")
            return pd.DataFrame(), report

        before = len(output)
        output = output[output["name"].notna() & (output["name"].astype(str).str.strip() != "")]
        report["dropped_missing_name"] = int(before - len(output))

        if "price" in output.columns:
            output["price"] = to_numeric(output["price"])

        for field in ["positive_reviews", "negative_reviews"]:
            if field not in output.columns:
                output[field] = 0
                report["filled_fields"].append(field)
                report["warnings"].append(f"缺少 {field}，已按 0 处理。")
            output[field] = to_numeric(output[field], 0)

        for field in ["genres", "tags", "developers", "publishers"]:
            if field not in output.columns:
                output[field] = "Unknown"
                report["filled_fields"].append(field)
                report["warnings"].append(f"缺少 {field}，已填充 Unknown。")
            output[field] = output[field].fillna("Unknown").replace("", "Unknown")

        before = len(output)
        if "app_id" in output.columns:
            output = output.drop_duplicates(subset=["app_id"], keep="first")
            report["duplicate_key"] = "app_id"
        else:
            output = output.drop_duplicates(subset=["name"], keep="first")
            report["duplicate_key"] = "name"
        report["dropped_duplicates"] = int(before - len(output))

        output, derived_report = add_derived_features(output)
        report["derived"] = derived_report
        report["warnings"].extend(derived_report.get("warnings", []))
        report["cleaned_rows"] = int(len(output))
        report["cleaned_columns"] = list(output.columns)
        return output.reset_index(drop=True), report
    except Exception as exc:
        report["errors"].append(f"数据清洗失败：{exc}")
        return pd.DataFrame(), report
