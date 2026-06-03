from __future__ import annotations

from contexttrace.verify.claims import Claim
from contexttrace.verify.evidence import lexical_score, score_claim_against_context
from contexttrace.verify.schema import RAGTrace, TraceCitation
from contexttrace.verify.verdicts import ClaimVerification, is_supported_match


CITATION_OK = "citation_ok"
CITED_SOURCE_MISSING = "cited_source_missing"
CITED_SOURCE_DOES_NOT_SUPPORT = "cited_source_does_not_support_claim"
CLAIM_HAS_NO_CITATION = "claim_has_no_citation"


def attach_citation_statuses(
    claims: list[Claim],
    verifications: list[ClaimVerification],
    trace: RAGTrace,
    *,
    mode: str = "lexical",
) -> list[ClaimVerification]:
    contexts_by_id = {context.id: context for context in trace.contexts}
    updated: list[ClaimVerification] = []
    for claim, verification in zip(claims, verifications):
        citation = find_citation_for_claim(claim.text, trace.citations, mode=mode)
        if citation is None:
            updated.append(
                verification.with_citation(status=CLAIM_HAS_NO_CITATION, source_id=None)
            )
            continue

        cited_context = contexts_by_id.get(citation.source_id)
        if cited_context is None:
            updated.append(
                verification.with_citation(
                    status=CITED_SOURCE_MISSING,
                    source_id=citation.source_id,
                )
            )
            continue

        cited_match = score_claim_against_context(claim.text, cited_context, mode=mode)
        if is_supported_match(claim.text, cited_match):
            status = CITATION_OK
        else:
            status = CITED_SOURCE_DOES_NOT_SUPPORT

        updated.append(
            verification.with_citation(status=status, source_id=citation.source_id)
        )
    return updated


def find_citation_for_claim(
    claim_text: str,
    citations: list[TraceCitation],
    *,
    mode: str = "lexical",
) -> TraceCitation | None:
    if not citations:
        return None
    normalized_claim = _normalize_text(claim_text)
    best: TraceCitation | None = None
    best_score = 0.0
    for citation in citations:
        normalized_citation = _normalize_text(citation.claim)
        if normalized_claim == normalized_citation:
            return citation
        if normalized_claim and normalized_citation and (
            normalized_claim in normalized_citation or normalized_citation in normalized_claim
        ):
            return citation
        score, _ = lexical_score(claim_text, citation.claim, mode=mode)
        if score > best_score:
            best = citation
            best_score = score
    return best if best_score >= 0.55 else None


def _normalize_text(text: str) -> str:
    return " ".join(str(text or "").lower().strip().strip(".!?").split())
