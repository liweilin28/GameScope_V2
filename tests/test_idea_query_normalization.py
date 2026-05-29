import pandas as pd
from fastapi.testclient import TestClient

import backend.services.idea_parser as idea_parser
from backend.main import app
from backend.services.data_cleaner import clean_steam_data
from backend.services.data_loader import set_current_data
from backend.services.idea_parser import normalize_market_query_intent, parse_idea


client = TestClient(app)


def sample_market_df():
    raw = pd.DataFrame(
        {
            "name": ["Phasmophobia", "Archive Zero", "Puzzle Story"],
            "release_date": ["2020-09-18", "2023-05-01", "2022-01-01"],
            "price": [13.99, 11.99, 9.99],
            "genres": ["Indie, Action", "Indie, Adventure", "Indie, Puzzle"],
            "tags": [
                "Horror, Co-op, Mystery, Investigation",
                "Investigation, Atmospheric, Mystery",
                "Puzzle, Story Rich, Atmospheric",
            ],
            "positive_reviews": [5000, 600, 900],
            "negative_reviews": [400, 80, 100],
        }
    )
    cleaned, _ = clean_steam_data(raw)
    return cleaned


def query_fields(profile: dict) -> list[str]:
    values = []
    for key in [
        "target_genres",
        "target_tags",
        "art_style_keywords",
        "gameplay_keywords",
        "narrative_keywords",
        "reference_games",
        "soft_keywords",
    ]:
        values.extend(profile.get(key, []) or [])
    return values


def has_cjk(values: list[str]) -> bool:
    return any(idea_parser.CJK_PATTERN.search(str(value or "")) for value in values)


def test_parse_idea_prompt_requires_english_query_fields(monkeypatch):
    captured = {}

    def fake_call_llm(prompt, system_prompt=None):
        captured["prompt"] = prompt
        return {
            "success": True,
            "llm_used": True,
            "content": """
            {
              "target_genres": ["Co-op Horror"],
              "target_tags": ["Co-op", "Horror", "Investigation", "Mystery"],
              "price_range": [0, 20],
              "art_style_keywords": ["cold palette"],
              "gameplay_keywords": ["phone coordination"],
              "narrative_keywords": ["anomaly investigation"],
              "target_players": ["co-op horror players"],
              "reference_games": ["Phasmophobia"]
            }
            """,
        }

    monkeypatch.setattr(idea_parser, "safe_call_llm", fake_call_llm)
    profile = parse_idea("做一个双人恐怖调查游戏", prefer_llm=True)

    assert "All query values must be English" in captured["prompt"]
    assert "Never output Chinese" in captured["prompt"]
    assert has_cjk(query_fields(profile)) is False


def test_normalize_market_query_intent_removes_cjk_from_hard_query_fields():
    df = sample_market_df()
    profile = normalize_market_query_intent(
        {
            "target_genres": ["独立", "不存在的中文类型"],
            "target_tags": ["剧情向", "神秘"],
            "price_range": [0, 20],
            "art_style_keywords": ["冷色调"],
            "gameplay_keywords": ["档案分析"],
            "narrative_keywords": ["官僚恐怖"],
            "reference_games": ["中文竞品名"],
        },
        df=df,
    )

    assert has_cjk(query_fields(profile)) is False
    assert "Indie" in profile["target_genres"]
    assert "Story Rich" in profile["target_tags"]
    assert "cold palette" in profile["art_style_keywords"]
    assert "case file analysis" in profile["gameplay_keywords"]
    assert "bureaucratic horror" in profile["narrative_keywords"]
    assert profile["normalization_notes"]
    assert profile["soft_keywords"] or not profile["reference_games"]


def test_market_scan_normalizes_manual_chinese_editor_values_before_query():
    df = sample_market_df()
    set_current_data(df, "test.csv", raw_df=df, cleaning_report={})

    response = client.post(
        "/api/idea/analyze",
        json={
            "idea_text": "中文创意",
            "idea_profile": {
                "target_genres": ["独立", "中文硬过滤"],
                "target_tags": ["中文标签"],
                "price_range": [0, 20],
                "art_style_keywords": ["冷色调"],
                "gameplay_keywords": ["档案分析"],
                "narrative_keywords": [],
                "reference_games": [],
            },
            "top_n": 5,
            "only_indie": True,
        },
    )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert has_cjk(query_fields(payload["idea_profile"])) is False
    assert payload["candidate_pool_size"] > 0
    assert payload["returned_competitor_count"] > 0
    assert payload["normalization_notes"]


def test_market_scan_falls_back_when_hard_match_pool_is_zero():
    df = sample_market_df()
    set_current_data(df, "test.csv", raw_df=df, cleaning_report={})

    response = client.post(
        "/api/idea/analyze",
        json={
            "idea_text": "strict filters should miss and then relax",
            "idea_profile": {
                "target_genres": ["Puzzle"],
                "target_tags": ["Co-op"],
                "price_range": [0, 20],
                "art_style_keywords": ["冷色调"],
                "gameplay_keywords": ["调查"],
                "narrative_keywords": ["异象调查"],
                "reference_games": [],
            },
            "top_n": 5,
            "only_indie": True,
        },
    )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["candidate_pool_size"] > 0
    assert payload["competitors"]
    assert any("fallback" in note.lower() for note in payload["normalization_notes"])


def test_english_input_path_still_works():
    df = sample_market_df()
    profile = normalize_market_query_intent(
        {
            "target_genres": ["Indie"],
            "target_tags": ["Puzzle", "Story Rich"],
            "price_range": [0, 20],
            "art_style_keywords": ["cold palette"],
            "gameplay_keywords": ["case file analysis"],
            "narrative_keywords": ["anomaly investigation"],
            "reference_games": ["Phasmophobia"],
        },
        df=df,
    )

    assert profile["target_genres"] == ["Indie"]
    assert profile["target_tags"] == ["Puzzle", "Story Rich"]
    assert profile["reference_games"] == ["Phasmophobia"]
    assert has_cjk(query_fields(profile)) is False
