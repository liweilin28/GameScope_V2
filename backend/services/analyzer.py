"""
来源：学生 + AI
作用：提供 Steam 市场基础统计分析、分布统计、排行榜和筛选函数。
"""

from __future__ import annotations

from collections import Counter
import math
from typing import Any

import pandas as pd

from backend.services.utils import dataframe_to_records


def _empty_safe(df: pd.DataFrame | None) -> pd.DataFrame:
    return df if df is not None else pd.DataFrame()


def _number_or_none(value) -> float | None:
    return None if pd.isna(value) else float(value)


def get_basic_metrics(df: pd.DataFrame) -> dict[str, Any]:
    """计算市场总览使用的核心指标卡数据。"""
    data = _empty_safe(df)
    if data.empty:
        return {
            "game_count": 0,
            "avg_price": None,
            "median_price": None,
            "avg_positive_rate": None,
            "avg_total_reviews": None,
            "free_game_ratio": None,
            "indie_game_ratio": None,
        }

    return {
        "game_count": int(len(data)),
        "avg_price": _number_or_none(data["price"].mean()) if "price" in data else None,
        "median_price": _number_or_none(data["price"].median()) if "price" in data else None,
        "avg_positive_rate": _number_or_none(data["positive_rate"].mean()) if "positive_rate" in data else None,
        "avg_total_reviews": _number_or_none(data["total_reviews"].mean()) if "total_reviews" in data else None,
        "free_game_ratio": _number_or_none((data["price"] == 0).mean()) if "price" in data else None,
        "indie_game_ratio": _number_or_none(data["is_indie"].mean()) if "is_indie" in data else None,
    }


def analyze_release_trend(df: pd.DataFrame) -> list[dict[str, Any]]:
    """按年份统计游戏发行数量。"""
    data = _empty_safe(df)
    if data.empty or "release_year" not in data:
        return []
    trend = (
        data.dropna(subset=["release_year"])
        .assign(release_year=lambda frame: frame["release_year"].astype(int))
        .groupby("release_year")
        .size()
        .sort_index()
    )
    return [{"year": int(year), "count": int(count)} for year, count in trend.items()]


def _flatten_list_column(df: pd.DataFrame, column: str) -> list[str]:
    values: list[str] = []
    if column not in df:
        return values
    for items in df[column]:
        if isinstance(items, list):
            values.extend([str(item) for item in items if str(item)])
    return values


def analyze_genre_distribution(df: pd.DataFrame, top_n: int = 10) -> list[dict[str, Any]]:
    data = _empty_safe(df)
    counter = Counter(_flatten_list_column(data, "genre_list"))
    return [{"genre": name, "count": int(count)} for name, count in counter.most_common(top_n)]


def analyze_tag_frequency(df: pd.DataFrame, top_n: int = 20) -> list[dict[str, Any]]:
    data = _empty_safe(df)
    counter = Counter(_flatten_list_column(data, "tag_list"))
    return [{"tag": name, "count": int(count)} for name, count in counter.most_common(top_n)]


def analyze_price_distribution(df: pd.DataFrame) -> list[dict[str, Any]]:
    data = _empty_safe(df)
    if data.empty or "price_level" not in data:
        return []
    order = ["Free", "Low", "Medium", "High", "Unknown"]
    counts = data["price_level"].fillna("Unknown").value_counts()
    return [{"price_level": level, "count": int(counts.get(level, 0))} for level in order]


def analyze_reception_distribution(df: pd.DataFrame) -> list[dict[str, Any]]:
    data = _empty_safe(df)
    if data.empty or "positive_rate" not in data:
        return []
    bins = [0, 0.5, 0.7, 0.85, 0.95, 1.0]
    labels = ["0-50%", "50-70%", "70-85%", "85-95%", "95-100%"]
    bucket = pd.cut(data["positive_rate"], bins=bins, labels=labels, include_lowest=True)
    counts = bucket.value_counts().reindex(labels, fill_value=0)
    return [{"range": label, "count": int(counts.get(label, 0))} for label in labels]


def analyze_numeric_histogram(
    df: pd.DataFrame,
    column: str,
    bins: int = 10,
    log_transform: bool = False,
) -> list[dict[str, Any]]:
    """Build histogram bins for numeric fields."""
    data = _empty_safe(df)
    if data.empty or column not in data:
        return []
    values = pd.to_numeric(data[column], errors="coerce").dropna()
    if values.empty:
        return []
    if log_transform:
        values = values.map(lambda value: math.log10(float(value) + 1))
    bucket = pd.cut(values, bins=bins, include_lowest=True)
    counts = bucket.value_counts().sort_index()
    return [
        {
            "bin": f"{interval.left:.2f}-{interval.right:.2f}",
            "bin_start": float(interval.left),
            "bin_end": float(interval.right),
            "count": int(count),
        }
        for interval, count in counts.items()
    ]


