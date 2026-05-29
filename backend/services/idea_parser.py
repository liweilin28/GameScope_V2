"""
Source: student + AI
Purpose: parse natural-language game ideas into a normalized market query intent.
"""

from __future__ import annotations

import json
import re
from difflib import get_close_matches
from typing import Any

import pandas as pd

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
    "soft_keywords": [],
    "normalization_notes": [],
}


GENRE_KEYWORDS = {
    "indie": "Indie",
    "独立": "Indie",
    "解谜": "Puzzle",
    "puzzle": "Puzzle",
    "冒险": "Adventure",
    "adventure": "Adventure",
    "rpg": "RPG",
    "角色扮演": "RPG",
    "模拟": "Simulation",
    "simulation": "Simulation",
    "策略": "Strategy",
    "strategy": "Strategy",
    "动作": "Action",
    "action": "Action",
    "恐怖": "Horror",
    "horror": "Horror",
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
    "co-op": "Co-op",
    "联机": "Multiplayer",
    "单人": "Singleplayer",
    "悬疑": "Mystery",
    "推理": "Investigation",
    "调查": "Investigation",
}


TERM_TRANSLATIONS = {
    **{key.lower(): value for key, value in GENRE_KEYWORDS.items()},
    **{key.lower(): value for key, value in TAG_KEYWORDS.items()},
    "独立游戏": "Indie",
    "解谜游戏": "Puzzle",
    "冒险游戏": "Adventure",
    "角色扮演游戏": "RPG",
    "模拟经营": "Simulation",
    "策略游戏": "Strategy",
    "动作游戏": "Action",
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
    "办公室": "Office",
    "档案分析": "case file analysis",
    "电话协调": "phone coordination",
    "监控": "surveillance monitoring",
    "异象调查": "anomaly investigation",
    "官僚恐怖": "bureaucratic horror",
    "信任崩塌": "trust breakdown",
    "低饱和": "low saturation",
    "冷色调": "cold palette",
    "室内": "interior",
}


QUERY_LIST_FIELDS = [
    "target_genres",
    "target_tags",
    "art_style_keywords",
    "gameplay_keywords",
    "narrative_keywords",
    "target_players",
    "reference_games",
    "soft_keywords",
]
CJK_PATTERN = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")
TOKEN_SPLIT_PATTERN = re.compile(r"[,;|/]+")
TEXT_TOKEN_PATTERN = re.compile(r"[a-z0-9][a-z0-9\-\+\.'&:]*", re.I)


def _contains_cjk(value: str) -> bool:
    return bool(CJK_PATTERN.search(str(value or "")))


def _split_terms(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        items = value
    else:
        items = TOKEN_SPLIT_PATTERN.split(str(value))
    output: list[str] = []
    for item in items:
        text = str(item or "").strip()
        if text:
            output.append(text)
    return output


def _tokenize_text(value: str) -> set[str]:
    return {match.group(0).lower() for match in TEXT_TOKEN_PATTERN.finditer(str(value or ""))}


def _translate_term(value: Any) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    translated = TERM_TRANSLATIONS.get(text.lower(), text)
    return TERM_TRANSLATIONS.get(str(translated).lower(), translated)


def _clean_json(text: str) -> dict | None:
    candidate = str(text or "").strip()
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


def _normalize_price_range(value: Any) -> list[float]:
    if not isinstance(value, list):
        return [0, 20]
    numeric: list[float] = []
    for item in value[:2]:
        try:
            numeric.append(float(item))
        except (TypeError, ValueError):
            continue
    if len(numeric) != 2:
        return [0, 20]
    low, high = sorted(numeric)
    return [low, high]


def _dedupe_preserve_order(values: list[str]) -> list[str]:
    output: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value or "").strip()
        if not text:
            continue
        key = text.lower()
        if key in seen:
            continue
        output.append(text)
        seen.add(key)
    return output


def _extract_dataset_vocab(df: pd.DataFrame | None) -> dict[str, list[str]]:
    if df is None or df.empty:
        return {"genres": [], "tags": [], "reference_games": []}
    genres = sorted({str(item).strip() for items in df.get("genre_list", []) for item in items if str(item).strip()})
    tags = sorted({str(item).strip() for items in df.get("tag_list", []) for item in items if str(item).strip()})
    names = sorted({str(item).strip() for item in df.get("name", []) if str(item).strip()})
    return {"genres": genres, "tags": tags, "reference_games": names}


