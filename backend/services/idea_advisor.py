"""
来源：学生 + AI
作用：为 Idea Lab 提供基于当前分析结果的立项顾问追问能力。
"""

from __future__ import annotations

import json
from typing import Any

from backend.services.llm_client import safe_call_llm


SYSTEM_PROMPT = """你是 GameScope「立项实验室」中的游戏立项顾问助手。

你的任务是：基于用户的游戏创意、创意解析结果、相似竞品、机会评分、差异化建议和 Project Brief，回答用户对立项报告的进一步追问。

你可以进行适度发散，提供创意方向、差异化策略、目标玩家定位、玩法包装、商店页卖点、验证方式和风险提醒。但必须遵守以下规则：

1. 所有涉及市场规模、竞品数量、评分、价格、评论数、好评率、标签频率等事实判断，必须只基于输入的结构化数据。
2. 不要编造新的 Steam 数据、竞品名称、销售成绩或不存在的统计结论。
3. 如果你在发散创意，请明确这是“基于当前数据的建议”或“可尝试的方向”，不要说成确定结论。
4. 回答要面向独立游戏开发者，强调低成本验证、清晰卖点、目标玩家和可执行下一步。
5. 如果用户的问题很宽泛，先给出直接判断，再拆成几个具体方向。
6. 如果用户问“如何差异化”，优先从玩法机制、叙事主题、美术风格、目标人群、定价/体量、商店页表达、Demo 验证方式七个角度回答。
7. 如果用户问报告中不懂的概念，请用通俗中文解释，并结合当前创意举例。
8. 语气要像一位有经验但不武断的游戏制作顾问：具体、鼓励、诚实、有启发性。
9. 在不编造数据的前提下，你可以主动提出大胆但可验证的创意方案，不必只复述报告内容。

回答格式：
- 先用 1-2 句话直接回答用户问题。
- 再列出 3-6 条具体建议。
- 最后给出“下一步可以做什么”的小行动清单。
- 不要重复完整报告。"""


def _trim_text(value: Any, max_length: int = 1600) -> str:
    text = str(value or "").strip()
    if len(text) <= max_length:
        return text
    return f"{text[:max_length].rstrip()}..."


def _compress_competitors(competitors: list[dict], limit: int = 8) -> list[dict]:
    items = []
    for item in (competitors or [])[:limit]:
        items.append(
            {
                "name": item.get("name"),
                "similarity_score": item.get("similarity_score"),
                "price": item.get("price"),
                "positive_rate": item.get("positive_rate"),
                "total_reviews": item.get("total_reviews"),
                "genres": item.get("genres"),
                "tags": item.get("tags"),
                "match_reason": item.get("match_reason"),
            }
        )
    return items


def _compress_support_data(support_data: dict[str, Any]) -> dict[str, Any]:
    support_data = support_data or {}
    summary = {}
    competitor_summary = support_data.get("competitor_evidence", {}).get("summary", {})
    score_summary = support_data.get("score_evidence", {}).get("summary", {})
    differentiation_summary = support_data.get("differentiation_evidence", {}).get("summary", {})
    brief_summary = support_data.get("brief_evidence", {}).get("summary", {})

    if competitor_summary:
        summary["competitor_summary"] = {
            "candidate_pool_size": competitor_summary.get("candidate_pool_size"),
            "top_n": competitor_summary.get("top_n"),
            "indie_only": competitor_summary.get("indie_only"),
            "target_genres": competitor_summary.get("target_genres"),
            "target_tags": competitor_summary.get("target_tags"),
            "price_range": competitor_summary.get("price_range"),
        }
    if score_summary:
        summary["score_summary"] = score_summary
    if differentiation_summary:
        summary["differentiation_summary"] = {
            "competitor_top_tags": differentiation_summary.get("competitor_top_tags", [])[:8],
            "idea_keywords": differentiation_summary.get("idea_keywords", [])[:12],
            "overlap_with_competitors": differentiation_summary.get("overlap_with_competitors", [])[:8],
            "different_keywords": differentiation_summary.get("different_keywords", [])[:8],
            "card_count": differentiation_summary.get("card_count"),
        }
    if brief_summary:
        summary["brief_summary"] = brief_summary
    return summary


