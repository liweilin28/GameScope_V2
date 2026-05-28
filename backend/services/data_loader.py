"""
来源：学生 + AI
作用：读取默认 Steam CSV 和用户上传 CSV，并维护当前会话使用的数据集。
"""

from __future__ import annotations

from io import BytesIO
from typing import BinaryIO

import pandas as pd

from backend.config import SAMPLE_DATA_PATH
from backend.services.data_cleaner import clean_steam_data
from backend.services.utils import standardize_columns


_current_raw_df: pd.DataFrame | None = None
_current_clean_df: pd.DataFrame | None = None
_current_source_name = "No data loaded"
_current_report: dict = {}


def _read_csv_bytes(content: bytes) -> pd.DataFrame:
    last_error: Exception | None = None
    for encoding in ["utf-8-sig", "utf-8", "gbk", "latin1"]:
        try:
            return pd.read_csv(BytesIO(content), low_memory=False, encoding=encoding)
        except UnicodeDecodeError as exc:
            last_error = exc
    if last_error:
        raise last_error
    raise ValueError("无法读取 CSV 文件。")


def _cleaning_failure_message(report: dict, cleaned: pd.DataFrame) -> str:
    errors = report.get("errors", []) if isinstance(report, dict) else []
    if errors:
        return "数据清洗失败：" + "；".join(str(item) for item in errors)
    if cleaned.empty:
        return "数据清洗后没有可用行，请检查 name 字段和数据内容。"
    return ""


def _prepare_data(df: pd.DataFrame, source_name: str) -> tuple[pd.DataFrame | None, dict]:
    raw, _ = standardize_columns(df)
    cleaned, report = clean_steam_data(raw)
    failure_message = _cleaning_failure_message(report, cleaned)
    if failure_message:
        report["message"] = failure_message
        return None, report
    set_current_data(cleaned, source_name, raw_df=raw, cleaning_report=report)
    return cleaned, report


def load_default_data() -> tuple[pd.DataFrame | None, dict]:
    """读取默认 CSV，完成清洗并设置为当前数据集。"""
    if not SAMPLE_DATA_PATH.exists():
        return None, {
            "success": False,
            "message": f"默认数据文件不存在：{SAMPLE_DATA_PATH}",
            "path": str(SAMPLE_DATA_PATH),
        }
    try:
        raw_df = pd.read_csv(SAMPLE_DATA_PATH, low_memory=False)
        cleaned, report = _prepare_data(raw_df, "sample_steam_games.csv")
        if cleaned is None:
            return None, {
                "success": False,
                "message": report.get("message", "默认数据清洗后不可用。"),
                "cleaning_report": report,
            }
        return cleaned, {"success": True, "message": "默认数据加载成功。", "cleaning_report": report}
    except Exception as exc:
        return None, {"success": False, "message": f"默认数据读取失败：{exc}"}


def load_uploaded_data(file: BinaryIO | bytes, source_name: str = "uploaded.csv") -> tuple[pd.DataFrame | None, dict]:
    """读取用户上传的 CSV 字节流，完成清洗并设置为当前数据集。"""
    try:
        if isinstance(file, bytes):
            content = file
        else:
            content = file.read()
        raw_df = _read_csv_bytes(content)
        cleaned, report = _prepare_data(raw_df, source_name)
        if cleaned is None:
            return None, {
                "success": False,
                "message": report.get("message", "上传数据清洗后不可用。"),
                "cleaning_report": report,
            }
        return cleaned, {"success": True, "message": "上传数据加载成功。", "cleaning_report": report}
    except Exception as exc:
        return None, {"success": False, "message": f"上传 CSV 读取失败：{exc}"}


def get_current_data() -> tuple[pd.DataFrame | None, str, dict]:
    """返回当前清洗后数据、数据来源名称和清洗报告。"""
    return _current_clean_df, _current_source_name, _current_report


def get_current_raw_data() -> pd.DataFrame | None:
    return _current_raw_df


def set_current_data(
    df: pd.DataFrame,
    source_name: str,
    raw_df: pd.DataFrame | None = None,
    cleaning_report: dict | None = None,
) -> None:
    """更新当前会话使用的数据集，供 Dashboard、Q&A 和 Idea Lab 复用。"""
    global _current_raw_df, _current_clean_df, _current_source_name, _current_report
    _current_clean_df = df.copy()
    _current_raw_df = raw_df.copy() if raw_df is not None else df.copy()
    _current_source_name = source_name
    _current_report = cleaning_report or {}


def ensure_current_data() -> tuple[pd.DataFrame | None, str, dict]:
    """如果当前无数据则尝试加载默认数据，始终以不崩溃的方式返回结果。"""
    current, source_name, report = get_current_data()
    if current is not None:
        return current, source_name, report
    loaded, result = load_default_data()
    if loaded is None:
        return None, _current_source_name, result
    current, source_name, report = get_current_data()
    return current, source_name, report