def _llm_translate_terms(terms: list[str]) -> dict[str, str]:
    unique_terms = _dedupe_preserve_order(
        [
            term
            for term in terms
            if _contains_cjk(term) and str(term or "").strip().lower() not in TERM_TRANSLATIONS
        ]
    )
    if not unique_terms:
        return {}
    prompt = (
        "A user edited a game market query in Chinese. Translate only the query terms to concise English. "
        "Return JSON object mapping each original string to a short English phrase. "
        "Do not include Chinese in values. Do not explain.\n"
        f"terms: {json.dumps(unique_terms, ensure_ascii=False)}"
    )
    llm = safe_call_llm(prompt, "You translate game query terms into English JSON only.")
    if not llm["success"]:
        return {}
    parsed = _clean_json(llm["content"])
    if not isinstance(parsed, dict):
        return {}
    output: dict[str, str] = {}
    for key, value in parsed.items():
        english = str(value or "").strip()
        if english and not _contains_cjk(english):
            output[str(key)] = english
    return output


def _choose_from_vocab(term: str, vocab: list[str], allow_fuzzy: bool = True) -> list[str]:
    if not term or not vocab:
        return []
    lower_map = {item.lower(): item for item in vocab}
    direct = lower_map.get(term.lower())
    if direct:
        return [direct]

    matches = [item for item in vocab if item.lower() in term.lower() or term.lower() in item.lower()]
    if matches:
        return _dedupe_preserve_order(matches)

    if allow_fuzzy:
        close = get_close_matches(term.lower(), list(lower_map.keys()), n=1, cutoff=0.92)
        if close:
            return [lower_map[close[0]]]
    return []


def _normalize_hard_field(
    values: Any,
    vocab: list[str],
    translated_terms: dict[str, str],
    notes: list[str],
    soft_keywords: list[str],
    field_label: str,
) -> list[str]:
    normalized: list[str] = []
    for raw in _split_terms(values):
        english = _translate_term(translated_terms.get(raw, _translate_term(raw)))
        aligned = _choose_from_vocab(english or "", vocab)
        if aligned:
            normalized.extend(aligned)
            continue
        if english and not _contains_cjk(english):
            soft_keywords.append(english)
            notes.append(f"{field_label} 中未命中词表的值已降级为 soft keywords: {english}")
        else:
            notes.append(f"{field_label} 中的中文值无法安全对齐，已忽略硬过滤: {raw}")
    return _dedupe_preserve_order(normalized)


def _normalize_soft_field(values: Any, translated_terms: dict[str, str], notes: list[str], field_label: str) -> list[str]:
    normalized: list[str] = []
    for raw in _split_terms(values):
        english = _translate_term(translated_terms.get(raw, _translate_term(raw)))
        if english and not _contains_cjk(english):
            normalized.append(english)
        elif raw and not _contains_cjk(raw):
            normalized.append(_translate_term(raw) or raw)
        elif raw:
            notes.append(f"{field_label} 中的中文值无法翻译，已忽略: {raw}")
    return _dedupe_preserve_order(normalized)


def _assert_query_intent_is_english(profile: dict) -> None:
    for field in QUERY_LIST_FIELDS:
        for value in profile.get(field, []) or []:
            if _contains_cjk(str(value)):
                raise ValueError(f"{field} still contains CJK text after normalization: {value}")


def normalize_idea_profile(profile: dict | None) -> dict:
    """Normalize an idea profile without dataset alignment."""
    profile = profile or {}
    notes: list[str] = []
    translated_terms = _llm_translate_terms(
        [term for field in QUERY_LIST_FIELDS if field in profile for term in _split_terms(profile.get(field))]
    )
    result = dict(DEFAULT_IDEA_PROFILE)
    result["target_genres"] = _normalize_soft_field(profile.get("target_genres"), translated_terms, notes, "target_genres") or ["Indie"]
    result["target_tags"] = _normalize_soft_field(profile.get("target_tags"), translated_terms, notes, "target_tags") or [
        "Puzzle",
        "Story Rich",
        "Atmospheric",
    ]
    result["art_style_keywords"] = _normalize_soft_field(profile.get("art_style_keywords"), translated_terms, notes, "art_style_keywords")
    result["gameplay_keywords"] = _normalize_soft_field(profile.get("gameplay_keywords"), translated_terms, notes, "gameplay_keywords")
    result["narrative_keywords"] = _normalize_soft_field(profile.get("narrative_keywords"), translated_terms, notes, "narrative_keywords")
    result["target_players"] = _normalize_soft_field(profile.get("target_players"), translated_terms, notes, "target_players")
    result["reference_games"] = _normalize_soft_field(profile.get("reference_games"), translated_terms, notes, "reference_games")
    result["soft_keywords"] = _normalize_soft_field(profile.get("soft_keywords"), translated_terms, notes, "soft_keywords")
    result["price_range"] = _normalize_price_range(profile.get("price_range"))
    result["llm_used"] = bool(profile.get("llm_used", False))
    result["normalization_notes"] = _dedupe_preserve_order(notes)
    _assert_query_intent_is_english(result)
    return result


