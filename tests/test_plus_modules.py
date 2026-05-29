import pandas as pd

import backend.services.idea_parser as idea_parser
from backend.services.competitor_radar import find_similar_games
from backend.services import analyzer
from backend.services.data_cleaner import clean_steam_data
from backend.services.idea_parser import normalize_idea_profile, parse_idea
from backend.services.idea_advisor import generate_idea_advisor_answer
from backend.services.llm_client import get_llm_status, safe_call_llm
from backend.services.opportunity_score import calculate_opportunity_score
from backend.services.report_generator import generate_differentiation_cards, generate_project_brief


def cleaned_df():
    raw = pd.DataFrame(
        {
            "name": ["Puzzle Story", "Action Blast", "Atmospheric Puzzle"],
            "release_date": ["2021-01-01", "2022-01-01", "2023-01-01"],
            "price": [9.99, 29.99, 19.99],
            "genres": ["Indie, Puzzle", "Action", "Indie, Adventure"],
            "tags": ["Story Rich, Puzzle", "Shooter", "Atmospheric, Puzzle"],
            "positive_reviews": [900, 300, 800],
            "negative_reviews": [100, 200, 200],
        }
    )
    cleaned, _ = clean_steam_data(raw)
    return cleaned


def test_idea_parser_fallback():
    profile = parse_idea("I want to make an indie puzzle story game under 20.", prefer_llm=False)

    assert "Indie" in profile["target_genres"]
    assert profile["price_range"] == [0, 20]
    assert profile["llm_used"] is False


def test_idea_profile_normalizes_chinese_terms_to_steam_english():
    profile = normalize_idea_profile(
        {
            "target_genres": ["独立", "解谜"],
            "target_tags": ["剧情向", "治愈", "氛围感", "像素"],
            "price_range": [0, 20],
            "art_style_keywords": ["像素"],
            "gameplay_keywords": ["解谜"],
            "narrative_keywords": ["剧情"],
            "target_players": ["独立游戏玩家"],
            "reference_games": [],
        }
    )

    assert profile["target_genres"] == ["Indie", "Puzzle"]
    assert "Story Rich" in profile["target_tags"]
    assert "Relaxing" in profile["target_tags"]
    assert "Atmospheric" in profile["target_tags"]
    assert "Pixel Graphics" in profile["target_tags"]


def test_idea_parser_accepts_fenced_llm_json(monkeypatch):
    def fake_call_llm(prompt, system_prompt=None):
        return {
            "success": True,
            "content": '```json\n{"target_genres":["独立"],"target_tags":["剧情向"],"price_range":[0,15]}\n```',
        }

    monkeypatch.setattr(idea_parser, "safe_call_llm", fake_call_llm)

    profile = parse_idea("一款剧情向独立游戏", prefer_llm=True)

    assert profile["target_genres"] == ["Indie"]
    assert profile["target_tags"] == ["Story Rich"]
    assert profile["price_range"] == [0, 15]
    assert profile["llm_used"] is True


def test_find_similar_games_returns_reasonable_scores():
    df = cleaned_df()
    profile = {
        "target_genres": ["Indie", "Puzzle"],
        "target_tags": ["Puzzle", "Story Rich"],
        "price_range": [0, 20],
        "art_style_keywords": [],
        "gameplay_keywords": ["Puzzle"],
        "narrative_keywords": ["Story Rich"],
    }
    results = find_similar_games(df, profile, top_n=2, only_indie=True)

    assert results
    assert 0 <= results[0]["similarity_score"] <= 100
    assert results[0]["match_reason"]


def test_idea_lab_candidate_pool_can_exceed_displayed_top_n():
    rows = []
    for index in range(15):
        rows.append(
            {
                "name": f"Puzzle Game {index}",
                "release_date": "2022-01-01",
                "price": 9.99,
                "genres": "Indie, Adventure",
                "tags": "Puzzle, Story Rich",
                "positive_reviews": 100 + index,
                "negative_reviews": 10,
            }
        )
    cleaned, _ = clean_steam_data(pd.DataFrame(rows))
    profile = {"target_genres": ["Indie", "Puzzle"], "target_tags": ["Story Rich"], "price_range": [0, 20]}
    segment = analyzer.filter_market(
        cleaned,
        only_indie=True,
        price_range=profile["price_range"],
        genres=profile["target_genres"],
        tags=profile["target_tags"],
    )
    competitors = find_similar_games(cleaned, profile, top_n=10, only_indie=True)

    assert len(segment) == 15
    assert len(competitors) == 10


