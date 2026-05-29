import pandas as pd

from backend.services.data_cleaner import clean_steam_data
from backend.services.qa_conversation import clear_conversations
from backend.services.qa_engine import answer_question, chat, identify_intent
import backend.services.qa_response_builder as qa_response_builder


def cleaned_df():
    raw = pd.DataFrame(
        {
            "name": ["A", "B", "C", "D"],
            "release_date": ["2019-01-01", "2021-01-01", "2022-01-01", "2023-01-01"],
            "price": [0, 9.99, 19.99, 29.99],
            "genres": ["Indie, Puzzle", "Action", "Indie, Puzzle", "RPG, Adventure"],
            "tags": ["Story Rich, Puzzle", "Shooter", "Atmospheric, Puzzle", "Adventure, RPG"],
            "positive_reviews": [90, 80, 95, 900],
            "negative_reviews": [10, 20, 5, 100],
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
    result = chat(cleaned_df(), "只看 Strategy 标签的价格分布")

    assert result["response_type"] == "final_answer"
    assert "没有足够数据" in result["assistant_message"] or "没有足够数据" in result["answer"]["summary"]


def test_new_question_does_not_inherit_empty_segment_filters():
    import os
    os.environ.pop("DEEPSEEK_API_KEY", None)
    clear_conversations()
    first = chat(cleaned_df(), "只看 Strategy 标签的价格分布")
    second = chat(cleaned_df(), "哪些游戏表现好？", conversation_id=first["conversation_id"])

    assert first["response_type"] == "final_answer"
    assert second["response_type"] == "final_answer"
    assert "没有足够数据" not in second["assistant_message"]
    assert second["understood_intent"]["analysis_type"] == "ranking"
    assert second["understood_intent"]["filters"]["tags"] == []


def test_chat_why_follow_up_returns_explanation_without_chart_or_table(monkeypatch):
    def fake_call_llm(prompt, system_prompt=None):
        return {
            "success": True,
            "llm_used": True,
            "content": "核心原因是当前样本价格集中在低门槛区间。\n- 数据显示该区间数量更高，因此结果会向它倾斜。",
        }

    monkeypatch.setattr(qa_response_builder, "safe_call_llm", fake_call_llm)
    clear_conversations()
    first = chat(cleaned_df(), "Indie 游戏价格主要集中在哪？")
    second = chat(cleaned_df(), "为什么会这样？", conversation_id=first["conversation_id"])

    assert second["response_type"] == "final_answer"
    assert second["understood_intent"]["answer_mode"] == "explanation"
    assert second["answer"]["display_mode"] == "explanation"
    assert second["answer"]["llm_used"] is True
    assert second["answer"]["chart"] is None
    assert second["answer"]["table"]["rows"] == []
    assert second["answer"]["support_data"] is None
