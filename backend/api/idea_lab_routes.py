"""
来源：学生 + AI
作用：提供 Idea Lab 创意解析、市场扫描和项目报告 API。
"""

from __future__ import annotations

import math

import pandas as pd
from fastapi import APIRouter

from backend.models import IdeaAnalyzeRequest, IdeaParseRequest, IdeaReportRequest, fail, ok
from backend.services import analyzer
from backend.services.competitor_radar import find_similar_games
from backend.services.data_loader import ensure_current_data
from backend.services.idea_parser import normalize_idea_profile, parse_idea
from backend.services.opportunity_score import calculate_opportunity_score
from backend.services.report_generator import generate_differentiation_cards, generate_project_brief


router = APIRouter(prefix="/api/idea", tags=["idea-lab"])


def _segment_for_profile(df: pd.DataFrame, profile: dict, only_indie: bool) -> pd.DataFrame:
    return analyzer.filter_market(
        df,
        only_indie=only_indie,
        price_range=profile.get("price_range"),
        genres=profile.get("target_genres"),
        tags=profile.get("target_tags"),
        min_reviews=0,
    )


def _charts(segment: pd.DataFrame, competitors: list[dict]) -> dict:
    competitor_df = pd.DataFrame(competitors)
    competitor_position = []
    if not competitor_df.empty:
        for item in competitors:
            reviews = item.get("total_reviews") or 0
            try:
                review_value = float(reviews)
            except (TypeError, ValueError):
                review_value = 0
            competitor_position.append(
                {
                    "name": item.get("name", "Unknown"),
                    "price": item.get("price"),
                    "positive_rate": item.get("positive_rate"),
                    "total_reviews": reviews,
                    "log_reviews": round(math.log10(review_value + 1), 4),
                    "genres": item.get("genres", ""),
                    "tags": item.get("tags", ""),
                    "similarity_score": item.get("similarity_score", 0),
                }
            )
    return {
        "price_distribution": analyzer.analyze_price_distribution(segment),
        "competitor_price_histogram": analyzer.analyze_numeric_histogram(competitor_df, "price", bins=8)
        if not competitor_df.empty
        else [],
        "competitor_reception_histogram": analyzer.analyze_numeric_histogram(
            competitor_df, "positive_rate", bins=8
        )
        if not competitor_df.empty
        else [],
        "competitor_position": competitor_position,
        "genre_distribution": analyzer.analyze_genre_distribution(segment, top_n=10),
        "competitor_scores": [
            {"name": item.get("name"), "similarity_score": item.get("similarity_score", 0)}
            for item in competitors
        ],
    }


def _split_terms(value) -> set[str]:
    if value is None:
        return set()
    if isinstance(value, list):
        raw = value
    else:
        raw = str(value).replace("|", ",").replace(";", ",").split(",")
    return {str(item).strip() for item in raw if str(item).strip()}


