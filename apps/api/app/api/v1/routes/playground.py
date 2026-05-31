from typing_extensions import Annotated

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import (
    get_answer_provider,
    get_current_user,
    get_db,
    get_embedding_provider,
    get_llm_judge_provider,
    get_vector_store,
)
from app.core.config import Settings, get_settings
from app.judge import LLMJudgeProvider
from app.models import User
from app.playground.providers import AnswerProvider, EmbeddingProvider
from app.playground.vector_store import VectorStore
from app.schemas import (
    PlaygroundCompareRequest,
    PlaygroundCompareResponse,
    PlaygroundDocumentUploadResponse,
    PlaygroundQueryRequest,
    PlaygroundQueryResponse,
)
from app.services.playground import PlaygroundService

router = APIRouter(prefix="/playground", tags=["playground"])


@router.post("/documents", response_model=PlaygroundDocumentUploadResponse, status_code=201)
async def upload_document(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    settings: Annotated[Settings, Depends(get_settings)],
    embedding_provider: Annotated[EmbeddingProvider, Depends(get_embedding_provider)],
    vector_store: Annotated[VectorStore, Depends(get_vector_store)],
    file: UploadFile = File(...),
) -> PlaygroundDocumentUploadResponse:
    content = await file.read()
    return await PlaygroundService(
        db=db,
        user=user,
        settings=settings,
        embedding_provider=embedding_provider,
        vector_store=vector_store,
    ).ingest_document(
        filename=file.filename or "",
        content=content,
        content_type=file.content_type,
    )


@router.post("/query", response_model=PlaygroundQueryResponse)
async def query_playground(
    request: PlaygroundQueryRequest,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    settings: Annotated[Settings, Depends(get_settings)],
    embedding_provider: Annotated[EmbeddingProvider, Depends(get_embedding_provider)],
    answer_provider: Annotated[AnswerProvider, Depends(get_answer_provider)],
    vector_store: Annotated[VectorStore, Depends(get_vector_store)],
    judge_provider: Annotated[LLMJudgeProvider, Depends(get_llm_judge_provider)],
) -> PlaygroundQueryResponse:
    return await PlaygroundService(
        db=db,
        user=user,
        settings=settings,
        embedding_provider=embedding_provider,
        answer_provider=answer_provider,
        vector_store=vector_store,
        judge_provider=judge_provider,
    ).query(request)


@router.post("/compare", response_model=PlaygroundCompareResponse)
async def compare_playground_strategies(
    request: PlaygroundCompareRequest,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    settings: Annotated[Settings, Depends(get_settings)],
    embedding_provider: Annotated[EmbeddingProvider, Depends(get_embedding_provider)],
    answer_provider: Annotated[AnswerProvider, Depends(get_answer_provider)],
    vector_store: Annotated[VectorStore, Depends(get_vector_store)],
    judge_provider: Annotated[LLMJudgeProvider, Depends(get_llm_judge_provider)],
) -> PlaygroundCompareResponse:
    return await PlaygroundService(
        db=db,
        user=user,
        settings=settings,
        embedding_provider=embedding_provider,
        answer_provider=answer_provider,
        vector_store=vector_store,
        judge_provider=judge_provider,
    ).compare(request)
