"""
来源：学生 + AI
作用：提供市场总览所需的基础统计和图表数据 API。
"""

from fastapi import APIRouter

from backend.models import fail, ok
from backend.services import analyzer
from backend.services.data_loader import ensure_current_data


router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


def _get_df_or_error():
    df, _, report = ensure_current_data()
    if df is None:
        return None, report.get("message", "当前没有可用数据。")
    return df, ""


@router.get("/metrics")
def metrics():
    df, message = _get_df_or_error()
    if df is None:
        return fail(message)
    return ok(analyzer.get_basic_metrics(df), "市场核心指标获取成功。")


@router.get("/release-trend")
def release_trend():
    df, message = _get_df_or_error()
    if df is None:
        return fail(message)
    return ok(analyzer.analyze_release_trend(df), "发行趋势获取成功。")


@router.get("/genre-distribution")
def genre_distribution(top_n: int = 10):
    df, message = _get_df_or_error()
    if df is None:
        return fail(message)
    return ok(analyzer.analyze_genre_distribution(df, top_n=top_n), "类型分布获取成功。")


@router.get("/tag-frequency")
def tag_frequency(top_n: int = 20):
    df, message = _get_df_or_error()
    if df is None:
        return fail(message)
    return ok(analyzer.analyze_tag_frequency(df, top_n=top_n), "标签频率获取成功。")


@router.get("/price-distribution")
def price_distribution():
    df, message = _get_df_or_error()
    if df is None:
        return fail(message)
    return ok(analyzer.analyze_price_distribution(df), "价格分布获取成功。")


@router.get("/reception-distribution")
def reception_distribution():
    df, message = _get_df_or_error()
    if df is None:
        return fail(message)
    return ok(analyzer.analyze_reception_distribution(df), "好评率分布获取成功。")


@router.get("/price-histogram")
def price_histogram():
    df, message = _get_df_or_error()
    if df is None:
        return fail(message)
    return ok(analyzer.analyze_numeric_histogram(df, "price", bins=10), "价格直方图获取成功。")


@router.get("/positive-rate-histogram")
def positive_rate_histogram():
    df, message = _get_df_or_error()
    if df is None:
        return fail(message)
    return ok(analyzer.analyze_numeric_histogram(df, "positive_rate", bins=10), "好评率直方图获取成功。")


@router.get("/review-log-histogram")
def review_log_histogram():
    df, message = _get_df_or_error()
    if df is None:
        return fail(message)
    return ok(
        analyzer.analyze_numeric_histogram(df, "total_reviews", bins=10, log_transform=True),
        "评论数 log 分布获取成功。",
    )


@router.get("/insights")
def dashboard_insights():
    df, message = _get_df_or_error()
    if df is None:
        return fail(message)
    return ok(analyzer.generate_dashboard_insights(df), "数据发现获取成功。")