def _compress_analysis_result(analysis_result: dict[str, Any]) -> dict[str, Any]:
    analysis_result = analysis_result or {}
    return {
        "idea_profile": analysis_result.get("idea_profile", {}),
        "opportunity_score": analysis_result.get("opportunity_score", {}),
        "competitors": _compress_competitors(analysis_result.get("competitors", [])),
        "differentiation_cards": analysis_result.get("differentiation_cards", [])[:6],
        "project_brief": _trim_text(analysis_result.get("brief", ""), max_length=2200),
        "candidate_pool_size": analysis_result.get("candidate_pool_size"),
        "returned_competitor_count": analysis_result.get("returned_competitor_count"),
        "support_summary": _compress_support_data(analysis_result.get("support_data", {})),
    }


def _compress_history(history: list[Any], limit: int = 8) -> list[dict[str, str]]:
    items = []
    for item in (history or [])[-limit:]:
        role = getattr(item, "role", None) if not isinstance(item, dict) else item.get("role")
        content = getattr(item, "content", None) if not isinstance(item, dict) else item.get("content")
        if not content:
            continue
        items.append({"role": str(role or "user"), "content": _trim_text(content, max_length=500)})
    return items


def _build_user_prompt(question: str, idea_text: str, analysis_result: dict[str, Any], history: list[Any]) -> str:
    compact = _compress_analysis_result(analysis_result)
    return """以下是用户在 GameScope 立项实验室中完成市场扫描后的上下文，请基于这些信息回答用户追问。

【用户原始创意】
{idea_text}

【创意解析结果】
{idea_profile}

【机会评分】
{opportunity_score}

【相似竞品】
{competitors}

【差异化建议卡片】
{differentiation_cards}

【Project Brief】
{project_brief}

【补充摘要】
{support_summary}

【最近对话历史】
{history}

【用户当前追问】
{question}

请回答用户追问。可以适度发散，但要区分“数据依据”和“创意建议”，不要编造新的市场数据。""".format(
        idea_text=_trim_text(idea_text, max_length=1200),
        idea_profile=json.dumps(compact["idea_profile"], ensure_ascii=False, indent=2),
        opportunity_score=json.dumps(compact["opportunity_score"], ensure_ascii=False, indent=2),
        competitors=json.dumps(compact["competitors"], ensure_ascii=False, indent=2),
        differentiation_cards=json.dumps(compact["differentiation_cards"], ensure_ascii=False, indent=2),
        project_brief=compact["project_brief"] or "暂无",
        support_summary=json.dumps(compact["support_summary"], ensure_ascii=False, indent=2),
        history=json.dumps(_compress_history(history), ensure_ascii=False, indent=2),
        question=question.strip(),
    )


def _fallback_answer(analysis_result: dict[str, Any]) -> str:
    cards = analysis_result.get("differentiation_cards", []) if isinstance(analysis_result, dict) else []
    score = (analysis_result or {}).get("opportunity_score", {})
    suggestions = [f"- {card.get('title', '建议')}：{card.get('content', '')}" for card in cards[:3] if card.get("content")]
    if not suggestions:
        suggestions = [
            "- 先回看机会评分，优先验证最低分或最不确定的维度。",
            "- 结合竞品表格，挑出最像你的 3 款产品，写清楚你准备避开的同质化点。",
            "- 把 Project Brief 里的核心卖点压缩成一句话，再拿去做商店页首屏测试。",
        ]

    return "\n".join(
        [
            "当前 LLM 未启用，无法进行自由追问。但你仍可以参考报告中的差异化建议、机会评分和竞品表格。",
            "",
            f"- 当前机会总分：{score.get('total_score', '暂无')}。",
            *suggestions,
            "",
            "下一步可以做什么：",
            "- 先选 1 条差异化方向，写成一句明确卖点。",
            "- 再做一个只验证该卖点的小型 Demo 或商店页文案版本。",
            "- 用竞品表格检查它是否真的避开了最拥挤的标签组合。",
        ]
    )


def generate_idea_advisor_answer(request_data: Any) -> dict[str, Any]:
    question = getattr(request_data, "question", "") or ""
    idea_text = getattr(request_data, "idea_text", "") or ""
    analysis_result = getattr(request_data, "analysis_result", {}) or {}
    history = getattr(request_data, "history", []) or []

    prompt = _build_user_prompt(question, idea_text, analysis_result, history)
    llm = safe_call_llm(prompt, SYSTEM_PROMPT)
    if llm.get("success") and llm.get("content"):
        return {
            "answer": str(llm["content"]).strip(),
            "llm_used": bool(llm.get("llm_used", False)),
            "fallback_used": False,
            "message": llm.get("message", "LLM 调用成功。"),
        }

    return {
        "answer": _fallback_answer(analysis_result),
        "llm_used": False,
        "fallback_used": True,
        "message": llm.get("message", "当前使用规则 fallback。"),
    }
