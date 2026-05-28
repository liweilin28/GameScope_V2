"""
来源：学生 + AI
作用：维护 Data Q&A 多轮对话上下文。当前使用内存字典，便于课程 Demo。
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any
from uuid import uuid4


DEFAULT_FILTERS = {
    "genres": [],
    "tags": [],
    "price_range": None,
    "year_range": None,
    "min_reviews": None,
    "market_scope": "unknown",
}

DEFAULT_INTENT = {
    "analysis_type": "unknown",
    "target_metric": "unknown",
    "filters": deepcopy(DEFAULT_FILTERS),
    "group_by": "none",
    "chart_type": "none",
}

_CONVERSATIONS: dict[str, dict[str, Any]] = {}


def create_conversation() -> str:
    """创建新的对话 ID。"""
    conversation_id = uuid4().hex
    _CONVERSATIONS[conversation_id] = {
        "history": [],
        "intent": deepcopy(DEFAULT_INTENT),
        "filters": deepcopy(DEFAULT_FILTERS),
    }
    return conversation_id


def get_or_create_conversation(conversation_id: str | None) -> tuple[str, dict[str, Any]]:
    """根据 conversation_id 读取上下文，不存在时自动创建。"""
    if not conversation_id or conversation_id not in _CONVERSATIONS:
        conversation_id = create_conversation()
    return conversation_id, _CONVERSATIONS[conversation_id]


def normalize_filters(filters: dict[str, Any] | None) -> dict[str, Any]:
    """补齐筛选条件字段，避免前端缺字段导致后端异常。"""
    output = deepcopy(DEFAULT_FILTERS)
    if filters:
        for key in output:
            value = filters.get(key)
            if value not in (None, [], ""):
                output[key] = value
    return output


def merge_filters(base: dict[str, Any] | None, updates: dict[str, Any] | None) -> dict[str, Any]:
    """合并筛选条件；新条件覆盖旧条件。"""
    merged = normalize_filters(base)
    if updates:
        for key, value in updates.items():
            if key in merged and value not in (None, [], ""):
                merged[key] = value
    return merged


def merge_intent(previous: dict[str, Any] | None, parsed: dict[str, Any] | None) -> dict[str, Any]:
    """合并上一轮 intent 和本轮解析结果，用于支持追问。"""
    output = deepcopy(DEFAULT_INTENT)
    if previous:
        output.update({k: v for k, v in previous.items() if k != "filters" and v not in (None, "")})
        output["filters"] = normalize_filters(previous.get("filters"))
    if parsed:
        for key in ["analysis_type", "target_metric", "group_by", "chart_type"]:
            value = parsed.get(key)
            if value and value != "unknown":
                output[key] = value
        output["filters"] = merge_filters(output.get("filters"), parsed.get("filters"))
    return output


def add_message(conversation_id: str, role: str, content: str) -> None:
    """保存一轮消息，仅保留最近 20 条，避免内存无限增长。"""
    conversation = _CONVERSATIONS[conversation_id]
    conversation["history"].append({"role": role, "content": content})
    conversation["history"] = conversation["history"][-20:]


def update_context(conversation_id: str, intent: dict[str, Any]) -> None:
    """保存当前已确认的 intent 和 filters。"""
    conversation = _CONVERSATIONS[conversation_id]
    conversation["intent"] = merge_intent(conversation.get("intent"), intent)
    conversation["filters"] = normalize_filters(conversation["intent"].get("filters"))


def clear_conversations() -> None:
    """测试用：清空内存对话。"""
    _CONVERSATIONS.clear()
