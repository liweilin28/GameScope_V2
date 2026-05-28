"""
来源：学生 + AI
作用：提供 Visual Explorer 所需的筛选数据和交互式图表数据 API。
"""

from __future__ import annotations

import math

import pandas as pd
from fastapi import APIRouter

from backend.models import ExplorerFilterRequest, fail, ok
from backend.services import analyzer
from backend.services.data_loader import ensure_current_data
from backend.services.utils import dataframe_to_records


router = APIRouter(prefix="/api/explorer", tags=["explorer"])


def _get_df_or_error():
    df, _, report = ensure_current_data()
    if df is None:
        return None, report.get("message", "当前没有可用数据。")
    return df, ""


def _apply_filters(df: pd.DataFrame, filters: ExplorerFilterRequest) -> pd.DataFrame:
    return analyzer.filter_market(
        df,
        only_indie=filters.only_indie,
        year_range=filters.year_range,
        price_range=filters.price_range,
        genres=filters.genres,
        tags=filters.tags,
        min_reviews=filters.min_reviews,
    )


def _filter_options(df: pd.DataFrame) -> dict:
    years = df["release_year"].dropna() if "release_year" in df else pd.Series(dtype=float)
    prices = df["price"].dropna() if "price" in df else pd.Series(dtype=float)
    genres = analyzer.analyze_genre_distribution(df, top_n=40)
    tags = analyzer.analyze_tag_frequency(df, top_n=60)
    return {
        "year_min": int(years.min()) if not years.empty else None,
        "year_max": int(years.max()) if not years.empty else None,
        "price_min": float(prices.min()) if not prices.empty else 0,
        "price_max": float(prices.max()) if not prices.empty else 100,
        "genres": [item["genre"] for item in genres],
        "tags": [item["tag"] for item in tags],
    }


def _scatter_points(df: pd.DataFrame) -> list[dict]:
    if df.empty:
        return []
    points = []
    for _, row in df.iterrows():
        price = row.get("price")
        reviews = row.get("total_reviews")
        if pd.isna(price) or pd.isna(reviews):
            continue
        points.append(
            {
                "name": row.get("name", "Unknown"),
                "price": float(price),
                "total_reviews": int(reviews),
                "log_reviews": round(math.log10(float(reviews) + 1), 4),
                "positive_rate": None if pd.isna(row.get("positive_rate")) else float(row.get("positive_rate")),
            }
        )
    return points[:1000]


def _genre_reception(df: pd.DataFrame, top_n: int = 10) -> list[dict]:
    rows = []
    for item in analyzer.analyze_genre_distribution(df, top_n=top_n):
        genre = item["genre"]
        subset = df[df["genre_list"].map(lambda values: genre in values)] if "genre_list" in df else pd.DataFrame()
        if subset.empty or "positive_rate" not in subset:
            avg_rate = None
        else:
            avg_rate = subset["positive_rate"].mean()
        rows.append(
            {
                "genre": genre,
                "game_count": item["count"],
                "avg_positive_rate": None if pd.isna(avg_rate) else float(avg_rate),
            }
        )
    return rows


def _build_explorer_payload(filtered: pd.DataFrame, full_df: pd.DataFrame, table_limit: int = 50) -> dict:
    top_columns = [
        column
        for column in ["name", "genres", "tags", "price", "positive_rate", "total_reviews", "release_year"]
        if column in filtered.columns
    ]
    table_columns = [
        column
        for column in ["name", "release_year", "price", "genres", "tags", "positive_rate", "total_reviews", "is_indie"]
        if column in filtered.columns
    ]
    return {
        "filtered_count": int(len(filtered)),
        "total_count": int(len(full_df)),
        "filter_options": _filter_options(full_df),
        "scatter": _scatter_points(filtered),
        "price_reviews_scatter": analyzer.build_market_scatter(filtered, "price", "total_reviews"),
        "price_positive_scatter": analyzer.build_market_scatter(filtered, "price", "positive_rate"),
        "reviews_positive_scatter": analyzer.build_market_scatter(
            filtered, "total_reviews", "positive_rate", log_x=True
        ),
        "genre_price_stack": analyzer.analyze_genre_price_level_stack(filtered, top_n=8),
        "genre_reception": _genre_reception(filtered),
        "free_paid": analyzer.compare_free_paid_games(filtered),
        "top_games": analyzer.get_top_games_by_reviews(filtered, n=10),
        "table": dataframe_to_records(filtered[table_columns], limit=table_limit) if table_columns else [],
        "top_positive_rate": analyzer.get_top_games_by_positive_rate(filtered, n=10, min_reviews=50),
        "available_columns": top_columns,
    }


@router.post("/filter")
def filter_data(filters: ExplorerFilterRequest):
    df, message = _get_df_or_error()
    if df is None:
        return fail(message)
    filtered = _apply_filters(df, filters)
    return ok(
        {
            "filtered_count": int(len(filtered)),
            "total_count": int(len(df)),
            "filter_options": _filter_options(df),
            "table": dataframe_to_records(filtered, limit=50),
        },
        "筛选数据获取成功。",
    )


@router.post("/charts")
def charts(filters: ExplorerFilterRequest):
    df, message = _get_df_or_error()
    if df is None:
        return fail(message)
    filtered = _apply_filters(df, filters)
    return ok(_build_explorer_payload(filtered, df), "探索图表数据获取成功。")
