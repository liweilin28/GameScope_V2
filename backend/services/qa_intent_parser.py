"""
来源：学生 + AI
作用：将用户自然语言问题解析成智能问数所需的结构化 intent。
"""

from __future__ import annotations

import json
import re
from copy import deepcopy
from datetime import date
from typing import Any

from backend.services.llm_client import get_llm_status, safe_call_llm
from backend.services.qa_conversation import DEFAULT_FILTERS, DEFAULT_INTENT, merge_filters, merge_intent


SYSTEM_PROMPT = """
你是 GameScope 的智能问数意图解析器。
你的任务不是回答用户问题，而是把用户自然语言问题解析为结构化 JSON。
你只能输出 JSON，不允许输出 Markdown。
如果用户问题不明确，你必须返回 need_clarification = true，并给出一个澄清问题和 3-6 个选项。
如果用户问题明确，你返回 need_clarification = false，并给出 analysis_type、target_metric、filters、group_by、chart_type。
你不能编造数据，不能生成最终分析结论，不能生成图表数据。
所有真实计算必须由 Python pandas 后端完成。
"""


PERFORMANCE_CLARIFICATION = {
    "question": "你说的表现好主要指哪一种指标？",
    "options": [
        {"label": "评论数量高", "value": "total_reviews"},
        {"label": "好评率高", "value": "positive_rate"},
        {"label": "近年增长快", "value": "release_trend"},
        {"label": "价格表现好", "value": "price"},
        {"label": "我自己输入", "value": "free_text"},
    ],
    "allow_free_text": True,
}

OBJECT_CLARIFICATION = {
    "question": "你想分析哪个类型或标签？",
    "options": [
        {"label": "Indie 类型", "value": "Indie", "field": "genre"},
        {"label": "RPG 类型", "value": "RPG", "field": "genre"},
        {"label": "Puzzle 标签", "value": "Puzzle", "field": "tag"},
        {"label": "Adventure 类型", "value": "Adventure", "field": "genre"},
        {"label": "Strategy 类型", "value": "Strategy", "field": "genre"},
        {"label": "我自己输入", "value": "free_text"},
    ],
    "allow_free_text": True,
}

SCOPE_CLARIFICATION = {
    "question": "你想分析全市场，还是只分析独立游戏？",
    "options": [
        {"label": "只看 Indie 游戏", "value": "indie"},
        {"label": "看全部游戏", "value": "all"},
        {"label": "我自己输入", "value": "free_text"},
    ],
    "allow_free_text": True,
}

GENERAL_CLARIFICATION = {
    "question": "你更想从哪个角度开始？",
    "options": [
        {"label": "市场趋势", "value": "release_trend"},
        {"label": "类型分布", "value": "genre_distribution"},
        {"label": "价格分布", "value": "price_distribution"},
        {"label": "口碑表现", "value": "positive_rate"},
        {"label": "细分市场竞争", "value": "market_pressure"},
        {"label": "我自己输入", "value": "free_text"},
    ],
    "allow_free_text": True,
}


def _default_parse() -> dict[str, Any]:
    return {
        "need_clarification": True,
        "clarification": deepcopy(GENERAL_CLARIFICATION),
        "intent": deepcopy(DEFAULT_INTENT),
    }


def _clean_json(text: str) -> dict[str, Any] | None:
    candidate = text.strip()
    if candidate.startswith("```"):
        candidate = re.sub(r"^```(?:json)?", "", candidate).strip()
        candidate = re.sub(r"```$", "", candidate).strip()
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", candidate, re.S)
        if not match:
            return None
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return None


def _normalize_intent(intent: dict[str, Any] | None) -> dict[str, Any]:
    output = deepcopy(DEFAULT_INTENT)
    if not intent:
        return output
    output.update({k: intent.get(k, output[k]) for k in ["analysis_type", "target_metric", "group_by", "chart_type"]})
    output["filters"] = merge_filters(DEFAULT_FILTERS, intent.get("filters"))
    return output


def _normalize_options(options: Any) -> list[dict[str, str]]:
    """兼容 LLM 返回字符串数组或对象数组，统一转成前端按钮结构。"""
    normalized: list[dict[str, str]] = []
    if not isinstance(options, list):
        return normalized
    for item in options:
        if isinstance(item, str):
            normalized.append({"label": item, "value": item})
        elif isinstance(item, dict):
            label = str(item.get("label") or item.get("value") or "选项")
            value = str(item.get("value") or item.get("label") or label)
            option = {"label": label, "value": value}
            if item.get("field"):
                option["field"] = str(item.get("field"))
            normalized.append(option)
    return normalized


