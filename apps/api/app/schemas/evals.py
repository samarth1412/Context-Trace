from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import FailureType, Severity


class APIModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True, from_attributes=True, extra="forbid")


class EvalSetCreateRequest(APIModel):
    name: str = Field(min_length=1, max_length=200)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class EvalSetResponse(APIModel):
    eval_set_id: str
    name: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class EvalQuestionPayload(APIModel):
    question: str = Field(min_length=1)
    trace_id: Optional[str] = None
    expected_answer: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class EvalQuestionsRequest(APIModel):
    questions: List[EvalQuestionPayload]


class EvalQuestionRead(APIModel):
    id: str
    question: str
    trace_id: Optional[str] = None
    expected_answer: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    position: int


class EvalQuestionsResponse(APIModel):
    eval_set_id: str
    accepted: int
    questions: List[EvalQuestionRead] = Field(default_factory=list)


class WorstTrace(APIModel):
    trace_id: str
    question_id: str
    question: str
    failure_type: FailureType
    severity: Severity
    citation_support: float = Field(ge=0.0, le=1.0)
    unsupported_claim_rate: float = Field(ge=0.0, le=1.0)
    root_cause: str


class EvalSetSummary(APIModel):
    eval_set_id: str
    name: str
    total_questions: int
    linked_trace_count: int
    evaluated_trace_count: int
    unevaluated_trace_count: int
    avg_citation_support: float = Field(ge=0.0, le=1.0)
    unsupported_claim_rate: float = Field(ge=0.0, le=1.0)
    failure_type_distribution: Dict[str, int] = Field(default_factory=dict)
    worst_traces: List[WorstTrace] = Field(default_factory=list)
