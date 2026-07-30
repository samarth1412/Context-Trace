"""Citation-state assessment kept separate from support and source condition."""

from __future__ import annotations

from contexttrace.verify.citations import find_citation_for_claim
from contexttrace.verify.claims import Claim
from contexttrace.verify.evidence import find_best_evidence
from contexttrace.verify.schema import RAGTrace
from contexttrace.verify.verdicts import classify_claim

from .claims import ClaimUnit
from .profile import V2Profile


def assess_citation(
    *,
    claim: ClaimUnit,
    verdict: str,
    best_context_id: str | None,
    trace: RAGTrace,
    profile: V2Profile,
) -> dict[str, object]:
    if not profile.citation_features:
        return _record("not_applicable", None, "citation_features_disabled")

    required = bool(trace.metadata.get("citation_required"))
    citation = find_citation_for_claim(
        claim.text,
        trace.citations,
        mode="semantic",
    ) or find_citation_for_claim(
        claim.verification_text,
        trace.citations,
        mode="semantic",
    )
    if citation is None:
        return _record(
            "missing" if required else "not_applicable",
            None,
            "required_citation_absent" if required else "citation_not_required",
        )

    contexts = {context.id: context for context in trace.contexts}
    cited = contexts.get(citation.source_id)
    if cited is None:
        return _record("malformed", citation.source_id, "citation_target_unresolvable")

    match = find_best_evidence(
        claim.verification_text,
        [cited],
        mode="semantic",
        localize_spans=True,
    )
    cited_verification = classify_claim(
        Claim(id=claim.id, text=claim.verification_text),
        match,
        has_contexts=True,
        mode="semantic",
        contradiction_checks=True,
    )
    if cited_verification.verdict == "supported":
        return _record("correct", citation.source_id, "cited_source_supports_claim")
    if cited_verification.verdict == "partially_supported":
        return _record(
            "partial", citation.source_id, "cited_source_partially_supports_claim"
        )
    if verdict == "supported" and best_context_id != citation.source_id:
        return _record(
            "wrong_source", citation.source_id, "support_exists_in_different_source"
        )
    return _record(
        "wrong_source", citation.source_id, "cited_source_does_not_support_claim"
    )


def _record(
    state: str,
    source_id: str | None,
    reason_code: str,
) -> dict[str, object]:
    return {
        "state": state,
        "source_id": source_id,
        "reason_code": reason_code,
    }