def parse_with_llm(message: str, history: list[dict[str, str]], previous_intent: dict[str, Any]) -> dict[str, Any] | None:
    """LLM 模式：只解析 intent 和澄清问题，不生成分析结论。"""
    if not get_llm_status()["enabled"]:
        return None

    prompt = {
        "user_message": message,
        "recent_history": history[-8:],
        "previous_intent": previous_intent,
        "allowed_analysis_type": [
            "price_distribution",
            "release_trend",
            "genre_distribution",
            "tag_frequency",
            "review_comparison",
            "market_pressure",
            "segment_analysis",
            "ranking",
            "correlation",
            "unknown",
        ],
        "allowed_target_metric": ["price", "total_reviews", "positive_rate", "release_count", "opportunity", "unknown"],
        "required_json_keys": ["need_clarification", "clarification_question", "clarification_options", "intent"],
    }
    result = safe_call_llm(json.dumps(prompt, ensure_ascii=False), SYSTEM_PROMPT)
    if not result["success"] or not result["content"]:
        return None
    parsed = _clean_json(result["content"])
    if not parsed:
        return None
    clarification = None
    if parsed.get("need_clarification"):
        options = _normalize_options(parsed.get("clarification_options")) or GENERAL_CLARIFICATION["options"]
        clarification = {
            "question": parsed.get("clarification_question") or GENERAL_CLARIFICATION["question"],
            "options": options,
            "allow_free_text": True,
        }
    return {
        "need_clarification": bool(parsed.get("need_clarification")),
        "clarification": clarification,
        "intent": _normalize_intent(parsed.get("intent")),
    }


def _extract_year_range(text: str) -> list[int] | None:
    current_year = date.today().year
    after_match = re.search(r"(20\d{2})\s*年?以[后後]", text)
    if after_match:
        return [int(after_match.group(1)), current_year]
    range_match = re.search(r"(20\d{2})\s*[-到至]\s*(20\d{2})", text)
    if range_match:
        return [int(range_match.group(1)), int(range_match.group(2))]
    if "近五年" in text or "最近五年" in text:
        return [current_year - 5, current_year]
    return None


def _extract_price_range(text: str) -> list[float] | None:
    under_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:元|块|美元)?以[内下]", text)
    if under_match:
        return [0, float(under_match.group(1))]
    range_match = re.search(r"(\d+(?:\.\d+)?)\s*[-到至]\s*(\d+(?:\.\d+)?)", text)
    if range_match and any(key in text for key in ["价格", "price", "元", "美元"]):
        return [float(range_match.group(1)), float(range_match.group(2))]
    return None


def _extract_terms(text: str, terms: list[str]) -> list[str]:
    lower = text.lower()
    return [term for term in terms if term.lower() in lower]


def _is_tag_context(text: str) -> bool:
    return any(key in text.lower() for key in ["标签", "tag", "tags", "热门标签"])


def _is_follow_up(message: str) -> bool:
    text = message.lower().strip()
    if re.fullmatch(r"\s*(genre|tag)\s*[:：]\s*.+?\s*", message, re.I):
        return True
    follow_up_markers = [
        "只看",
        "再看",
        "继续",
        "同样",
        "呢",
        "这个",
        "这些",
        "上面",
        "刚才",
        "换成",
        "改成",
        "限定",
        "筛选",
        "为什么",
        "为何",
        "原因",
        "解释",
        "背后",
        "怎么会",
        "after",
        "only",
    ]
    return any(marker in text for marker in follow_up_markers)


def _has_any(text: str, keywords: list[str]) -> bool:
    return any(keyword in text for keyword in keywords)


def _is_reasoning_request(text: str) -> bool:
    return any(keyword in text for keyword in ["为什么", "为何", "原因", "解释", "背后", "怎么会", "说明什么"])


