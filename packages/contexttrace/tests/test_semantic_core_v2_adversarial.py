from __future__ import annotations

from contexttrace.verify.schema import RAGTrace, TraceCitation, TraceContext
from contexttrace.verify.semantic_core_v2 import (
    DETERMINISTIC_ONLY_V2_PROFILE,
    V2Limits,
    verify_trace_v2,
)


def _verify(answer: str, context: str, *, metadata: dict | None = None):
    return verify_trace_v2(
        RAGTrace(
            query="What does the policy say?",
            answer=answer,
            contexts=[
                TraceContext(
                    id="c1",
                    text=context,
                    metadata=metadata or {"canonical": True, "current": True},
                )
            ],
        ),
        profile=DETERMINISTIC_ONLY_V2_PROFILE,
    )


def test_numeric_conflict_is_not_false_green() -> None:
    claim = _verify(
        "Refunds are available for 90 days.",
        "Refunds are available for 30 days.",
    )["claims"][0]
    assert claim["claim_verdict"] == "contradicted"
    assert claim["green"] is False


def test_negation_conflict_is_not_false_green() -> None:
    claim = _verify(
        "Administrators may export private keys.",
        "Administrators may not export private keys.",
    )["claims"][0]
    assert claim["claim_verdict"] != "supported"
    assert claim["green"] is False


def test_lexical_decoy_never_receives_high_confidence_green() -> None:
    claim = _verify(
        "The service permanently deletes audit logs every day.",
        "The service audit page describes how users can view daily logs.",
    )["claims"][0]
    assert claim["green"] is False
    if claim["claim_verdict"] == "supported":
        assert claim["diagnostic_confidence"] < 0.9


def test_malformed_citation_is_reported_separately() -> None:
    answer = "Refunds are available for 30 days."
    result = verify_trace_v2(
        RAGTrace(
            query="What is the refund window?",
            answer=answer,
            contexts=[
                TraceContext(
                    id="c1",
                    text=answer,
                    metadata={"canonical": True, "current": True},
                )
            ],
            citations=[TraceCitation(claim=answer, source_id="missing-source")],
            metadata={"citation_required": True},
        )
    )
    claim = result["claims"][0]
    assert claim["claim_verdict"] == "supported"
    assert claim["citation_state"] == "malformed"
    assert claim["failure_label"] == "citation_mismatch"


def test_oversized_payload_is_bounded_and_never_green() -> None:
    result = verify_trace_v2(
        RAGTrace(
            query="q" * 100,
            answer=("Refunds are available. " * 20),
            contexts=[
                TraceContext(id=f"c{i}", text="Refunds are available. " * 20)
                for i in range(6)
            ],
        ),
        profile=DETERMINISTIC_ONLY_V2_PROFILE,
        limits=V2Limits(
            max_query_chars=32,
            max_answer_chars=80,
            max_contexts=2,
            max_context_chars=64,
            max_total_context_chars=96,
            max_claims=2,
        ),
    )
    assert result["truncation"]["applied"] is True
    assert result["truncation"]["contexts_used"] <= 2
    assert len(result["claims"]) <= 2
    assert all(claim["green"] is False for claim in result["claims"])


class ExplodingNLI:
    def verify_claim(self, *, query, claim, contexts):
        del query, claim, contexts
        raise RuntimeError("secret-path=/private/labels.json")


def test_nli_failure_is_fail_closed_and_does_not_leak_exception_text() -> None:
    result = verify_trace_v2(
        RAGTrace(
            query="What remedy applies?",
            answer="Defective items qualify for a replacement.",
            contexts=[
                TraceContext(
                    id="c1",
                    text="The policy discusses defective products and available remedies.",
                )
            ],
        ),
        nli=ExplodingNLI(),
    )
    serialized = str(result)
    assert "secret-path" not in serialized
    claim = result["claims"][0]
    assert claim["diagnostic_abstention"] is True
    assert claim["nli_error_code"] == "nli_runtime_failure"


def test_source_metadata_secret_is_not_copied_to_prediction() -> None:
    result = _verify(
        "Refunds are available for 30 days.",
        "Refunds are available for 30 days.",
        metadata={
            "canonical": True,
            "current": True,
            "api_token": "pypi-secret-value",
            "private_path": "/private/gold.json",
        },
    )
    serialized = str(result)
    assert "pypi-secret-value" not in serialized
    assert "/private/gold.json" not in serialized
