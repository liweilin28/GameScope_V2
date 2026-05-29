"""
来源：学生 + AI
作用：提供数据状态、数据文件上传、数据预览和清洗报告 API。
"""

from __future__ import annotations

from fastapi import APIRouter, File, UploadFile

from backend.config import SAMPLE_DATA_PATH
from backend.models import fail, ok
from backend.services.analyzer import get_field_compatibility_report, get_missing_value_report
from backend.services.data_loader import (
    SUPPORTED_UPLOAD_EXTENSIONS,
    ensure_current_data,
    get_current_data,
    get_current_raw_data,
    load_uploaded_data,
)
from backend.services.utils import dataframe_to_records


router = APIRouter(prefix="/api/data", tags=["data"])


@router.get("/status")
def data_status():
    current, source_name, report = ensure_current_data()
    return ok(
        {
            "default_data_exists": SAMPLE_DATA_PATH.exists(),
            "default_data_path": str(SAMPLE_DATA_PATH),
            "has_current_data": current is not None,
            "source_name": source_name,
            "rows": int(len(current)) if current is not None else 0,
            "columns": list(current.columns) if current is not None else [],
            "cleaning_errors": report.get("errors", []) if isinstance(report, dict) else [],
        },
        "数据状态获取成功。",
    )


@router.post("/upload")
async def upload_data_file(file: UploadFile = File(...)):
    filename = file.filename or ""
    if not any(filename.lower().endswith(ext) for ext in SUPPORTED_UPLOAD_EXTENSIONS):
        return fail("仅支持 CSV、TSV、XLSX、JSON 文件上传。")
    content = await file.read()
    df, result = load_uploaded_data(content, filename)
    if df is None:
        return fail(result["message"])
    return ok(
        {
            "source_name": filename,
            "rows": int(len(df)),
            "columns": list(df.columns),
            "cleaning_report": result.get("cleaning_report", {}),
        },
        "上传数据文件已读取并清洗。",
    )


@router.get("/preview")
def data_preview(limit: int = 10):
    df, source_name, report = ensure_current_data()
    if df is None:
        return fail(report.get("message", "当前没有可用数据。"))

    raw_df = get_current_raw_data()
    useful_columns = [
        "app_id",
        "name",
        "release_date",
        "release_year",
        "price",
        "genres",
        "tags",
        "positive_reviews",
        "negative_reviews",
        "total_reviews",
        "positive_rate",
        "developers",
        "publishers",
        "recommendations",
        "average_playtime_forever",
        "peak_ccu",
        "is_indie",
        "price_level",
        "review_level",
    ]
    raw_preview_df = raw_df[[c for c in useful_columns if raw_df is not None and c in raw_df.columns]] if raw_df is not None else None
    clean_preview_df = df[[c for c in useful_columns if c in df.columns]]
    return ok(
        {
            "source_name": source_name,
            "raw": {
                "rows": int(len(raw_df)) if raw_df is not None else 0,
                "columns": list(raw_preview_df.columns) if raw_preview_df is not None else [],
                "preview": dataframe_to_records(raw_preview_df, limit=limit) if raw_preview_df is not None else [],
            },
            "cleaned": {
                "rows": int(len(df)),
                "columns": list(clean_preview_df.columns),
                "preview": dataframe_to_records(clean_preview_df, limit=limit),
            },
            "missing_values": get_missing_value_report(df),
            "field_compatibility": get_field_compatibility_report(df),
        },
        "数据预览获取成功。",
    )


@router.get("/raw")
def raw_data(limit: int = 0):
    df, _, report = ensure_current_data()
    if df is None:
        return fail(report.get("message", "当前没有可用数据。"))
    raw_df = get_current_raw_data()
    if raw_df is None:
        return fail("当前没有原始 CSV 数据。")
    row_limit = len(raw_df) if limit <= 0 else min(limit, len(raw_df))
    return ok(
        {
            "rows": int(len(raw_df)),
            "columns": list(raw_df.columns),
            "preview": dataframe_to_records(raw_df, limit=row_limit),
        },
        "原始 CSV 数据获取成功。",
    )


@router.get("/cleaning-report")
def cleaning_report():
    df, source_name, report = ensure_current_data()
    if df is None:
        return fail(report.get("message", "当前没有可用数据。"))
    return ok(
        {
            "source_name": source_name,
            "cleaning_report": report,
            "missing_values": get_missing_value_report(df),
            "field_compatibility": get_field_compatibility_report(df),
            "meets_1000_rows": bool(len(df) >= 1000),
        },
        "清洗报告获取成功。",
    )
