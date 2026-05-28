import pandas as pd

from backend.services import data_loader


def test_load_uploaded_data_rejects_cleaning_errors_and_keeps_current_data():
    seed = pd.DataFrame(
        {
            "name": ["Good Game"],
            "positive_reviews": [10],
            "negative_reviews": [1],
        }
    )
    data_loader.set_current_data(seed, "seed.csv", raw_df=seed, cleaning_report={})

    broken_csv = b"price,genres,tags,positive_reviews,negative_reviews\n9.99,Action,Shooter,10,2\n"
    df, result = data_loader.load_uploaded_data(broken_csv, "missing-name.csv")
    current, source_name, report = data_loader.get_current_data()

    assert df is None
    assert result["success"] is False
    assert "缺少关键字段 name" in result["message"]
    assert source_name == "seed.csv"
    assert len(current) == 1
    assert report == {}
