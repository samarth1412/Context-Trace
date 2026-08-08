from __future__ import annotations

from dataclasses import replace

from contexttrace.verify.schema import RAGTrace, TraceContext
from contexttrace.verify.semantic_core_v2_1 import (
    EVIDENCE_ATTRIBUTION_VERSION,
    SELECTIVE_V2_1_PROFILE,
    verify_trace_v2_1,
)


def _verify(answer: str, *contexts: TraceContext):
    return verify_trace_v2_1(
        RAGTrace(
            query="What does the evidence establish?",
            answer=answer,
            contexts=list(contexts),
        )
    )["claims"][0]


def _context(context_id: str, text: str) -> TraceContext:
    return TraceContext(
        id=context_id,
        text=text,
        metadata={"canonical": True, "current": True},
    )


def test_selects_minimal_exact_support_span_without_neighboring_noise() -> None:
    context = _context(
        "policy",
        "General account information. The refund window is 30 days. Contact support.",
    )

    claim = _verify("The refund window is 30 days.", context)

    assert claim["evidence_spans"] == [
        {
            "context_id": "policy",
            "start_char": 29,
            "end_char": 58,
            "text": "The refund window is 30 days.",
            "role": "supporting",
            "span_hash": claim["evidence_spans"][0]["span_hash"],
        }
    ]
    span = claim["evidence_spans"][0]
    assert context.text[span["start_char"] : span["end_char"]] == span["text"]


def test_selects_two_complementary_spans_for_one_atomic_claim() -> None:
    claim = _verify(
        "Refund requests require an unopened item within 30 days.",
        _context(
            "returns",
            "Refund requests require an unopened item. "
            "Requests must be submitted within 30 days. Contact support for help.",
        ),
    )

    assert claim["claim_verdict"] == "supported"
    assert [span["text"] for span in claim["evidence_spans"]] == [
        "Refund requests require an unopened item.",
        "Requests must be submitted within 30 days.",
    ]
    record = claim["deterministic"]["signals"]["evidence_attribution"]
    assert record["version"] == EVIDENCE_ATTRIBUTION_VERSION
    assert record["selected_span_count"] == 2
    assert record["claim_term_coverage"] == 1.0


def test_links_one_claim_to_complementary_spans_in_two_documents() -> None:
    claim = _verify(
        "The release requires security approval within 24 hours.",
        _context("policy", "The release requires security approval."),
        _context("sla", "Release approval must occur within 24 hours."),
    )

    assert claim["claim_verdict"] == "supported"
    assert claim["evidence_context_ids"] == ["policy", "sla"]
    record = claim["deterministic"]["signals"]["evidence_attribution"]
    assert record["document_count"] == 2
    assert record["supporting_span_count"] == 2


def test_contradiction_returns_exact_refuting_span_instead_of_decoy() -> None:
    context = _context(
        "refunds",
        "General refund information. The refund window is 30 days. Contact support.",
    )

    claim = _verify("The refund window is 90 days.", context)

    assert claim["claim_verdict"] == "contradicted"
    assert [(span["text"], span["role"]) for span in claim["evidence_spans"]] == [
        ("The refund window is 30 days.", "contradicting")
    ]
    record = claim["deterministic"]["signals"]["evidence_attribution"]
    assert record["contradicting_span_count"] == 1
    assert record["supporting_span_count"] == 0


def test_duplicate_refuting_documents_do_not_create_redundant_spans() -> None:
    claim = _verify(
        "The refund window is 90 days.",
        _context("primary", "The refund window is 30 days."),
        _context("duplicate", "The refund window is 30 days."),
    )

    assert [(span["context_id"], span["role"]) for span in claim["evidence_spans"]] == [
        ("primary", "contradicting")
    ]


def test_unsupported_claim_does_not_emit_unrelated_supporting_span() -> None:
    claim = _verify(
        "The enterprise retention period is seven years.",
        _context("pricing", "Account owners can update a billing address."),
    )

    assert claim["claim_verdict"] == "unsupported"
    assert claim["evidence_spans"] == []
    assert claim["evidence_context_ids"] == []


def test_unicode_source_and_answer_offsets_remain_exact() -> None:
    answer = "Café access requires résumé approval."
    context = _context("unicode", f"Préface. {answer} Après.")

    claim = _verify(answer, context)
    span = claim["evidence_spans"][0]

    assert context.text[span["start_char"] : span["end_char"]] == span["text"]
    assert answer[claim["start_char"] : claim["end_char"]] == claim["text"]


def test_attribution_is_bounded_to_schema_maximum() -> None:
    claim = _verify(
        "The release requires approval, encryption, logging, and monitoring.",
        _context(
            "controls",
            "The release requires approval. The release uses encryption. "
            "The release enables logging. The release includes monitoring.",
        ),
    )

    assert len(claim["evidence_spans"]) <= 3
    record = claim["deterministic"]["signals"]["evidence_attribution"]
    assert record["selected_span_count"] <= 3


def test_attribution_can_be_disabled_by_hash_identified_profile() -> None:
    profile = replace(
        SELECTIVE_V2_1_PROFILE,
        id="v2_1_no_hierarchical_evidence_test",
        hierarchical_evidence_attribution=False,
    )
    result = verify_trace_v2_1(
        RAGTrace(
            query="What is the refund window?",
            answer="The refund window is 30 days.",
            contexts=[_context("refunds", "The refund window is 30 days.")],
        ),
        profile=profile,
    )

    signals = result["claims"][0]["deterministic"]["signals"]
    assert "evidence_attribution" not in signals
    assert result["verification_profile"]["hierarchical_evidence_attribution"] is False
