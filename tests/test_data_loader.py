import json
from io import BytesIO

import pandas as pd

from backend.services import data_loader


def make_valid_rows():
    return [
        {
            "name": "Good Game",
            "price": 9.99,
            "genres": "Action",
            "tags": "Shooter",
            "positive_reviews": 10,
            "negative_reviews": 2,
        },
        {
            "name": "Nice Game",
            "price": 19.99,
            "genres": "Adventure",
            "tags": "Story Rich",
            "positive_reviews": 20,
            "negative_reviews": 3,
        },
    ]


def make_valid_df():
    return pd.DataFrame(make_valid_rows())


def test_load_uploaded_csv_still_works():
    csv_bytes = make_valid_df().to_csv(index=False).encode("utf-8")

    df, result = data_loader.load_uploaded_data(csv_bytes, "games.csv")

    assert result["success"] is True
    assert df is not None
    assert list(df["name"]) == ["Good Game", "Nice Game"]


def test_load_uploaded_tsv_works():
    tsv_bytes = make_valid_df().to_csv(index=False, sep="\t").encode("utf-8")

    df, result = data_loader.load_uploaded_data(tsv_bytes, "games.tsv")

    assert result["success"] is True
    assert df is not None
    assert len(df) == 2
    assert "genres" in df.columns


def test_load_uploaded_xlsx_works():
    buffer = BytesIO()
    make_valid_df().to_excel(buffer, index=False)

    df, result = data_loader.load_uploaded_data(buffer.getvalue(), "games.xlsx")

    assert result["success"] is True
    assert df is not None
    assert len(df) == 2
    assert "price" in df.columns


def test_load_uploaded_json_records_works():
    json_bytes = json.dumps(make_valid_rows(), ensure_ascii=False).encode("utf-8")

    df, result = data_loader.load_uploaded_data(json_bytes, "games.json")

    assert result["success"] is True
    assert df is not None
    assert list(df["name"]) == ["Good Game", "Nice Game"]


def test_load_uploaded_unsupported_format_returns_chinese_message():
    df, result = data_loader.load_uploaded_data(b"hello", "games.txt")

    assert df is None
    assert result["success"] is False
    assert "仅支持 CSV、TSV、XLSX、JSON 文件上传" in result["message"]


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
