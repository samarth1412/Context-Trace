from __future__ import annotations

from collections import Counter
from typing import Any


NO_FAILURE = "no_failure_detected"
RETRIEVAL_MISS = "retrieval_miss"
ANSWER_OVERREACH = "answer_overreach"
PARTIAL_CONTEXT_SUPPORT = "partial_context_support"
WRONG_SOURCE_CITED = "wrong_source_cited"
MISSING_CITED_SOURCE = "missing_cited_source"
CONFLICTING_CONTEXTS = "conflicting_contexts"
STALE_CONTEXT = "stale_context"
LOW_AUTHORITY_SOURCE = "low_authority_source"
INSUFFICIENT_CONTEXT = "insufficient_context"
SHOULD_HAVE_ABSTAINED = "should_have_abstained"


def attach_root_causes(
    claims: list[dict[str, Any]],
    abstention: dict[str, Any],
) -> list[dict[str, Any]]:
    return [
        {
            **claim,
            "root_cause": diagnose_claim(claim, abstention),
        }
        for claim in claims
    ]


def root_cause_summary(claims: list[dict[str, Any]]) -> dict[str, int]:
    counts = Counter(
        str((claim.get("root_cause") or {}).get("label") or NO_FAILURE)
        for claim in claims
    )
    return {key: counts[key] for key in sorted(counts)}


def primary_root_cause(claims: list[dict[str, Any]]) -> str:
    counts = root_cause_summary(claims)
    failures = {key: value for key, value in counts.items() if key != NO_FAILURE}
    if not failures:
        return NO_FAILURE
    priority = [
        SHOULD_HAVE_ABSTAINED,
        CONFLICTING_CONTEXTS,
        STALE_CONTEXT,
        LOW_AUTHORITY_SOURCE,
        RETRIEVAL_MISS,
        ANSWER_OVERREACH,
        PARTIAL_CONTEXT_SUPPORT,
        WRONG_SOURCE_CITED,
        MISSING_CITED_SOURCE,
        INSUFFICIENT_CONTEXT,
    ]
    return max(
        failures,
        key=lambda label: (
            failures[label],
            -priority.index(label) if label in priority else -len(priority),
        ),
    )


