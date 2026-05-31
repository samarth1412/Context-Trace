from __future__ import annotations

from typing import Optional

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session
from typing_extensions import Annotated

from app.core.config import Settings, get_settings
from app.core.security import hash_api_key
from app.db.session import get_db
from app.judge import LLMJudgeProvider, MockJudgeProvider, OpenAICompatibleJudgeProvider
from app.models import User
from app.playground.providers import (
    AnswerProvider,
    EmbeddingProvider,
    HashEmbeddingProvider,
    MockAnswerProvider,
    OpenAICompatibleAnswerProvider,
    OpenAICompatibleEmbeddingProvider,
)
from app.playground.vector_store import InMemoryVectorStore, QdrantVectorStore, VectorStore


_memory_vector_store = InMemoryVectorStore()


def _extract_api_key(authorization: Optional[str], x_api_key: Optional[str]) -> Optional[str]:
    if x_api_key:
        return x_api_key
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return None


def get_current_user(
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    authorization: Annotated[Optional[str], Header()] = None,
    x_api_key: Annotated[Optional[str], Header(alias="X-API-Key")] = None,
) -> User:
    api_key = _extract_api_key(authorization, x_api_key)
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key.",
        )

    api_key_hash = hash_api_key(api_key)
    user = db.scalar(select(User).where(User.api_key_hash == api_key_hash))
    if user:
        return user

    if settings.auto_create_dev_user and api_key == settings.default_api_key:
        user = User(api_key_hash=api_key_hash)
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid API key.",
    )


def get_llm_judge_provider(
    settings: Annotated[Settings, Depends(get_settings)],
) -> LLMJudgeProvider:
    if settings.judge_provider == "openai_compatible":
        if not settings.openai_compatible_api_key:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="OpenAI-compatible judge API key is not configured.",
            )
        return OpenAICompatibleJudgeProvider(
            base_url=settings.openai_compatible_base_url,
            api_key=settings.openai_compatible_api_key,
            model=settings.openai_compatible_model,
        )
    return MockJudgeProvider()


def get_embedding_provider(
    settings: Annotated[Settings, Depends(get_settings)],
) -> EmbeddingProvider:
    if settings.embedding_provider == "openai_compatible":
        if not settings.openai_compatible_api_key:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="OpenAI-compatible embedding API key is not configured.",
            )
        return OpenAICompatibleEmbeddingProvider(
            base_url=settings.openai_compatible_base_url,
            api_key=settings.openai_compatible_api_key,
            model=settings.openai_compatible_embedding_model,
        )
    return HashEmbeddingProvider(dimensions=settings.playground_embedding_dimensions)


def get_answer_provider(
    settings: Annotated[Settings, Depends(get_settings)],
) -> AnswerProvider:
    if settings.answer_provider == "openai_compatible":
        if not settings.openai_compatible_api_key:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="OpenAI-compatible answer API key is not configured.",
            )
        return OpenAICompatibleAnswerProvider(
            base_url=settings.openai_compatible_base_url,
            api_key=settings.openai_compatible_api_key,
            model=settings.openai_compatible_model,
        )
    return MockAnswerProvider()


def get_vector_store(
    settings: Annotated[Settings, Depends(get_settings)],
) -> VectorStore:
    if settings.playground_vector_store == "qdrant":
        return QdrantVectorStore(
            url=settings.qdrant_url,
            api_key=settings.qdrant_api_key,
            collection=settings.qdrant_collection,
            dimensions=settings.playground_embedding_dimensions,
        )
    return _memory_vector_store
