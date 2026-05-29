"""
来源：学生 + AI
作用：根据创意画像寻找相似 Steam 竞品，并给出可解释相似原因。
"""

from __future__ import annotations

import pandas as pd

from backend.services.utils import dataframe_to_records


def _norm_set(values) -> set[str]:
    return {str(item).lower() for item in values or [] if str(item).strip()}


def _tokenize_text(value: str) -> set[str]:
    tokens = []
    for raw in str(value or "").replace("/", " ").replace("-", " ").split():
        token = raw.strip(" ,.;:()[]{}\"'").lower()
        if token:
            tokens.append(token)
    return set(tokens)


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _price_similarity(price, price_range) -> float:
    if pd.isna(price) or not price_range or len(price_range) != 2:
        return 0.0
    low, high = float(price_range[0]), float(price_range[1])
    if low <= price <= high:
        return 1.0
    distance = min(abs(price - low), abs(price - high))
    return max(0.0, 1.0 - distance / max(high - low, 1.0))


def find_similar_games(df: pd.DataFrame, idea_profile: dict, top_n: int = 10, only_indie: bool = True) -> list[dict]:
    """按类型、标签、价格和关键词相似度寻找竞品，并输出匹配原因。"""
    if df is None or df.empty:
        return []

    data = df.copy()
    if only_indie and "is_indie" in data:
        data = data[data["is_indie"] == True]  # noqa: E712
    if data.empty:
        return []

    target_genres = _norm_set(idea_profile.get("target_genres"))
    target_tags = _norm_set(idea_profile.get("target_tags"))
    keywords = _norm_set(
        idea_profile.get("art_style_keywords", [])
        + idea_profile.get("gameplay_keywords", [])
        + idea_profile.get("narrative_keywords", [])
        + idea_profile.get("soft_keywords", [])
    )
    for title in idea_profile.get("reference_games", []) or []:
        keywords |= _tokenize_text(title)
    price_range = idea_profile.get("price_range", [0, 20])

    rows = []
    for _, row in data.iterrows():
        genres = _norm_set(row.get("genre_list", []))
        tags = _norm_set(row.get("tag_list", []))
        name = str(row.get("name", "")).lower()
        text_pool = genres | tags | {name} | _tokenize_text(name)
        genre_sim = _jaccard(target_genres, genres)
        tag_sim = _jaccard(target_tags, tags)
        price_sim = _price_similarity(row.get("price"), price_range)
        keyword_sim = _jaccard(keywords, text_pool)
        score = (genre_sim * 0.35 + tag_sim * 0.35 + price_sim * 0.2 + keyword_sim * 0.1) * 100

        reasons = []
        common_genres = target_genres & genres
        common_tags = target_tags & tags
        common_keywords = keywords & text_pool
        if common_genres:
            reasons.append("共同类型：" + ", ".join(sorted(common_genres)))
        if common_tags:
            reasons.append("共同标签：" + ", ".join(sorted(common_tags)))
        if price_sim >= 0.8:
            reasons.append("价格接近")
        if common_keywords:
            reasons.append("关键词接近：" + ", ".join(sorted(common_keywords)))
        if not reasons:
            reasons.append("综合特征有一定相似度")

        rows.append(
            {
                "name": row.get("name"),
                "genres": row.get("genres"),
                "tags": row.get("tags"),
                "price": None if pd.isna(row.get("price")) else float(row.get("price")),
                "positive_rate": None if pd.isna(row.get("positive_rate")) else float(row.get("positive_rate")),
                "total_reviews": int(row.get("total_reviews", 0)),
                "release_year": None if pd.isna(row.get("release_year")) else int(row.get("release_year")),
                "similarity_score": round(score, 2),
                "match_reason": "；".join(reasons),
            }
        )

    result = pd.DataFrame(rows).sort_values(["similarity_score", "total_reviews"], ascending=[False, False]).head(top_n)
    return dataframe_to_records(result, limit=top_n)
