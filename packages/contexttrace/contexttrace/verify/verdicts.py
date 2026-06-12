from __future__ import annotations

import re
from dataclasses import dataclass

from contexttrace.verify.claims import Claim
from contexttrace.verify.evidence import EvidenceMatch, extract_numbers, unique_important_tokens
from contexttrace.verify.facts import compare_facts


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
    evidence_span: dict[str, object] | None
    supporting_spans: list[dict[str, object]]
    matched_terms: list[str]
    required_facts: list[str]
    matched_facts: list[str]
    missing_facts: list[str]
    conflicting_facts: list[str]
    required_fact_details: list[dict[str, object]]
    matched_fact_details: list[dict[str, object]]
    missing_fact_details: list[dict[str, object]]
    conflicting_fact_details: list[dict[str, object]]
    reason: str
    citation_status: str = "claim_has_no_citation"
    citation_source_id: str | None = None
    judge: dict[str, object] | None = None

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
            evidence_span=dict(self.evidence_span) if self.evidence_span else None,
            supporting_spans=[dict(item) for item in self.supporting_spans],
            matched_terms=list(self.matched_terms),
            required_facts=list(self.required_facts),
            matched_facts=list(self.matched_facts),
            missing_facts=list(self.missing_facts),
            conflicting_facts=list(self.conflicting_facts),
            required_fact_details=[dict(item) for item in self.required_fact_details],
            matched_fact_details=[dict(item) for item in self.matched_fact_details],
            missing_fact_details=[dict(item) for item in self.missing_fact_details],
            conflicting_fact_details=[dict(item) for item in self.conflicting_fact_details],
            reason=self.reason,
            citation_status=status,
            citation_source_id=source_id,
            judge=dict(self.judge) if self.judge else None,
        )

    def with_judge(
        self,
        *,
        verdict: str,
        confidence: float,
        reason: str,
        matched_facts: list[str],
        missing_facts: list[str],
        conflicting_facts: list[str],
        judge: dict[str, object],
    ) -> "ClaimVerification":
        return ClaimVerification(
            claim_id=self.claim_id,
            claim=self.claim,
            verdict=verdict,
            confidence=confidence,
            best_context_id=self.best_context_id,
            best_context_text=self.best_context_text,
            best_score=self.best_score,
            evidence=self.evidence,
            evidence_span=dict(self.evidence_span) if self.evidence_span else None,
            supporting_spans=[dict(item) for item in self.supporting_spans],
            matched_terms=list(self.matched_terms),
            required_facts=list(self.required_facts),
            matched_facts=list(matched_facts),
            missing_facts=list(missing_facts),
            conflicting_facts=list(conflicting_facts),
            required_fact_details=[dict(item) for item in self.required_fact_details],
            matched_fact_details=[dict(item) for item in self.matched_fact_details],
            missing_fact_details=[dict(item) for item in self.missing_fact_details],
            conflicting_fact_details=[dict(item) for item in self.conflicting_fact_details],
            reason=reason,
            citation_status=self.citation_status,
            citation_source_id=self.citation_source_id,
            judge=dict(judge),
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
            "evidence_span": dict(self.evidence_span) if self.evidence_span else None,
            "supporting_spans": [dict(item) for item in self.supporting_spans],
            "matched_terms": list(self.matched_terms),
            "required_facts": list(self.required_facts),
            "matched_facts": list(self.matched_facts),
            "missing_facts": list(self.missing_facts),
            "conflicting_facts": list(self.conflicting_facts),
            "required_fact_details": [dict(item) for item in self.required_fact_details],
            "matched_fact_details": [dict(item) for item in self.matched_fact_details],
            "missing_fact_details": [dict(item) for item in self.missing_fact_details],
            "conflicting_fact_details": [dict(item) for item in self.conflicting_fact_details],
            "reason": self.reason,
            "citation_status": self.citation_status,
            "citation_source_id": self.citation_source_id,
            "judge": dict(self.judge) if self.judge else None,
        }


