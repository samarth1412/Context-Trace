"""Selective deterministic-to-NLI cascade for semantic_core_v2."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from contexttrace.verify.claims import Claim
from contexttrace.verify.evidence import (
    EvidenceMatch,
    find_best_evidence,
    has_unnegated_exact_surface_match,
)
from contexttrace.verify.judges import ClaimJudge, JudgeVerdict
from contexttrace.verify.schema import RAGTrace, TraceContext
from contexttrace.verify.verdicts import classify_claim

from .claims import ClaimUnit
from .profile import V2Profile


@dataclass(frozen=True)
class DeterministicDecision:
    verdict: str
    confidence: float
    reason_code: str
    requires_nli: bool
    match: EvidenceMatch
    signals: dict[str, Any]


@dataclass(frozen=True)
class CascadeDecision:
    verdict: str
    confidence: float
    route: str
    abstained: bool
    reason_code: str
    deterministic: DeterministicDecision
    nli: dict[str, Any] | None
    nli_error_code: str | None = None


def deterministic_decision(
    claim: ClaimUnit,
    trace: RAGTrace,
    profile: V2Profile,
) -> DeterministicDecision:
    match = find_best_evidence(
        claim.verification_text,
        trace.contexts,
        mode="semantic",
        localize_spans=True,
    )
    raw = classify_claim(
        Claim(id=claim.id, text=claim.verification_text),
        match,
        has_contexts=bool(trace.contexts),
        mode="semantic",
        contradiction_checks=True,
    )
    thresholds = profile.thresholds
    exact_support = bool(
        match.context_id
        and has_unnegated_exact_surface_match(
            claim.verification_text,
            match.supporting_text or match.snippet,
        )
    )
    all_material_facts = bool(
        raw.required_facts and not raw.missing_facts and not raw.conflicting_facts
    )
    conflict = bool(raw.conflicting_facts or raw.verdict == "contradicted")
    signals = {
        "best_context_id": match.context_id,
        "best_score": round(float(match.score), 6),
        "exact_surface_support": exact_support,
        "required_facts": list(raw.required_facts),
        "matched_facts": list(raw.matched_facts),
        "missing_facts": list(raw.missing_facts),
        "conflicting_facts": list(raw.conflicting_facts),
        "raw_verdict": raw.verdict,
        "evidence_span": match.span_dict(),
        "supporting_spans": [dict(item) for item in (match.supporting_spans or [])],
    }

    if not trace.contexts:
        verdict = "unverifiable"
        confidence = 0.99
        reason = "no_contexts"
    elif conflict and match.score >= thresholds.deterministic_conflict_score:
        verdict = "contradicted"
        confidence = max(0.94, min(0.98, float(raw.confidence)))
        reason = "observable_fact_or_polarity_conflict"
    elif (
        all_material_facts
        and match.score >= thresholds.deterministic_strong_support_score
    ):
        verdict = "supported"
        confidence = max(0.94, min(0.98, float(raw.confidence)))
        reason = "all_material_facts_matched"
    elif exact_support and match.score >= thresholds.deterministic_exact_support_score:
        verdict = "supported"
        confidence = 0.92
        reason = "exact_surface_support"
    elif match.score < thresholds.deterministic_unsupported_score:
        verdict = "unsupported"
        confidence = max(0.86, min(0.98, 1.0 - float(match.score)))
        reason = "insufficient_evidence_overlap"
    elif raw.verdict == "partially_supported":
        verdict = "partially_supported"
        confidence = min(0.79, max(0.55, float(raw.confidence)))
        reason = "material_fact_coverage_incomplete"
    else:
        verdict = "unverifiable"
        confidence = min(0.75, max(0.45, float(raw.confidence)))
        reason = "ambiguous_deterministic_evidence"

    requires_nli = bool(
        trace.contexts
        and (
            confidence < thresholds.deterministic_accept_confidence
            or verdict in {"partially_supported", "unverifiable"}
        )
    )
    return DeterministicDecision(
        verdict=verdict,
        confidence=round(confidence, 6),
        reason_code=reason,
        requires_nli=requires_nli,
        match=match,
        signals=signals,
    )


def resolve_cascade(
    *,
    claim: ClaimUnit,
    trace: RAGTrace,
    profile: V2Profile,
    deterministic: DeterministicDecision,
    nli: ClaimJudge | None,
) -> CascadeDecision:
    if not deterministic.requires_nli:
        abstained = deterministic.verdict == "unverifiable"
        return CascadeDecision(
            verdict=deterministic.verdict,
            confidence=deterministic.confidence,
            route="deterministic",
            abstained=abstained,
            reason_code=deterministic.reason_code,
            deterministic=deterministic,
            nli=None,
        )

    if not profile.enable_nli:
        return _unresolved(
            deterministic,
            reason_code="nli_disabled_for_low_confidence_claim",
            error_code=None,
            forced=profile.forced_classification,
        )

    if nli is None:
        return _unresolved(
            deterministic,
            reason_code="nli_required_but_unavailable",
            error_code="nli_unavailable",
            forced=profile.forced_classification,
        )

    contexts = _nli_contexts(deterministic.match, profile)
    if not contexts:
        return _unresolved(
            deterministic,
            reason_code="no_bounded_evidence_span_for_nli",
            error_code="nli_evidence_unavailable",
            forced=profile.forced_classification,
        )
    try:
        verdict = nli.verify_claim(
            query=trace.query,
            claim=claim.verification_text,
            contexts=contexts,
        )
    except Exception:
        return _unresolved(
            deterministic,
            reason_code="local_nli_execution_failed",
            error_code="nli_runtime_failure",
            forced=profile.forced_classification,
        )

    nli_record = _nli_record(verdict)
    nli_verdict, accepted = _accepted_nli_verdict(verdict, profile)
    if not accepted:
        return _unresolved(
            deterministic,
            reason_code="local_nli_below_frozen_threshold",
            error_code=None,
            forced=profile.forced_classification,
            nli_record=nli_record,
        )

    if deterministic.verdict == "unverifiable":
        return CascadeDecision(
            verdict=nli_verdict,
            confidence=round(float(verdict.confidence), 6),
            route="nli",
            abstained=False,
            reason_code="nli_resolved_ambiguous_deterministic_evidence",
            deterministic=deterministic,
            nli=nli_record,
        )

    if _agreement(deterministic.verdict, nli_verdict):
        return CascadeDecision(
            verdict=nli_verdict,
            confidence=round(
                min(
                    0.98,
                    max(deterministic.confidence, float(verdict.confidence)),
                ),
                6,
            ),
            route="deterministic_nli_agreement",
            abstained=False,
            reason_code="deterministic_nli_agreement",
            deterministic=deterministic,
            nli=nli_record,
        )

    if profile.use_deterministic_on_nli_disagreement or profile.forced_classification:
        return CascadeDecision(
            verdict=deterministic.verdict,
            confidence=round(min(0.79, deterministic.confidence), 6),
            route="deterministic_nli_disagreement",
            abstained=False,
            reason_code="forced_deterministic_after_nli_disagreement",
            deterministic=deterministic,
            nli=nli_record,
        )

    return CascadeDecision(
        verdict="unverifiable",
        confidence=round(
            min(
                0.79,
                max(deterministic.confidence, float(verdict.confidence)),
            ),
            6,
        ),
        route="deterministic_nli_disagreement",
        abstained=True,
        reason_code="unresolved_deterministic_nli_disagreement",
        deterministic=deterministic,
        nli=nli_record,
    )


def _nli_contexts(match: EvidenceMatch, profile: V2Profile) -> list[TraceContext]:
    spans = list(match.supporting_spans or [])
    if not spans:
        span = match.span_dict()
        if span:
            spans = [span]
    contexts: list[TraceContext] = []
    seen: set[tuple[object, ...]] = set()
    for span in spans:
        text = str(span.get("text") or "")[: profile.max_nli_span_chars].strip()
        context_id = str(span.get("context_id") or match.context_id or "").strip()
        key = (context_id, span.get("start_char"), span.get("end_char"))
        if not text or not context_id or key in seen:
            continue
        seen.add(key)
        contexts.append(
            TraceContext(
                id=context_id,
                text=text,
                metadata={
                    "evidence_scope": "bounded_selected_span",
                    "start_char": span.get("start_char"),
                    "end_char": span.get("end_char"),
                    "span_hash": span.get("span_hash"),
                },
            )
        )
        if len(contexts) == profile.max_nli_spans:
            break
    return contexts


def _accepted_nli_verdict(
    verdict: JudgeVerdict,
    profile: V2Profile,
) -> tuple[str, bool]:
    raw_label = str(verdict.raw.get("nli_label") or "").casefold()
    thresholds = profile.thresholds
    if raw_label == "entailment":
        return "supported", verdict.confidence >= thresholds.nli_entailment_confidence
    if raw_label == "contradiction":
        return (
            "contradicted",
            verdict.confidence >= thresholds.nli_contradiction_confidence,
        )
    if raw_label == "neutral":
        return "unsupported", verdict.confidence >= thresholds.nli_neutral_confidence
    if verdict.verdict in {"supported", "contradicted", "unsupported"}:
        threshold = (
            thresholds.nli_entailment_confidence
            if verdict.verdict == "supported"
            else thresholds.nli_contradiction_confidence
            if verdict.verdict == "contradicted"
            else thresholds.nli_neutral_confidence
        )
        return verdict.verdict, verdict.confidence >= threshold
    return "unverifiable", False


def _agreement(deterministic: str, nli: str) -> bool:
    return deterministic == nli


def _nli_record(verdict: JudgeVerdict) -> dict[str, Any]:
    return {
        "provider": str(verdict.provider),
        "model": str(verdict.model) if verdict.model else None,
        "verdict": verdict.verdict,
        "confidence": round(float(verdict.confidence), 6),
        "nli_label": verdict.raw.get("nli_label"),
        "nli_scores": dict(verdict.raw.get("nli_scores") or {}),
        "backend": verdict.raw.get("backend"),
        "evidence_scope": "bounded_selected_spans_only",
        "context_id": verdict.raw.get("context_id"),
    }


def _unresolved(
    deterministic: DeterministicDecision,
    *,
    reason_code: str,
    error_code: str | None,
    forced: bool,
    nli_record: dict[str, Any] | None = None,
) -> CascadeDecision:
    if forced:
        return CascadeDecision(
            verdict=deterministic.verdict,
            confidence=round(min(0.79, deterministic.confidence), 6),
            route="unresolved",
            abstained=False,
            reason_code=f"forced_classification:{reason_code}",
            deterministic=deterministic,
            nli=nli_record,
            nli_error_code=error_code,
        )
    return CascadeDecision(
        verdict="unverifiable",
        confidence=round(min(0.79, deterministic.confidence), 6),
        route="unresolved",
        abstained=True,
        reason_code=reason_code,
        deterministic=deterministic,
        nli=nli_record,
        nli_error_code=error_code,
    )
