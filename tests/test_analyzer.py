import pandas as pd

from backend.services.analyzer import (
    analyze_genre_distribution,
    build_market_scatter,
    filter_market,
    get_basic_metrics,
)
from backend.services.data_cleaner import clean_steam_data


def sample_cleaned_df():
    raw = pd.DataFrame(
        {
            "name": ["A", "B", "C"],
            "release_date": ["2021-01-01", "2022-01-01", "2022-06-01"],
            "price": [0, 9.99, 19.99],
            "genres": ["Indie, Puzzle", "Action", "Indie|Adventure"],
            "tags": ["Story Rich", "Shooter", "Atmospheric; Puzzle"],
            "positive_reviews": [90, 300, 800],
            "negative_reviews": [10, 100, 200],
        }
    )
    cleaned, report = clean_steam_data(raw)
    assert report["errors"] == []
    return cleaned


def test_get_basic_metrics_does_not_crash():
    metrics = get_basic_metrics(sample_cleaned_df())

    assert metrics["game_count"] == 3
    assert metrics["avg_price"] is not None
    assert metrics["avg_positive_rate"] is not None


def test_analyze_genre_distribution_does_not_crash():
    distribution = analyze_genre_distribution(sample_cleaned_df())

    assert distribution
    assert any(item["genre"] == "Indie" for item in distribution)


def test_filter_market_does_not_crash():
    filtered = filter_market(
        sample_cleaned_df(),
        only_indie=True,
        year_range=[2021, 2022],
        price_range=[0, 20],
        genres=["Puzzle"],
        tags=None,
        min_reviews=50,
    )

    assert len(filtered) >= 1
    assert "genre_list" in filtered.columns


def test_filter_market_genre_filter_can_match_tag_only_terms():
    raw = pd.DataFrame(
        {
            "name": ["Puzzle Tag Game", "Action Game"],
            "release_date": ["2020-01-01", "2021-01-01"],
            "price": [9.99, 19.99],
            "genres": ["Adventure", "Action"],
            "tags": ["Puzzle, Story Rich", "Shooter"],
            "positive_reviews": [10, 20],
            "negative_reviews": [1, 2],
        }
    )
    cleaned, _ = clean_steam_data(raw)
    filtered = filter_market(cleaned, only_indie=False, genres=["Puzzle"])

    assert len(filtered) == 1
    assert filtered.iloc[0]["name"] == "Puzzle Tag Game"


def test_build_market_scatter_keeps_raw_and_log_x_values():
    rows = build_market_scatter(sample_cleaned_df(), "total_reviews", "positive_rate", log_x=True)

    assert rows
    assert rows[0]["total_reviews"] == 100
    assert "log_total_reviews" in rows[0]
    assert rows[0]["log_total_reviews"] != rows[0]["total_reviews"]
