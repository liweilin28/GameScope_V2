"""
来源：学生 + AI
作用：提供系统健康、LLM 状态和课程提交验收 readiness API。
"""

from __future__ import annotations

from fastapi import APIRouter

from backend.config import BASE_DIR, get_settings
from backend.models import ok
from backend.services import analyzer
from backend.services.data_loader import ensure_current_data
from backend.services.llm_client import get_llm_status


router = APIRouter(prefix="/api/system", tags=["system"])
settings = get_settings()

REQUIRED_DOCS = [
    "README.md",
    "docs/AI使用说明书.md",
    "docs/测试记录.md",
    "docs/数据字典.md",
    "docs/Demo演示脚本.md",
    "docs/提交验收清单.md",
    "docs/代码来源标注.md",
]


def _module_item(key: str, label: str, status: bool, evidence: str) -> tuple[str, dict]:
    return key, {"label": label, "status": status, "evidence": evidence}


@router.get("/health")
def health_check():
    return ok(
        {
            "app": settings.app_name,
            "version": settings.app_version,
            "status": "running",
        },
        "GameScope_V2 后端运行正常。",
    )


@router.get("/llm-status")
def llm_status():
    status = get_llm_status()
    return ok(status, "LLM 已启用。" if status["enabled"] else "当前使用规则 fallback。")


@router.get("/submission-readiness")
def submission_readiness():
    df, source_name, _ = ensure_current_data()
    llm = get_llm_status()
    compatibility = analyzer.get_field_compatibility_report(df) if df is not None else {}

    rows = int(len(df)) if df is not None else 0
    columns = int(len(df.columns)) if df is not None else 0

    docs_items = {}
    for relative_path in REQUIRED_DOCS:
        path = BASE_DIR / relative_path
        docs_items[relative_path] = {"exists": path.exists(), "path": str(path)}

    modules = dict(
        [
            _module_item(
                "data_pipeline",
                "数据读取与预处理",
                df is not None and rows > 0,
                f"当前数据源：{source_name}；清洗后 {rows} 行。"
                if df is not None
                else "当前未加载成功的数据集。",
            ),
            _module_item(
                "dashboard",
                "Dashboard 市场总览",
                df is not None and rows > 0,
                "已具备核心指标与图表统计输入。"
                if df is not None
                else "缺少可分析数据，Dashboard 仅能展示空状态。",
            ),
            _module_item(
                "explorer",
                "Visual Explorer 可视化探索",
                df is not None and rows > 0,
                "筛选分析依赖当前数据集，可进行交互式探索。"
                if df is not None
                else "缺少可分析数据，Explorer 仅能展示空状态。",
            ),
            _module_item(
                "qa",
                "Data Q&A 智能问数",
                df is not None and rows > 0,
                "后端问答接口已注册，回答基于真实数据计算。"
                if df is not None
                else "接口可用，但当前无数据可供问答。",
            ),
            _module_item(
                "idea_lab",
                "Idea Lab PLUS 创新",
                df is not None and rows > 0,
                "创意解析、竞品分析与机会评分模块已接入当前数据集。"
                if df is not None
                else "接口可用，但当前无数据支撑 Idea Lab 分析。",
            ),
        ]
    )

    payload = {
        "rows": rows,
        "columns": columns,
        "meets_1000_rows": rows >= 1000,
        "meets_10_columns": columns >= 10,
        "required_modules": modules,
        "docs_status": {
            "complete": all(item["exists"] for item in docs_items.values()),
            "items": docs_items,
        },
        "llm_status": {
            "enabled": llm["enabled"],
            "mode": llm["mode"],
            "note": "已启用可选 LLM。"
            if llm["enabled"]
            else "未配置 API Key 时自动使用规则 fallback，适合课堂稳定演示。",
        },
        "field_compatibility": compatibility,
        "test_command": "python3 -m pytest -q（Windows 可用 python -m pytest -q）",
    }
    return ok(payload, "课程提交验收状态获取成功。")
