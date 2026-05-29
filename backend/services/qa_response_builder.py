"""
Build frontend-ready answer payloads from backend analysis results.
"""

from __future__ import annotations

import json
from typing import Any

from backend.services.llm_client import safe_call_llm


def _fmt_number(value: Any, digits: int = 2) -> str:
    if value is None:
        return "暂无"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    if number.is_integer():
        return f"{int(number):,}"
    return f"{number:,.{digits}f}"


def _fmt_percent(value: Any) -> str:
    if value is None:
        return "暂无"
    try:
        return f"{float(value) * 100:.1f}%"
    except (TypeError, ValueError):
        return str(value)


def _bar_option(title: str, rows: list[dict[str, Any]], x_key: str, y_key: str) -> dict[str, Any]:
    return {
        "title": {"text": title, "left": 12, "top": 8, "textStyle": {"fontSize": 14}},
        "tooltip": {"trigger": "axis"},
        "grid": {"left": 52, "right": 24, "top": 58, "bottom": 70},
        "xAxis": {"type": "category", "data": [row.get(x_key) for row in rows], "axisLabel": {"rotate": 25}},
        "yAxis": {"type": "value"},
        "series": [{"type": "bar", "data": [row.get(y_key) for row in rows], "barMaxWidth": 34, "color": "#2563eb"}],
    }


def _line_option(title: str, rows: list[dict[str, Any]], x_key: str, y_key: str) -> dict[str, Any]:
    return {
        "title": {"text": title, "left": 12, "top": 8, "textStyle": {"fontSize": 14}},
        "tooltip": {"trigger": "axis"},
        "grid": {"left": 52, "right": 24, "top": 58, "bottom": 42},
        "xAxis": {"type": "category", "data": [row.get(x_key) for row in rows]},
        "yAxis": {"type": "value"},
        "series": [{"type": "line", "smooth": True, "data": [row.get(y_key) for row in rows], "color": "#2563eb"}],
    }


def _scatter_option(title: str, rows: list[dict[str, Any]], x_key: str, y_key: str) -> dict[str, Any]:
    return {
        "title": {"text": title, "left": 12, "top": 8, "textStyle": {"fontSize": 14}},
        "tooltip": {"trigger": "item"},
        "grid": {"left": 58, "right": 24, "top": 58, "bottom": 48},
        "xAxis": {"type": "value", "name": x_key},
        "yAxis": {"type": "value", "name": y_key},
        "series": [{"type": "scatter", "data": [[row.get(x_key), row.get(y_key)] for row in rows], "color": "#2563eb"}],
    }


def _table_from_rows(rows: list[dict[str, Any]], limit: int = 20) -> dict[str, Any]:
    visible = rows[:limit] if rows else []
    columns = list(visible[0].keys()) if visible else []
    return {"columns": columns, "rows": visible}


def _safe_pct(count: Any, total: int) -> str:
    try:
        if not total:
            return "0%"
        return f"{float(count) / total * 100:.1f}%"
    except (TypeError, ValueError):
        return "0%"


def _support_table(title: str, rows: list[dict[str, Any]], columns: list[str] | None = None, limit: int = 10) -> dict[str, Any]:
    visible = rows[:limit] if rows else []
    return {
        "title": title,
        "columns": columns or (list(visible[0].keys()) if visible else []),
        "rows": visible,
    }


def _filters_text(filters: dict[str, Any]) -> str:
    parts: list[str] = []
    if filters.get("genres"):
        parts.append("类型=" + "/".join(filters["genres"]))
    if filters.get("tags"):
        parts.append("标签=" + "/".join(filters["tags"]))
    if filters.get("price_range"):
        parts.append(f"价格={filters['price_range'][0]}-{filters['price_range'][1]}")
    if filters.get("year_range"):
        parts.append(f"年份={filters['year_range'][0]}-{filters['year_range'][1]}")
    if filters.get("market_scope") and filters.get("market_scope") != "unknown":
        parts.append("范围=" + ("仅 Indie" if filters["market_scope"] == "indie" else "全量样本"))
    return "，".join(parts) if parts else "未额外筛选"


def _representative_names(evidence_payload: dict[str, Any]) -> str:
    games = evidence_payload.get("representative_games") or []
    names = [str(item.get("name")) for item in games if item.get("name")]
    return "、".join(names[:5]) if names else "暂无代表性游戏"


