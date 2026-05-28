import pandas as pd

from backend.services.data_cleaner import clean_steam_data


def test_cleaner_generates_review_fields_and_year():
    raw = pd.DataFrame(
        {
            "Name": ["Puzzle One", "Zero Review"],
            "Release date": ["2021-05-01", "Apr 12, 2020"],
            "Price": ["4.99", "0"],
            "Genres": ["Indie, Puzzle", "Adventure"],
            "Tags": ["Story Rich; Atmospheric", "Casual"],
            "Positive": [80, 0],
            "Negative": [20, 0],
        }
    )

    cleaned, report = clean_steam_data(raw)

    assert report["errors"] == []
    assert cleaned.loc[0, "total_reviews"] == 100
    assert cleaned.loc[0, "positive_rate"] == 0.8
    assert pd.isna(cleaned.loc[1, "positive_rate"])
    assert cleaned.loc[0, "release_year"] == 2021
    assert cleaned.loc[1, "release_year"] == 2020


def test_cleaner_generates_indie_price_and_review_levels():
    raw = pd.DataFrame(
        {
            "name": ["Free Indie", "Low Paid", "Medium Paid", "High Paid"],
            "release_date": ["2022", "2022", "2022", "2022"],
            "price": [0, 4.99, 9.99, 29.99],
            "genres": ["Indie", "Action", "RPG", "Strategy"],
            "tags": ["Puzzle", "Indie|Arcade", "Story Rich", "Simulation"],
            "positive_reviews": [10, 100, 1000, 10000],
            "negative_reviews": [0, 0, 0, 0],
        }
    )

    cleaned, _ = clean_steam_data(raw)

    assert cleaned.loc[0, "is_indie"] is True or cleaned.loc[0, "is_indie"] == True
    assert cleaned.loc[1, "is_indie"] is True or cleaned.loc[1, "is_indie"] == True
    assert list(cleaned["price_level"]) == ["Free", "Low", "Medium", "High"]
    assert list(cleaned["review_level"]) == ["Low", "Medium", "High", "Very High"]


def test_cleaner_drops_missing_name_and_duplicates():
    raw = pd.DataFrame(
        {
            "app_id": [1, 1, 2],
            "name": ["Game A", "Game A Duplicate", None],
            "positive_reviews": [1, 2, 3],
            "negative_reviews": [0, 0, 0],
        }
    )

    cleaned, report = clean_steam_data(raw)

    assert len(cleaned) == 1
    assert report["dropped_missing_name"] == 1
    assert report["dropped_duplicates"] == 1
