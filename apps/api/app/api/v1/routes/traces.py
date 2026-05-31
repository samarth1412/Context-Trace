from typing_extensions import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, get_llm_judge_provider
from app.judge import LLMJudgeProvider
from app.models import User
from app.schemas import (
    AnswerRequest,
    CitationsRequest,
    ContextRequest,
    EvaluationResponse,
    RetrievalRequest,
    TraceEventResponse,
    TraceRead,
    TraceStartRequest,
    TraceStartResponse,
)
from app.services.traces import TraceService

router = APIRouter(prefix="/traces", tags=["traces"])


@router.post("/start", response_model=TraceStartResponse, status_code=201)
def start_trace(
    request: TraceStartRequest,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> TraceStartResponse:
    return TraceService(db, user).start_trace(request)


@router.post("/{trace_id}/retrieval", response_model=TraceEventResponse)
def log_retrieval(
    trace_id: str,
    request: RetrievalRequest,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> TraceEventResponse:
    return TraceService(db, user).log_retrieval(trace_id, request)


@router.post("/{trace_id}/context", response_model=TraceEventResponse)
def log_context(
    trace_id: str,
    request: ContextRequest,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> TraceEventResponse:
    return TraceService(db, user).log_context(trace_id, request)


@router.post("/{trace_id}/answer", response_model=TraceEventResponse)
def log_answer(
    trace_id: str,
    request: AnswerRequest,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> TraceEventResponse:
    return TraceService(db, user).log_answer(trace_id, request)


@router.post("/{trace_id}/citations", response_model=TraceEventResponse)
def log_citations(
    trace_id: str,
    request: CitationsRequest,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> TraceEventResponse:
    return TraceService(db, user).log_citations(trace_id, request)


@router.post("/{trace_id}/evaluate", response_model=EvaluationResponse)
async def evaluate_trace(
    trace_id: str,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    judge_provider: Annotated[LLMJudgeProvider, Depends(get_llm_judge_provider)],
) -> EvaluationResponse:
    return await TraceService(db, user).evaluate_trace(trace_id, judge_provider)


@router.get("/{trace_id}", response_model=TraceRead)
def get_trace(
    trace_id: str,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> TraceRead:
    return TraceService(db, user).get_trace(trace_id)