def normalize_market_query_intent(
    profile: dict | None,
    df: pd.DataFrame | None = None,
) -> dict:
    """
    Normalize editor/LLM output into a dataset-aligned English-only query intent.

    Hard filters: target_genres, target_tags, reference_games
    Soft similarity terms: art_style_keywords, gameplay_keywords, narrative_keywords, target_players, soft_keywords
    """
    base = normalize_idea_profile(profile)
    vocab = _extract_dataset_vocab(df)
    notes = list(base.get("normalization_notes", []))
    soft_keywords = list(base.get("soft_keywords", []))
    translated_terms = _llm_translate_terms(
        [term for field in QUERY_LIST_FIELDS for term in _split_terms((profile or {}).get(field))]
    )

    result = dict(base)
    result["target_genres"] = _normalize_hard_field(
        base.get("target_genres", []),
        vocab["genres"] + vocab["tags"],
        translated_terms,
        notes,
        soft_keywords,
        "target_genres",
    ) or (["Indie"] if "Indie" in vocab["genres"] + vocab["tags"] else [])
    result["target_tags"] = _normalize_hard_field(
        base.get("target_tags", []),
        vocab["tags"],
        translated_terms,
        notes,
        soft_keywords,
        "target_tags",
    )
    result["reference_games"] = _normalize_hard_field(
        base.get("reference_games", []),
        vocab["reference_games"],
        translated_terms,
        notes,
        soft_keywords,
        "reference_games",
    )
    result["art_style_keywords"] = _normalize_soft_field((profile or {}).get("art_style_keywords"), translated_terms, notes, "art_style_keywords")
    result["gameplay_keywords"] = _normalize_soft_field((profile or {}).get("gameplay_keywords"), translated_terms, notes, "gameplay_keywords")
    result["narrative_keywords"] = _normalize_soft_field((profile or {}).get("narrative_keywords"), translated_terms, notes, "narrative_keywords")
    result["target_players"] = _normalize_soft_field((profile or {}).get("target_players"), translated_terms, notes, "target_players")
    result["soft_keywords"] = _dedupe_preserve_order(soft_keywords)
    result["normalization_notes"] = _dedupe_preserve_order(notes)
    _assert_query_intent_is_english(result)
    return result


def _rule_parse(idea_text: str) -> dict:
    text = idea_text.lower()
    genres = sorted({value for key, value in GENRE_KEYWORDS.items() if key in text})
    tags = sorted({value for key, value in TAG_KEYWORDS.items() if key in text})

    price_range = [0, 20]
    match = re.search(r"(\d+(?:\.\d+)?)\s*(?:元以内|以内|以下|rmb|¥)", text)
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
    normalized = normalize_idea_profile(profile)
    normalized["llm_used"] = False
    return normalized


def parse_idea(idea_text: str, prefer_llm: bool = True) -> dict:
    """Parse a raw game idea into an English-only editor/query profile."""
    if prefer_llm:
        prompt = (
            "The user may write the game idea in any language.\n"
            "Return JSON only with these keys: "
            "target_genres,target_tags,price_range,art_style_keywords,gameplay_keywords,"
            "narrative_keywords,target_players,reference_games.\n"
            "All query values must be English. Never output Chinese in target_genres, target_tags, "
            "art_style_keywords, gameplay_keywords, narrative_keywords, target_players, or reference_games.\n"
            "UI labels may be Chinese, but JSON field values must be English.\n"
            "Prefer Steam-like English labels when possible.\n"
            "Example:\n"
            '{'
            '"target_genres":["Co-op Horror","Investigation Sim"],'
            '"target_tags":["Co-op","Horror","Investigation","Mystery"],'
            '"art_style_keywords":["cold palette","low saturation","office interior"],'
            '"gameplay_keywords":["phone coordination","surveillance monitoring","case file analysis"],'
            '"narrative_keywords":["anomaly investigation","bureaucratic horror","trust breakdown"],'
            '"target_players":["co-op horror players"],'
            '"reference_games":["Phasmophobia","SCP: Containment Breach"],'
            '"price_range":[0,20]'
            '}\n'
            f"Idea: {idea_text}"
        )
        llm = safe_call_llm(prompt, "You are a game idea analysis assistant. Output valid JSON only.")
        if llm["success"]:
            parsed = _clean_json(llm["content"])
            if parsed:
                normalized = normalize_idea_profile({**parsed, "llm_used": True})
                normalized["llm_used"] = True
                return normalized
    return _rule_parse(idea_text)