def _idea_support_data(
    profile: dict,
    segment: pd.DataFrame,
    competitors: list[dict],
    score: dict,
    cards: list[dict],
    charts: dict,
    only_indie: bool,
    top_n: int,
) -> dict:
    target_genres = _split_terms(profile.get("target_genres"))
    target_tags = _split_terms(profile.get("target_tags"))
    competitor_rows = []
    tag_counts: dict[str, int] = {}
    for item in competitors[:10]:
        genres = _split_terms(item.get("genres"))
        tags = _split_terms(item.get("tags"))
        for tag in tags:
            tag_counts[tag] = tag_counts.get(tag, 0) + 1
        competitor_rows.append(
            {
                "name": item.get("name"),
                "similarity_score": item.get("similarity_score"),
                "matched_genres": ", ".join(sorted(target_genres & genres)),
                "matched_tags": ", ".join(sorted(target_tags & tags)),
                "price": item.get("price"),
                "positive_rate": item.get("positive_rate"),
                "total_reviews": item.get("total_reviews"),
                "match_reason": item.get("match_reason"),
            }
        )

    dimensions = score.get("dimensions", {}) if isinstance(score, dict) else {}
    score_breakdown = [
        {
            "dimension": name,
            "score": item.get("score"),
            "basis": item.get("explanation"),
            "evidence": item.get("evidence"),
        }
        for name, item in dimensions.items()
    ]
    idea_keywords = []
    for key in ["art_style_keywords", "gameplay_keywords", "narrative_keywords", "target_players"]:
        idea_keywords.extend(profile.get(key) or [])
    top_tags = sorted(tag_counts.items(), key=lambda pair: pair[1], reverse=True)[:10]
    overlap = sorted(target_tags & {tag for tag, _ in top_tags})
    difference = sorted(set(map(str, idea_keywords)) - {tag for tag, _ in top_tags})

    return {
        "competitor_evidence": {
            "title": "竞品雷达支撑数据",
            "summary": {
                "candidate_pool_size": int(len(segment)),
                "top_n": top_n,
                "indie_only": bool(only_indie),
                "target_genres": list(target_genres),
                "target_tags": list(target_tags),
                "price_range": profile.get("price_range"),
            },
            "tables": [
                {
                    "title": "Top competitors",
                    "columns": [
                        "name",
                        "similarity_score",
                        "matched_genres",
                        "matched_tags",
                        "price",
                        "positive_rate",
                        "total_reviews",
                        "match_reason",
                    ],
                    "rows": competitor_rows,
                }
            ],
        },
        "score_evidence": {
            "title": "机会评分支撑数据",
            "summary": {
                "final_score": score.get("total_score"),
                "sample_size": int(len(segment)),
                "competitor_count": len(competitors),
            },
            "score_breakdown": score_breakdown,
        },
        "differentiation_evidence": {
            "title": "差异化建议依据",
            "summary": {
                "competitor_top_tags": [{"tag": tag, "count": count} for tag, count in top_tags],
                "idea_keywords": idea_keywords,
                "overlap_with_competitors": overlap,
                "different_keywords": difference,
                "card_count": len(cards),
            },
            "tables": [
                {
                    "title": "竞品高频标签",
                    "columns": ["tag", "count"],
                    "rows": [{"tag": tag, "count": count} for tag, count in top_tags],
                }
            ],
        },
        "brief_evidence": {
            "title": "Project Brief 报告依据",
            "summary": {
                "used_sources": [
                    "idea_profile",
                    "competitors",
                    "opportunity_score",
                    "differentiation_cards",
                    "charts",
                ],
                "competitor_count": len(competitors),
                "final_score": score.get("total_score"),
                "chart_keys": list(charts.keys()),
                "llm_role": "LLM 只负责语言组织，不作为数据来源。",
            },
            "tables": [
                {
                    "title": "竞品摘要",
                    "columns": ["name", "similarity_score", "price", "positive_rate", "total_reviews"],
                    "rows": [
                        {
                            "name": item.get("name"),
                            "similarity_score": item.get("similarity_score"),
                            "price": item.get("price"),
                            "positive_rate": item.get("positive_rate"),
                            "total_reviews": item.get("total_reviews"),
                        }
                        for item in competitors[:10]
                    ],
                }
            ],
        },
    }


@router.post("/parse")
def parse(request: IdeaParseRequest):
    profile = parse_idea(request.idea_text, prefer_llm=True)
    return ok(profile, "创意解析完成。")


@router.post("/analyze")
def analyze(request: IdeaAnalyzeRequest):
    df, _, report = ensure_current_data()
    if df is None:
        return fail(report.get("message", "当前没有可用数据，请先上传 CSV。"))

    profile = normalize_idea_profile(request.idea_profile) if request.idea_profile else parse_idea(request.idea_text, prefer_llm=True)
    top_n = max(1, min(request.top_n, 30))
    competitors = find_similar_games(df, profile, top_n=top_n, only_indie=request.only_indie)
    segment = _segment_for_profile(df, profile, request.only_indie)
    score = calculate_opportunity_score(segment, df, competitors)
    cards = generate_differentiation_cards(profile, competitors, score)
    charts = _charts(segment, competitors)
    analysis_result = {
        "idea_profile": profile,
        "opportunity_score": score,
        "competitors": competitors,
        "differentiation_cards": cards,
        "charts": charts,
        "support_data": _idea_support_data(profile, segment, competitors, score, cards, charts, request.only_indie, top_n),
        "candidate_pool_size": int(len(segment)),
        "returned_competitor_count": len(competitors),
        "llm_used": bool(profile.get("llm_used", False)),
    }
    brief, brief_llm_used = generate_project_brief(analysis_result, use_llm=True)
    analysis_result["brief"] = brief
    analysis_result["llm_used"] = analysis_result["llm_used"] or brief_llm_used
    return ok(analysis_result, "Idea Lab 市场扫描完成。")


@router.post("/report")
def report(request: IdeaReportRequest):
    brief, llm_used = generate_project_brief(request.analysis_result, use_llm=True)
    return ok({"brief": brief, "llm_used": llm_used}, "Project Brief 生成完成。")
