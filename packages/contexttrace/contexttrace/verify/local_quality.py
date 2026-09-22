"""Opt-in local claim verification with atomic evidence assessment.

This module is experimental. It does not alter the stable verifier or provider
selection and never downloads a model or calls a remote service.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Iterable

from contexttrace.verify.claims import Claim, extract_claims
from contexttrace.verify.evidence import find_best_evidence, lexical_score
from contexttrace.verify.judges import ClaimJudge, JudgeVerdict
from contexttrace.verify.schema import RAGTrace, TraceContext
from contexttrace.verify.semantic_core_v2.profile import SELECTIVE_V2_PROFILE
from contexttrace.verify.semantic_core_v2.source import assess_source_condition
from contexttrace.verify.spans import EvidenceSpan, split_context_spans
from contexttrace.verify.verdicts import classify_claim


VERIFIER_VERSION = "local_quality_v1_experimental"
CONFIDENCE_SEMANTICS = "uncalibrated_decision_strength"

_MODALS = "may|can|must|should|will|would|could|might"
_SECOND_PREDICATES = {
    "allow",
    "allows",
    "approve",
    "approves",
    "contain",
    "contains",
    "include",
    "includes",
    "modify",
    "modifies",
    "offer",
    "offers",
    "process",
    "processes",
    "provide",
    "provides",
    "receive",
    "receives",
    "require",
    "requires",
    "support",
    "supports",
    "use",
    "uses",
}
_ABSENCE_RE = re.compile(
    r"\b(?:(?:does\s+not|doesn't|do\s+not|don't|not)\s+"
    r"(?:state|specify|describe|provide|mention|identify|say|list|explain|give)|"
    r"(?:is|are|was|were)\s+not\s+"
    r"(?:stated|specified|described|provided|mentioned|identified|listed|explained|given)|"
    r"(?:gives?|provides?|contains?)\s+no\s+(?:information|details?))\b",
    flags=re.IGNORECASE,
)
_UNIVERSAL_RE = re.compile(r"\b(?:all|every|always|any|entirely|guaranteed?)\b", re.IGNORECASE)
_QUALIFIER_RE = re.compile(
    r"\b(?:may|might|can\s+sometimes|some|eligible|gradually|typically|usually|"
    r"subject\s+to|depending\s+on|up\s+to|approximately|about)\b",
    re.IGNORECASE,
)
_EXPLICIT_EXCLUSION_RE = re.compile(
    r"\b(?:not\s+all|only\s+some|no|none|never|ineligible|excluded?|does\s+not|do\s+not)\b",
    re.IGNORECASE,
)
_NEGATION_RE = re.compile(
    r"\b(?:no|not|never|cannot|can't|must\s+not|may\s+not|doesn't|does\s+not|"
    r"isn't|is\s+not|aren't|are\s+not|without|prohibited|forbidden)\b",
    re.IGNORECASE,
)
_WORD_NUMBERS = {
    "zero": "0",
    "one": "1",
    "two": "2",
    "three": "3",
    "four": "4",
    "five": "5",
    "six": "6",
    "seven": "7",
    "eight": "8",
    "nine": "9",
    "ten": "10",
    "eleven": "11",
    "twelve": "12",
    "thirteen": "13",
    "fourteen": "14",
    "fifteen": "15",
    "sixteen": "16",
    "seventeen": "17",
    "eighteen": "18",
    "nineteen": "19",
    "twenty": "20",
    "thirty": "30",
    "forty": "40",
    "fifty": "50",
    "sixty": "60",
    "ninety": "90",
}
_UNIT_ALIASES = {
    "day": "day",
    "days": "day",
    "hour": "hour",
    "hours": "hour",
    "minute": "minute",
    "minutes": "minute",
    "month": "month",
    "months": "month",
    "second": "second",
    "seconds": "second",
    "week": "week",
    "weeks": "week",
    "year": "year",
    "years": "year",
}


class LocalQualityError(RuntimeError):
    """Raised when an explicitly requested local-quality backend cannot run."""


@dataclass(frozen=True)
class LocalQualityProfile:
    decompose_claims: bool = True
    relation_rules: bool = True
    require_nli: bool = False
    review_threshold: float = 0.80
    max_evidence_spans: int = 8
    nli_entailment_threshold: float = 0.70
    nli_contradiction_threshold: float = 0.80
    nli_neutral_threshold: float = 0.70

    def __post_init__(self) -> None:
        if self.max_evidence_spans < 1:
            raise ValueError("max_evidence_spans must be at least 1.")
        for name in (
            "review_threshold",
            "nli_entailment_threshold",
            "nli_contradiction_threshold",
            "nli_neutral_threshold",
        ):
            value = float(getattr(self, name))
            if not 0.0 <= value <= 1.0:
                raise ValueError("%s must be between 0 and 1." % name)


@dataclass(frozen=True)
class AtomicAssessment:
    text: str
    verdict: str
    confidence: float
    reason_code: str
    evidence_context_ids: tuple[str, ...]
    deterministic: dict[str, Any]
    nli: tuple[dict[str, Any], ...]
    evidence_conflict: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "verdict": self.verdict,
            "confidence": self.confidence,
            "confidence_semantics": CONFIDENCE_SEMANTICS,
            "reason_code": self.reason_code,
            "evidence_context_ids": list(self.evidence_context_ids),
            "evidence_conflict": self.evidence_conflict,
            "deterministic": dict(self.deterministic),
            "nli": [dict(item) for item in self.nli],
        }


class LocalQualityJudge:
    """ClaimJudge-compatible experimental local verifier."""

    provider = "local_quality"

    def __init__(
        self,
        *,
        nli: ClaimJudge | None = None,
        profile: LocalQualityProfile | None = None,
    ) -> None:
        self.nli = nli
        self.profile = profile or LocalQualityProfile(require_nli=nli is not None)
        if self.profile.require_nli and nli is None:
            raise LocalQualityError(
                "local_quality require_nli=True needs an explicitly provisioned LocalNLIJudge. "
                "Set CONTEXTTRACE_NLI_MODEL_PATH or construct the pinned local provider; "
                "ContextTrace will not download a model or silently substitute another backend."
            )

    @property
    def model(self) -> str | None:
        value = getattr(self.nli, "model", None)
        return str(value) if value else None

    def verify_claim(
        self,
        *,
        query: str,
        claim: str,
        contexts: list[TraceContext],
    ) -> JudgeVerdict:
        selected = select_local_evidence(
            query=query,
            claim=claim,
            contexts=contexts,
            limit=self.profile.max_evidence_spans,
        )
        selected_contexts = [
            TraceContext(
                id=_selected_id(span),
                text=span.text,
                metadata={
                    "source_context_id": span.context_id,
                    "start_char": span.start_char,
                    "end_char": span.end_char,
                    "span_hash": span.span_hash,
                },
            )
            for span in selected
        ]
        atoms = (
            decompose_material_claim(claim)
            if self.profile.decompose_claims
            else [claim.strip()]
        )
        assessments = [
            self._assess_atom(atom, selected_contexts)
            for atom in atoms
            if atom.strip()
        ]
        verdict, confidence, reason_code, conflict = _aggregate(assessments)
        review_required = bool(
            verdict == "unverifiable"
            or conflict
            or confidence < self.profile.review_threshold
        )
        matched = [item.text for item in assessments if item.verdict == "supported"]
        missing = [
            item.text
            for item in assessments
            if item.verdict in {"unsupported", "unverifiable"}
        ]
        conflicting = [item.text for item in assessments if item.verdict == "contradicted"]
        return JudgeVerdict(
            verdict=verdict,
            confidence=confidence,
            reason=reason_code,
            matched_facts=matched,
            missing_facts=missing,
            conflicting_facts=conflicting,
            provider=self.provider,
            model=self.model,
            raw={
                "verifier_version": VERIFIER_VERSION,
                "confidence_semantics": CONFIDENCE_SEMANTICS,
                "review_required": review_required,
                "automatic_supported": verdict == "supported" and not review_required,
                "reason_code": reason_code,
                "backend": _backend_identity(self.nli),
                "profile": {
                    "decompose_claims": self.profile.decompose_claims,
                    "relation_rules": self.profile.relation_rules,
                    "require_nli": self.profile.require_nli,
                    "review_threshold": self.profile.review_threshold,
                    "nli_entailment_threshold": self.profile.nli_entailment_threshold,
                    "nli_contradiction_threshold": self.profile.nli_contradiction_threshold,
                    "nli_neutral_threshold": self.profile.nli_neutral_threshold,
                },
                "atomic_claims": [item.to_dict() for item in assessments],
                "selected_evidence_spans": [_span_record(span) for span in selected],
                "evidence_scope": "locally_selected_spans_only",
            },
        )

    def _assess_atom(
        self,
        atom: str,
        contexts: list[TraceContext],
    ) -> AtomicAssessment:
        deterministic = _deterministic_assessment(
            atom,
            contexts,
            relation_rules=self.profile.relation_rules,
        )
        nli_rows = self._nli_rows(atom, contexts)
        if not nli_rows:
            return AtomicAssessment(
                text=atom,
                verdict=str(deterministic["verdict"]),
                confidence=float(deterministic["confidence"]),
                reason_code=str(deterministic["reason_code"]),
                evidence_context_ids=tuple(deterministic["evidence_context_ids"]),
                deterministic=deterministic,
                nli=(),
                evidence_conflict=bool(deterministic.get("evidence_conflict")),
            )

        return _resolve_atom_with_nli(atom, deterministic, nli_rows, self.profile)

    def _nli_rows(
        self,
        atom: str,
        contexts: list[TraceContext],
    ) -> tuple[dict[str, Any], ...]:
        if self.nli is None:
            return ()
        rows: list[dict[str, Any]] = []
        for context in contexts:
            result = self.nli.verify_claim(query="", claim=atom, contexts=[context])
            label = str(result.raw.get("nli_label") or "").casefold()
            if label not in {"entailment", "contradiction", "neutral"}:
                raise LocalQualityError(
                    "The configured NLI backend did not expose entailment, contradiction, or neutral."
                )
            rows.append(
                {
                    "context_id": context.id,
                    "source_context_id": context.metadata.get("source_context_id"),
                    "label": label,
                    "score": float(result.confidence),
                    "scores": dict(result.raw.get("nli_scores") or {}),
                    "backend": result.raw.get("backend"),
                    "model": result.model,
                }
            )
        return tuple(rows)


def verify_trace_local_quality(
    trace: RAGTrace,
    *,
    nli: ClaimJudge | None = None,
    profile: LocalQualityProfile | None = None,
) -> dict[str, Any]:
    """Verify a trace through the explicit local-quality experimental path."""

    judge = LocalQualityJudge(nli=nli, profile=profile)
    claims = extract_claims(trace.answer)
    rows: list[dict[str, Any]] = []
    for claim in claims:
        verdict = judge.verify_claim(
            query=trace.query,
            claim=claim.text,
            contexts=list(trace.contexts),
        )
        selected = list(verdict.raw.get("selected_evidence_spans") or [])
        best_context_id = (
            str(selected[0].get("context_id")) if selected else None
        )
        source = assess_source_condition(
            best_context_id=best_context_id,
            trace=trace,
            profile=SELECTIVE_V2_PROFILE,
        )
        rows.append(
            {
                "claim_id": claim.id,
                "claim": claim.text,
                "verdict": verdict.verdict,
                "confidence": verdict.confidence,
                "confidence_semantics": CONFIDENCE_SEMANTICS,
                "review_required": bool(verdict.raw["review_required"]),
                "automatic_supported": bool(verdict.raw["automatic_supported"]),
                "support_status": verdict.verdict,
                "truth_status": "not_assessed",
                "source_condition": source,
                "reason_code": verdict.raw["reason_code"],
                "matched_facts": list(verdict.matched_facts),
                "missing_facts": list(verdict.missing_facts),
                "conflicting_facts": list(verdict.conflicting_facts),
                "evidence_spans": selected,
                "atomic_claims": list(verdict.raw["atomic_claims"]),
                "backend": dict(verdict.raw["backend"]),
            }
        )
    return {
        "schema_version": "experimental-local-quality-1.0",
        "verifier_version": VERIFIER_VERSION,
        "experimental": True,
        "local_only": True,
        "backend": _backend_identity(nli),
        "claims": rows,
        "summary": {
            "claims": len(rows),
            "verdict_counts": _counts(row["verdict"] for row in rows),
            "review_required": sum(bool(row["review_required"]) for row in rows),
            "automatic_supported": sum(bool(row["automatic_supported"]) for row in rows),
        },
    }


def select_local_evidence(
    *,
    query: str,
    claim: str,
    contexts: Iterable[TraceContext],
    limit: int = 8,
) -> list[EvidenceSpan]:
    """Select exact local spans, retaining explicit absence/conflict statements."""

    ranked: list[tuple[float, int, EvidenceSpan]] = []
    query_claim = "%s %s" % (query, claim)
    for context_index, context in enumerate(contexts):
        for span_index, span in enumerate(split_context_spans(context)):
            score, _ = lexical_score(query_claim, span.text, mode="semantic")
            bonus = 0.0
            if _explicit_absence(claim, span.text):
                bonus = max(bonus, 0.45)
            if _numeric_conflict(claim, span.text):
                bonus = max(bonus, 0.55)
            if _possible_negation_relation(claim, span.text):
                bonus = max(bonus, 0.40)
            if _universal_qualified(claim, span.text):
                bonus = max(bonus, 0.40)
            relevance = max(float(score), bonus)
            if relevance <= 0:
                continue
            stable_order = context_index * 10000 + span_index
            ranked.append((relevance, stable_order, span))
    ranked.sort(key=lambda item: (-item[0], item[1]))
    selected: list[EvidenceSpan] = []
    seen: set[tuple[str, str]] = set()
    for _, _, span in ranked:
        key = (span.context_id, span.span_hash)
        if key in seen:
            continue
        seen.add(key)
        selected.append(span)
        if len(selected) >= limit:
            break
    return selected


def decompose_material_claim(claim: str) -> list[str]:
    """Conservatively split coordinated predicates and required objects."""

    text = " ".join(str(claim or "").split()).strip()
    if not text:
        return []
    terminal = text[-1] if text[-1:] in ".!?" else "."
    body = text.rstrip(".!?")

    modal = re.match(
        rf"^(?P<subject>.+?\b(?P<modal>{_MODALS}))\s+"
        r"(?P<left>.+?)\s+and\s+(?P<right>[A-Za-z][^.]+)$",
        body,
        flags=re.IGNORECASE,
    )
    if modal:
        right_first = modal.group("right").split()[0].casefold()
        if right_first in _SECOND_PREDICATES:
            prefix = "%s " % modal.group("subject").strip()
            return [
                _terminal(prefix + modal.group("left"), terminal),
                _terminal(prefix + modal.group("right"), terminal),
            ]

    shared = re.match(
        r"^(?P<subject>.+?)\s+"
        r"(?P<predicate>requires|includes|provides|offers|contains|supports|has)\s+"
        r"(?P<objects>.+)$",
        body,
        flags=re.IGNORECASE,
    )
    if shared and " and " in shared.group("objects").casefold():
        objects = _split_required_objects(shared.group("objects"))
        if len(objects) > 1:
            prefix = "%s %s " % (shared.group("subject"), shared.group("predicate"))
            return [_terminal(prefix + item, terminal) for item in objects]
    return [_terminal(body, terminal)]


def _split_required_objects(value: str) -> list[str]:
    parts = re.split(r"\s+and\s+", value, maxsplit=1, flags=re.IGNORECASE)
    if len(parts) != 2:
        return [value]
    left, right = (part.strip(" ,") for part in parts)
    nested = re.match(
        r"^(?P<prefix>.+?\bfrom)\s+both\s+(?P<first>.+?)\s+and\s+(?P<second>.+)$",
        right,
        flags=re.IGNORECASE,
    )
    if nested:
        return [
            left,
            "%s %s" % (nested.group("prefix"), nested.group("first")),
            "%s %s" % (nested.group("prefix"), nested.group("second")),
        ]
    return [left, right]


def _deterministic_assessment(
    atom: str,
    contexts: list[TraceContext],
    *,
    relation_rules: bool,
) -> dict[str, Any]:
    if not contexts:
        return {
            "verdict": "unsupported",
            "confidence": 0.95,
            "reason_code": "no_selected_evidence",
            "evidence_context_ids": [],
            "raw_verdict": "unsupported",
        }
    match = find_best_evidence(atom, contexts, mode="semantic", localize_spans=False)
    raw = classify_claim(
        Claim(id="atomic", text=atom),
        match,
        has_contexts=True,
        mode="semantic",
    )
    evidence_ids = [
        context.id
        for context in contexts
        if lexical_score(atom, context.text, mode="semantic")[0] > 0
    ] or [contexts[0].id]
    base = {
        "raw_verdict": raw.verdict,
        "raw_confidence": raw.confidence,
        "best_score": raw.best_score,
        "required_facts": list(raw.required_facts),
        "matched_facts": list(raw.matched_facts),
        "missing_facts": list(raw.missing_facts),
        "conflicting_facts": list(raw.conflicting_facts),
        "evidence_context_ids": evidence_ids,
    }
    if relation_rules:
        if any(_numeric_conflict(atom, context.text) for context in contexts):
            return {**base, "verdict": "contradicted", "confidence": 0.96, "reason_code": "numeric_value_conflict"}
        if _evidence_polarity_conflict(atom, contexts):
            return {
                **base,
                "verdict": "unverifiable",
                "confidence": 0.70,
                "reason_code": "conflicting_selected_evidence",
                "evidence_conflict": True,
            }
        if any(_explicit_absence(atom, context.text) for context in contexts):
            return {**base, "verdict": "unsupported", "confidence": 0.94, "reason_code": "evidence_explicitly_omits_asserted_detail"}
        if any(_exact_claim_approximate_evidence(atom, context.text) for context in contexts):
            return {**base, "verdict": "unverifiable", "confidence": 0.70, "reason_code": "approximate_evidence_for_exact_claim"}
        if any(_universal_excluded(atom, context.text) for context in contexts):
            return {**base, "verdict": "contradicted", "confidence": 0.94, "reason_code": "explicit_universal_exclusion"}
        if any(_universal_qualified(atom, context.text) for context in contexts):
            return {**base, "verdict": "unverifiable", "confidence": 0.72, "reason_code": "qualified_evidence_for_universal_claim"}
        if any(_negation_conflict(atom, context.text) for context in contexts):
            return {**base, "verdict": "contradicted", "confidence": 0.94, "reason_code": "explicit_negation_conflict"}
    if raw.verdict == "supported":
        return {**base, "verdict": "supported", "confidence": max(0.82, raw.confidence), "reason_code": "deterministic_support"}
    if raw.verdict == "contradicted":
        return {**base, "verdict": "unsupported", "confidence": 0.80, "reason_code": "unconfirmed_legacy_conflict"}
    if raw.verdict == "unsupported":
        return {**base, "verdict": "unsupported", "confidence": max(0.80, raw.confidence), "reason_code": "insufficient_support"}
    if raw.matched_facts:
        return {**base, "verdict": "supported", "confidence": 0.80, "reason_code": "deterministic_atom_support"}
    return {**base, "verdict": "unsupported", "confidence": 0.80, "reason_code": "related_but_not_entailed"}


def _resolve_atom_with_nli(
    atom: str,
    deterministic: dict[str, Any],
    nli_rows: tuple[dict[str, Any], ...],
    profile: LocalQualityProfile,
) -> AtomicAssessment:
    reason = str(deterministic["reason_code"])
    if reason in {
        "numeric_value_conflict",
        "explicit_universal_exclusion",
        "qualified_evidence_for_universal_claim",
        "evidence_explicitly_omits_asserted_detail",
        "approximate_evidence_for_exact_claim",
        "explicit_negation_conflict",
        "conflicting_selected_evidence",
    }:
        return AtomicAssessment(
            text=atom,
            verdict=str(deterministic["verdict"]),
            confidence=float(deterministic["confidence"]),
            reason_code=reason,
            evidence_context_ids=tuple(deterministic["evidence_context_ids"]),
            deterministic=deterministic,
            nli=nli_rows,
            evidence_conflict=bool(deterministic.get("evidence_conflict")),
        )

    accepted = {
        "entailment": [
            row
            for row in nli_rows
            if row["label"] == "entailment"
            and row["score"] >= profile.nli_entailment_threshold
        ],
        "contradiction": [
            row
            for row in nli_rows
            if row["label"] == "contradiction"
            and row["score"] >= profile.nli_contradiction_threshold
        ],
        "neutral": [
            row
            for row in nli_rows
            if row["label"] == "neutral"
            and row["score"] >= profile.nli_neutral_threshold
        ],
    }
    if accepted["entailment"] and accepted["contradiction"]:
        rows = accepted["entailment"] + accepted["contradiction"]
        return AtomicAssessment(
            atom,
            "unverifiable",
            0.70,
            "nli_detected_conflicting_evidence",
            tuple(str(row["context_id"]) for row in rows),
            deterministic,
            nli_rows,
            True,
        )
    for label, verdict, reason_code in (
        ("entailment", "supported", "local_nli_entailment"),
        ("contradiction", "contradicted", "local_nli_contradiction"),
        ("neutral", "unsupported", "local_nli_neutral"),
    ):
        if accepted[label]:
            best = max(accepted[label], key=lambda row: float(row["score"]))
            if (
                label == "contradiction"
                and deterministic.get("verdict") == "unsupported"
                and deterministic.get("reason_code")
                in {
                    "insufficient_support",
                    "related_but_not_entailed",
                    "unconfirmed_legacy_conflict",
                }
            ):
                return AtomicAssessment(
                    atom,
                    "unsupported",
                    min(0.94, float(best["score"])),
                    "nli_contradiction_not_confirmed_by_local_relation",
                    (str(best["context_id"]),),
                    deterministic,
                    nli_rows,
                )
            return AtomicAssessment(
                atom,
                verdict,
                float(best["score"]),
                reason_code,
                (str(best["context_id"]),),
                deterministic,
                nli_rows,
            )
    return AtomicAssessment(
        atom,
        "unverifiable",
        max(float(row["score"]) for row in nli_rows),
        "local_nli_below_acceptance_threshold",
        tuple(str(row["context_id"]) for row in nli_rows),
        deterministic,
        nli_rows,
    )


def _aggregate(assessments: list[AtomicAssessment]) -> tuple[str, float, str, bool]:
    if not assessments:
        return "unverifiable", 0.0, "no_verifiable_atomic_claims", False
    verdicts = [item.verdict for item in assessments]
    conflict = any(item.evidence_conflict for item in assessments)
    if conflict:
        return "unverifiable", 0.70, "conflicting_selected_evidence", True
    if "contradicted" in verdicts:
        confidence = max(item.confidence for item in assessments if item.verdict == "contradicted")
        return "contradicted", round(confidence, 3), "one_or_more_atomic_claims_contradicted", False
    if all(verdict == "supported" for verdict in verdicts):
        return "supported", round(min(item.confidence for item in assessments), 3), "all_atomic_claims_supported", False
    if "supported" in verdicts:
        confidence = min(0.92, max(0.80, min(item.confidence for item in assessments)))
        return "partially_supported", round(confidence, 3), "some_atomic_claims_not_supported", False
    if "unverifiable" in verdicts:
        confidence = max(item.confidence for item in assessments if item.verdict == "unverifiable")
        return "unverifiable", round(confidence, 3), "one_or_more_atomic_claims_ambiguous", False
    confidence = min(item.confidence for item in assessments)
    return "unsupported", round(confidence, 3), "no_atomic_claim_supported", False


def _backend_identity(nli: ClaimJudge | None) -> dict[str, Any]:
    if nli is None:
        return {
            "pipeline": VERIFIER_VERSION,
            "kind": "deterministic",
            "provider": "local_quality_rules",
            "model": None,
            "remote_inference": False,
        }
    return {
        "pipeline": VERIFIER_VERSION,
        "kind": "deterministic_plus_local_nli",
        "provider": str(getattr(nli, "provider", nli.__class__.__name__)),
        "model": str(getattr(nli, "model", "") or "") or None,
        "remote_inference": False,
    }


def _span_record(span: EvidenceSpan) -> dict[str, Any]:
    return {
        "context_id": span.context_id,
        "text": span.text,
        "start_char": span.start_char,
        "end_char": span.end_char,
        "span_hash": span.span_hash,
    }


def _selected_id(span: EvidenceSpan) -> str:
    return "%s:%s:%s" % (span.context_id, span.start_char, span.end_char)


def _terminal(value: str, terminal: str) -> str:
    text = " ".join(value.split()).strip(" ,")
    return text if text[-1:] in ".!?" else text + terminal


def _explicit_absence(claim: str, evidence: str) -> bool:
    if not _ABSENCE_RE.search(evidence):
        return False
    return bool(_topic_tokens(claim) & _topic_tokens(evidence))


def _universal_qualified(claim: str, evidence: str) -> bool:
    return bool(
        _has_universal_quantifier(claim)
        and _QUALIFIER_RE.search(evidence)
        and not _EXPLICIT_EXCLUSION_RE.search(evidence)
        and _topic_tokens(claim) & _topic_tokens(evidence)
    )


def _universal_excluded(claim: str, evidence: str) -> bool:
    return bool(
        _has_universal_quantifier(claim)
        and _EXPLICIT_EXCLUSION_RE.search(evidence)
        and len(_topic_tokens(claim) & _topic_tokens(evidence)) >= 2
    )


def _has_universal_quantifier(claim: str) -> bool:
    value = str(claim or "")
    value = re.sub(
        r"\bevery\s+(?:\d+(?:\.\d+)?|" + "|".join(_WORD_NUMBERS) + r")\s+"
        r"(?:seconds?|minutes?|hours?|days?|weeks?|months?|years?)\b",
        "",
        value,
        flags=re.IGNORECASE,
    )
    return bool(_UNIVERSAL_RE.search(value))


def _numeric_conflict(claim: str, evidence: str) -> bool:
    claim_values = _number_units(claim)
    evidence_values = _number_units(evidence)
    if not claim_values or not evidence_values:
        return False
    shared_topics = _topic_tokens(claim) & _topic_tokens(evidence)
    if len(shared_topics) < 2:
        return False
    for unit, values in claim_values.items():
        other = evidence_values.get(unit)
        if other and values.isdisjoint(other):
            return True
    return False


def _number_units(value: str) -> dict[str, set[str]]:
    normalized = str(value or "").casefold()
    for word, number in _WORD_NUMBERS.items():
        normalized = re.sub(rf"\b{word}\b", number, normalized)
    found: dict[str, set[str]] = {}
    for number, unit in re.findall(
        r"\b(\d+(?:\.\d+)?)\s+"
        r"(seconds?|minutes?|hours?|days?|weeks?|months?|years?|degrees?|percent)\b",
        normalized,
    ):
        canonical_unit = _UNIT_ALIASES.get(unit, unit.rstrip("s"))
        found.setdefault(canonical_unit, set()).add(number)
    for relation, number in re.findall(
        r"\b(platform|version|gate|room)\s+(\d+(?:\.\d+)?)\b",
        normalized,
    ):
        found.setdefault(relation, set()).add(number)
    return found


def _exact_claim_approximate_evidence(claim: str, evidence: str) -> bool:
    return bool(
        re.search(r"\b(?:exactly|exact|precisely)\b", claim, flags=re.IGNORECASE)
        and re.search(
            r"\b(?:approximately|approximate|about|around|roughly|planned|pending)\b",
            evidence,
            flags=re.IGNORECASE,
        )
        and _topic_tokens(claim) & _topic_tokens(evidence)
    )


def _possible_negation_relation(claim: str, evidence: str) -> bool:
    return bool(
        _has_semantic_negation(claim) != _has_semantic_negation(evidence)
        and len(_topic_tokens(claim) & _topic_tokens(evidence)) >= 2
    )


def _negation_conflict(claim: str, evidence: str) -> bool:
    return bool(
        _has_semantic_negation(claim) != _has_semantic_negation(evidence)
        and len(_topic_tokens(claim) & _topic_tokens(evidence)) >= 2
        and not _ABSENCE_RE.search(evidence)
    )


def _has_semantic_negation(value: str) -> bool:
    text = re.sub(
        r"\bno\s+(?:later|earlier|more|less|fewer)\s+than\b",
        "",
        str(value or ""),
        flags=re.IGNORECASE,
    )
    return bool(_NEGATION_RE.search(text))


def _evidence_polarity_conflict(atom: str, contexts: list[TraceContext]) -> bool:
    positive = negative = False
    for context in contexts:
        if len(_topic_tokens(atom) & _topic_tokens(context.text)) < 2:
            continue
        if _ABSENCE_RE.search(context.text):
            continue
        if _has_semantic_negation(context.text):
            negative = True
        else:
            positive = True
    return positive and negative


def _topic_tokens(value: str) -> set[str]:
    aliases = {
        "backed": "backup",
        "backing": "backup",
        "backups": "backup",
        "processed": "process",
        "processing": "process",
        "takes": "take",
        "customers": "customer",
        "employees": "employee",
        "plans": "plan",
        "requests": "request",
        "accounts": "account",
        "receipts": "receipt",
    }
    stop = {
        "a", "an", "and", "are", "as", "at", "be", "both", "by", "can", "each",
        "every", "for", "from", "has", "in", "is", "it", "may", "must", "of", "on",
        "or", "the", "their", "this", "to", "within", "all", "some", "not", "does", "do",
    }
    tokens = set()
    for token in re.findall(r"[a-z0-9]+", str(value or "").casefold()):
        token = aliases.get(token, token)
        if token not in stop and token not in _WORD_NUMBERS and not token.isdigit():
            tokens.add(token)
    return tokens


def _counts(values: Iterable[object]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        key = str(value)
        counts[key] = counts.get(key, 0) + 1
    return counts