def build_market_scatter(df: pd.DataFrame, x_field: str, y_field: str, log_x: bool = False, limit: int = 1000) -> list[dict[str, Any]]:
    """Return scatter points with tooltip fields."""
    data = _empty_safe(df)
    if data.empty or x_field not in data or y_field not in data:
        return []
    rows = []
    for _, row in data.head(limit).iterrows():
        x_value = row.get(x_field)
        y_value = row.get(y_field)
        if pd.isna(x_value) or pd.isna(y_value):
            continue
        x_numeric = float(x_value)
        point = {
            "name": row.get("name", "Unknown"),
            x_field: x_numeric,
            y_field: float(y_value),
            "price": None if pd.isna(row.get("price")) else float(row.get("price")),
            "positive_rate": None if pd.isna(row.get("positive_rate")) else float(row.get("positive_rate")),
            "total_reviews": int(row.get("total_reviews", 0)) if not pd.isna(row.get("total_reviews")) else 0,
            "price_level": row.get("price_level", "Unknown"),
            "review_level": row.get("review_level", "Unknown"),
            "genres": row.get("genres", ""),
            "tags": row.get("tags", ""),
        }
        if log_x:
            point[f"log_{x_field}"] = math.log10(x_numeric + 1)
        rows.append(point)
    return rows


def analyze_genre_price_level_stack(df: pd.DataFrame, top_n: int = 8) -> dict[str, Any]:
    """Count price_level composition for top genres."""
    data = _empty_safe(df)
    if data.empty or "genre_list" not in data or "price_level" not in data:
        return {"categories": [], "series": []}
    top_genres = [item["genre"] for item in analyze_genre_distribution(data, top_n=top_n)]
    levels = ["Free", "Low", "Medium", "High", "Unknown"]
    series = [{"name": level, "data": []} for level in levels]
    for genre in top_genres:
        subset = data[data["genre_list"].map(lambda values: genre in values)]
        counts = subset["price_level"].fillna("Unknown").value_counts()
        for item in series:
            item["data"].append(int(counts.get(item["name"], 0)))
    return {"categories": top_genres, "series": series}


def compare_free_paid_games(df: pd.DataFrame) -> list[dict[str, Any]]:
    data = _empty_safe(df)
    if data.empty or "price" not in data:
        return []
    working = data.copy()
    working["price_type"] = working["price"].fillna(-1).map(lambda value: "Free" if value == 0 else "Paid")
    grouped = working.groupby("price_type").agg(
        game_count=("name", "count"),
        avg_positive_rate=("positive_rate", "mean"),
        avg_total_reviews=("total_reviews", "mean"),
    )
    return [
        {
            "price_type": str(index),
            "game_count": int(row["game_count"]),
            "avg_positive_rate": None if pd.isna(row["avg_positive_rate"]) else float(row["avg_positive_rate"]),
            "avg_total_reviews": None if pd.isna(row["avg_total_reviews"]) else float(row["avg_total_reviews"]),
        }
        for index, row in grouped.iterrows()
    ]


def get_top_games_by_reviews(df: pd.DataFrame, n: int = 10) -> list[dict[str, Any]]:
    data = _empty_safe(df)
    if data.empty or "total_reviews" not in data:
        return []
    columns = [col for col in ["name", "genres", "tags", "price", "positive_rate", "total_reviews", "release_year"] if col in data]
    top = data.sort_values("total_reviews", ascending=False).head(n)
    return dataframe_to_records(top[columns], limit=n)


def get_top_games_by_positive_rate(df: pd.DataFrame, n: int = 10, min_reviews: int = 50) -> list[dict[str, Any]]:
    data = _empty_safe(df)
    if data.empty or "positive_rate" not in data or "total_reviews" not in data:
        return []
    filtered = data[data["total_reviews"] >= min_reviews]
    columns = [col for col in ["name", "genres", "tags", "price", "positive_rate", "total_reviews", "release_year"] if col in data]
    top = filtered.sort_values(["positive_rate", "total_reviews"], ascending=[False, False]).head(n)
    return dataframe_to_records(top[columns], limit=n)


