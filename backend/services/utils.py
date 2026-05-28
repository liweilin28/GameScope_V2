"""
来源：学生 + AI
作用：提供数据清洗、字段兼容、表格序列化等通用工具函数。
"""

from __future__ import annotations

import ast
import re
from typing import Any

import numpy as np
import pandas as pd


FIELD_ALIASES = {
    "Name": "name",
    "Release date": "release_date",
    "Release Date": "release_date",
    "Price": "price",
    "Genres": "genres",
    "Tags": "tags",
    "Positive": "positive_reviews",
    "Negative": "negative_reviews",
    "Recommendations": "recommendations",
    "Average playtime forever": "average_playtime_forever",
    "Average Playtime Forever": "average_playtime_forever",
    "Peak CCU": "peak_ccu",
    "DLC count": "dlc_count",
    "DLC Count": "dlc_count",
    "Metacritic score": "metacritic_score",
    "Metacritic Score": "metacritic_score",
}


REQUIRED_CORE_FIELDS = ["name"]
RECOMMENDED_FIELDS = [
    "app_id",
    "release_date",
    "release_year",
    "price",
    "genres",
    "tags",
    "positive_reviews",
    "negative_reviews",
    "total_reviews",
    "positive_rate",
    "developers",
    "publishers",
]


def normalize_column_name(column: Any) -> str:
    text = str(column).strip()
    text = FIELD_ALIASES.get(text, text)
    text = text.strip().lower()
    text = re.sub(r"[\s\-]+", "_", text)
    text = re.sub(r"[^a-z0-9_]", "", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text


def standardize_columns(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, str]]:
    renamed = {column: normalize_column_name(column) for column in df.columns}
    output = df.rename(columns=renamed).copy()
    return output, renamed


def to_numeric(series: pd.Series, fill_value: float | None = None) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce")
    if fill_value is not None:
        numeric = numeric.fillna(fill_value)
    return numeric


def split_multi_value(value: Any) -> list[str]:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]

    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "unknown"}:
        return [] if text.lower() != "unknown" else ["Unknown"]

    if text.startswith("[") and text.endswith("]"):
        try:
            parsed = ast.literal_eval(text)
            if isinstance(parsed, list):
                return [str(item).strip().strip("'\"") for item in parsed if str(item).strip()]
        except (SyntaxError, ValueError):
            pass

    cleaned = text.strip("[]")
    parts = re.split(r"[,;|/]+", cleaned)
    return [part.strip().strip("'\"") for part in parts if part.strip().strip("'\"")]


def dataframe_to_records(df: pd.DataFrame, limit: int = 20) -> list[dict[str, Any]]:
    if df is None or df.empty:
        return []
    preview = df.head(limit).copy()

    def clean_value(value: Any) -> Any:
        if isinstance(value, (list, tuple, set)):
            return list(value)
        if pd.isna(value):
            return None
        return value

    for column in preview.columns:
        preview[column] = preview[column].map(clean_value)
    return preview.to_dict(orient="records")


def series_count_to_records(series: pd.Series, key_name: str, value_name: str) -> list[dict[str, Any]]:
    if series is None or series.empty:
        return []
    return [
        {key_name: str(index), value_name: int(value) if pd.notna(value) else 0}
        for index, value in series.items()
    ]


def safe_float(value: Any) -> float | None:
    if pd.isna(value):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(value, upper))
