"""
Data Q&A agent orchestration.
"""

from __future__ import annotations

import re
from copy import deepcopy
from typing import Any

import pandas as pd

from backend.services.data_loader import get_current_raw_data
from backend.services.qa_analysis_runner import run_analysis
from backend.services.qa_conversation import (
    DEFAULT_INTENT,
    add_message,
    get_last_analysis,
    get_or_create_conversation,
    merge_intent,
    normalize_filters,
    update_context,
    update_last_analysis,
)
from backend.services.qa_intent_parser import parse_intent
from backend.services.qa_response_builder import build_answer


AMBIGUOUS_NOTICE = "你的问题比较模糊，我先将“机会”暂定为：候选竞品数量、评论表现、价格带集中度、标签竞争密度。"
BOUNDARY_LIMITATION = "当前数据不足以回答真实收入、平台外数据、未来爆款预测或确定性趋势。"


def identify_intent(question: str) -> str:
    parsed = parse_intent(question, [], DEFAULT_INTENT)
    return parsed.get("intent", {}).get("analysis_type", "unknown")


def _standard_intent(intent: dict[str, Any]) -> dict[str, Any]:
    filters = normalize_filters(intent.get("filters"))
    return {
        "analysis_type": intent.get("analysis_type", "unknown"),
        "target_metric": intent.get("target_metric", "unknown"),
        "filters": filters,
        "group_by": intent.get("group_by", "none"),
        "chart_type": intent.get("chart_type", "none"),
        "ambiguity_notice": intent.get("ambiguity_notice"),
    }


def _response(
    conversation_id: str,
    response_type: str,
    assistant_message: str,
    intent: dict[str, Any],
    clarification: dict[str, Any] | None = None,
    answer: dict[str, Any] | None = None,
    analysis_plan: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "conversation_id": conversation_id,
        "response_type": response_type,
        "assistant_message": assistant_message,
        "clarification": clarification,
        "understood_intent": _standard_intent(intent),
        "analysis_plan": analysis_plan,
        "answer": answer,
    }


def _filters_from_idea_context(idea_context: dict[str, Any] | None) -> dict[str, Any]:
    context = idea_context or {}
    profile = {}
    if isinstance(context.get("query_intent"), dict):
        profile = context.get("query_intent") or {}
    elif isinstance(context.get("idea_profile"), dict):
        profile = context.get("idea_profile") or {}
    return {
        "genres": profile.get("target_genres") or [],
        "tags": profile.get("target_tags") or [],
        "price_range": profile.get("price_range"),
        "year_range": None,
        "min_reviews": None,
        "market_scope": "indie" if context.get("idea_profile") is not None else "unknown",
    }


def _merge_with_context(previous_intent: dict[str, Any], current_filters: dict[str, Any] | None, idea_context: dict[str, Any] | None) -> dict[str, Any]:
    intent = deepcopy(previous_intent)
    merged_filters = normalize_filters(intent.get("filters"))
    if current_filters:
        merged_filters = normalize_filters({**merged_filters, **current_filters})
    context_filters = _filters_from_idea_context(idea_context)
    for key, value in context_filters.items():
        if merged_filters.get(key) in (None, [], "", "unknown") and value not in (None, [], "", "unknown"):
            merged_filters[key] = value
    intent["filters"] = merged_filters
    return intent


def _has_context_filters(filters: dict[str, Any]) -> bool:
    return bool(filters.get("genres") or filters.get("tags") or filters.get("price_range") or filters.get("year_range"))


def _is_ambiguous_question(message: str) -> bool:
    text = (message or "").lower()
    return any(
        phrase in text
        for phrase in ["有没有机会", "赛道赚钱吗", "哪个类型更好", "这个方向", "我的创意行不行", "有没有前景", "值不值得做"]
    )


def _is_out_of_scope_question(message: str) -> bool:
    text = (message or "").lower()
    return any(
        phrase in text
        for phrase in ["真实收入", "真实销量", "未来爆款", "平台外", "外部平台", "预测会不会火", "未来一定"]
    )


