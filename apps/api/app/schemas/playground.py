from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.traces import EvaluationResponse


class APIModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True, from_attributes=True, extra="forbid")


class PlaygroundDocumentUploadResponse(APIModel):
    document_id: str
    filename: str
    chunk_count: int


class PlaygroundQueryRequest(APIModel):
    query: str = Field(min_length=1)
    top_k: int = Field(default=5, ge=1, le=20)
    project: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class PlaygroundChunk(APIModel):
    chunk_id: str
    content: str
    source: Optional[str] = None
    score: float
    metadata: Dict[str, Any] = Field(default_factory=dict)


class PlaygroundQueryResponse(APIModel):
    answer: str
    trace_id: str
    retrieved_chunks: List[PlaygroundChunk]
    citations: List[Dict[str, str]]
    evaluation: EvaluationResponse
