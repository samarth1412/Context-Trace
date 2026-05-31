from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.traces import EvaluationResponse


class APIModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True, from_attributes=True, extra="forbid")


class PlaygroundDocumentUploadResponse(APIModel):
    document_id: str
    filename: str
    chunk_count: int


class RetrievalStrategyName(str, Enum):
    DENSE_TOP_K = "dense_top_k"
    BM25_TOP_K = "bm25_top_k"
    HYBRID = "hybrid"
    HYBRID_RERANK = "hybrid_rerank"


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


class PlaygroundCompareRequest(APIModel):
    query: str = Field(min_length=1)
    top_k: int = Field(default=5, ge=1, le=20)
    strategies: List[RetrievalStrategyName] = Field(
        default_factory=lambda: [
            RetrievalStrategyName.DENSE_TOP_K,
            RetrievalStrategyName.BM25_TOP_K,
            RetrievalStrategyName.HYBRID,
            RetrievalStrategyName.HYBRID_RERANK,
        ]
    )
    project: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class PlaygroundComparisonMetrics(APIModel):
    citation_support: float
    unsupported_claim_rate: float
    failure_type: str
    token_usage: Dict[str, Any] = Field(default_factory=dict)
    latency_ms: float


class PlaygroundComparisonResult(APIModel):
    strategy: RetrievalStrategyName
    trace_id: str
    answer: str
    retrieved_chunks: List[PlaygroundChunk]
    citations: List[Dict[str, str]]
    metrics: PlaygroundComparisonMetrics
    evaluation: EvaluationResponse


class PlaygroundCompareResponse(APIModel):
    query: str
    results: List[PlaygroundComparisonResult]