def _filters_from_text(message: str, previous_filters: dict[str, Any] | None = None) -> dict[str, Any]:
    text = message.lower()
    filters = merge_filters(previous_filters, {})
    field_match = re.fullmatch(r"\s*(genre|tag)\s*[:：]\s*(.+?)\s*", message, re.I)
    if field_match:
        field = field_match.group(1).lower()
        value = field_match.group(2).strip()
        if field == "genre":
            filters["genres"] = [value]
        else:
            filters["tags"] = [value]
        return filters
    genre_terms = ["Indie", "RPG", "Puzzle", "Adventure", "Strategy", "Action", "Simulation", "Casual"]
    tag_terms = ["Story Rich", "Atmospheric", "Singleplayer", "2D", "Pixel Graphics", "Relaxing", "Horror"]
    ambiguous_terms = {"Puzzle", "Adventure", "Strategy", "Action", "Simulation", "Casual"}
    detected_terms = _extract_terms(message, genre_terms)
    tags = _extract_terms(message, tag_terms)
    genres: list[str] = []

    for term in detected_terms:
        if term in ambiguous_terms and _is_tag_context(message):
            if term not in tags:
                tags.append(term)
        else:
            genres.append(term)
    if "独立" in message or "indie" in text:
        filters["market_scope"] = "indie"
        if "Indie" not in genres:
            genres.append("Indie")
    if "全市场" in message or "全部" in message or "all" in text:
        filters["market_scope"] = "all"
    if genres:
        filters["genres"] = genres
    if tags:
        filters["tags"] = tags
    year_range = _extract_year_range(message)
    if year_range:
        filters["year_range"] = year_range
    price_range = _extract_price_range(message)
    if price_range:
        filters["price_range"] = price_range
    min_reviews = re.search(r"至少\s*(\d+)\s*(?:条)?评论", message)
    if min_reviews:
        filters["min_reviews"] = int(min_reviews.group(1))
    return filters


