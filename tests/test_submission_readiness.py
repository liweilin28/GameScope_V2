from fastapi.testclient import TestClient

from backend.main import app
from backend.services import data_loader


client = TestClient(app)


def test_submission_readiness_endpoint_returns_expected_structure():
    loaded, result = data_loader.load_default_data()
    assert loaded is not None, result

    response = client.get("/api/system/submission-readiness")

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True

    data = payload["data"]
    assert data["rows"] >= 1000
    assert data["columns"] >= 10
    assert data["meets_1000_rows"] is True
    assert data["meets_10_columns"] is True
    assert set(data["required_modules"].keys()) >= {"data_pipeline", "dashboard", "explorer", "qa", "idea_lab"}
    assert data["docs_status"]["complete"] is True
    assert "README.md" in data["docs_status"]["items"]
    assert "docs/提交验收清单.md" in data["docs_status"]["items"]
    assert "python3 -m pytest -q" in data["test_command"]


def test_generic_csv_without_name_can_preview_and_return_cleaning_report():
    upload = client.post(
        "/api/data/upload",
        files={"file": ("generic.csv", b"id,category,value,date\n1,Puzzle,10,2024-01-01\n2,Strategy,20,2024-01-02\n", "text/csv")},
    )

    assert upload.status_code == 200
    upload_payload = upload.json()
    assert upload_payload["success"] is True
    assert upload_payload["data"]["rows"] == 2
    assert "display_name" in upload_payload["data"]["columns"]
    assert any("缺少 name" in warning for warning in upload_payload["data"]["cleaning_report"]["warnings"])

    preview = client.get("/api/data/preview?limit=5")
    assert preview.status_code == 200
    preview_payload = preview.json()
    assert preview_payload["success"] is True
    assert preview_payload["data"]["cleaned"]["rows"] == 2
    assert preview_payload["data"]["cleaned"]["preview"][0]["name"] == "Puzzle"

    report = client.get("/api/data/cleaning-report")
    assert report.status_code == 200
    report_payload = report.json()
    assert report_payload["success"] is True
    assert any("缺少 name" in warning for warning in report_payload["data"]["cleaning_report"]["warnings"])
