from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.traces import EvaluationResponse


class APIModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True, from_attributes=True, extra="forbid")


class PlaygroundChunkPreview(APIModel):
    chunk_id: str
    content: str
    source: str
    token_count: int
    metadata: Dict[str, Any] = Field(default_factory=dict)


class PlaygroundDocumentUploadResponse(APIModel):
    document_id: str
    filename: str
    chunk_count: int
    text_preview: str
    chunks: List[PlaygroundChunkPreview]


class PlaygroundSampleDataset(APIModel):
    sample_id: str
    name: str
    description: str
    suggested_queries: List[str]


class PlaygroundSamplesResponse(APIModel):
    samples: List[PlaygroundSampleDataset]


class PlaygroundSampleLoadResponse(APIModel):
    sample_id: str
    name: str
    description: str
    suggested_queries: List[str]
    documents: List[PlaygroundDocumentUploadResponse]
    chunk_count: int


class RetrievalStrategyName(str, Enum):
    DENSE_TOP_K = "dense_top_k"
    BM25_TOP_K = "bm25_top_k"
    HYBRID = "hybrid"
    HYBRID_RERANK = "hybrid_rerank"
    CORRECTIVE_RAG = "corrective_rag"
    CONTEXTTRACE_ADAPTIVE = "contexttrace_adaptive"


class PlaygroundQueryRequest(APIModel):
    query: str = Field(min_length=1)
    top_k: int = Field(default=5, ge=1, le=20)
    strategy: RetrievalStrategyName = RetrievalStrategyName.CONTEXTTRACE_ADAPTIVE
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
    strategy: RetrievalStrategyName
    retrieved_chunks: List[PlaygroundChunk]
    selected_context: List[PlaygroundChunk]
    dropped_context: List[PlaygroundChunk]
    citations: List[Dict[str, str]]
    metrics: "PlaygroundComparisonMetrics"
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
                RetrievalStrategyName.CORRECTIVE_RAG,
                RetrievalStrategyName.CONTEXTTRACE_ADAPTIVE,
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
    estimated_cost_usd: float = 0.0


class PlaygroundComparisonResult(APIModel):
    strategy: RetrievalStrategyName
    trace_id: str
    answer: str
    retrieved_chunks: List[PlaygroundChunk]
    selected_context: List[PlaygroundChunk] = Field(default_factory=list)
    dropped_context: List[PlaygroundChunk] = Field(default_factory=list)
    citations: List[Dict[str, str]]
    metrics: PlaygroundComparisonMetrics
    evaluation: EvaluationResponse


class PlaygroundCompareResponse(APIModel):
    query: str
    results: List[PlaygroundComparisonResult]