def diagnose_claim(claim: dict[str, Any], abstention: dict[str, Any]) -> dict[str, Any]:
    verdict = _string(claim.get("verdict"))
    citation_status = _string(claim.get("citation_status"))
    missing_fact = _first_fact(claim.get("missing_fact_details") or claim.get("missing_facts") or [])
    conflicting_fact_values = claim.get("conflicting_fact_details") or claim.get("conflicting_facts") or []
    conflicting_fact = _first_fact(conflicting_fact_values)
    closest_context_id = _string(claim.get("best_context_id")) or None
    closest_evidence = _string(claim.get("evidence")) or None
    source_status = _string(claim.get("source_status"))
    source_assessment = claim.get("source_assessment") if isinstance(claim.get("source_assessment"), dict) else {}

    if verdict == "supported" and source_status == "grounded_but_conflicted":
        conflict = _first_source_signal(source_assessment.get("stronger_conflicting_sources") or source_assessment.get("conflicting_sources") or [])
        return _diagnosis(
            label=CONFLICTING_CONTEXTS,
            reason=(
                "The claim is grounded by %s, but conflicting evidence was found in %s."
                % (closest_context_id or "the selected source", _string(conflict.get("context_id")) or "another source")
            ),
            suggested_fix="Resolve source authority, freshness, or canonical-source precedence before treating this grounded claim as reliable.",
            missing_fact=_string(claim.get("claim")),
            closest_context_id=closest_context_id,
            closest_evidence=closest_evidence,
        )

    if verdict == "supported" and source_status == "grounded_but_stale":
        newer = _first_source_signal(source_assessment.get("newer_related_sources") or [])
        reason = "The claim is grounded, but the supporting source appears stale or explicitly marked stale."
        if newer:
            reason = (
                "The claim is grounded by %s, but newer related source %s was also retrieved."
                % (closest_context_id or "the selected source", _string(newer.get("context_id")) or "another source")
            )
        return _diagnosis(
            label=STALE_CONTEXT,
            reason=reason,
            suggested_fix="Refresh the source or prefer the newer canonical source before generation.",
            missing_fact=_string(claim.get("claim")),
            closest_context_id=closest_context_id,
            closest_evidence=closest_evidence,
        )

    if verdict == "supported" and source_status == "grounded_by_low_authority_source":
        return _diagnosis(
            label=LOW_AUTHORITY_SOURCE,
            reason="The claim is grounded, but the supporting source is low authority.",
            suggested_fix="Prefer canonical or higher-authority evidence, or expose lower confidence to the user.",
            missing_fact=_string(claim.get("claim")),
            closest_context_id=closest_context_id,
            closest_evidence=closest_evidence,
        )

    if citation_status == "claim_supported_by_different_source":
        return _diagnosis(
            label=WRONG_SOURCE_CITED,
            reason=(
                "The claim is supported by %s, but the supplied citation points to %s."
                % (_string(claim.get("best_context_id")) or "another source", _string(claim.get("citation_source_id")) or "none")
            ),
            suggested_fix="Cite the source that actually supports this claim, or regenerate citations after retrieval.",
            missing_fact=missing_fact,
            closest_context_id=closest_context_id,
            closest_evidence=closest_evidence,
        )

    if citation_status == "cited_source_missing":
        return _diagnosis(
            label=MISSING_CITED_SOURCE,
            reason="The answer cites a source ID that was not present in the retrieved contexts.",
            suggested_fix="Preserve retrieved source IDs through generation and reject citations that are not in the trace.",
            missing_fact=missing_fact,
            closest_context_id=closest_context_id,
            closest_evidence=closest_evidence,
        )

    if verdict == "contradicted":
        label = STALE_CONTEXT if _looks_stale_fact(conflicting_fact_values) else CONFLICTING_CONTEXTS
        return _diagnosis(
            label=label,
            reason=(
                "The retrieved evidence conflicts with the claim%s."
                % (" on %s" % conflicting_fact if conflicting_fact else "")
            ),
            suggested_fix="Resolve stale or conflicting retrieved sources before allowing the generator to answer.",
            missing_fact=missing_fact or conflicting_fact,
            closest_context_id=closest_context_id,
            closest_evidence=closest_evidence,
        )

    if verdict == "unsupported":
        if bool(abstention.get("should_abstain")):
            return _diagnosis(
                label=SHOULD_HAVE_ABSTAINED,
                reason="The answer made a factual claim without retrieved evidence that supports it.",
                suggested_fix="Return an unavailable/insufficient-context answer unless retrieval returns evidence for the missing fact.",
                missing_fact=missing_fact or _string(claim.get("claim")),
                closest_context_id=closest_context_id,
                closest_evidence=closest_evidence,
            )
        return _diagnosis(
            label=RETRIEVAL_MISS,
            reason="No retrieved context contains enough evidence for this claim.",
            suggested_fix="Improve retrieval, filters, chunking, or reranking so a source with the missing fact is retrieved.",
            missing_fact=missing_fact or _string(claim.get("claim")),
            closest_context_id=closest_context_id,
            closest_evidence=closest_evidence,
        )

    if verdict == "partially_supported":
        return _diagnosis(
            label=ANSWER_OVERREACH if missing_fact else PARTIAL_CONTEXT_SUPPORT,
            reason=(
                "The retrieved evidence supports part of the claim, but not %s."
                % missing_fact
                if missing_fact
                else "The retrieved evidence supports only part of the claim."
            ),
            suggested_fix="Remove the unsupported detail or retrieve a source that explicitly supports it.",
            missing_fact=missing_fact,
            closest_context_id=closest_context_id,
            closest_evidence=closest_evidence,
        )

    if verdict == "unverifiable":
        return _diagnosis(
            label=INSUFFICIENT_CONTEXT,
            reason="The closest retrieved context overlaps with the claim but is too weak or ambiguous.",
            suggested_fix="Retrieve more specific context or require the answer to qualify the claim.",
            missing_fact=missing_fact,
            closest_context_id=closest_context_id,
            closest_evidence=closest_evidence,
        )

    if citation_status == "cited_source_does_not_support_claim":
        return _diagnosis(
            label=WRONG_SOURCE_CITED,
            reason="The cited source does not support the claim, even though the claim itself may be supportable.",
            suggested_fix="Choose citations after claim verification, not from raw generation text.",
            missing_fact=missing_fact,
            closest_context_id=closest_context_id,
            closest_evidence=closest_evidence,
        )

    return _diagnosis(
        label=NO_FAILURE,
        reason="The claim is supported by retrieved evidence and no citation failure was detected.",
        suggested_fix="No fix needed for this claim.",
        missing_fact=None,
        closest_context_id=closest_context_id,
        closest_evidence=closest_evidence,
    )


def _diagnosis(
    *,
    label: str,
    reason: str,
    suggested_fix: str,
    missing_fact: str | None,
    closest_context_id: str | None,
    closest_evidence: str | None,
) -> dict[str, object]:
    return {
        "label": label,
        "reason": reason,
        "missing_fact": missing_fact,
        "closest_context_id": closest_context_id,
        "closest_evidence": closest_evidence,
        "suggested_fix": suggested_fix,
    }


def _first_fact(facts: list[Any]) -> str | None:
    for fact in facts:
        if isinstance(fact, dict):
            value = _string(fact.get("text"))
        else:
            value = _string(fact)
        if value:
            return value
    return None


def _looks_stale_fact(facts: list[Any]) -> bool:
    for fact in facts:
        if isinstance(fact, dict) and _string(fact.get("type")) == "version":
            return True
        value = _string(fact).lower()
        if value.startswith("v") and any(char.isdigit() for char in value):
            return True
    return False


def _first_source_signal(signals: list[Any]) -> dict[str, Any]:
    for signal in signals:
        if isinstance(signal, dict):
            return signal
    return {}


def _string(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()
