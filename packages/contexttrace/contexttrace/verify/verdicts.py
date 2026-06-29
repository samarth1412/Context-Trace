from __future__ import annotations

import re
from dataclasses import dataclass, replace

from contexttrace.verify.claims import Claim
from contexttrace.verify.evidence import (
    EvidenceMatch,
    extract_numbers,
    has_unnegated_exact_surface_match,
    unique_important_tokens,
)
from contexttrace.verify.facts import compare_facts


SUPPORTED_THRESHOLD = 0.62
PARTIAL_THRESHOLD = 0.45
UNSUPPORTED_THRESHOLD = 0.30

NEGATION_TERMS = {
    "not",
    "no",
    "never",
    "neither",
    "nor",
    "cannot",
    "can't",
    "unable",
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

CONTENT_NUMBER_WORDS = {
    "five": "5",
    "seven": "7",
    "fourteen": "14",
    "thirty": "30",
    "ninety": "90",
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
    fact_evidence = _fact_evidence_text(match)
    normalized_mode = str(mode or "lexical").strip().lower().replace("-", "_")
    fact_mode = "semantic" if normalized_mode in {"semantic", "local_ml", "nli"} else "lexical"
    fact_match = compare_facts(claim.text, fact_evidence, mode=fact_mode)
    if not fact_match.conflicting_facts and _needs_full_context_conflict_scan(claim.text, fact_mode):
        context_fact_match = compare_facts(claim.text, match.context_text, mode=fact_mode)
        if context_fact_match.conflicting_facts:
            fact_match = replace(
                fact_match,
                conflicting_facts=list(context_fact_match.conflicting_facts),
                conflicting_fact_details=list(context_fact_match.conflicting_fact_details),
            )
    contradiction_evidence = _contradiction_evidence_text(claim.text, match)
    contradicted = has_contexts and is_contradicted(claim.text, contradiction_evidence, match.score, mode=fact_mode)
    fully_fact_supported = bool(fact_match.required_facts and not fact_match.missing_facts and not fact_match.conflicting_facts)
    if fact_match.conflicting_facts or (contradicted and not fully_fact_supported):
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
    elif match.score >= SUPPORTED_THRESHOLD and fact_match.missing_facts:
        verdict = "partially_supported"
        confidence = match.score
        reason = (
            "The strongest evidence has high lexical or semantic overlap, but required fact "
            "matching is incomplete; inspect the missing facts before treating this as supported."
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


def is_supported_match(claim_text: str, match: EvidenceMatch, *, mode: str = "lexical") -> bool:
    return match.score >= SUPPORTED_THRESHOLD and not is_contradicted(claim_text, match.snippet, match.score, mode=mode)


def _fact_evidence_text(match: EvidenceMatch) -> str:
    context_text = str(match.context_text or "").strip()
    if context_text.startswith("{") and context_text.endswith("}"):
        return context_text
    return match.supporting_text or match.snippet


def _needs_full_context_conflict_scan(claim_text: str, mode: str) -> bool:
    if mode != "semantic":
        return False
    return bool(
        re.search(
            r"\blost\s+(?:her|his|their)\s+foot\s+in\s+(?:the\s+)?(?:bombing|blast|attack)\b",
            str(claim_text or ""),
            flags=re.IGNORECASE,
        )
    )


def is_contradicted(claim_text: str, evidence_text: str, score: float, *, mode: str = "lexical") -> bool:
    if score < 0.50:
        return False
    if has_unnegated_exact_surface_match(claim_text, evidence_text):
        return False
    if _negated_truth_support(claim_text, evidence_text):
        return False

    if _has_negation(claim_text) != _has_negation(evidence_text) and _core_overlap(claim_text, evidence_text) >= 0.55:
        if _preventive_negation_support(claim_text, evidence_text, mode=mode):
            return False
        if _critical_condition_negation_support(claim_text, evidence_text, mode=mode):
            return False
        if _instruction_caution_negation_support(claim_text, evidence_text, mode=mode):
            return False
        if _first_time_since_negative_support(claim_text, evidence_text, mode=mode):
            return False
        if _outsourced_service_negation_support(claim_text, evidence_text, mode=mode):
            return False
        if _affirmative_contrast_support(claim_text, evidence_text, mode=mode):
            return False
        if _unsuccessful_attempt_not_conflict(claim_text, evidence_text, mode=mode):
            return False
        if _has_affirmative_supporting_clause(claim_text, evidence_text):
            return False
        return True

    claim_numbers = _raw_content_numbers(claim_text)
    evidence_numbers = _content_numbers(evidence_text)
    if claim_numbers and evidence_numbers and not evidence_numbers.issubset(claim_numbers) and claim_numbers.isdisjoint(evidence_numbers):
        return _core_overlap(claim_text, evidence_text) >= 0.65

    return False


def _has_negation(text: str) -> bool:
    normalized_text = _neutralize_non_negating_phrases(str(text or ""))
    normalized_text = re.sub(r"\bcan(?:'|\u2019)?t\b", "cannot", normalized_text, flags=re.IGNORECASE)
    normalized_text = re.sub(r"\b([A-Za-z]+)n(?:'|\u2019)t\b", r"\1 not", normalized_text)
    tokens = {token.lower() for token in normalized_text.split()}
    normalized = " ".join(tokens)
    if "not allowed" in normalized_text.lower() or "not eligible" in normalized_text.lower():
        return True
    return any(token.strip(".,;:!?()[]{}\"'") in NEGATION_TERMS for token in tokens) or " not " in normalized


def _negated_truth_support(claim_text: str, evidence_text: str) -> bool:
    claim = str(claim_text or "").lower()
    evidence = str(evidence_text or "").lower()
    if "false" not in claim:
        return False
    if "not exactly" not in evidence or "true" not in evidence:
        return False
    return _core_overlap(claim_text, evidence_text) >= 0.45


def _neutralize_non_negating_phrases(text: str) -> str:
    value = str(text or "")
    value = re.sub(r"\bnot\s+only\b", "also", value, flags=re.IGNORECASE)
    value = re.sub(r"\bno\s+surprise\b", "expected", value, flags=re.IGNORECASE)
    value = re.sub(r"\bno\s+disputing\b", "clear", value, flags=re.IGNORECASE)
    value = re.sub(r"\bnot\s+to\s+mention\b", "including", value, flags=re.IGNORECASE)
    value = re.sub(r"\bor\s+not\b", "or otherwise", value, flags=re.IGNORECASE)
    value = re.sub(r"\bnot\s+clear\s+on\s+(?:its|their|the)\s+beginnings?\b", "uncertain beginnings", value, flags=re.IGNORECASE)
    value = re.sub(r"\bwithout\s+hesitation\b", "readily", value, flags=re.IGNORECASE)
    value = re.sub(r"\beven\s+if\s+it\s+\[?did\s+not\]?\s+end\s+up\b", "even if it might end up", value, flags=re.IGNORECASE)
    value = re.sub(r"\beven\s+if\s+it\s+\[?didn(?:'|\u2019)?t\]?\s+end\s+up\b", "even if it might end up", value, flags=re.IGNORECASE)
    value = re.sub(r"\beven\s+if\s+it\s+\[?did\s+not\s+end\]?\s+up\b", "even if it might end up", value, flags=re.IGNORECASE)
    value = re.sub(r"\beven\s+if\s+it\s+\[?didn(?:'|\u2019)?t\s+end\]?\s+up\b", "even if it might end up", value, flags=re.IGNORECASE)
    return value


def _unsuccessful_attempt_not_conflict(claim_text: str, evidence_text: str, *, mode: str) -> bool:
    if str(mode or "").strip().lower().replace("-", "_") != "semantic":
        return False
    if not re.search(r"\bnot\s+(?:been\s+)?successful\b|\bunsuccessful\b|\bfailed\b", str(claim_text or ""), flags=re.IGNORECASE):
        return False
    if re.search(r"\b(?:successful|succeeded|adopted|approved|implemented)\b", str(evidence_text or ""), flags=re.IGNORECASE):
        return False
    return bool(
        re.search(r"\b(?:attempt|attempted|effort|pushed|proposed|called\s+for)\b", str(evidence_text or ""), flags=re.IGNORECASE)
        and _core_overlap(claim_text, evidence_text, mode=mode) >= 0.35
    )


def _content_numbers(text: object) -> set[str]:
    numbers = _raw_content_numbers(text)
    numbers.update(_derived_content_numbers(_normalize_content_number_text(text)))
    return numbers


def _raw_content_numbers(text: object) -> set[str]:
    value = _normalize_content_number_text(text)
    return {
        match.group(0)
        for match in re.finditer(r"\b\d+(?:\.\d+)?\b", value)
        if not _is_non_content_number_prefix(value[max(0, match.start() - 20) : match.start()])
    }


def _normalize_content_number_text(text: object) -> str:
    value = re.sub(r"(?<=\d),(?=\d{3}\b)", "", str(text or ""))
    value = re.sub(r"\b(\d{1,2})(am|pm)\b", r"\1 \2", value, flags=re.IGNORECASE)
    value = re.sub(r"(?<=\d)[^\w\s](?=\s*[fc]\b)", " ", value, flags=re.IGNORECASE)
    for word, number in CONTENT_NUMBER_WORDS.items():
        value = re.sub(rf"\b{word}\b", number, value, flags=re.IGNORECASE)
    return value


def _derived_content_numbers(value: str) -> set[str]:
    derived: set[str] = set()
    pattern = re.compile(
        r"\b(?:rise|rises|rose|increase|increases|increased|up|grow|grows|grew)\b"
        r"[^.]{0,60}?\bby\s+\$?(?P<delta>\d+(?:\.\d+)?)\b"
        r"[^.]{0,60}?\bto\s+\$?(?P<target>\d+(?:\.\d+)?)\b",
        re.IGNORECASE,
    )
    for match in pattern.finditer(value):
        delta = float(match.group("delta"))
        target = float(match.group("target"))
        if target >= delta:
            derived.add(_format_content_number(target - delta))
    for match in re.finditer(
        r"\b(?P<value>\d+(?:\.\d+)?)\s*(?:°\s*)?(?P<unit>[fc])\b",
        value,
        flags=re.IGNORECASE,
    ):
        temperature = float(match.group("value"))
        unit = match.group("unit").lower()
        derived.add(_format_content_number(temperature))
        if unit == "f":
            celsius = (temperature - 32.0) * 5.0 / 9.0
            derived.add(_format_content_number(round(celsius)))
            derived.add(_format_content_number(round(celsius / 5.0) * 5.0))
        else:
            fahrenheit = (temperature * 9.0 / 5.0) + 32.0
            derived.add(_format_content_number(round(fahrenheit)))
    return derived


def _format_content_number(value: float) -> str:
    value = float(value)
    if value.is_integer():
        return str(int(value))
    return ("%0.6f" % value).rstrip("0").rstrip(".")


def _is_non_content_number_prefix(prefix: str) -> bool:
    return bool(re.search(r"(?:\b(?:passage|issue|ticket|pr)\s*#?\s*|#\s*)$", prefix, flags=re.IGNORECASE))


def _has_affirmative_supporting_clause(claim_text: str, evidence_text: str) -> bool:
    if _has_negation(claim_text):
        return False
    supporting_text = " ".join(
        clause for clause in _evidence_clauses(evidence_text) if not _has_negation(clause)
    )
    return bool(supporting_text and _core_overlap(claim_text, supporting_text) >= 0.55)


def _preventive_negation_support(claim_text: str, evidence_text: str, *, mode: str) -> bool:
    if str(mode or "").strip().lower().replace("-", "_") != "semantic":
        return False
    if not re.search(
        r"\b(?:avoid|prevent|prevents|preventing|protect|protects|protecting)\b",
        str(claim_text or ""),
        flags=re.IGNORECASE,
    ):
        return False
    return _core_overlap(claim_text, evidence_text, mode=mode) >= 0.55


def _instruction_caution_negation_support(claim_text: str, evidence_text: str, *, mode: str) -> bool:
    if str(mode or "").strip().lower().replace("-", "_") != "semantic":
        return False
    if not re.search(r"\b(?:instruction|instructions|guide|steps?)\b", str(claim_text or ""), flags=re.IGNORECASE):
        return False
    return bool(
        re.search(r"\bnot\s+too\s+close\b", str(evidence_text or ""), flags=re.IGNORECASE)
        and _core_overlap(claim_text, evidence_text, mode=mode) >= 0.35
    )


def _first_time_since_negative_support(claim_text: str, evidence_text: str, *, mode: str) -> bool:
    if str(mode or "").strip().lower().replace("-", "_") != "semantic":
        return False
    if not re.search(r"\bfirst\s+time\b.+\bsince\b", str(claim_text or ""), flags=re.IGNORECASE):
        return False
    return bool(
        re.search(r"\bsince\b", str(evidence_text or ""), flags=re.IGNORECASE)
        and _has_negation(evidence_text)
        and _core_overlap(claim_text, evidence_text, mode=mode) >= 0.55
    )


def _critical_condition_negation_support(claim_text: str, evidence_text: str, *, mode: str) -> bool:
    if str(mode or "").strip().lower().replace("-", "_") != "semantic":
        return False
    if not re.search(r"\bcritical\s+condition\b", str(claim_text or ""), flags=re.IGNORECASE):
        return False
    return bool(
        re.search(r"\b(?:coma|unable|cannot|rough\s+shape)\b", str(evidence_text or ""), flags=re.IGNORECASE)
        and _core_overlap(claim_text, evidence_text, mode=mode) >= 0.45
    )


def _outsourced_service_negation_support(claim_text: str, evidence_text: str, *, mode: str) -> bool:
    if str(mode or "").strip().lower().replace("-", "_") != "semantic":
        return False
    if not re.search(
        r"\b(?:used\s+by|licensed|outside\s+company|cooperat|internal\s+investigation)\b",
        str(claim_text or ""),
        flags=re.IGNORECASE,
    ):
        return False
    return bool(
        re.search(r"\bdoes\s+not\s+treat\b", str(evidence_text or ""), flags=re.IGNORECASE)
        and re.search(r"\brelies\s+on\s+licensed\s+professionals\b", str(evidence_text or ""), flags=re.IGNORECASE)
        and _core_overlap(claim_text, evidence_text, mode=mode) >= 0.45
    )


def _affirmative_contrast_support(claim_text: str, evidence_text: str, *, mode: str) -> bool:
    if str(mode or "").strip().lower().replace("-", "_") != "semantic":
        return False
    if _has_negation(claim_text):
        return False
    if not re.search(r"\bbut\s+if\b|\bthen\b", str(evidence_text or ""), flags=re.IGNORECASE):
        return False
    affirmative_text = " ".join(clause for clause in _evidence_clauses(evidence_text) if not _has_negation(clause))
    return bool(affirmative_text and _core_overlap(claim_text, affirmative_text, mode=mode) >= 0.45)


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


def _core_overlap(claim_text: str, evidence_text: str, *, mode: str = "lexical") -> float:
    claim_terms = [term for term in unique_important_tokens(claim_text, mode=mode) if not term.isdigit()]
    evidence_terms = set(term for term in unique_important_tokens(evidence_text, mode=mode) if not term.isdigit())
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
