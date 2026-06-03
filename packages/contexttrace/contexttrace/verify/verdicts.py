from __future__ import annotations

from dataclasses import dataclass

from contexttrace.verify.claims import Claim
from contexttrace.verify.evidence import EvidenceMatch, extract_numbers, unique_important_tokens


SUPPORTED_THRESHOLD = 0.62
PARTIAL_THRESHOLD = 0.45
UNSUPPORTED_THRESHOLD = 0.30

NEGATION_TERMS = {
    "not",
    "no",
    "never",
    "cannot",
    "can't",
    "wont",
    "won't",
    "doesnt",
    "doesn't",
    "dont",
    "don't",
    "isnt",
    "isn't",
    "arent",
    "aren't",
    "without",
    "prohibited",
    "forbidden",
    "disallowed",
    "ineligible",
}


@dataclass(frozen=True)
class ClaimVerification:
    claim_id: str
    claim: str
    verdict: str
    confidence: float
    best_context_id: str | None
    best_context_text: str
    best_score: float
    evidence: str
    matched_terms: list[str]
    reason: str
    citation_status: str = "claim_has_no_citation"
    citation_source_id: str | None = None

    def with_citation(self, *, status: str, source_id: str | None) -> "ClaimVerification":
        return ClaimVerification(
            claim_id=self.claim_id,
            claim=self.claim,
            verdict=self.verdict,
            confidence=self.confidence,
            best_context_id=self.best_context_id,
            best_context_text=self.best_context_text,
            best_score=self.best_score,
            evidence=self.evidence,
            matched_terms=list(self.matched_terms),
            reason=self.reason,
            citation_status=status,
            citation_source_id=source_id,
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "claim_id": self.claim_id,
            "claim": self.claim,
            "verdict": self.verdict,
            "confidence": self.confidence,
            "best_context_id": self.best_context_id,
            "best_context_text": self.best_context_text,
            "best_score": self.best_score,
            "evidence": self.evidence,
            "matched_terms": list(self.matched_terms),
            "reason": self.reason,
            "citation_status": self.citation_status,
            "citation_source_id": self.citation_source_id,
        }


def classify_claim(claim: Claim, match: EvidenceMatch, *, has_contexts: bool) -> ClaimVerification:
    contradicted = has_contexts and is_contradicted(claim.text, match.snippet, match.score)
    if contradicted:
        verdict = "contradicted"
        confidence = max(0.66, min(0.98, match.score + 0.12))
        reason = (
            "The strongest evidence appears to conflict with the claim because it uses "
            "negation or a different numeric/date value for the same subject."
        )
    elif not has_contexts:
        verdict = "unsupported"
        confidence = 0.95
        reason = "No retrieved contexts were provided, so the claim has no evidence to verify against."
    elif match.score >= SUPPORTED_THRESHOLD:
        verdict = "supported"
        confidence = match.score
        reason = "The claim is supported by %s because the context states: %s" % (
            match.context_id,
            match.snippet,
        )
    elif match.score >= PARTIAL_THRESHOLD and len(match.matched_terms) >= 2:
        verdict = "partially_supported"
        confidence = match.score
        reason = (
            "The strongest context supports part of the claim through %s, but it does not clearly support every detail."
            % (", ".join(match.matched_terms) or "overlapping terms")
        )
    elif match.score < UNSUPPORTED_THRESHOLD:
        verdict = "unsupported"
        confidence = round(max(0.55, 1.0 - match.score), 3)
        reason = "No retrieved context has enough evidence overlap to support the claim."
    else:
        verdict = "unverifiable"
        confidence = round(max(0.4, match.score), 3)
        reason = (
            "The strongest context overlaps with %s, but the evidence is weak or ambiguous."
            % (", ".join(match.matched_terms) or "some terms")
        )

    return ClaimVerification(
        claim_id=claim.id,
        claim=claim.text,
        verdict=verdict,
        confidence=round(confidence, 3),
        best_context_id=match.context_id,
        best_context_text=match.context_text,
        best_score=match.score,
        evidence=match.snippet,
        matched_terms=list(match.matched_terms),
        reason=reason,
    )


def is_supported_match(claim_text: str, match: EvidenceMatch) -> bool:
    return match.score >= SUPPORTED_THRESHOLD and not is_contradicted(claim_text, match.snippet, match.score)


def is_contradicted(claim_text: str, evidence_text: str, score: float) -> bool:
    if score < 0.50:
        return False

    if _has_negation(claim_text) != _has_negation(evidence_text) and _core_overlap(claim_text, evidence_text) >= 0.55:
        return True

    claim_numbers = set(extract_numbers(claim_text))
    evidence_numbers = set(extract_numbers(evidence_text))
    if claim_numbers and evidence_numbers and claim_numbers.isdisjoint(evidence_numbers):
        return _core_overlap(claim_text, evidence_text) >= 0.65

    return False


def _has_negation(text: str) -> bool:
    tokens = {token.lower() for token in str(text or "").replace("n't", " not").split()}
    normalized = " ".join(tokens)
    if "not allowed" in str(text or "").lower() or "not eligible" in str(text or "").lower():
        return True
    return any(token.strip(".,;:!?()[]{}\"'") in NEGATION_TERMS for token in tokens) or " not " in normalized


def _core_overlap(claim_text: str, evidence_text: str) -> float:
    claim_terms = [term for term in unique_important_tokens(claim_text) if not term.isdigit()]
    evidence_terms = set(term for term in unique_important_tokens(evidence_text) if not term.isdigit())
    if not claim_terms:
        return 0.0
    return len([term for term in claim_terms if term in evidence_terms]) / len(claim_terms)