def _is_follow_up_message(message: str) -> bool:
    text = (message or "").lower().strip()
    if re.fullmatch(r"\s*(genre|tag)\s*[:：]\s*.+?\s*", message, re.I):
        return True
    markers = [
        "只看",
        "再看",
        "继续",
        "这个",
        "这些",
        "上面",
        "刚才",
        "换成",
        "改成",
        "限定",
        "筛选",
        "列出",
        "前10",
        "前 10",
        "前5",
        "前 5",
        "top",
        "表格",
        "排行",
        "排名",
        "代表游戏",
        "为什么",
        "原因",
        "按价格",
        "按评论",
        "按好评",
        "after",
        "only",
    ]
    return any(marker in text for marker in markers)


def _select_analysis_type(message: str, base_intent: dict[str, Any], idea_context: dict[str, Any] | None) -> tuple[str, str | None]:
    text = (message or "").lower()
    if any(key in text for key in ["竞品", "相似游戏", "similar game", "competitor"]):
        if "相似" in text:
            return "similar_games_analysis", None
        return "competitor_lookup", None
    if any(key in text for key in ["定价", "适合定价多少", "价格带", "价格区间推荐"]):
        return "price_band_analysis", None
    if any(key in text for key in ["标签组合", "哪些标签", "保留哪些标签", "标签机会"]):
        return "tag_combination_analysis", None
    if any(key in text for key in ["风险", "行不行", "值不值得做"]):
        return "idea_risk_analysis", AMBIGUOUS_NOTICE if _is_ambiguous_question(message) else None
    if _is_ambiguous_question(message):
        return "opportunity_analysis", AMBIGUOUS_NOTICE
    if idea_context and any(key in text for key in ["这个方向", "这个赛道", "适合", "竞争激烈", "机会"]):
        return "opportunity_analysis", AMBIGUOUS_NOTICE
    return base_intent.get("analysis_type", "unknown"), None


def _extract_limit(message: str, default: int = 10) -> int:
    match = re.search(r"(\d+)", message or "")
    if match:
        return max(1, min(int(match.group(1)), 50))
    if "前五" in (message or ""):
        return 5
    return default


def _sort_from_message(message: str, fallback: str = "total_reviews", fallback_order: str = "desc") -> tuple[str, str]:
    text = (message or "").lower()
    ascending = any(token in text for token in ["从低到高", "升序", "low to high", "asc"])
    descending = any(token in text for token in ["从高到低", "降序", "high to low", "desc"])
    order = "asc" if ascending else ("desc" if descending else fallback_order)
    if "价格" in text or "price" in text:
        return "price", order
    if "好评" in text or "positive" in text or "rating" in text:
        return "positive_rate", order
    if "年份" in text or "release" in text:
        return "release_year", order
    if "评论" in text or "reviews" in text:
        return "total_reviews", order
    return fallback, order


def detect_follow_up_intent(message: str, last_analysis: dict[str, Any] | None) -> dict[str, Any] | None:
    if not last_analysis or not _is_follow_up_message(message):
        return None
    text = (message or "").lower().strip()
    last_plan = last_analysis.get("analysis_plan") or {}
    last_result = last_analysis.get("analysis") or {}
    fallback_sort = last_result.get("sort_by") or ("positive_rate" if last_plan.get("target_metric") == "positive_rate" else "total_reviews")
    fallback_order = last_result.get("sort_order") or "desc"
    wants_listing = any(token in text for token in ["列出", "代表游戏", "表格", "排行", "排名", "top", "前10", "前 10", "前5", "前 5"]) or (
        "只看" in text and any(token in text for token in ["最高", "最低", "前", "个"])
    )
    wants_sorting = any(token in text for token in ["按价格", "按评论", "按好评", "从低到高", "从高到低", "升序", "降序", "最高", "最低"])
    wants_reason = any(token in text for token in ["为什么", "原因", "why"])

    if wants_listing or wants_sorting:
        sort_by, sort_order = _sort_from_message(message, fallback_sort, fallback_order)
        return {
            "analysis_type": "representative_games",
            "limit": _extract_limit(message, 10),
            "sort_by": sort_by,
            "sort_order": sort_order,
            "focus": "table",
        }
    if wants_reason:
        return {
            "analysis_type": last_plan.get("analysis_type", "unknown"),
            "focus": "explanation",
        }
    return None


