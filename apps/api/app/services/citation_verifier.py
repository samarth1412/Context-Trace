from __future__ import annotations

from pydantic import BaseModel, Field

from app.judge import LLMJudgeProvider
from app.models import CitationVerdict
from app.services.structured_json import request_validated_json


class CitationVerificationResult(BaseModel):
    verdict: CitationVerdict
    support_score: float = Field(ge=0.0, le=1.0)
    reason: str = Field(min_length=1)


class CitationVerifier:
    system_prompt = (
        "You are a strict RAG citation verifier. Given one claim and one source chunk, "
        "return only JSON with this schema: "
        "{\"verdict\":\"directly_supported|partially_supported|unsupported|contradicted|not_enough_info\","
        "\"support_score\":0.0,\"reason\":\"brief explanation\"}. "
        "Use directly_supported only when the source explicitly supports the claim. "
        "Use contradicted when the source conflicts with the claim."
    )

    def __init__(self, provider: LLMJudgeProvider) -> None:
        self.provider = provider

    async def verify(self, *, claim: str, source_chunk_text: str) -> CitationVerificationResult:
        try:
            result = await request_validated_json(
                provider=self.provider,
                task="citation_verification",
                system_prompt=self.system_prompt,
                user_payload={
                    "claim": claim,
                    "source_chunk_text": source_chunk_text,
                },
                response_model=CitationVerificationResult,
            )
            return result  # type: ignore[return-value]
        except ValueError as exc:
            return CitationVerificationResult(
                verdict=CitationVerdict.NOT_ENOUGH_INFO,
                support_score=0.0,
                reason="Judge returned invalid JSON after retry: %s" % exc,
            )
