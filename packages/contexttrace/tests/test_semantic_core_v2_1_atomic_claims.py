from __future__ import annotations

from dataclasses import replace

from contexttrace.verify.schema import RAGTrace, TraceContext
from contexttrace.verify.semantic_core_v2 import verify_trace_v2
from contexttrace.verify.semantic_core_v2_1 import (
    ATOMIC_CLAIM_UNITIZER_VERSION,
    SELECTIVE_V2_1_PROFILE,
    unitize_atomic_claims,
    verify_trace_v2_1,
)


def test_splits_explicit_coordinated_clauses_with_exact_offsets() -> None:
    answer = "The API accepts JSON, but the SDK requires XML."

    claims, limited = unitize_atomic_claims(answer)

    assert not limited
    assert [claim.text for claim in claims] == [
        "The API accepts JSON",
        "the SDK requires XML.",
    ]
    assert [claim.verification_text for claim in claims] == [
        "The API accepts JSON",
        "the SDK requires XML.",
    ]
    for claim in claims:
        assert answer[claim.start_char : claim.end_char] == claim.text
        assert claim.unitizer_version == ATOMIC_CLAIM_UNITIZER_VERSION


def test_reconstructs_shared_subject_without_corrupting_surface_offset() -> None:
    answer = "The policy is current and expires on June 1, 2027."

    claims, _ = unitize_atomic_claims(answer)

    assert [claim.text for claim in claims] == [
        "The policy is current",
        "expires on June 1, 2027.",
    ]
    assert claims[1].verification_text == "The policy expires on June 1, 2027."
    assert answer[claims[1].start_char : claims[1].end_char] == claims[1].text


def test_does_not_split_entity_or_object_lists() -> None:
    claims, _ = unitize_atomic_claims(
        "Research and Development supports Windows, macOS, and Linux."
    )

    assert len(claims) == 1
    assert claims[0].text == (
        "Research and Development supports Windows, macOS, and Linux."
    )


def test_does_not_split_coordinated_product_names_or_participle_modifiers() -> None:
    product, _ = unitize_atomic_claims(
        "DSPy Assert and Suggest can define constraints within a program."
    )
    objects, _ = unitize_atomic_claims(
        "Delete removes embeddings, documents, and metadata associated with IDs."
    )

    assert len(product) == 1
    assert len(objects) == 1


def test_preserves_dotted_identifiers_and_splits_shared_passive_predicates() -> None:
    answer = (
        "An FT.SEARCH query uses index.knn. "
        "The results are merged and reordered using RRF."
    )

    claims, _ = unitize_atomic_claims(answer)

    assert [claim.verification_text for claim in claims] == [
        "An FT.SEARCH query uses index.knn.",
        "The results are merged",
        "The results are reordered using RRF.",
    ]


def test_numbered_lists_do_not_emit_marker_claims() -> None:
    answer = "1. Alpha launched in 2024. 2. Beta launched in 2025."

    claims, _ = unitize_atomic_claims(answer)

    assert [claim.text for claim in claims] == [
        "Alpha launched in 2024.",
        "Beta launched in 2025.",
    ]


def test_preserves_unicode_offsets_and_removes_inline_citation_for_verification() -> (
    None
):
    answer = (
        "• Café access requires an ID [policy-v3].\n• Résumés are retained 30 days."
    )

    claims, _ = unitize_atomic_claims(answer)

    assert len(claims) == 2
    assert claims[0].verification_text == "Café access requires an ID."
    for claim in claims:
        assert answer[claim.start_char : claim.end_char] == claim.text


def test_claim_bound_is_reported_after_atomic_expansion() -> None:
    claims, limited = unitize_atomic_claims(
        "The API accepts JSON, but the SDK requires XML.",
        max_claims=1,
    )

    assert limited
    assert len(claims) == 1


def test_v2_1_uses_atomic_claims_but_frozen_v2_remains_unchanged() -> None:
    trace = RAGTrace(
        query="What formats are accepted?",
        answer="The API accepts JSON, but the SDK requires XML.",
        contexts=[
            TraceContext(
                id="formats",
                text="The API accepts JSON.",
                metadata={"canonical": True, "current": True},
            )
        ],
    )

    frozen = verify_trace_v2(trace)
    atomic = verify_trace_v2_1(trace)

    assert len(frozen["claims"]) == 1
    assert frozen["claims"][0]["unitizer_version"] == "claim-unitizer-v2.0.0"
    assert len(atomic["claims"]) == 2
    assert {claim["unitizer_version"] for claim in atomic["claims"]} == {
        ATOMIC_CLAIM_UNITIZER_VERSION
    }
    assert atomic["summary"]["overall_status"] != "green"


def test_atomic_unitization_can_be_disabled_by_hash_identified_profile() -> None:
    profile = replace(
        SELECTIVE_V2_1_PROFILE,
        id="v2_1_legacy_unitizer_test",
        atomic_claim_unitization=False,
    )
    trace = RAGTrace(
        query="What formats are accepted?",
        answer="The API accepts JSON, but the SDK requires XML.",
        contexts=[TraceContext(id="formats", text="The API accepts JSON.")],
    )

    result = verify_trace_v2_1(trace, profile=profile)

    assert len(result["claims"]) == 1
    assert result["verification_profile"]["atomic_claim_unitization"] is False
