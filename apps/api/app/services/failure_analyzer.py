from __future__ import annotations

from typing import Any, Dict, List

from pydantic import BaseModel, Field

from app.judge import LLMJudgeProvider
from app.models import FailureType, Severity
from app.services.structured_json import request_validated_json


class FailureAnalysisResult(BaseModel):
    failure_type: FailureType
    severity: Severity
    root_cause: str = Field(min_length=1)
    suggested_fix: str = Field(min_length=1)


class FailureAnalyzer:
    system_prompt = (
        "You are a RAG reliability failure analyzer. Return only JSON with this schema: "
        "{\"failure_type\":\"no_failure_detected|retrieval_miss|low_relevance_context|"
        "citation_mismatch|unsupported_answer|contradicted_answer|conflicting_sources|"
        "bad_chunking|over_compression|should_have_abstained|query_needs_decomposition|"
        "wrong_tool_used|tool_error|stale_memory_used|missing_memory|excessive_tool_calls|"
        "agent_loop_detected|unknown\","
        "\"severity\":\"none|low|medium|high\","
        "\"root_cause\":\"brief root cause\","
        "\"suggested_fix\":\"actionable fix\"}. "
        "Prefer citation_mismatch when cited evidence does not support cited claims. "
        "Prefer unsupported_answer when the answer makes material claims without supporting citations."
    )

    def __init__(self, provider: LLMJudgeProvider) -> None:
        self.provider = provider

    async def analyze(
        self,
        *,
        query: str,
        chunks: List[Dict[str, Any]],
        selected_context: List[Dict[str, Any]],
        answer: str,
        citation_checks: List[Dict[str, Any]],
    ) -> FailureAnalysisResult:
        try:
            result = await request_validated_json(
                provider=self.provider,
                task="failure_analysis",
                system_prompt=self.system_prompt,
                user_payload={
                    "query": query,
                    "chunks": chunks,
                    "selected_context": selected_context,
                    "answer": answer,
                    "citation_checks": citation_checks,
                },
                response_model=FailureAnalysisResult,
            )
            return result  # type: ignore[return-value]
        except ValueError as exc:
            return FailureAnalysisResult(
                failure_type=FailureType.UNKNOWN,
                severity=Severity.MEDIUM,
                root_cause="Judge returned invalid JSON after retry: %s" % exc,
                suggested_fix="Inspect the judge provider response format and retry evaluation.",
            )