def test_opportunity_score_returns_total_and_dimensions():
    df = cleaned_df()
    competitors = find_similar_games(df, {"target_genres": ["Indie"], "target_tags": ["Puzzle"], "price_range": [0, 20]})
    score = calculate_opportunity_score(df[df["is_indie"] == True], df, competitors)

    assert 0 <= score["total_score"] <= 100
    assert len(score["dimensions"]) == 5
    assert "真实商业决策" in score["conclusion"]


def test_report_generator_template_without_llm():
    profile = {"target_genres": ["Indie"], "target_tags": ["Puzzle"], "price_range": [0, 20]}
    score = calculate_opportunity_score(cleaned_df(), cleaned_df(), [])
    cards = generate_differentiation_cards(profile, [], score)
    brief, llm_used = generate_project_brief(
        {"idea_profile": profile, "opportunity_score": score, "competitors": [], "differentiation_cards": cards},
        use_llm=False,
    )

    assert llm_used is False
    assert "目标方向" in brief
    assert "数据使用边界" in brief


def test_no_api_key_does_not_crash(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)

    status = get_llm_status()
    result = safe_call_llm("hello")

    assert status["enabled"] is False
    assert result["llm_used"] is False
    assert result["success"] is False


def test_idea_advisor_uses_llm_and_compresses_payload(monkeypatch):
    captured = {}

    def fake_call_llm(prompt, system_prompt=None):
        captured["prompt"] = prompt
        captured["system_prompt"] = system_prompt
        return {"success": True, "llm_used": True, "content": "先做差异化验证。\n\n- 建议一\n\n下一步可以做什么：\n- 做一个 Demo"}

    monkeypatch.setattr("backend.services.idea_advisor.safe_call_llm", fake_call_llm)

    result = generate_idea_advisor_answer(
        type(
            "Req",
            (),
            {
                "question": "我应该如何做出差异化？",
                "idea_text": "一款治愈叙事解谜游戏",
                "analysis_result": {
                    "idea_profile": {"target_tags": ["Puzzle", "Story Rich"]},
                    "opportunity_score": {"total_score": 72},
                    "competitors": [
                        {"name": f"Game {index}", "similarity_score": 80 - index, "price": 10 + index, "positive_rate": 0.9}
                        for index in range(12)
                    ],
                    "differentiation_cards": [{"title": "玩法机制差异化", "content": "先验证 10 分钟内能感知的独特点。"}],
                    "brief": "这是简报。",
                    "charts": {"competitor_scores": [{"name": "Too much data"}]},
                    "support_data": {"competitor_evidence": {"summary": {"candidate_pool_size": 99}}},
                    "candidate_pool_size": 99,
                    "returned_competitor_count": 10,
                },
                "history": [{"role": "user", "content": "先前问题"}],
            },
        )()
    )

    assert result["llm_used"] is True
    assert result["fallback_used"] is False
    assert "Game 8" not in captured["prompt"]
    assert "Too much data" not in captured["prompt"]
    assert "用户当前追问" in captured["prompt"]
    assert "游戏立项顾问助手" in captured["system_prompt"]


def test_idea_advisor_fallback_returns_cards(monkeypatch):
    def fake_call_llm(prompt, system_prompt=None):
        return {"success": False, "llm_used": False, "content": "", "message": "mock failure"}

    monkeypatch.setattr("backend.services.idea_advisor.safe_call_llm", fake_call_llm)

    result = generate_idea_advisor_answer(
        type(
            "Req",
            (),
            {
                "question": "风险是什么？",
                "idea_text": "一款叙事游戏",
                "analysis_result": {
                    "opportunity_score": {"total_score": 61},
                    "differentiation_cards": [{"title": "竞品避让策略", "content": "避开最拥挤标签。"}],
                },
                "history": [],
            },
        )()
    )

    assert result["llm_used"] is False
    assert result["fallback_used"] is True
    assert "当前 LLM 未启用" in result["answer"]
    assert "竞品避让策略" in result["answer"]
