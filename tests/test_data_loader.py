from io import BytesIO
import json

import pandas as pd

from backend.services import data_loader


def _sample_rows():
    return [
        {
            "name": "Good Game",
            "price": 9.99,
            "genres": "Action;Indie",
            "tags": "Shooter;Arcade",
            "positive_reviews": 10,
            "negative_reviews": 2,
        },
        {
            "name": "Great Game",
            "price": 0,
            "genres": "Adventure",
            "tags": "Story Rich",
            "positive_reviews": 20,
            "negative_reviews": 1,
        },
    ]


def _seed_current_data():
    seed = pd.DataFrame(
        {
            "name": ["Seed Game"],
            "positive_reviews": [10],
            "negative_reviews": [1],
        }
    )
    data_loader.set_current_data(seed, "seed.csv", raw_df=seed, cleaning_report={})


def test_load_uploaded_data_supports_csv():
    raw = b"name,price,genres,tags,positive_reviews,negative_reviews\nGood Game,9.99,Action,Shooter,10,2\n"

    df, result = data_loader.load_uploaded_data(raw, "games.csv")

    assert df is not None
    assert result["success"] is True
    assert len(df) == 1
    assert "positive_rate" in df.columns


def test_load_uploaded_data_supports_tsv():
    raw = b"name\tprice\tgenres\ttags\tpositive_reviews\tnegative_reviews\nGood Game\t9.99\tAction\tShooter\t10\t2\n"

    df, result = data_loader.load_uploaded_data(raw, "games.tsv")

    assert df is not None
    assert result["success"] is True
    assert len(df) == 1
    assert df.iloc[0]["name"] == "Good Game"


def test_load_uploaded_data_supports_xlsx():
    frame = pd.DataFrame(_sample_rows())
    buffer = BytesIO()
    frame.to_excel(buffer, index=False)

    df, result = data_loader.load_uploaded_data(buffer.getvalue(), "games.xlsx")

    assert df is not None
    assert result["success"] is True
    assert len(df) == 2
    assert "total_reviews" in df.columns


def test_load_uploaded_data_supports_json_records():
    raw = json.dumps(_sample_rows(), ensure_ascii=False).encode("utf-8")

    df, result = data_loader.load_uploaded_data(raw, "games.json")

    assert df is not None
    assert result["success"] is True
    assert len(df) == 2
    assert df.iloc[0]["name"] == "Good Game"


def test_load_uploaded_data_rejects_unsupported_extension_with_chinese_message():
    df, result = data_loader.load_uploaded_data(b"hello", "games.txt")

    assert df is None
    assert result["success"] is False
    assert result["message"] == "上传数据文件读取失败：仅支持 CSV、TSV、XLSX、JSON 文件上传。"


def test_load_uploaded_data_generates_name_for_generic_csv_without_name():
    generic_csv = b"id,category,value,date\n1,Puzzle,10,2024-01-01\n2,Strategy,20,2024-01-02\n"

    df, result = data_loader.load_uploaded_data(generic_csv, "generic.csv")

    assert df is not None
    assert result["success"] is True
    assert list(df["name"]) == ["Puzzle", "Strategy"]
    assert "display_name" in df.columns
    assert any("缺少 name" in warning for warning in result["cleaning_report"]["warnings"])


def test_load_uploaded_data_read_failure_keeps_current_data():
    _seed_current_data()
    invalid_json = b'{"name": "Not tabular"}'

    df, result = data_loader.load_uploaded_data(invalid_json, "games.json")
    current, source_name, report = data_loader.get_current_data()

    assert df is None
    assert result["success"] is False
    assert "上传数据文件读取失败" in result["message"]
    assert "records/list-of-objects" in result["message"]
    assert source_name == "seed.csv"
    assert len(current) == 1
    assert report == {}
