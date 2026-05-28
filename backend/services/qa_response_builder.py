"""
来源：学生 + AI
作用：把 Q&A 分析结果转换为前端可展示的 summary、指标卡、表格和 ECharts option。
"""

from __future__ import annotations

from typing import Any


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


def _build_support_data(intent: dict[str, Any], analysis: dict[str, Any]) -> dict[str, Any]:
    """Build compact evidence data from backend pandas results only."""
    metrics = analysis.get("metrics", {})
    rows = analysis.get("rows", []) or []
    filters = analysis.get("filters", {}) or {}
    analysis_type = analysis.get("analysis_type", "unknown")
    sample_size = int(analysis.get("segment_count") or metrics.get("game_count") or 0)

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
    }
    tables: list[dict[str, Any]] = []

    if analysis_type == "price_distribution":
        price_rows = [
            {**row, "percentage": _safe_pct(row.get("count"), sample_size)}
            for row in rows
        ]
        tables.append(_support_table("价格区间统计", price_rows, ["price_level", "count", "percentage"]))
    elif analysis_type == "release_trend":
        tables.append(_support_table("每年游戏数量", rows, ["year", "count"], limit=20))
    elif analysis_type in {"genre_distribution", "tag_frequency"}:
        label_key = "genre" if analysis_type == "genre_distribution" else "tag"
        dist_rows = [
            {**row, "percentage": _safe_pct(row.get("count"), sample_size)}
            for row in rows
        ]
        tables.append(_support_table("Top 分布", dist_rows, [label_key, "count", "percentage"], limit=20))
    elif analysis_type in {"ranking", "market_pressure", "segment_analysis"}:
        tables.append(
            _support_table(
                "Top games",
                rows,
                ["name", "positive_rate", "total_reviews", "price", "genres", "tags"],
                limit=10,
            )
        )
    elif analysis_type == "correlation":
        summary["correlation"] = analysis.get("correlation")
        summary["x_field"] = analysis.get("x_key")
        summary["y_field"] = analysis.get("y_key")
        tables.append(_support_table("代表性样本", rows, ["name", "price", "positive_rate", "total_reviews"], limit=10))
    elif rows:
        tables.append(_support_table("结果明细", rows, limit=10))

    return {
        "title": "分析支撑数据",
        "summary": summary,
        "tables": tables,
        "notes": [
            "本区域展示的是后端 pandas 分析函数返回的关键支撑信息，不是原始完整 CSV。",
            "LLM 仅负责将结构化结果组织成自然语言，不直接生成核心统计数值、竞品排序或机会评分。",
            "结论仅作为课程项目中的数据分析参考，不替代真实商业决策。",
        ],
    }


def build_answer(intent: dict[str, Any], analysis: dict[str, Any]) -> dict[str, Any]:
    """构造 final_answer 的 answer 字段。"""
    if analysis.get("empty"):
        return {
            "summary": analysis["message"],
            "key_metrics": [{"label": "筛选后样本数", "value": "0", "description": "当前条件下没有可分析样本"}],
            "chart": None,
            "table": {"columns": [], "rows": []},
            "follow_up_suggestions": ["放宽年份范围", "减少类型或标签限制", "切换到全市场再试一次"],
        }

    metrics = analysis.get("metrics", {})
    rows = analysis.get("rows", [])
    analysis_type = analysis.get("analysis_type")
    chart_type = intent.get("chart_type", "bar")
    x_key = analysis.get("x_key")
    y_key = analysis.get("y_key")

    key_metrics = [
        {"label": "样本数量", "value": _fmt_number(metrics.get("game_count"), 0), "description": "当前筛选条件下的游戏数量"},
        {"label": "平均价格", "value": _fmt_number(metrics.get("avg_price"), 2), "description": "当前样本的平均价格"},
        {"label": "中位数价格", "value": _fmt_number(metrics.get("median_price"), 2), "description": "价格中位数能降低极端值影响"},
        {"label": "平均好评率", "value": _fmt_percent(metrics.get("avg_positive_rate")), "description": "仅基于有评论数据的样本"},
    ]
    if analysis_type == "market_pressure":
        key_metrics.append(
            {
                "label": "头部集中度",
                "value": _fmt_percent(analysis.get("competition_concentration")),
                "description": "Top 5 游戏评论数占当前样本评论总量的比例",
            }
        )

    summary_map = {
        "price_distribution": "以下结论基于当前加载的数据集计算，仅作为数据分析参考。当前样本的价格分布已按价格等级统计，可用于观察免费、低价、中价和高价游戏的集中情况。",
        "release_trend": "以下结论基于当前加载的数据集计算，仅作为数据分析参考。发行趋势按年份聚合，可用于观察该市场近年的供给变化。",
        "genre_distribution": "以下结论基于当前加载的数据集计算，仅作为数据分析参考。类型分布展示当前样本中出现频率最高的游戏类型。",
        "tag_frequency": "以下结论基于当前加载的数据集计算，仅作为数据分析参考。标签频率可用于理解玩家和开发者常用的市场定位关键词。",
        "segment_analysis": "以下结论基于当前加载的数据集计算，仅作为数据分析参考。细分市场结果展示样本规模、基础指标和头部竞品。",
        "market_pressure": f"以下结论基于当前加载的数据集计算，仅作为数据分析参考。当前判断为：{analysis.get('pressure_text', '暂无判断')}。",
        "ranking": "以下结论基于当前加载的数据集计算，仅作为数据分析参考。排行榜仅代表当前数据集中的排序结果。",
        "correlation": "以下结论基于当前加载的数据集计算，仅作为数据分析参考。相关关系图只表示样本观察，不代表因果关系。",
    }
    if analysis_type == "review_comparison":
        metric_name = "评论数" if analysis.get("target_metric") == "total_reviews" else "好评率"
        summary = f"以下结论基于当前加载的数据集计算，仅作为数据分析参考。不同分组的{metric_name}对比可辅助观察当前样本中的差异。"
    else:
        summary = summary_map.get(analysis_type, "以下结论基于当前加载的数据集计算，仅作为数据分析参考。")

    echarts_option = None
    chart_rows = rows
    if analysis_type == "price_distribution" and rows:
        chart_rows = [row for row in rows if row.get("count", 0) > 0]

    if chart_rows and x_key and y_key:
        if chart_type == "line":
            echarts_option = _line_option(analysis.get("chart_title", "分析图表"), chart_rows, x_key, y_key)
        elif chart_type == "scatter":
            echarts_option = _scatter_option(analysis.get("chart_title", "分析图表"), chart_rows, x_key, y_key)
        else:
            echarts_option = _bar_option(analysis.get("chart_title", "分析图表"), chart_rows[:15], x_key, y_key)

    return {
        "summary": summary,
        "key_metrics": key_metrics,
        "chart": {
            "title": analysis.get("chart_title", "分析图表"),
            "type": chart_type if chart_type != "none" else "bar",
            "echarts_option": echarts_option,
        }
        if echarts_option
        else None,
        "table": _table_from_rows(rows, 20),
        "support_data": _build_support_data(intent, analysis),
        "follow_up_suggestions": [
            "为什么会这样？",
            "能不能只看 Indie 游戏？",
            "能不能按年份拆开？",
            "给我列出前 10 个游戏",
        ],
    }