def build_follow_up_analysis_plan(message: str, follow_up: dict[str, Any], last_analysis: dict[str, Any], idea_context: dict[str, Any] | None) -> dict[str, Any]:
    previous_plan = deepcopy(last_analysis.get("analysis_plan") or {})
    previous_result = deepcopy(last_analysis.get("analysis") or {})
    previous_intent = deepcopy(last_analysis.get("intent") or {})
    filters = normalize_filters(previous_plan.get("filters") or previous_intent.get("filters"))
    target_metric = previous_plan.get("target_metric") or previous_intent.get("target_metric") or "total_reviews"
    sort_by = follow_up.get("sort_by") or previous_result.get("sort_by") or ("positive_rate" if target_metric == "positive_rate" else "total_reviews")
    sort_order = follow_up.get("sort_order") or previous_result.get("sort_order") or "desc"
    limit = int(follow_up.get("limit") or 10)
    return {
        "plan_type": "execute",
        "analysis_type": follow_up.get("analysis_type", "representative_games"),
        "target_metric": target_metric,
        "filters": filters,
        "group_by": "none",
        "chart_type": "bar",
        "query_context": deepcopy(previous_plan.get("query_context") or previous_intent.get("query_context") or {}),
        "idea_context": idea_context or deepcopy(previous_plan.get("idea_context") or {}),
        "message": message,
        "ambiguity_notice": None,
        "is_follow_up": True,
        "inherit_previous_context": True,
        "sort_by": sort_by,
        "sort_order": sort_order,
        "limit": limit,
        "previous_analysis_type": previous_plan.get("analysis_type"),
        "summary_mode": follow_up.get("focus", "table"),
    }


def _build_analysis_plan(message: str, parsed_intent: dict[str, Any], idea_context: dict[str, Any] | None) -> dict[str, Any]:
    idea_context = idea_context or {}
    filters = normalize_filters(parsed_intent.get("filters"))
    analysis_type, ambiguity_notice = _select_analysis_type(message, parsed_intent, idea_context)
    chart_type = parsed_intent.get("chart_type", "bar")
    if analysis_type in {"competitor_lookup", "similar_games_analysis", "tag_combination_analysis", "opportunity_analysis", "idea_risk_analysis"}:
        chart_type = "bar"
    if analysis_type == "price_band_analysis":
        chart_type = "bar"

    if _is_out_of_scope_question(message):
        return {
            "plan_type": "limitation",
            "analysis_type": "limitation",
            "message": BOUNDARY_LIMITATION,
            "filters": filters,
        }

    if _is_follow_up_message(message) and not _has_context_filters(filters) and analysis_type == "unknown":
        return {
            "plan_type": "clarification",
            "analysis_type": "representative_games",
            "message": "请先提供要分析的类型、标签或关键词；如果这是追问，请先完成上一轮分析。",
            "clarification": {
                "question": "你想查看哪一类样本的代表游戏？",
                "options": [
                    {"label": "输入类型", "value": "genre:Indie", "field": "genre"},
                    {"label": "输入标签", "value": "tag:Puzzle", "field": "tag"},
                    {"label": "输入关键词", "value": "Co-op Horror"},
                ],
                "allow_free_text": True,
            },
            "filters": filters,
        }

    if analysis_type in {"opportunity_analysis", "competitor_lookup", "similar_games_analysis", "price_band_analysis", "tag_combination_analysis", "idea_risk_analysis"} and not _has_context_filters(filters):
        return {
            "plan_type": "clarification",
            "analysis_type": analysis_type,
            "message": "请先提供要分析的类型、标签或关键词；如果你已在立项实验室完成解析，也可以直接先运行一次市场扫描。",
            "clarification": {
                "question": "你想基于什么对象分析？",
                "options": [
                    {"label": "输入类型", "value": "genre:Indie", "field": "genre"},
                    {"label": "输入标签", "value": "tag:Horror", "field": "tag"},
                    {"label": "输入关键词", "value": "Co-op Horror"},
                ],
                "allow_free_text": True,
            },
            "filters": filters,
        }

    query_context = {}
    if isinstance(idea_context.get("query_intent"), dict):
        query_context = deepcopy(idea_context.get("query_intent") or {})
    elif isinstance(idea_context.get("idea_profile"), dict):
        query_context = deepcopy(idea_context.get("idea_profile") or {})

    return {
        "plan_type": "execute",
        "analysis_type": analysis_type,
        "target_metric": parsed_intent.get("target_metric", "unknown"),
        "filters": filters,
        "group_by": parsed_intent.get("group_by", "none"),
        "chart_type": chart_type,
        "query_context": query_context,
        "idea_context": idea_context or {},
        "message": message,
        "ambiguity_notice": ambiguity_notice,
        "is_follow_up": False,
    }


