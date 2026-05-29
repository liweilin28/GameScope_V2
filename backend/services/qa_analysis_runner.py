"""
Data Q&A analysis executor.

Rules:
- LLM may help with intent understanding and result narration.
- All numeric results, filtering, ranking, aggregation, and chart data come from Python.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from itertools import combinations
from statistics import median
from typing import Any

import pandas as pd

from backend.services import analyzer
from backend.services.competitor_radar import find_similar_games
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


def _with_price_type(df: pd.DataFrame) -> pd.DataFrame:
    working = df.copy()
    if "price" in working.columns:
        prices = pd.to_numeric(working["price"], errors="coerce")
        working["price_type"] = prices.map(lambda value: "Unknown" if pd.isna(value) else ("Free" if value == 0 else "Paid"))
    return working


def _top_rows(df: pd.DataFrame, metric: str, n: int = 10) -> list[dict[str, Any]]:
    if df.empty or metric not in df.columns:
        return []
    columns = [c for c in ["name", "genres", "tags", "price", "positive_rate", "total_reviews", "release_year"] if c in df.columns]
    return dataframe_to_records(df.sort_values(metric, ascending=False)[columns].head(n), limit=n)


def _sort_rows(df: pd.DataFrame, sort_by: str, ascending: bool, n: int = 10) -> list[dict[str, Any]]:
    if df.empty:
        return []
    candidate = sort_by if sort_by in df.columns else ("total_reviews" if "total_reviews" in df.columns else "name")
    columns = [c for c in ["name", "release_year", "total_reviews", "positive_rate", "price", "genres", "tags"] if c in df.columns]
    working = df.copy()
    if candidate in {"price", "positive_rate", "total_reviews", "release_year"} and candidate in working.columns:
        working[candidate] = pd.to_numeric(working[candidate], errors="coerce")
    sorted_df = working.sort_values(candidate, ascending=ascending, na_position="last")
    rows = dataframe_to_records(sorted_df[columns].head(n), limit=n)
    reason_map = {
        "total_reviews": "按评论数排序",
        "positive_rate": "按好评率排序",
        "price": "按价格排序",
        "release_year": "按发行年份排序",
        "name": "按名称排序",
    }
    for item in rows:
        item["reason"] = reason_map.get(candidate, f"按 {candidate} 排序")
    return rows


def _competition_concentration(df: pd.DataFrame) -> float | None:
    if df.empty or "total_reviews" not in df.columns:
        return None
    total = df["total_reviews"].sum()
    if not total:
        return 0.0
    top_reviews = df.sort_values("total_reviews", ascending=False).head(5)["total_reviews"].sum()
    return float(top_reviews / total)


def _split_phrase_terms(value: str) -> list[str]:
    if not value:
        return []
    parts = re.split(r"[,+/|]+|\s{2,}", value)
    cleaned = []
    for part in parts:
        text = part.strip(" -_")
        if text:
            cleaned.append(text)
    return cleaned


def _extract_keywords(message: str) -> list[str]:
    if not message:
        return []
    phrases = re.findall(r"[A-Za-z][A-Za-z0-9+\- ]{1,40}", message)
    results: list[str] = []
    for phrase in phrases:
        value = phrase.strip()
        if len(value) >= 3:
            results.append(value)
            results.extend(_split_phrase_terms(value))
    unique: list[str] = []
    for item in results:
        if item not in unique:
            unique.append(item)
    return unique[:8]


def _build_profile(plan: dict[str, Any]) -> dict[str, Any]:
    filters = plan.get("filters", {}) or {}
    query_context = plan.get("query_context", {}) or {}
    idea_context = plan.get("idea_context", {}) or {}
    base_profile = {}
    for key in ["target_genres", "target_tags", "price_range", "art_style_keywords", "gameplay_keywords", "narrative_keywords", "target_players", "reference_games", "soft_keywords"]:
        if key in query_context:
            base_profile[key] = query_context.get(key)
    if not base_profile and isinstance(idea_context.get("query_intent"), dict):
        base_profile.update(idea_context.get("query_intent") or {})
    if not base_profile and isinstance(idea_context.get("idea_profile"), dict):
        base_profile.update(idea_context.get("idea_profile") or {})

    target_genres = list(dict.fromkeys((base_profile.get("target_genres") or []) + (filters.get("genres") or [])))
    target_tags = list(dict.fromkeys((base_profile.get("target_tags") or []) + (filters.get("tags") or [])))
    keywords = list(dict.fromkeys((base_profile.get("soft_keywords") or []) + _extract_keywords(plan.get("message", ""))))

    return {
        "target_genres": target_genres,
        "target_tags": target_tags,
        "price_range": base_profile.get("price_range") or filters.get("price_range") or [0, 30],
        "art_style_keywords": base_profile.get("art_style_keywords") or [],
        "gameplay_keywords": base_profile.get("gameplay_keywords") or [],
        "narrative_keywords": base_profile.get("narrative_keywords") or [],
        "target_players": base_profile.get("target_players") or [],
        "reference_games": base_profile.get("reference_games") or [],
        "soft_keywords": keywords,
    }


def _representative_games(segment: pd.DataFrame, n: int = 5) -> list[dict[str, Any]]:
    if segment.empty:
        return []
    columns = [c for c in ["name", "price", "positive_rate", "total_reviews", "genres", "tags", "release_year"] if c in segment.columns]
    sort_col = "total_reviews" if "total_reviews" in segment.columns else "name"
    return dataframe_to_records(segment.sort_values(sort_col, ascending=False)[columns].head(n), limit=n)


def _numeric_price_bins(segment: pd.DataFrame, bins: int = 6) -> list[dict[str, Any]]:
    hist = analyzer.analyze_numeric_histogram(segment, "price", bins=bins)
    return hist


def _recommend_price_range(price_bins: list[dict[str, Any]], segment: pd.DataFrame) -> dict[str, Any]:
    non_free_bins = [row for row in price_bins if (row.get("bin_end") or 0) > 0]
    dominant = max(non_free_bins, key=lambda item: item.get("count", 0), default=None)
    prices = pd.to_numeric(segment.get("price"), errors="coerce").dropna() if "price" in segment.columns else pd.Series(dtype=float)
    paid_prices = prices[prices > 0]
    return {
        "dominant_bin": dominant,
        "median_paid_price": None if paid_prices.empty else float(paid_prices.median()),
        "avg_paid_price": None if paid_prices.empty else float(paid_prices.mean()),
    }


def _tag_combo_rows(segment: pd.DataFrame, top_n: int = 10) -> list[dict[str, Any]]:
    if segment.empty or "tag_list" not in segment.columns:
        return []
    combo_counter: Counter[tuple[str, ...]] = Counter()
    example_games: dict[tuple[str, ...], list[str]] = {}
    for _, row in segment.iterrows():
        raw_tags = [str(item).strip() for item in (row.get("tag_list") or []) if str(item).strip()]
        tags = sorted(dict.fromkeys(raw_tags))[:8]
        for combo in combinations(tags, 2):
            combo_counter[combo] += 1
            example_games.setdefault(combo, [])
            if len(example_games[combo]) < 3:
                example_games[combo].append(str(row.get("name", "Unknown")))
    rows = []
    for combo, count in combo_counter.most_common(top_n):
        rows.append(
            {
                "tag_combo": " + ".join(combo),
                "count": int(count),
                "representative_games": ", ".join(example_games.get(combo, [])[:3]),
            }
        )
    return rows


def _review_summary(segment: pd.DataFrame) -> dict[str, Any]:
    if segment.empty:
        return {}
    reviews = pd.to_numeric(segment.get("total_reviews"), errors="coerce").dropna() if "total_reviews" in segment.columns else pd.Series(dtype=float)
    rates = pd.to_numeric(segment.get("positive_rate"), errors="coerce").dropna() if "positive_rate" in segment.columns else pd.Series(dtype=float)
    return {
        "median_reviews": None if reviews.empty else float(reviews.median()),
        "avg_reviews": None if reviews.empty else float(reviews.mean()),
        "median_positive_rate": None if rates.empty else float(rates.median()),
        "avg_positive_rate": None if rates.empty else float(rates.mean()),
    }


def _opportunity_points(segment: pd.DataFrame, competitors: list[dict[str, Any]], tag_rows: list[dict[str, Any]], price_bins: list[dict[str, Any]]) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    risks: list[dict[str, str]] = []
    opportunities: list[dict[str, str]] = []
    sample_size = int(len(segment))
    review_info = _review_summary(segment)
    concentration = _competition_concentration(segment)

    if sample_size < 15:
        risks.append({"type": "低样本风险", "evidence": f"当前样本量仅 {sample_size}，结论稳定性有限。"})
    else:
        opportunities.append({"type": "样本可用", "evidence": f"当前样本量 {sample_size}，可以做基础赛道判断。"})

    if concentration is not None and concentration > 0.55:
        risks.append({"type": "头部竞争风险", "evidence": f"Top 5 评论量占比约 {concentration:.1%}，头部集中度偏高。"})
    elif concentration is not None:
        opportunities.append({"type": "集中度适中", "evidence": f"Top 5 评论量占比约 {concentration:.1%}，头部垄断不算极端。"})

    if review_info.get("median_positive_rate") is not None and review_info["median_positive_rate"] >= 0.8:
        opportunities.append({"type": "口碑基础较好", "evidence": f"样本好评率中位数约 {review_info['median_positive_rate']:.1%}。"})
    elif review_info.get("median_positive_rate") is not None:
        risks.append({"type": "口碑门槛风险", "evidence": f"样本好评率中位数约 {review_info['median_positive_rate']:.1%}，口碑门槛不低。"})

    dominant_bin = _recommend_price_range(price_bins, segment).get("dominant_bin")
    if dominant_bin:
        opportunities.append({"type": "定价带清晰", "evidence": f"样本主要落在 {dominant_bin['bin']} 美元区间。"})

    if tag_rows:
        opportunities.append({"type": "标签共性明显", "evidence": f"高频标签组合包括 {tag_rows[0]['tag_combo']}。"})

    if competitors:
        risks.append({"type": "相似竞品压力", "evidence": f"已找到 {len(competitors)} 个高相似竞品，需要明确差异化。"})

    return opportunities[:4], risks[:4]


def _risk_rows(segment: pd.DataFrame, competitors: list[dict[str, Any]], price_bins: list[dict[str, Any]], tag_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    sample_size = int(len(segment))
    concentration = _competition_concentration(segment)
    review_info = _review_summary(segment)
    price_stats = _recommend_price_range(price_bins, segment)

    rows.append(
        {
            "risk_type": "低样本风险",
            "level": "高" if sample_size < 15 else ("中" if sample_size < 40 else "低"),
            "evidence": f"样本量 {sample_size}",
            "suggestion": "扩大标签/类型范围交叉验证" if sample_size < 40 else "当前样本量可支撑基础判断",
        }
    )
    rows.append(
        {
            "risk_type": "高竞争风险",
            "level": "高" if (concentration or 0) > 0.55 or len(competitors) >= 10 else ("中" if len(competitors) >= 5 else "低"),
            "evidence": f"Top 5 评论量占比 {((concentration or 0) * 100):.1f}%，相似竞品 {len(competitors)} 个",
            "suggestion": "先验证差异化卖点" if len(competitors) >= 5 else "竞品压力可控，但仍需细分定位",
        }
    )
    rows.append(
        {
            "risk_type": "定价风险",
            "level": "中" if price_stats.get("dominant_bin") else "高",
            "evidence": f"主价格桶 {price_stats['dominant_bin']['bin']}" if price_stats.get("dominant_bin") else "样本中无法形成清晰价格带",
            "suggestion": "围绕主价格带测试愿望单转化" if price_stats.get("dominant_bin") else "先补充更多可比样本",
        }
    )
    rows.append(
        {
            "risk_type": "标签定位风险",
            "level": "中" if tag_rows else "高",
            "evidence": f"Top 标签组合 {tag_rows[0]['tag_combo']}" if tag_rows else "未识别出稳定标签组合",
            "suggestion": "保留高相关标签，删除弱相关标签" if tag_rows else "先明确核心标签与目标玩家",
        }
    )
    rows.append(
        {
            "risk_type": "口碑门槛风险",
            "level": "中" if review_info.get("median_positive_rate") and review_info["median_positive_rate"] >= 0.75 else "高",
            "evidence": f"好评率中位数 {((review_info.get('median_positive_rate') or 0) * 100):.1f}%",
            "suggestion": "把口碑预期当成相关性参考，不要直接推导销量",
        }
    )
    return rows


def _empty_result(analysis_type: str, filters: dict[str, Any], metrics: dict[str, Any], message: str) -> dict[str, Any]:
    return {
        "analysis_type": analysis_type,
        "filters": filters,
        "segment_count": 0,
        "empty": True,
        "message": message,
        "metrics": metrics,
        "rows": [],
        "evidence_payload": {
            "filters": filters,
            "sample_size": 0,
            "representative_games": [],
            "key_statistics": {},
            "limitations": [message],
        },
    }


def run_analysis(df: pd.DataFrame, intent: dict[str, Any]) -> dict[str, Any]:
    filters = intent.get("filters", {}) or {}
    segment = _apply_filters(df, filters)
    analysis_type = intent.get("analysis_type", "unknown")
    target_metric = intent.get("target_metric", "unknown")
    group_by = intent.get("group_by", "none")
    metrics = analyzer.get_basic_metrics(segment)

    if segment.empty and analysis_type not in {"competitor_lookup", "similar_games_analysis"}:
        return _empty_result(
            analysis_type,
            filters,
            metrics,
            "按当前筛选条件没有得到可分析样本，请放宽类型、标签、年份或价格范围。",
        )

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
        value_column = "total_reviews" if target_metric == "total_reviews" else "positive_rate"
        group_column = "price_level" if group_by in {"none", "price_level"} else group_by
        working = _with_price_type(segment) if group_column == "price_type" else segment
        rows = _mean_median_by_group(working, group_column, value_column)
        metric_label = "评论数" if value_column == "total_reviews" else "好评率"
        result.update(
            {
                "rows": rows,
                "x_key": "group",
                "y_key": "avg_value",
                "chart_title": f"不同分组平均{metric_label}",
            }
        )
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
        limit = int(intent.get("limit") or 10)
        rows = _top_rows(segment, metric, limit)
        result.update(
            {
                "rows": rows,
                "x_key": "name",
                "y_key": metric,
                "chart_title": "游戏排行榜",
            }
        )
    elif analysis_type == "representative_games":
        sort_by = intent.get("sort_by") or ("positive_rate" if target_metric == "positive_rate" else "total_reviews")
        sort_order = intent.get("sort_order", "desc")
        limit = int(intent.get("limit") or 10)
        rows = _sort_rows(segment, sort_by, ascending=sort_order == "asc", n=limit)
        result.update(
            {
                "rows": rows,
                "sort_by": sort_by,
                "sort_order": sort_order,
                "limit": limit,
                "x_key": "name",
                "y_key": sort_by if sort_by in {"total_reviews", "positive_rate", "price", "release_year"} else "total_reviews",
                "chart_title": "代表游戏列表",
            }
        )
    elif analysis_type == "correlation":
        columns = [c for c in ["name", "price", "total_reviews", "positive_rate"] if c in segment.columns]
        rows = dataframe_to_records(segment[columns].head(100), limit=100) if columns else []
        if group_by == "reviews_positive":
            x_key = "total_reviews"
            y_key = "positive_rate"
            chart_title = "评论数与好评率关系"
        else:
            x_key = "price"
            y_key = "positive_rate" if target_metric == "positive_rate" else "total_reviews"
            chart_title = "价格与好评率关系" if y_key == "positive_rate" else "价格与评论数关系"
        result.update({"rows": rows, "x_key": x_key, "y_key": y_key, "chart_title": chart_title})
    elif analysis_type in {"competitor_lookup", "similar_games_analysis"}:
        profile = _build_profile(intent)
        competitors = find_similar_games(df, profile, top_n=10, only_indie=filters.get("market_scope") != "all")
        if not competitors:
            return _empty_result(
                analysis_type,
                filters,
                metrics,
                "当前数据中没有找到足够相似的竞品样本，请补充类型、标签或关键词。",
            )
        rows = []
        for item in competitors:
            rows.append(
                {
                    "name": item.get("name"),
                    "price": item.get("price"),
                    "total_reviews": item.get("total_reviews"),
                    "positive_rate": item.get("positive_rate"),
                    "genres": item.get("genres"),
                    "tags": item.get("tags"),
                    "similar_reason": item.get("match_reason"),
                    "similarity_score": item.get("similarity_score"),
                }
            )
        result.update(
            {
                "rows": rows,
                "competitors": competitors,
                "x_key": "name",
                "y_key": "similarity_score",
                "chart_title": "相似竞品排序",
            }
        )
        if segment.empty:
            segment = _apply_filters(df, {**filters, "genres": profile.get("target_genres") or [], "tags": profile.get("target_tags") or []})
            result["segment_count"] = int(len(segment))
            result["metrics"] = analyzer.get_basic_metrics(segment)
    elif analysis_type == "price_band_analysis":
        price_bins = _numeric_price_bins(segment)
        recommendation = _recommend_price_range(price_bins, segment)
        result.update(
            {
                "rows": price_bins,
                "price_level_summary": analyzer.analyze_price_distribution(segment),
                "recommendation": recommendation,
                "x_key": "bin",
                "y_key": "count",
                "chart_title": "价格分布",
            }
        )
    elif analysis_type == "tag_combination_analysis":
        combo_rows = _tag_combo_rows(segment, top_n=10)
        if not combo_rows:
            return _empty_result(
                analysis_type,
                filters,
                metrics,
                "当前样本缺少足够标签组合，无法稳定回答标签组合问题。",
            )
        result.update(
            {
                "rows": combo_rows,
                "x_key": "tag_combo",
                "y_key": "count",
                "chart_title": "高频标签组合",
            }
        )
    elif analysis_type == "opportunity_analysis":
        profile = _build_profile(intent)
        competitors = find_similar_games(df, profile, top_n=10, only_indie=filters.get("market_scope") != "all")
        price_bins = _numeric_price_bins(segment)
        tag_rows = _tag_combo_rows(segment, top_n=8)
        opportunities, risks = _opportunity_points(segment, competitors, tag_rows, price_bins)
        result.update(
            {
                "rows": _representative_games(segment, 10),
                "competitors": competitors,
                "price_bins": price_bins,
                "tag_combinations": tag_rows,
                "opportunities": opportunities,
                "risks": risks,
                "x_key": "bin",
                "y_key": "count",
                "chart_title": "价格分布",
                "extra_charts": [
                    {"title": "价格分布", "type": "bar", "data": price_bins, "x": "bin", "y": "count"},
                    {"title": "标签频次", "type": "bar", "data": analyzer.analyze_tag_frequency(segment, top_n=10), "x": "tag", "y": "count"},
                ],
            }
        )
    elif analysis_type == "idea_risk_analysis":
        profile = _build_profile(intent)
        competitors = find_similar_games(df, profile, top_n=10, only_indie=filters.get("market_scope") != "all")
        price_bins = _numeric_price_bins(segment)
        tag_rows = _tag_combo_rows(segment, top_n=8)
        risk_rows = _risk_rows(segment, competitors, price_bins, tag_rows)
        result.update(
            {
                "rows": risk_rows,
                "competitors": competitors,
                "price_bins": price_bins,
                "tag_combinations": tag_rows,
                "x_key": "risk_type",
                "y_key": "level",
                "chart_title": "创意风险列表",
            }
        )
    else:
        result.update({"rows": [metrics], "chart_title": "基础指标概览"})

    representative_games = _representative_games(segment, 5)
    evidence_payload = {
        "filters": filters,
        "sample_size": int(result.get("segment_count", 0)),
        "representative_games": representative_games,
        "key_statistics": {
            **_review_summary(segment),
            "avg_price": result["metrics"].get("avg_price"),
            "median_price": result["metrics"].get("median_price"),
            "competition_concentration": result.get("competition_concentration"),
        },
        "limitations": [],
    }

    if analysis_type == "price_band_analysis":
        evidence_payload["key_statistics"]["recommended_price_range"] = result.get("recommendation", {}).get("dominant_bin", {}).get("bin")
    if analysis_type == "tag_combination_analysis":
        evidence_payload["key_statistics"]["top_tag_combo"] = result["rows"][0]["tag_combo"] if result["rows"] else None
    if analysis_type == "representative_games":
        evidence_payload["key_statistics"]["sort_by"] = result.get("sort_by")
        evidence_payload["key_statistics"]["sort_order"] = result.get("sort_order")
        evidence_payload["key_statistics"]["result_limit"] = result.get("limit")
    if analysis_type == "opportunity_analysis":
        evidence_payload["key_statistics"]["opportunity_points"] = result.get("opportunities", [])
        evidence_payload["key_statistics"]["risk_points"] = result.get("risks", [])
    if analysis_type == "idea_risk_analysis":
        evidence_payload["key_statistics"]["risk_count"] = len(result["rows"])
    if analysis_type in {"competitor_lookup", "similar_games_analysis"}:
        evidence_payload["key_statistics"]["competitor_count"] = len(result.get("rows", []))

    if evidence_payload["sample_size"] == 0:
        evidence_payload["limitations"].append("当前数据不足以支持该问题。")

    result["evidence_payload"] = evidence_payload
    return result
