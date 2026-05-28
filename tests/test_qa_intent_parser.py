from backend.services.qa_conversation import DEFAULT_INTENT
from backend.services.qa_intent_parser import parse_with_rules


def test_rule_parser_clear_price_question():
    import os
    os.environ.pop("DEEPSEEK_API_KEY", None)
    result = parse_with_rules("Indie 游戏价格主要集中在哪？", [], DEFAULT_INTENT)

    assert result["need_clarification"] is False
    assert result["intent"]["analysis_type"] == "price_distribution"
    assert result["intent"]["filters"]["market_scope"] == "indie"


def test_rule_parser_generic_performance_question_uses_reviews_ranking():
    result = parse_with_rules("哪些游戏表现比较好？", [], DEFAULT_INTENT)

    assert result["need_clarification"] is False
    assert result["intent"]["analysis_type"] == "ranking"
    assert result["intent"]["target_metric"] == "total_reviews"


def test_rule_parser_follow_up_year_range():
    previous = {
        "analysis_type": "price_distribution",
        "target_metric": "price",
        "filters": {"market_scope": "indie", "genres": ["Indie"]},
        "group_by": "price_level",
        "chart_type": "bar",
    }
    result = parse_with_rules("只看 2020 年以后呢？", [], previous)

    assert result["need_clarification"] is False
    assert result["intent"]["analysis_type"] == "price_distribution"
    assert result["intent"]["filters"]["year_range"][0] == 2020


def test_rule_parser_object_clarification_keeps_requested_analysis_type():
    result = parse_with_rules("我想看某个类型游戏的发行趋势", [], DEFAULT_INTENT)

    assert result["need_clarification"] is True
    assert result["intent"]["analysis_type"] == "release_trend"
    assert result["clarification"]["options"][0]["field"] == "genre"


def test_rule_parser_field_answer_inherits_previous_intent():
    previous = {
        "analysis_type": "release_trend",
        "target_metric": "release_count",
        "filters": {},
        "group_by": "year",
        "chart_type": "line",
    }
    result = parse_with_rules("tag:Puzzle", [], previous)

    assert result["need_clarification"] is False
    assert result["intent"]["analysis_type"] == "release_trend"
    assert result["intent"]["filters"]["tags"] == ["Puzzle"]


def test_rule_parser_tag_context_does_not_treat_puzzle_as_genre():
    result = parse_with_rules("Puzzle 标签的价格分布", [], DEFAULT_INTENT)

    assert result["need_clarification"] is False
    assert result["intent"]["analysis_type"] == "price_distribution"
    assert result["intent"]["filters"]["genres"] == []
    assert result["intent"]["filters"]["tags"] == ["Puzzle"]


def test_rule_parser_hot_tags_uses_tag_frequency():
    result = parse_with_rules("有哪些热门标签？", [], DEFAULT_INTENT)

    assert result["need_clarification"] is False
    assert result["intent"]["analysis_type"] == "tag_frequency"
    assert result["intent"]["group_by"] == "tag"


def test_rule_parser_price_reception_comparison_is_not_price_distribution():
    result = parse_with_rules("低价格游戏和高价格游戏的口碑有差异吗？", [], DEFAULT_INTENT)

    assert result["need_clarification"] is False
    assert result["intent"]["analysis_type"] == "review_comparison"
    assert result["intent"]["target_metric"] == "positive_rate"
    assert result["intent"]["group_by"] == "price_level"


def test_rule_parser_free_paid_review_count_comparison():
    result = parse_with_rules("免费游戏和付费游戏的评论数量差异大吗？", [], DEFAULT_INTENT)

    assert result["need_clarification"] is False
    assert result["intent"]["analysis_type"] == "review_comparison"
    assert result["intent"]["target_metric"] == "total_reviews"
    assert result["intent"]["group_by"] == "price_type"


def test_rule_parser_price_review_relationship_uses_correlation():
    result = parse_with_rules("价格和评论数有关系吗？", [], DEFAULT_INTENT)

    assert result["need_clarification"] is False
    assert result["intent"]["analysis_type"] == "correlation"
    assert result["intent"]["target_metric"] == "total_reviews"
    assert result["intent"]["chart_type"] == "scatter"