def _template_summary(analysis: dict[str, Any], evidence_payload: dict[str, Any], ambiguity_notice: str | None = None) -> str:
    filters_text = _filters_text(evidence_payload.get("filters", {}))
    sample_size = int(evidence_payload.get("sample_size") or 0)
    stats = evidence_payload.get("key_statistics") or {}
    names = _representative_names(evidence_payload)
    limitations = evidence_payload.get("limitations") or []
    limitation_text = "；".join(limitations) if limitations else "结论仅基于当前数据集和当前筛选条件，不代表真实收入、未来趋势或因果关系。"

    lines: list[str] = []
    if ambiguity_notice:
        lines.append(ambiguity_notice)
    lines.append(f"本次分析使用的筛选条件：{filters_text}。")
    lines.append(f"样本量：{sample_size}。")

    analysis_type = analysis.get("analysis_type")
    if analysis_type in {"competitor_lookup", "similar_games_analysis"}:
        lines.append(
            f"共找到 {len(analysis.get('rows', []))} 个相似竞品，代表性游戏包括 {names}。"
        )
    elif analysis_type == "price_band_analysis":
        lines.append(
            f"价格中位数约 {_fmt_number(stats.get('median_price'))} 美元，推荐观察区间 {stats.get('recommended_price_range') or '暂无'}。"
        )
        lines.append(f"代表性游戏包括 {names}。")
    elif analysis_type == "tag_combination_analysis":
        lines.append(f"高频标签组合为 {stats.get('top_tag_combo') or '暂无'}，代表性游戏包括 {names}。")
    elif analysis_type == "representative_games":
        sort_by = stats.get("sort_by") or "total_reviews"
        sort_order = "升序" if stats.get("sort_order") == "asc" else "降序"
        result_limit = stats.get("result_limit") or len(analysis.get("rows", []))
        lines.append(f"本轮追问沿用上一轮筛选结果，按 {sort_by} {sort_order} 排序，返回前 {result_limit} 个代表游戏。")
        lines.append(f"代表性游戏包括 {names}。")
    elif analysis_type == "opportunity_analysis":
        opportunity_points = stats.get("opportunity_points") or []
        risk_points = stats.get("risk_points") or []
        if stats.get("median_reviews") is not None:
            lines.append(f"评论数中位数约 {_fmt_number(stats.get('median_reviews'))}，好评率中位数约 {_fmt_percent(stats.get('median_positive_rate'))}。")
        lines.append(f"代表性游戏包括 {names}。")
        if opportunity_points:
            lines.append("机会点：" + "；".join(item.get("evidence", "") for item in opportunity_points[:3] if item.get("evidence")))
        if risk_points:
            lines.append("风险点：" + "；".join(item.get("evidence", "") for item in risk_points[:3] if item.get("evidence")))
    elif analysis_type == "idea_risk_analysis":
        lines.append(f"已识别 {len(analysis.get('rows', []))} 类主要风险，代表性游戏包括 {names}。")
    else:
        lines.append(
            f"关键统计：平均价格 {_fmt_number(stats.get('avg_price'))}，价格中位数 {_fmt_number(stats.get('median_price'))}，评论数中位数 {_fmt_number(stats.get('median_reviews'))}。"
        )
        lines.append(f"代表性游戏包括 {names}。")

    lines.append("结论与建议：请优先结合结构化结果判断，不要把相关性当成因果。")
    lines.append("数据限制或置信度说明：" + limitation_text)
    return "\n".join(lines)


def _llm_summary(analysis: dict[str, Any], evidence_payload: dict[str, Any], ambiguity_notice: str | None = None) -> str | None:
    if not evidence_payload or not evidence_payload.get("sample_size"):
        return None
    system_prompt = (
        "你是 GameScope 的数据分析解释器。"
        "你只能基于给定的 evidence_payload 和 analysis_result 生成中文解释。"
        "禁止编造不存在的字段、真实收入、销量、平台外数据、未来确定性趋势。"
        "禁止把相关性说成因果。"
        "回答必须明确包含：筛选条件、样本量、关键统计、代表性游戏、结论与建议、数据限制。"
        "如果 evidence 不足，请直接说明当前数据不足以回答。"
    )
    prompt = {
        "analysis_result": {
            "analysis_type": analysis.get("analysis_type"),
            "chart_title": analysis.get("chart_title"),
            "rows_preview": (analysis.get("rows") or [])[:8],
        },
        "evidence_payload": evidence_payload,
        "ambiguity_notice": ambiguity_notice or "",
    }
    result = safe_call_llm(json.dumps(prompt, ensure_ascii=False), system_prompt)
    if result.get("success") and result.get("content"):
        return str(result["content"]).strip()
    return None


