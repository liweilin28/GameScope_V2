"""
来源：学生 + AI
作用：根据智能问数 intent 调用 pandas 分析函数，产出真实计算结果。
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from backend.services import analyzer
from backend.services.utils import dataframe_to_records


def _apply_filters(df: pd.DataFrame, filters: dict[str, Any]) -> pd.DataFrame:
    market_scope = filters.get("market_scope", "unknown")
    only_indie = market_scope == "indie"
    return analyzer.filter_market(
        df,
        only_indie=only_indie,
        year_range=filters.get("year_range"),
        price_range=filters.get("price_range"),
        genres=filters.get("genres") or None,
        tags=filters.get("tags") or None,
        min_reviews=filters.get("min_reviews") or 0,
    )


def _mean_median_by_group(df: pd.DataFrame, group_column: str, value_column: str) -> list[dict[str, Any]]:
    if df.empty or group_column not in df.columns or value_column not in df.columns:
        return []
    grouped = df.dropna(subset=[value_column]).groupby(group_column).agg(
        sample_count=("name", "count"),
        avg_value=(value_column, "mean"),
        median_value=(value_column, "median"),
    )
    return [
        {
            "group": str(index),
            "sample_count": int(row["sample_count"]),
            "avg_value": None if pd.isna(row["avg_value"]) else float(row["avg_value"]),
            "median_value": None if pd.isna(row["median_value"]) else float(row["median_value"]),
        }
        for index, row in grouped.sort_values("sample_count", ascending=False).head(15).iterrows()
    ]


def _top_rows(df: pd.DataFrame, metric: str, n: int = 10) -> list[dict[str, Any]]:
    if df.empty or metric not in df.columns:
        return []
    columns = [c for c in ["name", "genres", "tags", "price", "positive_rate", "total_reviews", "release_year"] if c in df.columns]
    return dataframe_to_records(df.sort_values(metric, ascending=False)[columns].head(n), limit=n)


def _competition_concentration(df: pd.DataFrame) -> float | None:
    if df.empty or "total_reviews" not in df.columns:
        return None
    total = df["total_reviews"].sum()
    if not total:
        return 0.0
    top_reviews = df.sort_values("total_reviews", ascending=False).head(5)["total_reviews"].sum()
    return float(top_reviews / total)


def run_analysis(df: pd.DataFrame, intent: dict[str, Any]) -> dict[str, Any]:
    """根据 understood_intent 执行真实数据分析。"""
    filters = intent.get("filters", {})
    segment = _apply_filters(df, filters)
    analysis_type = intent.get("analysis_type", "unknown")
    target_metric = intent.get("target_metric", "unknown")
    group_by = intent.get("group_by", "none")

    if segment.empty:
        return {
            "analysis_type": analysis_type,
            "filters": filters,
            "segment_count": 0,
            "empty": True,
            "message": "按当前条件筛选后没有足够数据，请放宽类型、标签、年份或价格条件。",
            "metrics": analyzer.get_basic_metrics(segment),
            "rows": [],
        }

    metrics = analyzer.get_basic_metrics(segment)
    result: dict[str, Any] = {
        "analysis_type": analysis_type,
        "target_metric": target_metric,
        "group_by": group_by,
        "filters": filters,
        "segment_count": int(len(segment)),
        "filtered_preview": dataframe_to_records(
            segment[[c for c in ["name", "genres", "tags", "price", "positive_rate", "total_reviews", "release_year"] if c in segment.columns]].head(10),
            limit=10,
        ),
        "empty": False,
        "metrics": metrics,
        "rows": [],
    }

    if analysis_type == "price_distribution":
        result.update(
            {
                "rows": analyzer.analyze_price_distribution(segment),
                "x_key": "price_level",
                "y_key": "count",
                "chart_title": "价格区间分布",
            }
        )
    elif analysis_type == "release_trend":
        result.update(
            {
                "rows": analyzer.analyze_release_trend(segment),
                "x_key": "year",
                "y_key": "count",
                "chart_title": "发行年份趋势",
            }
        )
    elif analysis_type == "genre_distribution":
        result.update(
            {
                "rows": analyzer.analyze_genre_distribution(segment, top_n=15),
                "x_key": "genre",
                "y_key": "count",
                "chart_title": "类型数量分布",
            }
        )
    elif analysis_type == "tag_frequency":
        result.update(
            {
                "rows": analyzer.analyze_tag_frequency(segment, top_n=20),
                "x_key": "tag",
                "y_key": "count",
                "chart_title": "高频标签分布",
            }
        )
    elif analysis_type == "review_comparison":
        group_column = "price_level" if group_by in {"none", "price_level"} else group_by
        rows = _mean_median_by_group(segment, group_column, "positive_rate")
        result.update({"rows": rows, "x_key": "group", "y_key": "avg_value", "chart_title": "不同分组平均好评率"})
    elif analysis_type == "segment_analysis":
        top = _top_rows(segment, "total_reviews", 10)
        result.update(
            {
                "rows": top,
                "top_competitors": top,
                "price_distribution": analyzer.analyze_price_distribution(segment),
                "tag_frequency": analyzer.analyze_tag_frequency(segment, top_n=10),
                "x_key": "name",
                "y_key": "total_reviews",
                "chart_title": "细分市场头部竞品评论数",
            }
        )
    elif analysis_type == "market_pressure":
        concentration = _competition_concentration(segment)
        pressure_text = "竞争压力较高" if len(segment) >= 1000 or (concentration and concentration > 0.55) else "竞争压力中等或偏低"
        rows = _top_rows(segment, "total_reviews", 10)
        result.update(
            {
                "rows": rows,
                "competition_concentration": concentration,
                "pressure_text": pressure_text,
                "x_key": "name",
                "y_key": "total_reviews",
                "chart_title": "头部竞品评论数集中度",
            }
        )
    elif analysis_type == "ranking":
        metric = "positive_rate" if target_metric == "positive_rate" else "total_reviews"
        rows = _top_rows(segment, metric, 10)
        result.update(
            {
                "rows": rows,
                "x_key": "name",
                "y_key": metric,
                "chart_title": "游戏排行榜",
            }
        )
    elif analysis_type == "correlation":
        columns = [c for c in ["name", "price", "total_reviews", "positive_rate"] if c in segment.columns]
        rows = dataframe_to_records(segment[columns].head(100), limit=100) if columns else []
        result.update({"rows": rows, "x_key": "price", "y_key": "total_reviews", "chart_title": "价格与评论数关系"})
    else:
        result.update({"rows": [metrics], "chart_title": "基础指标概览"})

    return result
