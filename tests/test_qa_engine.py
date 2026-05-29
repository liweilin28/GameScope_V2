import pandas as pd

from backend.services.data_cleaner import clean_steam_data
from backend.services.qa_conversation import clear_conversations
from backend.services.qa_engine import answer_question, chat, identify_intent


def cleaned_df():
    raw = pd.DataFrame(
        {
            "name": ["A", "B", "C", "D", "E", "F"],
            "release_date": ["2019-01-01", "2021-01-01", "2022-01-01", "2023-01-01", "2024-03-01", "2025-02-01"],
            "price": [0, 9.99, 19.99, 29.99, 4.99, 14.99],
            "genres": ["Indie, Puzzle", "Action", "Indie, Puzzle", "RPG, Adventure", "Strategy, Indie", "Simulation, Indie"],
            "tags": ["Story Rich, Puzzle", "Shooter", "Atmospheric, Puzzle", "Adventure, RPG", "Strategy, Indie", "Simulation, Indie"],
            "positive_reviews": [90, 80, 95, 900, 300, 500],
            "negative_reviews": [10, 20, 5, 100, 50, 100],
        }
    )
    cleaned, _ = clean_steam_data(raw)
    return cleaned


def test_qa_intent_recognition():
    import os

    os.environ.pop("DEEPSEEK_API_KEY", None)
    assert identify_intent("近几年 Steam 游戏发行数量有什么变化？") == "release_trend"
    assert identify_intent("Indie 游戏价格主要集中在哪？") == "price_distribution"
    assert identify_intent("哪些类型游戏数量最多？") == "genre_distribution"


def test_chat_clear_question_returns_final_answer():
    import os

    os.environ.pop("DEEPSEEK_API_KEY", None)
    clear_conversations()
    result = chat(cleaned_df(), "Indie 游戏价格主要集中在哪？")

    assert result["response_type"] == "final_answer"
    assert result["understood_intent"]["analysis_type"] == "price_distribution"
    assert result["answer"]["chart"]["echarts_option"]


def test_chat_generic_performance_question_returns_default_ranking():
    import os

    os.environ.pop("DEEPSEEK_API_KEY", None)
    clear_conversations()
    result = chat(cleaned_df(), "哪些游戏表现好？")

    assert result["response_type"] == "final_answer"
    assert result["understood_intent"]["analysis_type"] == "ranking"
    assert result["understood_intent"]["target_metric"] == "total_reviews"


def test_chat_follow_up_inherits_intent_and_updates_year_range():
    import os

    os.environ.pop("DEEPSEEK_API_KEY", None)
    clear_conversations()
    first = chat(cleaned_df(), "Indie 游戏价格主要集中在哪？")
    second = chat(cleaned_df(), "只看 2020 年以后呢？", conversation_id=first["conversation_id"])

    assert second["response_type"] == "final_answer"
    assert second["understood_intent"]["analysis_type"] == "price_distribution"
    assert second["understood_intent"]["filters"]["year_range"][0] == 2020