def _build_support_data(intent: dict[str, Any], analysis: dict[str, Any]) -> dict[str, Any]:
    metrics = analysis.get("metrics", {})
    rows = analysis.get("rows", []) or []
    filters = analysis.get("filters", {}) or {}
    analysis_type = analysis.get("analysis_type", "unknown")
    evidence_payload = analysis.get("evidence_payload") or {}
    sample_size = int(analysis.get("segment_count") or metrics.get("game_count") or evidence_payload.get("sample_size") or 0)

    summary = {
        "sample_size": sample_size,
        "analysis_type": analysis_type,
        "target_metric": analysis.get("target_metric") or intent.get("target_metric", "unknown"),
        "filters": filters,
        "metrics": {
            "avg_price": metrics.get("avg_price"),
            "median_price": metrics.get("median_price"),
            "avg_positive_rate": metrics.get("avg_positive_rate"),
            "avg_total_reviews": metrics.get("avg_total_reviews"),
        },
        "evidence_payload": evidence_payload,
    }
    tables: list[dict[str, Any]] = []

    if analysis_type == "price_distribution":
        price_rows = [{**row, "percentage": _safe_pct(row.get("count"), sample_size)} for row in rows]
        tables.append(_support_table("价格区间统计", price_rows, ["price_level", "count", "percentage"]))
    elif analysis_type == "price_band_analysis":
        tables.append(_support_table("价格分桶统计", rows, ["bin", "count", "bin_start", "bin_end"], limit=12))
        if analysis.get("price_level_summary"):
            tables.append(_support_table("价格等级统计", analysis["price_level_summary"], ["price_level", "count"], limit=10))
    elif analysis_type in {"genre_distribution", "tag_frequency"}:
        label_key = "genre" if analysis_type == "genre_distribution" else "tag"
        dist_rows = [{**row, "percentage": _safe_pct(row.get("count"), sample_size)} for row in rows]
        tables.append(_support_table("Top 分布", dist_rows, [label_key, "count", "percentage"], limit=20))
    elif analysis_type == "tag_combination_analysis":
        tables.append(_support_table("标签组合", rows, ["tag_combo", "count", "representative_games"], limit=10))
    elif analysis_type in {"ranking", "market_pressure", "segment_analysis", "competitor_lookup", "similar_games_analysis", "opportunity_analysis", "representative_games"}:
        tables.append(
            _support_table(
                "代表游戏",
                rows,
                list(rows[0].keys()) if rows else [],
                limit=10,
            )
        )
    elif analysis_type == "idea_risk_analysis":
        tables.append(_support_table("风险明细", rows, ["risk_type", "level", "evidence", "suggestion"], limit=10))
    elif analysis_type == "correlation":
        summary["x_field"] = analysis.get("x_key")
        summary["y_field"] = analysis.get("y_key")
        tables.append(_support_table("代表性样本", rows, ["name", "price", "positive_rate", "total_reviews"], limit=10))
    elif rows:
        tables.append(_support_table("结果明细", rows, limit=10))

    if analysis.get("competitors"):
        competitor_rows = []
        for item in analysis["competitors"][:10]:
            competitor_rows.append(
                {
                    "name": item.get("name"),
                    "similarity_score": item.get("similarity_score"),
                    "price": item.get("price"),
                    "positive_rate": item.get("positive_rate"),
                    "total_reviews": item.get("total_reviews"),
                    "match_reason": item.get("match_reason"),
                }
            )
        tables.append(_support_table("相似竞品证据", competitor_rows, limit=10))

    return {
        "title": "分析支撑数据",
        "summary": summary,
        "tables": tables,
        "notes": [
            "所有结论都来自后端 pandas 计算结果或立项实验室当前解析结果，LLM 只负责解释。",
            "当前数据不能回答真实收入、平台外数据、未来爆款预测等问题。",
            "相关性结果不代表因果关系。",
        ],
    }


def _build_chart_object(chart_type: str, title: str, rows: list[dict[str, Any]], x_key: str | None, y_key: str | None) -> dict[str, Any] | None:
    if not rows or not x_key or not y_key:
        return None
    if chart_type == "line":
        option = _line_option(title, rows, x_key, y_key)
    elif chart_type == "scatter":
        option = _scatter_option(title, rows, x_key, y_key)
    else:
        option = _bar_option(title, rows[:15], x_key, y_key)
    return {
        "title": title,
        "type": chart_type if chart_type != "none" else "bar",
        "echarts_option": option,
    }


