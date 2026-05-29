"""
来源：学生 + AI
作用：计算早期游戏立项机会评分，输出五维解释和保守结论。
"""

from __future__ import annotations

import pandas as pd

from backend.services.utils import clamp


OPPORTUNITY_SCORE_FORMULAS = {
    "total": {
        "label": "机会总分",
        "formula": "total_score = (popularity_score + reception_score + trend_score + competition_pressure + differentiation_space) / 5",
        "weight": "五个维度等权，每项 20%。",
    },
    "dimensions": {
        "popularity_score": {
            "label": "热度分",
            "formula": "popularity_score = clamp((segment_avg_reviews / max(full_avg_reviews, 1)) * 55 + 25, 0, 100)",
            "weight": "20%",
        },
        "reception_score": {
            "label": "口碑分",
            "formula": "reception_score = clamp(segment_avg_positive_rate * 100, 0, 100)",
            "weight": "20%",
        },
        "trend_score": {
            "label": "趋势分",
            "formula": "trend_score = clamp(50 + (recent_2_year_avg_count - earlier_year_avg_count) * 8, 0, 100)，缺少年份数据时取 45",
            "weight": "20%",
        },
        "competition_pressure": {
            "label": "竞争压力机会分",
            "formula": "competition_raw = clamp(segment_density * 220 + competitor_count * 3, 0, 100); competition_pressure = 100 - competition_raw",
            "weight": "20%",
        },
        "differentiation_space": {
            "label": "差异化空间分",
            "formula": "differentiation_space = clamp(100 - competitor_count * 6 + (100 - competition_raw) * 0.25, 0, 100)",
            "weight": "20%",
        },
    },
    "fallback": "当细分市场或全市场数据为空时，总分和五个维度均采用保守分 40。",
}


def _score_band(total: float) -> str:
    if total >= 80:
        return "建议重点关注。"
    if total >= 60:
        return "建议进入，但必须差异化。"
    if total >= 40:
        return "谨慎进入，建议先做小体量 Demo 验证。"
    return "不建议作为小团队首选。"


def calculate_opportunity_score(segment_df: pd.DataFrame, full_df: pd.DataFrame, competitors_df) -> dict:
    """计算五维机会评分，并给出非商业承诺式的早期立项建议。"""
    segment = segment_df if segment_df is not None else pd.DataFrame()
    full = full_df if full_df is not None else pd.DataFrame()
    comp_count = len(competitors_df) if competitors_df is not None else 0

    if segment.empty or full.empty:
        conservative = {
            "score": 40,
            "explanation": "数据不足，采用保守评分。",
            "evidence": {"segment_count": int(len(segment)), "full_count": int(len(full))},
        }
        return {
            "total_score": 40,
            "formulas": OPPORTUNITY_SCORE_FORMULAS,
            "dimensions": {
                "popularity_score": conservative,
                "reception_score": conservative,
                "trend_score": conservative,
                "competition_pressure": conservative,
                "differentiation_space": conservative,
            },
            "conclusion": _score_band(40) + " 该结论仅作为早期立项参考，不替代真实商业决策。",
        }

    avg_reviews = segment["total_reviews"].mean() if "total_reviews" in segment else 0
    full_avg_reviews = full["total_reviews"].mean() if "total_reviews" in full else 1
    popularity = clamp((avg_reviews / max(full_avg_reviews, 1)) * 55 + 25, 0, 100)

    avg_rate = segment["positive_rate"].mean() if "positive_rate" in segment else 0.6
    reception = clamp((avg_rate or 0) * 100, 0, 100)

    if "release_year" in segment and segment["release_year"].notna().any():
        yearly = segment.dropna(subset=["release_year"]).groupby("release_year").size().sort_index()
        recent = yearly.tail(2).mean() if len(yearly) else 0
        earlier = yearly.head(max(len(yearly) - 2, 1)).mean() if len(yearly) > 2 else recent
        trend = clamp(50 + (recent - earlier) * 8, 0, 100)
    else:
        trend = 45

    density = len(segment) / max(len(full), 1)
    competition_raw = clamp(density * 220 + comp_count * 3, 0, 100)
    competition_opportunity = 100 - competition_raw
    differentiation = clamp(100 - comp_count * 6 + (100 - competition_raw) * 0.25, 0, 100)

    dimensions = {
        "popularity_score": {
            "score": round(popularity, 1),
            "explanation": "用细分市场平均评论数相对全市场评论数估计热度。",
            "evidence": {"segment_avg_reviews": round(avg_reviews, 2), "full_avg_reviews": round(full_avg_reviews, 2)},
        },
        "reception_score": {
            "score": round(reception, 1),
            "explanation": "用细分市场平均好评率估计玩家接受度。",
            "evidence": {"segment_avg_positive_rate": None if pd.isna(avg_rate) else round(float(avg_rate), 4)},
        },
        "trend_score": {
            "score": round(trend, 1),
            "explanation": "用近两年样本量相对更早年份的变化估计增长趋势。",
            "evidence": {"segment_count": int(len(segment))},
        },
        "competition_pressure": {
            "score": round(competition_opportunity, 1),
            "explanation": "竞争压力越高，该维度机会分越低。",
            "evidence": {"segment_density": round(density, 4), "competitor_count": comp_count},
        },
        "differentiation_space": {
            "score": round(differentiation, 1),
            "explanation": "竞品越少、拥挤度越低，差异化空间越大。",
            "evidence": {"competitor_count": comp_count, "competition_raw": round(competition_raw, 1)},
        },
    }
    total = sum(item["score"] for item in dimensions.values()) / len(dimensions)
    return {
        "total_score": round(total, 1),
        "formulas": OPPORTUNITY_SCORE_FORMULAS,
        "dimensions": dimensions,
        "conclusion": _score_band(total) + " 该结论仅作为早期立项参考，不替代真实商业决策。",
    }