def test_answer_question_legacy_interface_still_works(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    result = answer_question(cleaned_df(), "Indie 游戏价格主要集中在哪？")

    assert result["intent"] == "price_distribution"
    assert result["table"]


def test_empty_segment_returns_friendly_message():
    import os

    os.environ.pop("DEEPSEEK_API_KEY", None)
    clear_conversations()
    result = chat(cleaned_df(), "tag:Roguelike")

    assert result["response_type"] == "final_answer"
    assert "没有得到可分析样本" in result["assistant_message"] or "没有可分析样本" in result["answer"]["summary"]


def test_new_question_does_not_inherit_empty_segment_filters():
    import os

    os.environ.pop("DEEPSEEK_API_KEY", None)
    clear_conversations()
    first = chat(cleaned_df(), "只看 Strategy 标签的价格分布")
    second = chat(cleaned_df(), "哪些游戏表现好？", conversation_id=first["conversation_id"])

    assert first["response_type"] == "final_answer"
    assert second["response_type"] == "final_answer"
    assert "没有得到可分析样本" not in second["assistant_message"]
    assert second["understood_intent"]["analysis_type"] == "ranking"
    assert second["understood_intent"]["filters"]["tags"] == []


def test_ambiguous_opportunity_question_uses_default_metric_notice():
    import os

    os.environ.pop("DEEPSEEK_API_KEY", None)
    clear_conversations()
    result = chat(
        cleaned_df(),
        "这个方向有没有机会？",
        idea_context={
            "query_intent": {
                "target_genres": ["Indie"],
                "target_tags": ["Puzzle", "Story Rich"],
                "price_range": [0, 20],
            }
        },
    )

    assert result["response_type"] == "final_answer"
    assert result["analysis_plan"]["analysis_type"] == "opportunity_analysis"
    assert "暂定为" in result["assistant_message"]


def test_competitor_lookup_returns_table_results():
    import os

    os.environ.pop("DEEPSEEK_API_KEY", None)
    clear_conversations()
    result = chat(
        cleaned_df(),
        "帮我找 Co-op Horror 的竞品",
        idea_context={"query_intent": {"target_genres": ["Indie"], "target_tags": ["Puzzle"], "price_range": [0, 20]}},
    )

    assert result["response_type"] == "final_answer"
    assert result["analysis_plan"]["analysis_type"] == "competitor_lookup"
    assert result["answer"]["table"]["rows"]


def test_price_band_question_returns_distribution_and_sample_size():
    import os

    os.environ.pop("DEEPSEEK_API_KEY", None)
    clear_conversations()
    result = chat(
        cleaned_df(),
        "适合定价多少？",
        idea_context={"query_intent": {"target_genres": ["Indie"], "target_tags": ["Puzzle"], "price_range": [0, 20]}},
    )

    assert result["response_type"] == "final_answer"
    assert result["analysis_plan"]["analysis_type"] == "price_band_analysis"
    assert result["answer"]["evidence_payload"]["sample_size"] > 0
    assert result["answer"]["chart"] or result["answer"]["charts"]


def test_no_data_result_does_not_claim_displays_data():
    import os

    os.environ.pop("DEEPSEEK_API_KEY", None)
    clear_conversations()
    result = chat(cleaned_df(), "只看 Strategy 标签的价格分布")

    assert "数据显示" not in result["assistant_message"]


def test_idea_context_is_used_as_default_filters():
    import os

    os.environ.pop("DEEPSEEK_API_KEY", None)
    clear_conversations()
    result = chat(
        cleaned_df(),
        "适合定价多少？",
        idea_context={"query_intent": {"target_genres": ["Indie"], "target_tags": ["Puzzle"], "price_range": [0, 20]}},
    )

    assert result["understood_intent"]["filters"]["genres"] == ["Indie"]
    assert result["understood_intent"]["filters"]["tags"] == ["Puzzle"]


def test_out_of_scope_question_reports_limitation():
    import os

    os.environ.pop("DEEPSEEK_API_KEY", None)
    clear_conversations()
    result = chat(cleaned_df(), "这个方向未来会不会是爆款，真实收入大概多少？")

    assert result["response_type"] == "final_answer"
    assert "当前数据不足以回答" in result["assistant_message"]


def test_follow_up_lists_top_10_games_instead_of_repeating_report():
    import os

    os.environ.pop("DEEPSEEK_API_KEY", None)
    clear_conversations()
    first = chat(cleaned_df(), "帮我查找一下 2020-2025 年哪类游戏的评论数量最多")
    second = chat(cleaned_df(), "列出前 10 个代表游戏", conversation_id=first["conversation_id"])

    assert first["response_type"] == "final_answer"
    assert second["response_type"] == "final_answer"
    assert second["analysis_plan"]["is_follow_up"] is True
    assert second["analysis_plan"]["analysis_type"] == "representative_games"
    assert second["analysis_plan"]["filters"]["year_range"] == [2020, 2025]
    assert second["answer"]["table"]["rows"]
    assert len(second["answer"]["table"]["rows"]) <= 10
    assert "排序" in second["assistant_message"]
    assert second["assistant_message"] != first["assistant_message"]


def test_follow_up_top_5_respects_limit():
    import os

    os.environ.pop("DEEPSEEK_API_KEY", None)
    clear_conversations()
    first = chat(cleaned_df(), "帮我查找一下 2020-2025 年哪类游戏的评论数量最多")
    second = chat(cleaned_df(), "只看评论数最高的 5 个", conversation_id=first["conversation_id"])

    assert second["response_type"] == "final_answer"
    assert second["analysis_plan"]["analysis_type"] == "representative_games"
    assert second["analysis_plan"]["limit"] == 5
    assert len(second["answer"]["table"]["rows"]) == 5


def test_follow_up_can_change_sort_order_within_previous_scope():
    import os

    os.environ.pop("DEEPSEEK_API_KEY", None)
    clear_conversations()
    first = chat(cleaned_df(), "帮我查找一下 2020-2025 年哪类游戏的评论数量最多")
    second = chat(cleaned_df(), "按价格从低到高排序", conversation_id=first["conversation_id"])

    rows = second["answer"]["table"]["rows"]
    prices = [row["price"] for row in rows if row.get("price") is not None]
    assert second["response_type"] == "final_answer"
    assert second["analysis_plan"]["analysis_type"] == "representative_games"
    assert second["analysis_plan"]["filters"]["year_range"] == [2020, 2025]
    assert prices == sorted(prices)


def test_new_question_does_not_wrongly_inherit_previous_follow_up_scope():
    import os

    os.environ.pop("DEEPSEEK_API_KEY", None)
    clear_conversations()
    first = chat(cleaned_df(), "帮我查找一下 2020-2025 年哪类游戏的评论数量最多")
    second = chat(cleaned_df(), "Indie 游戏价格主要集中在哪？", conversation_id=first["conversation_id"])

    assert second["response_type"] == "final_answer"
    assert second["understood_intent"]["analysis_type"] == "price_distribution"
    assert second["understood_intent"]["filters"]["year_range"] is None


def test_direct_follow_up_without_context_requests_scope():
    import os

    os.environ.pop("DEEPSEEK_API_KEY", None)
    clear_conversations()
    result = chat(cleaned_df(), "列出前 10 个代表游戏")

    assert result["response_type"] == "clarification"
    assert "请先提供要分析的类型、标签或关键词" in result["assistant_message"]
