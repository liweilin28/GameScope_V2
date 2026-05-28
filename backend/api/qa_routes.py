"""
来源：学生 + AI
作用：提供 Data Q&A 智能问数 API，包括旧单轮接口和新多轮 chat 接口。
"""

from fastapi import APIRouter

from backend.models import QaAskRequest, QaChatRequest, fail, ok
from backend.services.data_loader import ensure_current_data
from backend.services.qa_engine import answer_question, chat


router = APIRouter(prefix="/api/qa", tags=["qa"])


@router.post("/ask")
def ask(request: QaAskRequest):
    """兼容旧前端：单轮问答接口。"""
    df, _, report = ensure_current_data()
    if df is None:
        return fail(report.get("message", "当前没有可用数据，请先上传 CSV。"))
    return ok(answer_question(df, request.question), "问答分析完成。")


@router.post("/chat")
def chat_endpoint(request: QaChatRequest):
    """多轮澄清式智能问数接口。"""
    df, _, report = ensure_current_data()
    if df is None:
        data = chat(
            None,
            request.message,
            conversation_id=request.conversation_id,
            history=[item.model_dump() for item in request.history],
            current_filters=request.current_filters.model_dump() if request.current_filters else None,
        )
        return ok(data, report.get("message", "当前没有可分析的数据。"))
    data = chat(
        df,
        request.message,
        conversation_id=request.conversation_id,
        history=[item.model_dump() for item in request.history],
        current_filters=request.current_filters.model_dump() if request.current_filters else None,
    )
    return ok(data, "智能问数处理完成。")