def filter_market(
    df: pd.DataFrame,
    only_indie: bool = True,
    year_range: tuple[int, int] | list[int] | None = None,
    price_range: tuple[float, float] | list[float] | None = None,
    genres: list[str] | None = None,
    tags: list[str] | None = None,
    min_reviews: int = 0,
) -> pd.DataFrame:
    """根据 Indie、年份、价格、类型、标签和最低评论数筛选市场样本。"""
    data = _empty_safe(df).copy()
    if data.empty:
        return data

    if only_indie and "is_indie" in data:
        data = data[data["is_indie"] == True]  # noqa: E712
    if year_range and "release_year" in data:
        data = data[data["release_year"].between(year_range[0], year_range[1], inclusive="both")]
    if price_range and "price" in data:
        data = data[data["price"].between(price_range[0], price_range[1], inclusive="both")]
    if min_reviews and "total_reviews" in data:
        data = data[data["total_reviews"] >= min_reviews]
    if genres and "genre_list" in data:
        wanted = {item.lower() for item in genres}
        genre_match = data["genre_list"].map(lambda items: bool(wanted & {str(item).lower() for item in items}))
        if "tag_list" in data:
            tag_match = data["tag_list"].map(lambda items: bool(wanted & {str(item).lower() for item in items}))
            data = data[genre_match | tag_match]
        else:
            data = data[genre_match]
    if tags and "tag_list" in data:
        wanted = {item.lower() for item in tags}
        data = data[data["tag_list"].map(lambda items: bool(wanted & {str(item).lower() for item in items}))]
    return data.reset_index(drop=True)


def get_missing_value_report(df: pd.DataFrame) -> list[dict[str, Any]]:
    data = _empty_safe(df)
    if data.empty:
        return []
    total = len(data)
    return [
        {
            "field": column,
            "missing_count": int(data[column].isna().sum()),
            "missing_ratio": float(data[column].isna().mean()) if total else 0.0,
        }
        for column in data.columns
    ]


def get_field_compatibility_report(df: pd.DataFrame) -> dict[str, Any]:
    data = _empty_safe(df)
    fields = set(data.columns)
    core = ["name", "price", "genres", "tags", "positive_reviews", "negative_reviews"]
    derived = ["total_reviews", "positive_rate", "release_year", "is_indie", "price_level", "review_level"]
    return {
        "available_fields": sorted(fields),
        "missing_core_fields": [field for field in core if field not in fields],
        "available_derived_fields": [field for field in derived if field in fields],
        "missing_derived_fields": [field for field in derived if field not in fields],
        "can_basic_analyze": "name" in fields,
        "can_review_analyze": {"positive_reviews", "negative_reviews", "total_reviews"}.intersection(fields) != set(),
        "can_price_analyze": "price" in fields,
        "can_genre_analyze": "genre_list" in fields or "genres" in fields,
    }


def generate_dashboard_insights(df: pd.DataFrame) -> list[dict[str, str]]:
    data = _empty_safe(df)
    if data.empty:
        return [{"type": "warning", "text": "当前没有可分析数据，请先加载默认数据或上传 CSV。"}]

    insights: list[dict[str, str]] = []
    insights.append({"type": "metric", "text": f"当前样本共 {len(data)} 行，覆盖 {len(data.columns)} 个字段。"})

    if "release_year" in data.columns:
        release_counts = (
            data.dropna(subset=["release_year"])
            .assign(release_year=lambda frame: frame["release_year"].astype(int))
            .groupby("release_year")
            .size()
            .sort_values(ascending=False)
        )
        if not release_counts.empty:
            peak_year = int(release_counts.index[0])
            peak_count = int(release_counts.iloc[0])
            insights.append({"type": "trend", "text": f"发行高峰年份是 {peak_year} 年，共有 {peak_count} 款样本。"})

    genre_distribution = analyze_genre_distribution(data, top_n=1)
    if genre_distribution:
        top_genre = genre_distribution[0]
        insights.append({"type": "genre", "text": f"最常见类型是 {top_genre['genre']}，出现 {top_genre['count']} 次。"})

    tag_frequency = analyze_tag_frequency(data, top_n=1)
    if tag_frequency:
        top_tag = tag_frequency[0]
        insights.append({"type": "tag", "text": f"最高频标签是 {top_tag['tag']}，出现 {top_tag['count']} 次。"})

    price_distribution = analyze_price_distribution(data)
    if price_distribution:
        top_price = max(price_distribution, key=lambda item: item["count"])
        if top_price["count"] > 0:
            insights.append({"type": "price", "text": f"主要价格区间为 {top_price['price_level']}，共有 {top_price['count']} 款样本。"})

    reception_distribution = analyze_reception_distribution(data)
    if reception_distribution:
        top_reception = max(reception_distribution, key=lambda item: item["count"])
        if top_reception["count"] > 0:
            insights.append({"type": "reception", "text": f"好评率主要集中在 {top_reception['range']}，共有 {top_reception['count']} 款样本。"})

    if len(insights) == 1:
        compatibility = get_field_compatibility_report(data)
        notes = []
        if not compatibility["can_price_analyze"]:
            notes.append("缺少 price，无法展示价格结论")
        if not compatibility["can_genre_analyze"]:
            notes.append("缺少 genres/tags，无法展示类型与标签结论")
        if not compatibility["can_review_analyze"]:
            notes.append("缺少评论字段，无法展示口碑结论")
        message = "；".join(notes) if notes else "当前数据字段较少，Steam 专用分析能力受限。"
        insights.append({"type": "warning", "text": message})

    return insights[:5]
