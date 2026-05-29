"""
来源：学生 + AI
作用：Data Q&A 多轮澄清式智能问数 Agent 总控模块。
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from backend.services.qa_analysis_runner import run_analysis
from backend.services.qa_conversation import (
    DEFAULT_INTENT,
    add_message,
    get_or_create_conversation,
    merge_intent,
    normalize_filters,
    update_context,
)
from backend.services.qa_intent_parser import parse_intent
from backend.services.qa_response_builder import build_answer
from backend.services.data_loader import get_current_raw_data


def identify_intent(question: str) -> str:
    """兼容旧测试和旧接口：返回单轮问题的大致分析类型。"""
    parsed = parse_intent(question, [], DEFAULT_INTENT)
    return parsed.get("intent", {}).get("analysis_type", "unknown")


def _standard_intent(intent: dict[str, Any]) -> dict[str, Any]:
    filters = normalize_filters(intent.get("filters"))
    standard = {
        "analysis_type": intent.get("analysis_type", "unknown"),
        "target_metric": intent.get("target_metric", "unknown"),
        "filters": filters,
        "group_by": intent.get("group_by", "none"),
        "chart_type": intent.get("chart_type", "none"),
    }
    if intent.get("answer_mode"):
        standard["answer_mode"] = intent.get("answer_mode")
    return standard


def _response(
    conversation_id: str,
    response_type: str,
    assistant_message: str,
    intent: dict[str, Any],
    clarification: dict[str, Any] | None = None,
    answer: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "conversation_id": conversation_id,
        "response_type": response_type,
        "assistant_message": assistant_message,
        "clarification": clarification,
        "understood_intent": _standard_intent(intent),
        "answer": answer,
    }


def chat(
    df: pd.DataFrame | None,
    message: str,
    conversation_id: str | None = None,
    history: list[dict[str, str]] | None = None,
    current_filters: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """处理一轮多轮智能问数请求。"""
    cid, context = get_or_create_conversation(conversation_id)
    history = history or context.get("history", [])
    previous_intent = context.get("intent") or DEFAULT_INTENT
    if current_filters:
        previous_intent = merge_intent(previous_intent, {"filters": current_filters})

    add_message(cid, "user", message)

    if df is None or df.empty:
        assistant_message = "当前还没有可分析的数据，请先在 Data Pipeline 页面加载默认数据或上传 CSV。"
        add_message(cid, "assistant", assistant_message)
        return _response(cid, "error", assistant_message, previous_intent, answer=None)

    try:
        parsed = parse_intent(message, history, previous_intent)
        intent = parsed.get("intent") or previous_intent
        if parsed.get("need_clarification"):
            clarification = parsed.get("clarification")
            assistant_message = clarification.get("question", "请补充你的分析目标。") if clarification else "请补充你的分析目标。"
            update_context(cid, intent)
            add_message(cid, "assistant", assistant_message)
            return _response(cid, "clarification", assistant_message, intent, clarification=clarification, answer=None)

        analysis = run_analysis(df, intent)
        answer = build_answer(intent, analysis)
        raw_df = get_current_raw_data()
        if answer.get("display_mode") == "explanation":
            answer["support_data"] = None
        else:
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
            support_data["notes"] = [
                "本区域优先展示本次筛选后的样本和后端 pandas 分析结果。",
                "点击“查看全部原始 CSV”会打开新页面展示完整当前原始数据。",
                *([note for note in support_data.get("notes", []) if "本区域" not in note and "LLM" in note] or []),
            ]
            answer["support_data"] = support_data
        assistant_message = answer["summary"]
        update_context(cid, intent)
        add_message(cid, "assistant", assistant_message)
        return _response(cid, "final_answer", assistant_message, intent, clarification=None, answer=answer)
    except Exception as exc:
        assistant_message = f"问数分析失败：{exc}"
        add_message(cid, "assistant", assistant_message)
        return _response(cid, "error", assistant_message, previous_intent, answer=None)


def answer_question(df: pd.DataFrame, question: str) -> dict[str, Any]:
    """兼容旧 /api/qa/ask：把新 chat 输出转换为旧格式。"""
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