def parse_with_rules(message: str, history: list[dict[str, str]], previous_intent: dict[str, Any]) -> dict[str, Any]:
    """规则 fallback：支持常见问法、模糊反问和追问条件合并。"""
    text = message.lower().strip()
    is_follow_up = _is_follow_up(message)
    base_intent = previous_intent if is_follow_up else DEFAULT_INTENT
    filters = _filters_from_text(message, base_intent.get("filters"))
    intent = merge_intent(base_intent, {"filters": filters})
    previous_analysis = base_intent.get("analysis_type", "unknown")
    filter_changed = filters != merge_filters(base_intent.get("filters"), {})

    if text in {"total_reviews", "评论数量高", "评论数高"}:
        intent.update({"analysis_type": "ranking", "target_metric": "total_reviews", "group_by": "none", "chart_type": "bar"})
        return {"need_clarification": False, "clarification": None, "intent": intent}
    if text in {"positive_rate", "好评率高", "口碑好"}:
        intent.update({"analysis_type": "ranking", "target_metric": "positive_rate", "group_by": "none", "chart_type": "bar"})
        return {"need_clarification": False, "clarification": None, "intent": intent}
    if text in {"release_trend", "近年增长快", "市场趋势"}:
        intent.update({"analysis_type": "release_trend", "target_metric": "release_count", "group_by": "year", "chart_type": "line"})
        return {"need_clarification": False, "clarification": None, "intent": intent}
    if text in {"price_distribution", "价格分布", "价格表现好"}:
        intent.update({"analysis_type": "price_distribution", "target_metric": "price", "group_by": "price_level", "chart_type": "bar"})
        return {"need_clarification": False, "clarification": None, "intent": intent}
    if text in {"market_pressure", "细分市场竞争"}:
        intent.update({"analysis_type": "market_pressure", "target_metric": "opportunity", "group_by": "none", "chart_type": "bar"})
        if intent["filters"].get("market_scope") == "unknown":
            intent["filters"]["market_scope"] = "all"
        return {"need_clarification": False, "clarification": None, "intent": intent}

    if _is_reasoning_request(text) and intent["analysis_type"] != "unknown" and previous_analysis != "unknown":
        intent["answer_mode"] = "explanation"
        intent["chart_type"] = "none"
        return {"need_clarification": False, "clarification": None, "intent": intent}

    if any(key in text for key in ["靠谱吗", "用图表", "列出", "前 10", "top"]) and intent["analysis_type"] != "unknown":
        if any(key in text for key in ["列出", "前 10", "top"]):
            intent.update({"analysis_type": "ranking", "target_metric": intent.get("target_metric") or "total_reviews", "chart_type": "bar"})
        return {"need_clarification": False, "clarification": None, "intent": intent}

    if filter_changed and previous_analysis != "unknown":
        return {"need_clarification": False, "clarification": None, "intent": intent}

    if any(key in text for key in ["标签", "tag", "热门标签"]) and not any(
        key in text for key in ["价格", "price", "多少钱", "免费", "付费"]
    ):
        intent.update({"analysis_type": "tag_frequency", "target_metric": "release_count", "group_by": "tag", "chart_type": "bar"})
        return {"need_clarification": False, "clarification": None, "intent": intent}
    if any(key in text for key in ["这个类型", "某个类型", "哪个类型"]) and not intent["filters"].get("genres"):
        if any(key in text for key in ["年份", "趋势", "近几年", "增长", "发行"]):
            intent.update({"analysis_type": "release_trend", "target_metric": "release_count", "group_by": "year", "chart_type": "line"})
        elif any(key in text for key in ["价格", "price", "多少钱", "免费", "付费"]):
            intent.update({"analysis_type": "price_distribution", "target_metric": "price", "group_by": "price_level", "chart_type": "bar"})
        return {"need_clarification": True, "clarification": deepcopy(OBJECT_CLARIFICATION), "intent": intent}
    if any(key in text for key in ["竞争", "竞品", "拥挤", "市场压力"]) and intent["filters"].get("market_scope") == "unknown":
        intent.update({"analysis_type": "market_pressure", "target_metric": "opportunity", "chart_type": "bar"})
        intent["filters"]["market_scope"] = "all"
        return {"need_clarification": False, "clarification": None, "intent": intent}
    if message.strip() in {"帮我分析一下 Steam 游戏", "分析一下", "看看市场", "steam游戏怎么样"}:
        return {"need_clarification": True, "clarification": deepcopy(GENERAL_CLARIFICATION), "intent": intent}

    price_terms = ["价格", "price", "多少钱", "免费", "付费", "低价", "高价"]
    review_terms = ["评论", "热度", "reviews", "popular"]
    reception_terms = ["好评", "口碑", "positive", "评价"]
    relation_terms = ["关系", "相关", "影响", "有关", "差异", "差别", "对比", "比较"]
    comparison_terms = ["差异", "差别", "对比", "比较", "免费", "付费", "低价", "高价"]

    has_price = _has_any(text, price_terms)
    has_reviews = _has_any(text, review_terms)
    has_reception = _has_any(text, reception_terms)
    has_relation = _has_any(text, relation_terms)
    wants_group_comparison = _has_any(text, comparison_terms)
    price_group = "price_type" if _has_any(text, ["免费", "付费"]) else "price_level"

    if has_relation and has_price and has_reception:
        intent.update(
            {
                "analysis_type": "review_comparison" if wants_group_comparison else "correlation",
                "target_metric": "positive_rate",
                "group_by": price_group if wants_group_comparison else "none",
                "chart_type": "bar" if wants_group_comparison else "scatter",
            }
        )
    elif has_relation and has_price and has_reviews:
        intent.update(
            {
                "analysis_type": "review_comparison" if wants_group_comparison else "correlation",
                "target_metric": "total_reviews",
                "group_by": price_group if wants_group_comparison else "none",
                "chart_type": "bar" if wants_group_comparison else "scatter",
            }
        )
    elif has_relation and has_reviews and has_reception:
        intent.update({"analysis_type": "correlation", "target_metric": "positive_rate", "group_by": "reviews_positive", "chart_type": "scatter"})
    elif any(key in text for key in ["价格", "price", "多少钱", "免费", "付费"]):
        intent.update({"analysis_type": "price_distribution", "target_metric": "price", "group_by": "price_level", "chart_type": "bar"})
    elif any(key in text for key in ["年份", "趋势", "近几年", "增长", "发行"]):
        intent.update({"analysis_type": "release_trend", "target_metric": "release_count", "group_by": "year", "chart_type": "line"})
    elif any(key in text for key in ["类型", "genre", "类别", "分布"]):
        intent.update({"analysis_type": "genre_distribution", "target_metric": "release_count", "group_by": "genre", "chart_type": "bar"})
    elif any(key in text for key in ["表现好", "比较好", "最好", "好游戏", "热门", "热度高"]):
        intent.update({"analysis_type": "ranking", "target_metric": "total_reviews", "group_by": "none", "chart_type": "bar"})
    elif any(key in text for key in ["好评", "口碑", "positive", "评价"]):
        intent.update({"analysis_type": "review_comparison", "target_metric": "positive_rate", "group_by": "price_level", "chart_type": "bar"})
    elif any(key in text for key in ["评论", "热度", "reviews", "popular"]):
        intent.update({"analysis_type": "ranking", "target_metric": "total_reviews", "group_by": "none", "chart_type": "bar"})
    elif any(key in text for key in ["细分市场", "竞品市场", "+"]):
        intent.update({"analysis_type": "segment_analysis", "target_metric": "opportunity", "group_by": "none", "chart_type": "bar"})
    else:
        return {"need_clarification": True, "clarification": deepcopy(GENERAL_CLARIFICATION), "intent": intent}

    return {"need_clarification": False, "clarification": None, "intent": intent}


def parse_intent(message: str, history: list[dict[str, str]], previous_intent: dict[str, Any]) -> dict[str, Any]:
    """优先使用 LLM 解析；失败或未配置时使用规则 fallback。"""
    rule_result = parse_with_rules(message, history, previous_intent)
    if not rule_result.get("need_clarification"):
        return rule_result
    llm_result = parse_with_llm(message, history, previous_intent)
    if llm_result and not llm_result.get("need_clarification"):
        return llm_result
    return rule_result