def resolve_question_context(
    message: str,
    parsed_intent: dict[str, Any],
    previous_intent: dict[str, Any],
    last_analysis: dict[str, Any] | None,
    idea_context: dict[str, Any] | None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    follow_up = detect_follow_up_intent(message, last_analysis)
    if follow_up:
        plan = build_follow_up_analysis_plan(message, follow_up, last_analysis, idea_context)
        intent = merge_intent(previous_intent, parsed_intent.get("intent") or previous_intent)
        intent["is_follow_up"] = True
        intent["sort_by"] = plan.get("sort_by")
        intent["sort_order"] = plan.get("sort_order")
        intent["limit"] = plan.get("limit")
        return intent, plan

    if _is_follow_up_message(message):
        intent = merge_intent(previous_intent, parsed_intent.get("intent") or previous_intent)
    else:
        fresh_base = deepcopy(DEFAULT_INTENT)
        fresh_base["filters"] = normalize_filters(_filters_from_idea_context(idea_context))
        intent = merge_intent(fresh_base, parsed_intent.get("intent") or fresh_base)
    return intent, _build_analysis_plan(message, intent, idea_context)


def chat(
    df: pd.DataFrame | None,
    message: str,
    conversation_id: str | None = None,
    history: list[dict[str, str]] | None = None,
    current_filters: dict[str, Any] | None = None,
    idea_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    cid, context = get_or_create_conversation(conversation_id)
    history = history or context.get("history", [])
    previous_intent = context.get("intent") or DEFAULT_INTENT
    previous_intent = _merge_with_context(previous_intent, current_filters, idea_context)
    last_analysis = get_last_analysis(cid)

    add_message(cid, "user", message)

    if df is None or df.empty:
        assistant_message = "当前还没有可分析的数据，请先在 Data Pipeline 加载默认数据或上传 CSV。"
        add_message(cid, "assistant", assistant_message)
        return _response(cid, "error", assistant_message, previous_intent, answer=None)

    try:
        parsed = parse_intent(message, history, previous_intent)
        intent, plan = resolve_question_context(message, parsed, previous_intent, last_analysis, idea_context)

        if plan["plan_type"] == "clarification":
            assistant_message = plan["message"]
            if plan.get("analysis_type") == "opportunity_analysis":
                intent["ambiguity_notice"] = AMBIGUOUS_NOTICE
            update_context(cid, intent)
            add_message(cid, "assistant", assistant_message)
            return _response(cid, "clarification", assistant_message, intent, clarification=plan.get("clarification"), answer=None, analysis_plan=plan)

        if plan["plan_type"] == "limitation":
            answer = {
                "summary": plan["message"],
                "key_metrics": [{"label": "数据边界", "value": "超出范围", "description": "当前数据集无法回答"}],
                "chart": None,
                "charts": [],
                "table": {"columns": [], "rows": []},
                "evidence_payload": {"filters": plan.get("filters", {}), "sample_size": 0, "representative_games": [], "key_statistics": {}, "limitations": [plan["message"]]},
                "evidence_brief": {"filters_text": "未额外筛选", "sample_size": 0, "representative_games": [], "limitations": [plan["message"]]},
                "follow_up_suggestions": ["改问当前数据集中存在的类型、标签、评论、价格或相似竞品问题"],
            }
            add_message(cid, "assistant", plan["message"])
            return _response(cid, "final_answer", plan["message"], intent, answer=answer, analysis_plan=plan)

        executable_intent = merge_intent(
            intent,
            {
                "analysis_type": plan["analysis_type"],
                "target_metric": plan.get("target_metric"),
                "filters": plan.get("filters"),
                "group_by": plan.get("group_by"),
                "chart_type": plan.get("chart_type"),
            },
        )
        executable_intent["ambiguity_notice"] = plan.get("ambiguity_notice")
        executable_intent["query_context"] = plan.get("query_context") or {}
        executable_intent["idea_context"] = plan.get("idea_context") or {}
        executable_intent["message"] = plan.get("message") or message
        executable_intent["is_follow_up"] = bool(plan.get("is_follow_up"))
        executable_intent["sort_by"] = plan.get("sort_by")
        executable_intent["sort_order"] = plan.get("sort_order")
        executable_intent["limit"] = plan.get("limit")
        analysis = run_analysis(df, executable_intent)
        answer = build_answer(executable_intent, analysis)

        raw_df = get_current_raw_data()
        support_data = answer.get("support_data") or {"summary": {}, "tables": [], "notes": []}
        support_data["raw_csv"] = {
            "rows": int(len(raw_df)) if raw_df is not None else 0,
            "columns": list(raw_df.columns) if raw_df is not None else [],
            "view_url": "/raw-data.html",
        }
        support_data["summary"] = {
            **(support_data.get("summary") or {}),
            "segment_count": analysis.get("segment_count", 0),
            "filters": analysis.get("filters", {}),
            "analysis_plan": plan,
        }
        filtered_preview = analysis.get("filtered_preview") or []
        if filtered_preview:
            support_data.setdefault("tables", []).insert(
                0,
                {
                    "title": "筛选后样本预览",
                    "columns": list(filtered_preview[0].keys()),
                    "rows": filtered_preview,
                },
            )
        answer["support_data"] = support_data
        assistant_message = answer["summary"]
        update_context(cid, executable_intent)
        update_last_analysis(
            cid,
            {
                "analysis_plan": plan,
                "analysis": analysis,
                "answer": answer,
                "intent": executable_intent,
            },
        )
        add_message(cid, "assistant", assistant_message)
        return _response(cid, "final_answer", assistant_message, executable_intent, clarification=None, answer=answer, analysis_plan=plan)
    except Exception as exc:
        assistant_message = f"问数分析失败：{exc}"
        add_message(cid, "assistant", assistant_message)
        return _response(cid, "error", assistant_message, previous_intent, answer=None)


def answer_question(df: pd.DataFrame, question: str) -> dict[str, Any]:
    result = chat(df, question)
    intent = result.get("understood_intent", {})
    answer = result.get("answer") or {}
    table = answer.get("table", {}).get("rows", []) if answer else []
    chart_obj = answer.get("chart") or {}
    legacy_chart = {}
    option = chart_obj.get("echarts_option") if chart_obj else None
    if option:
        legacy_chart = {"type": chart_obj.get("type", "bar"), "echarts_option": option}
    return {
        "answer": result.get("assistant_message", ""),
        "intent": intent.get("analysis_type", "unknown"),
        "table": table,
        "chart": legacy_chart,
        "support_data": answer.get("support_data"),
        "llm_used": False,
    }