def classify_claim(
    claim: Claim,
    match: EvidenceMatch,
    *,
    has_contexts: bool,
    mode: str = "lexical",
) -> ClaimVerification:
    fact_evidence = match.supporting_text or match.snippet
    normalized_mode = str(mode or "lexical").strip().lower().replace("-", "_")
    fact_mode = "semantic" if normalized_mode in {"semantic", "local_ml", "nli"} else "lexical"
    fact_match = compare_facts(claim.text, fact_evidence, mode=fact_mode)
    contradiction_evidence = _contradiction_evidence_text(claim.text, match)
    contradicted = has_contexts and is_contradicted(claim.text, contradiction_evidence, match.score)
    if contradicted or fact_match.conflicting_facts:
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
    elif fact_match.required_facts and not fact_match.missing_facts:
        verdict = "supported"
        confidence = round(max(match.score, 0.82), 3)
        reason = "The claim is supported by the retrieved evidence because all required facts were matched."
    elif _is_partially_supported(fact_match):
        verdict = "partially_supported"
        confidence = round(max(match.score, min(0.88, 0.45 + (0.35 * fact_match.coverage))), 3)
        reason = (
            "The strongest evidence supports %s, but it is missing %s."
            % (
                _join_facts(fact_match.matched_facts),
                _join_facts(fact_match.missing_facts),
            )
        )
    elif match.score >= SUPPORTED_THRESHOLD and normalized_mode != "local_ml":
        verdict = "supported"
        confidence = match.score
        reason = "The claim is supported by %s because the context states: %s" % (
            match.context_id,
            match.snippet,
        )
    elif match.score >= SUPPORTED_THRESHOLD and fact_match.coverage >= 0.4:
        verdict = "partially_supported"
        confidence = match.score
        reason = (
            "The local-ML evidence score is high, but required fact matching is incomplete; inspect the missing facts before treating this as supported."
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
        evidence_span=match.span_dict(),
        supporting_spans=list(match.supporting_spans or []),
        matched_terms=list(match.matched_terms),
        required_facts=list(fact_match.required_facts),
        matched_facts=list(fact_match.matched_facts),
        missing_facts=list(fact_match.missing_facts),
        conflicting_facts=list(fact_match.conflicting_facts),
        required_fact_details=[fact.to_dict() for fact in fact_match.required_fact_details],
        matched_fact_details=[fact.to_dict() for fact in fact_match.matched_fact_details],
        missing_fact_details=[fact.to_dict() for fact in fact_match.missing_fact_details],
        conflicting_fact_details=[fact.to_dict() for fact in fact_match.conflicting_fact_details],
        reason=reason,
    )


def is_supported_match(claim_text: str, match: EvidenceMatch) -> bool:
    return match.score >= SUPPORTED_THRESHOLD and not is_contradicted(claim_text, match.snippet, match.score)


def is_contradicted(claim_text: str, evidence_text: str, score: float) -> bool:
    if score < 0.50:
        return False

    if _has_negation(claim_text) != _has_negation(evidence_text) and _core_overlap(claim_text, evidence_text) >= 0.55:
        if _has_affirmative_supporting_clause(claim_text, evidence_text):
            return False
        return True

    claim_numbers = set(extract_numbers(claim_text))
    evidence_numbers = set(extract_numbers(evidence_text))
    if claim_numbers and evidence_numbers and claim_numbers.isdisjoint(evidence_numbers):
        return _core_overlap(claim_text, evidence_text) >= 0.65

    return False


def _has_negation(text: str) -> bool:
    normalized_text = _neutralize_non_negating_phrases(str(text or "").replace("n't", " not"))
    tokens = {token.lower() for token in normalized_text.split()}
    normalized = " ".join(tokens)
    if "not allowed" in normalized_text.lower() or "not eligible" in normalized_text.lower():
        return True
    return any(token.strip(".,;:!?()[]{}\"'") in NEGATION_TERMS for token in tokens) or " not " in normalized


def _neutralize_non_negating_phrases(text: str) -> str:
    value = str(text or "")
    return value.replace("not only", "also").replace("Not only", "Also")


def _has_affirmative_supporting_clause(claim_text: str, evidence_text: str) -> bool:
    if _has_negation(claim_text):
        return False
    supporting_text = " ".join(
        clause for clause in _evidence_clauses(evidence_text) if not _has_negation(clause)
    )
    return bool(supporting_text and _core_overlap(claim_text, supporting_text) >= 0.55)


def _evidence_clauses(text: str) -> list[str]:
    clauses = [
        clause.strip()
        for clause in re.split(r"--|;|,|\band\b|\bbut\b", str(text or ""))
        if clause.strip()
    ]
    return clauses or [str(text or "")]


def _contradiction_evidence_text(claim_text: str, match: EvidenceMatch) -> str:
    supporting_text = str(match.supporting_text or "").strip()
    if supporting_text and _has_negation(claim_text) == _has_negation(supporting_text):
        return supporting_text
    return match.snippet


def _core_overlap(claim_text: str, evidence_text: str) -> float:
    claim_terms = [term for term in unique_important_tokens(claim_text) if not term.isdigit()]
    evidence_terms = set(term for term in unique_important_tokens(evidence_text) if not term.isdigit())
    if not claim_terms:
        return 0.0
    return len([term for term in claim_terms if term in evidence_terms]) / len(claim_terms)


def _is_partially_supported(fact_match: object) -> bool:
    matched = list(getattr(fact_match, "matched_facts", []) or [])
    missing = list(getattr(fact_match, "missing_facts", []) or [])
    required = list(getattr(fact_match, "required_facts", []) or [])
    coverage = float(getattr(fact_match, "coverage", 0.0) or 0.0)
    if matched and missing and len(required) >= 3 and coverage >= 0.30:
        return True
    return bool(matched and missing and coverage >= 0.4 and (len(matched) >= 2 or coverage >= 0.5))


def _join_facts(facts: list[str]) -> str:
    if not facts:
        return "some facts"
    if len(facts) == 1:
        return '"%s"' % facts[0]
    return ", ".join('"%s"' % fact for fact in facts)
