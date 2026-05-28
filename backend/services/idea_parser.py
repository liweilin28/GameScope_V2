"""
来源：学生 + AI
作用：将自然语言游戏创意解析为结构化 idea_profile，优先 LLM，失败时规则 fallback。
"""

from __future__ import annotations

import json
import re

from backend.services.llm_client import safe_call_llm


DEFAULT_IDEA_PROFILE = {
    "target_genres": ["Indie"],
    "target_tags": ["Puzzle", "Story Rich", "Atmospheric"],
    "price_range": [0, 20],
    "art_style_keywords": [],
    "gameplay_keywords": [],
    "narrative_keywords": [],
    "target_players": [],
    "reference_games": [],
}


GENRE_KEYWORDS = {
    "独立": "Indie",
    "indie": "Indie",
    "解谜": "Puzzle",
    "puzzle": "Puzzle",
    "冒险": "Adventure",
    "rpg": "RPG",
    "角色扮演": "RPG",
    "模拟": "Simulation",
    "策略": "Strategy",
    "动作": "Action",
}

TAG_KEYWORDS = {
    "剧情": "Story Rich",
    "剧情向": "Story Rich",
    "叙事": "Story Rich",
    "故事": "Story Rich",
    "治愈": "Relaxing",
    "氛围": "Atmospheric",
    "氛围感": "Atmospheric",
    "atmospheric": "Atmospheric",
    "2d": "2D",
    "像素": "Pixel Graphics",
    "手绘": "Hand-drawn",
    "合作": "Co-op",
    "恐怖": "Horror",
}


TERM_TRANSLATIONS = {
    **{key.lower(): value for key, value in GENRE_KEYWORDS.items()},
    **{key.lower(): value for key, value in TAG_KEYWORDS.items()},
    "独立游戏": "Indie",
    "解谜游戏": "Puzzle",
    "冒险游戏": "Adventure",
    "角色扮演": "RPG",
    "模拟经营": "Simulation",
    "策略游戏": "Strategy",
    "动作游戏": "Action",
    "单人": "Singleplayer",
    "单机": "Singleplayer",
    "多人": "Multiplayer",
    "合作游戏": "Co-op",
    "恐怖游戏": "Horror",
    "休闲": "Casual",
    "可爱": "Cute",
    "卡通": "Cartoony",
    "彩色": "Colorful",
    "情感": "Emotional",
    "女性主角": "Female Protagonist",
    "选择导向": "Choices Matter",
    "多结局": "Multiple Endings",
}


def _translate_term(value) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    lower = text.lower()
    return TERM_TRANSLATIONS.get(lower, text)


def _normalize_list(values) -> list[str]:
    if not isinstance(values, list):
        return []
    normalized: list[str] = []
    seen: set[str] = set()
    for value in values:
        translated = _translate_term(value)
        if not translated:
            continue
        key = translated.lower()
        if key not in seen:
            normalized.append(translated)
            seen.add(key)
    return normalized


def _normalize_profile(profile: dict) -> dict:
    result = DEFAULT_IDEA_PROFILE.copy()
    for key in result:
        value = profile.get(key, result[key])
        if key == "price_range":
            result[key] = value if isinstance(value, list) and len(value) == 2 else result[key]
        else:
            normalized = _normalize_list(value)
            result[key] = normalized if normalized else result[key]
    return result


def normalize_idea_profile(profile: dict | None) -> dict:
    """Normalize any LLM/user-edited idea profile to Steam-compatible English terms."""
    return _normalize_profile(profile or {})


def _rule_parse(idea_text: str) -> dict:
    text = idea_text.lower()
    genres = sorted({value for key, value in GENRE_KEYWORDS.items() if key in text})
    tags = sorted({value for key, value in TAG_KEYWORDS.items() if key in text})

    price_range = [0, 20]
    match = re.search(r"(\d+(?:\.\d+)?)\s*(?:元|块|以内|以下|rmb|￥)", text)
    if match:
        price_range = [0, float(match.group(1))]

    profile = {
        "target_genres": genres or ["Indie"],
        "target_tags": tags or ["Puzzle", "Story Rich", "Atmospheric"],
        "price_range": price_range,
        "art_style_keywords": [word for word in ["2D", "Pixel Graphics", "Hand-drawn", "Relaxing"] if word in tags],
        "gameplay_keywords": [word for word in ["Puzzle", "Co-op", "Simulation"] if word in genres + tags],
        "narrative_keywords": [word for word in ["Story Rich", "Atmospheric"] if word in tags],
        "target_players": ["Indie players"] if "indie" in text or "独立" in text else [],
        "reference_games": [],
    }
    return _normalize_profile(profile)


def parse_idea(idea_text: str, prefer_llm: bool = True) -> dict:
    """解析游戏创意；优先 LLM，失败或未配置时使用关键词规则。"""
    if prefer_llm:
        prompt = (
            "请把游戏创意解析为 JSON，字段固定为 target_genres,target_tags,price_range,"
            "art_style_keywords,gameplay_keywords,narrative_keywords,target_players,reference_games。"
            "target_genres 和 target_tags 必须使用 Steam 数据常见英文标签，例如 Indie, Puzzle, Story Rich, Atmospheric, Relaxing, 2D。"
            f"只返回 JSON，不要解释。创意：{idea_text}"
        )
        llm = safe_call_llm(prompt, "你是游戏立项分析助手，只能输出 JSON。")
        if llm["success"]:
            try:
                return {**_normalize_profile(json.loads(llm["content"])), "llm_used": True}
            except Exception:
                pass
    profile = _rule_parse(idea_text)
    profile["llm_used"] = False
    return profile
