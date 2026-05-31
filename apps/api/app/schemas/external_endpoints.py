from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.evals import EvalSetSummary
from app.schemas.traces import ChunkPayload, CitationPayload, EvaluationResponse


class APIModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True, from_attributes=True, extra="forbid")


class ExternalEndpointConfig(APIModel):
    url: str = Field(min_length=1)
    method: Literal["GET", "POST"] = "POST"
    headers: Dict[str, str] = Field(default_factory=dict)
    body_template: Dict[str, Any] = Field(default_factory=lambda: {"question": "{{query}}"})
    response_mapping: Dict[str, str] = Field(
        default_factory=lambda: {
            "answer": "$.answer",
            "citations": "$.citations",
            "retrieved_chunks": "$.retrieved_chunks",
        }
    )

    @field_validator("method", mode="before")
    @classmethod
    def uppercase_method(cls, value: Any) -> Any:
        if isinstance(value, str):
            return value.upper()
        return value


class ExternalEndpointCreateRequest(ExternalEndpointConfig):
    name: str = Field(min_length=1, max_length=200)


class ExternalEndpointResponse(APIModel):
    id: str
    project_id: str
    name: str
    url: str
    method: Literal["GET", "POST"]
    headers: Dict[str, str] = Field(default_factory=dict)
    body_template: Dict[str, Any] = Field(default_factory=dict)
    response_mapping: Dict[str, str] = Field(default_factory=dict)
    created_at: datetime


class ExternalEndpointTestRequest(APIModel):
    query: str = Field(min_length=1)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class MappedExternalResponse(APIModel):
    raw_response: Dict[str, Any] = Field(default_factory=dict)
    answer: str
    retrieved_chunks: List[ChunkPayload] = Field(default_factory=list)
    citations: List[CitationPayload] = Field(default_factory=list)
    usage: Dict[str, Any] = Field(default_factory=dict)
    model: Optional[str] = None


class ExternalEndpointTestResponse(APIModel):
    endpoint_id: str
    trace_id: str
    mapped: MappedExternalResponse


class ExternalEndpointRunEvalRequest(APIModel):
    eval_set_id: str = Field(min_length=1)


class ExternalEndpointEvalTrace(APIModel):
    question_id: str
    question: str
    trace_id: str
    evaluation: EvaluationResponse


class ExternalEndpointRunEvalResponse(APIModel):
    endpoint_id: str
    eval_set_id: str
    traces: List[ExternalEndpointEvalTrace] = Field(default_factory=list)
    summary: EvalSetSummary
