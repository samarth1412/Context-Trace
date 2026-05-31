from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import AgentEventType, CitationVerdict, FailureType, Severity, SupportStatus


class APIModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True, from_attributes=True, extra="forbid")


class ChunkPayload(APIModel):
    chunk_id: Optional[str] = None
    content: str
    source: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    relevance_score: Optional[float] = None


class TraceStartRequest(APIModel):
    project: str = Field(min_length=1, max_length=200)
    query: str = Field(min_length=1)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class TraceStartResponse(APIModel):
    trace_id: str
    project_id: str


class RetrievalRequest(APIModel):
    chunks: List[ChunkPayload]
    retriever_name: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ContextRequest(APIModel):
    chunks: Optional[List[ChunkPayload]] = None
    chunk_ids: Optional[List[str]] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class AnswerRequest(APIModel):
    answer: str = Field(min_length=1)
    model: Optional[str] = None
    usage: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class CitationPayload(APIModel):
    claim: str = Field(min_length=1)
    source_chunk_id: str = Field(min_length=1)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class CitationsRequest(APIModel):
    citations: List[CitationPayload]


class TraceEventResponse(APIModel):
    trace_id: str
    accepted: int


class AgentEventRequest(APIModel):
    event_type: AgentEventType
    name: Optional[str] = None
    input_json: Any = Field(default_factory=dict)
    output_json: Any = Field(default_factory=dict)
    metadata_json: Dict[str, Any] = Field(default_factory=dict)
    latency_ms: Optional[float] = Field(default=None, ge=0.0)
    error_message: Optional[str] = None


class AgentEventResponse(APIModel):
    trace_id: str
    event_id: str
    accepted: int


class AgentEventRead(APIModel):
    id: str
    trace_id: str
    event_type: AgentEventType
    name: Optional[str] = None
    input_json: Any = Field(default_factory=dict)
    output_json: Any = Field(default_factory=dict)
    metadata_json: Dict[str, Any] = Field(default_factory=dict)
    latency_ms: Optional[float] = None
    error_message: Optional[str] = None
    created_at: datetime


class AgentEventsResponse(APIModel):
    trace_id: str
    events: List[AgentEventRead] = Field(default_factory=list)


class EvaluatedCitationCheck(APIModel):
    claim: str
    source_chunk_id: str
    verdict: CitationVerdict
    support_score: float = Field(ge=0.0, le=1.0)
    reason: str


class FailurePayload(APIModel):
    failure_type: FailureType
    severity: Severity
    root_cause: str
    suggested_fix: str


class EvaluationResponse(APIModel):
    citation_checks: List[EvaluatedCitationCheck] = Field(default_factory=list)
    failure: FailurePayload


class ChunkRead(APIModel):
    id: str
    chunk_id: str
    content: str
    source: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    relevance_score: Optional[float] = None
    position: int
    selected: bool


class AnswerRead(APIModel):
    id: str
    answer: str
    model: Optional[str] = None
    usage: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class CitationCheckRead(APIModel):
    id: str
    claim: str
    source_chunk_id: str
    support_status: SupportStatus
    support_score: Optional[float] = None
    rationale: Optional[str] = None


class TraceRead(APIModel):
    id: str
    project_id: str
    project: str
    query: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    status: str
    chunks: List[ChunkRead] = Field(default_factory=list)
    answer: Optional[AnswerRead] = None
    citation_checks: List[CitationCheckRead] = Field(default_factory=list)
    agent_events: List[AgentEventRead] = Field(default_factory=list)
    evaluation: Optional[EvaluationResponse] = None
    created_at: datetime
    updated_at: datetime
