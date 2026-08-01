from __future__ import annotations

from contexttrace.verify.schema import RAGTrace, TraceContext
from contexttrace.verify.semantic_core_v2 import verify_trace_v2
from contexttrace.verify.semantic_core_v2_1 import (
    SELECTIVE_V2_1_PROFILE,
    assess_source_condition_v2_1,
    verify_trace_v2_1,
)


def _assess(
    selected: TraceContext,
    *others: TraceContext,
    claim: str = "The API timeout is 60 seconds.",
):
    return assess_source_condition_v2_1(
        best_context_id=selected.id,
        claim=claim,
        trace=RAGTrace(
            query="What is the current API timeout?",
            answer=claim,
            contexts=[selected, *others],
        ),
        profile=SELECTIVE_V2_1_PROFILE,
    )


def test_explicit_stale_flag_outranks_inconsistent_current_label() -> None:
    result = _assess(
        TraceContext(
            id="old",
            text="The API timeout is 60 seconds.",
            metadata={"source_condition": "current_canonical", "stale": True},
        )
    )

    assert result["condition"] == "stale"
    assert result["reason_code"] == "explicit_stale_metadata"


def test_string_boole_are_parsed_without_truthiness_errors() -> None:
    result = _assess(
        TraceContext(
            id="copy",
            text="The API timeout is 60 seconds.",
            metadata={"canonical": "false", "current": "true"},
        )
    )

    assert result["condition"] == "current_noncanonical"
    assert result["observables"]["canonical"] is False


def test_explicit_replacement_relation_marks_selected_source_superseded() -> None:
    old = TraceContext(
        id="old",
        text="The API timeout is 60 seconds.",
        metadata={"source_version": "1.0"},
    )
    current = TraceContext(
        id="current",
        text="The API timeout is 30 seconds.",
        metadata={"source_version": "2.0", "replaces": "old"},
    )

    result = _assess(old, current)

    assert result["condition"] == "superseded"
    assert result["related_sources"][0]["context_id"] == "current"


def test_newer_related_conflicting_version_marks_selected_source_superseded() -> None:
    old = TraceContext(
        id="old",
        text="The API timeout is 60 seconds.",
        metadata={
            "source_family": "api-timeout",
            "source_version": "1.0",
            "canonical": True,
        },
    )
    current = TraceContext(
        id="current",
        text="The API timeout is 30 seconds.",
        metadata={
            "source_family": "api-timeout",
            "source_version": "2.0",
            "canonical": True,
        },
    )

    result = _assess(old, current)

    assert result["condition"] == "superseded"
    assert result["reason_code"] == "newer_related_source_conflicts_with_claim"


def test_newer_related_nonconflicting_source_marks_selected_source_stale() -> None:
    old = TraceContext(
        id="old",
        text="The API timeout is 60 seconds.",
        metadata={"source_group": "api", "published_at": "2025-01-01"},
    )
    current = TraceContext(
        id="current",
        text="The API timeout remains 60 seconds.",
        metadata={"source_group": "api", "published_at": "2026-01-01"},
    )

    result = _assess(old, current)

    assert result["condition"] == "stale"
    assert result["reason_code"] == "newer_related_source_observed"


def test_mixed_iso_timezone_forms_compare_safely() -> None:
    old = TraceContext(
        id="old",
        text="The API timeout is 60 seconds.",
        metadata={"source_group": "api", "published_at": "2025-01-01"},
    )
    current = TraceContext(
        id="current",
        text="The API timeout remains 60 seconds.",
        metadata={"source_group": "api", "published_at": "2026-01-01T00:00:00Z"},
    )

    assert _assess(old, current)["condition"] == "stale"


def test_authoritative_observable_conflict_is_not_silently_green() -> None:
    first = TraceContext(
        id="policy-a",
        text="The filing deadline is September 1.",
        metadata={"source_authority": "official", "current": True},
    )
    second = TraceContext(
        id="policy-b",
        text="The filing deadline is October 1.",
        metadata={"source_authority": "regulator", "current": True},
    )

    result = _assess(
        first,
        second,
        claim="The filing deadline is September 1.",
    )

    assert result["condition"] == "conflicting_authorities"
    assert result["reason_code"] == "authoritative_sources_observably_conflict"


def test_authority_label_can_expose_low_authority_without_numeric_score() -> None:
    result = _assess(
        TraceContext(
            id="summary",
            text="The API timeout is 60 seconds.",
            metadata={"source_authority": "summary"},
        )
    )

    assert result["condition"] == "low_authority"
    assert result["observables"]["authority_score"] == 0.25


def test_unrelated_newer_source_does_not_create_staleness() -> None:
    selected = TraceContext(
        id="api",
        text="The API timeout is 60 seconds.",
        metadata={
            "source_family": "api",
            "source_version": "1.0",
            "canonical": True,
        },
    )
    unrelated = TraceContext(
        id="policy",
        text="The filing deadline is October 1.",
        metadata={
            "source_family": "policy",
            "source_version": "9.0",
            "canonical": True,
        },
    )

    assert _assess(selected, unrelated)["condition"] == "current_canonical"


def test_v2_1_updates_diagnosis_summary_without_changing_frozen_v2() -> None:
    trace = RAGTrace(
        query="What is the current API timeout?",
        answer="The API timeout is 60 seconds.",
        contexts=[
            TraceContext(
                id="old",
                text="The API timeout is 60 seconds.",
                metadata={
                    "source_family": "api",
                    "source_version": "1.0",
                    "canonical": True,
                },
            ),
            TraceContext(
                id="current",
                text="The API timeout is 30 seconds.",
                metadata={
                    "source_family": "api",
                    "source_version": "2.0",
                    "canonical": True,
                },
            ),
        ],
    )

    frozen = verify_trace_v2(trace)
    candidate = verify_trace_v2_1(trace)

    assert frozen["claims"][0]["source_condition"] == "current_canonical"
    assert candidate["claims"][0]["source_condition"] == "superseded"
    assert candidate["claims"][0]["failure_label"] == "source_condition_failure"
    assert candidate["summary"]["failure_labels"] == {"source_condition_failure": 1}
    assert candidate["summary"]["root_causes"] == {"stale_or_superseded_source": 1}
    assert candidate["claims"][0]["green"] is False
    assert (
        "text" not in candidate["claims"][0]["source_assessment"]["related_sources"][0]
    )
