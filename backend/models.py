"""
来源：学生 + AI
作用：定义统一 API 响应模型和阶段 2-4 使用的请求模型。
"""

from typing import Any

from pydantic import BaseModel, Field


class ApiResponse(BaseModel):
    success: bool
    message: str = ""
    data: Any = None


class ExplorerFilterRequest(BaseModel):
    only_indie: bool = True
    year_range: list[int] | None = None
    price_range: list[float] | None = None
    genres: list[str] | None = None
    tags: list[str] | None = None
    min_reviews: int = 0


class QaAskRequest(BaseModel):
    question: str = Field(..., min_length=1)


class QaHistoryMessage(BaseModel):
    role: str
    content: str


class QaFilters(BaseModel):
    genres: list[str] = []
    tags: list[str] = []
    price_range: list[float] | None = None
    year_range: list[int] | None = None
    min_reviews: int | None = None
    market_scope: str = "unknown"


class QaChatRequest(BaseModel):
    conversation_id: str | None = None
    message: str = Field(..., min_length=1)
    history: list[QaHistoryMessage] = []
    current_filters: QaFilters | None = None
    idea_context: dict[str, Any] | None = None


class IdeaParseRequest(BaseModel):
    idea_text: str = Field(..., min_length=1)


class IdeaAnalyzeRequest(BaseModel):
    idea_text: str = ""
    idea_profile: dict[str, Any] | None = None
    top_n: int = 10
    only_indie: bool = True


class IdeaReportRequest(BaseModel):
    analysis_result: dict[str, Any]


class IdeaAdvisorChatRequest(BaseModel):
    question: str = Field(..., min_length=1)
    idea_text: str = ""
    analysis_result: dict[str, Any] = {}
    history: list[QaHistoryMessage] = []


def ok(data: Any = None, message: str = "") -> dict[str, Any]:
    return ApiResponse(success=True, message=message, data=data).model_dump()


def fail(message: str, data: Any = None) -> dict[str, Any]:
    return ApiResponse(success=False, message=message, data=data).model_dump()
