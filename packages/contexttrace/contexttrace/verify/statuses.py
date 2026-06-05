from __future__ import annotations

from typing import Any

from contexttrace.verify.root_cause import CONFLICTING_CONTEXTS, MISSING_CITED_SOURCE, STALE_CONTEXT
from contexttrace.verify.source_trust import (
    GROUNDED_BUT_CONFLICTED,
    GROUNDED_BUT_STALE,
    GROUNDED_BY_LOW_AUTHORITY_SOURCE,
    SUPPORTED_BY_CANONICAL_SOURCE,
)
from contexttrace.verify.schema import RAGTrace


TRUTH_NOT_ASSESSED = "not_assessed"
SOURCE_FRESHNESS_UNKNOWN = "freshness_unknown"


def attach_grounding_statuses(
    claims: list[dict[str, Any]],
    trace: RAGTrace,
) -> list[dict[str, Any]]:
    contexts_by_id = {context.id: context for context in trace.contexts}
    return [
        {
            **claim,
            "support_status": support_status(claim),
            "truth_status": truth_status(claim),
            "source_status": source_status(claim, contexts_by_id),
            "status_note": status_note(claim),
        }
        for claim in claims
    ]


def support_status(claim: dict[str, Any]) -> str:
    verdict = _string(claim.get("verdict"))
    has_span = isinstance(claim.get("evidence_span"), dict)
    if verdict == "supported":
        return "grounded_by_span" if has_span else "grounded_without_span"
    if verdict == "partially_supported":
        return "partially_grounded_by_span" if has_span else "partially_grounded"
    if verdict == "contradicted":
        return "contradicted_by_evidence"
    if verdict == "unsupported":
        return "unsupported_by_retrieved_context"
    if verdict == "unverifiable":
        return "insufficient_evidence"
    return "unknown"


def truth_status(claim: dict[str, Any]) -> str:
    explicit = _string(claim.get("truth_status"))
    return explicit or TRUTH_NOT_ASSESSED


def source_status(claim: dict[str, Any], contexts_by_id: dict[str, Any]) -> str:
    explicit_claim_status = _string(claim.get("source_status"))
    if explicit_claim_status:
        return explicit_claim_status

    root_label = _string((claim.get("root_cause") or {}).get("label"))
    if root_label == STALE_CONTEXT:
        return GROUNDED_BUT_STALE
    if root_label == CONFLICTING_CONTEXTS:
        return GROUNDED_BUT_CONFLICTED
    if root_label == MISSING_CITED_SOURCE:
        return "cited_source_missing"

    context_id = _string(claim.get("best_context_id"))
    if not context_id:
        return "no_source"

    metadata = getattr(contexts_by_id.get(context_id), "metadata", {}) or {}
    explicit = _string(metadata.get("source_status"))
    if explicit:
        return explicit
    freshness = _string(metadata.get("freshness") or metadata.get("freshness_status"))
    if freshness:
        return freshness
    if bool(metadata.get("stale")):
        return "stale_source"
    return SOURCE_FRESHNESS_UNKNOWN


def status_note(claim: dict[str, Any]) -> str:
    source = source_status(claim, {})
    if source == GROUNDED_BUT_CONFLICTED:
        return (
            "The selected evidence grounds the claim, but another retrieved source appears to conflict. "
            "Resolve source authority or freshness before treating it as reliable."
        )
    if source == GROUNDED_BUT_STALE:
        return (
            "The selected evidence grounds the claim, but the source appears stale or superseded. "
            "Grounded is not the same as current."
        )
    if source == GROUNDED_BY_LOW_AUTHORITY_SOURCE:
        return (
            "The selected evidence grounds the claim, but source authority is low. "
            "Prefer canonical or higher-trust evidence."
        )
    if source == SUPPORTED_BY_CANONICAL_SOURCE:
        return (
            "The claim is grounded by selected evidence from a canonical or high-authority source. "
            "This still does not certify independent real-world truth."
        )
    if support_status(claim) == "grounded_by_span":
        return (
            "Grounded means the claim is supported by the selected evidence span. "
            "It does not mean the source is independently true, current, or authoritative."
        )
    return (
        "ContextTrace checks whether provided evidence grounds the claim; it does not certify "
        "independent truth."
    )


def _string(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()
