import pandas as pd

from backend.services.data_cleaner import clean_steam_data
from backend.services.qa_analysis_runner import run_analysis


def cleaned_df():
    raw = pd.DataFrame(
        {
            "name": ["A", "B", "C"],
            "release_date": ["2021-01-01", "2022-01-01", "2023-01-01"],
            "price": [0, 9.99, 19.99],
            "genres": ["Indie, Puzzle", "Action", "Indie, Puzzle"],
            "tags": ["Story Rich, Puzzle", "Shooter", "Atmospheric, Puzzle"],
            "positive_reviews": [90, 80, 95],
            "negative_reviews": [10, 20, 5],
        }
    )
    cleaned, _ = clean_steam_data(raw)
    return cleaned


def test_run_price_distribution_analysis():
    intent = {
        "analysis_type": "price_distribution",
        "target_metric": "price",
        "filters": {"market_scope": "indie", "genres": ["Indie"]},
        "group_by": "price_level",
        "chart_type": "bar",
    }
    result = run_analysis(cleaned_df(), intent)

    assert result["empty"] is False
    assert result["rows"]
    assert result["x_key"] == "price_level"


def test_run_analysis_empty_segment():
    intent = {
        "analysis_type": "price_distribution",
        "target_metric": "price",
        "filters": {"genres": ["NotExistingGenre"], "market_scope": "all"},
        "group_by": "price_level",
        "chart_type": "bar",
    }
    result = run_analysis(cleaned_df(), intent)

    assert result["empty"] is True
    assert result["segment_count"] == 0


def test_correlation_analysis_tolerates_missing_columns():
    raw = pd.DataFrame(
        {
            "name": ["A", "B"],
            "genres": ["Indie", "Action"],
            "tags": ["Puzzle", "Shooter"],
            "positive_reviews": [10, 20],
            "negative_reviews": [1, 2],
        }
    )
    cleaned, _ = clean_steam_data(raw)
    result = run_analysis(
        cleaned,
        {
            "analysis_type": "correlation",
            "target_metric": "total_reviews",
            "filters": {"market_scope": "all"},
            "group_by": "none",
            "chart_type": "scatter",
        },
    )

    assert result["empty"] is False
    assert isinstance(result["rows"], list)
