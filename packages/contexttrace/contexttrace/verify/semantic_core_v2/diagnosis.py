"""Frozen failure-label, observable-root, abstention, and green policy."""

from __future__ import annotations

import re
from typing import Any

from contexttrace.verify.schema import RAGTrace

from .profile import V2Profile


_DANGEROUS_SOURCE = {
    "current_noncanonical",
    "stale",
    "superseded",
    "low_authority",
    "conflicting_authorities",
}
_CITATION_ERRORS = {"partial", "wrong_source", "missing", "malformed"}


def diagnose(
    *,
    verdict: str,
    confidence: float,
    route: str,
    abstained: bool,
    citation_state: str,
    source_condition: str,
    trace: RAGTrace,
    profile: V2Profile,
) -> dict[str, Any]:
    metadata = dict(trace.metadata or {})
    unsafe_source = source_condition in _DANGEROUS_SOURCE

    if unsafe_source and verdict == "supported":
        failure = "source_condition_failure"
        root = (
            "stale_or_superseded_source"
            if source_condition in {"stale", "superseded"}
            else "noncanonical_or_low_authority_source"
            if source_condition in {"current_noncanonical", "low_authority"}
            else "conflicting_contexts"
        )
        requirement = (
            "must_abstain"
            if source_condition == "conflicting_authorities"
            else "may_answer_with_qualification"
        )
    elif citation_state in _CITATION_ERRORS:
        failure = "citation_mismatch"
        root = "citation_mismatch"
        requirement = "may_answer_with_qualification"
    elif verdict == "contradicted":
        failure = "contradiction"
        root = (
            "conflicting_contexts"
            if source_condition == "conflicting_authorities"
            else "answer_overreach"
        )
        requirement = "must_abstain"
    elif verdict == "partially_supported":
        failure = "answer_overreach"
        root = "answer_overreach"
        requirement = "may_answer_with_qualification"
    elif verdict == "unsupported":
        failure, root = _unsupported_diagnosis(metadata)
        requirement = "must_abstain"
    elif verdict == "unverifiable" or abstained:
        failure = "insufficient_evidence"
        root = _insufficient_root(metadata)
        requirement = "must_abstain"
    else:
        failure = "none"
        root = "none"
        requirement = "must_answer"

    if requirement == "must_abstain" and not _answer_is_abstention(trace.answer):
        failure = "should_have_abstained"
        if root == "not_observable":
            root = "failure_to_abstain"

    diagnostic_confidence = round(float(confidence), 6)
    green = bool(
        not abstained
        and verdict == "supported"
        and failure == "none"
        and citation_state in {"correct", "not_applicable"}
        and source_condition in {"current_canonical", "unknown"}
        and diagnostic_confidence >= profile.thresholds.green_confidence
    )
    qualification_required = bool(
        requirement == "may_answer_with_qualification"
        or source_condition in {"current_noncanonical", "unknown"}
    )
    if qualification_required:
        green = False

    return {
        "failure_label": failure,
        "primary_root_cause": root,
        "abstention_requirement": requirement,
        "diagnostic_confidence": diagnostic_confidence,
        "confidence_semantics": "estimated_probability_that_the_emitted_diagnosis_is_correct",
        "green": green,
        "qualification_required": qualification_required,
        "route": route,
    }


def _unsupported_diagnosis(metadata: dict[str, Any]) -> tuple[str, str]:
    if metadata.get("eligible_evidence_in_retrieved_candidates") is True:
        if metadata.get("reranking_enabled") is True:
            return "context_selection_error", "reranking_failure"
        return "context_selection_error", "insufficient_selected_context"
    if metadata.get("eligible_evidence_in_corpus") is True:
        return "retrieval_miss", "retrieval_miss"
    if metadata.get("eligible_evidence_in_corpus") is False:
        return "insufficient_evidence", "corpus_gap"
    if metadata.get("chunking_destroyed_relation") is True:
        return "context_selection_error", "chunking_issue"
    return "insufficient_evidence", "not_observable"


def _insufficient_root(metadata: dict[str, Any]) -> str:
    if metadata.get("eligible_evidence_in_corpus") is False:
        return "corpus_gap"
    if metadata.get("chunking_destroyed_relation") is True:
        return "chunking_issue"
    return "not_observable"


def _answer_is_abstention(answer: str) -> bool:
    return bool(
        re.search(
            r"\b(?:cannot|can't|unable to|insufficient (?:context|evidence)|"
            r"not enough (?:context|information)|do not know|don't know|"
            r"cannot determine|can't determine)\b",
            str(answer or ""),
            flags=re.IGNORECASE,
        )
    )