def build_answer(intent: dict[str, Any], analysis: dict[str, Any]) -> dict[str, Any]:
    if analysis.get("empty"):
        evidence_payload = analysis.get("evidence_payload") or {}
        summary = _template_summary(analysis, evidence_payload, intent.get("ambiguity_notice"))
        return {
            "summary": summary,
            "key_metrics": [{"label": "筛选后样本量", "value": "0", "description": "当前条件下没有可分析样本"}],
            "chart": None,
            "charts": [],
            "table": {"columns": [], "rows": []},
            "evidence_payload": evidence_payload,
            "evidence_brief": {
                "filters_text": _filters_text(evidence_payload.get("filters", {})),
                "sample_size": 0,
                "representative_games": [],
                "limitations": evidence_payload.get("limitations") or ["当前数据不足以回答。"],
            },
            "follow_up_suggestions": ["放宽年份范围", "减少类型或标签限制", "补充更明确的类型、标签或关键词"],
        }

    metrics = analysis.get("metrics", {})
    rows = analysis.get("rows", [])
    analysis_type = analysis.get("analysis_type")
    chart_type = intent.get("chart_type", "bar")
    x_key = analysis.get("x_key")
    y_key = analysis.get("y_key")
    evidence_payload = analysis.get("evidence_payload") or {}
    ambiguity_notice = intent.get("ambiguity_notice")

    if analysis_type == "representative_games" or intent.get("is_follow_up"):
        summary = _template_summary(analysis, evidence_payload, ambiguity_notice)
    else:
        summary = _llm_summary(analysis, evidence_payload, ambiguity_notice) or _template_summary(analysis, evidence_payload, ambiguity_notice)

    key_metrics = [
        {"label": "样本量", "value": _fmt_number(metrics.get("game_count"), 0), "description": "当前筛选条件下的游戏数量"},
        {"label": "平均价格", "value": _fmt_number(metrics.get("avg_price"), 2), "description": "当前样本的平均价格"},
        {"label": "价格中位数", "value": _fmt_number(metrics.get("median_price"), 2), "description": "用于减少极端值影响"},
        {"label": "平均好评率", "value": _fmt_percent(metrics.get("avg_positive_rate")), "description": "仅基于有评论样本"},
    ]
    if analysis_type in {"competitor_lookup", "similar_games_analysis"}:
        key_metrics.append({"label": "相似竞品数", "value": str(len(rows)), "description": "当前返回的高相似样本"})
    if analysis_type == "price_band_analysis":
        key_metrics.append(
            {
                "label": "推荐价格带",
                "value": str((analysis.get("recommendation") or {}).get("dominant_bin", {}).get("bin") or "暂无"),
                "description": "按当前样本分布提取的主价格带",
            }
        )
    if analysis_type == "market_pressure":
        key_metrics.append(
            {
                "label": "头部集中度",
                "value": _fmt_percent(analysis.get("competition_concentration")),
                "description": "Top 5 游戏评论量占当前样本评论总量的比例",
            }
        )
    if analysis_type == "representative_games":
        key_metrics.append(
            {
                "label": "排序依据",
                "value": str((analysis.get("sort_by") or evidence_payload.get("key_statistics", {}).get("sort_by") or "total_reviews")),
                "description": "当前追问沿用上一轮筛选结果后的排序字段",
            }
        )

    main_chart = _build_chart_object(chart_type, analysis.get("chart_title", "分析图表"), rows, x_key, y_key)
    extra_charts = []
    for chart in analysis.get("extra_charts") or []:
        extra_charts.append(
            _build_chart_object(chart.get("type", "bar"), chart.get("title", "分析图表"), chart.get("data") or [], chart.get("x"), chart.get("y"))
        )
    extra_charts = [chart for chart in extra_charts if chart]

    representative_games = evidence_payload.get("representative_games") or []
    return {
        "summary": summary,
        "key_metrics": key_metrics,
        "chart": main_chart,
        "charts": ([main_chart] if main_chart else []) + extra_charts,
        "table": _table_from_rows(rows, 20),
        "support_data": _build_support_data(intent, analysis),
        "evidence_payload": evidence_payload,
        "evidence_brief": {
            "filters_text": _filters_text(evidence_payload.get("filters", {})),
            "sample_size": int(evidence_payload.get("sample_size") or 0),
            "representative_games": representative_games,
            "limitations": evidence_payload.get("limitations") or [],
        },
        "follow_up_suggestions": [
            "按年份拆开看",
            "只看 Indie 样本",
            "列出前 10 个代表游戏",
            "换一个标签组合再分析",
        ],
    }
