"""Fail-closed complexity bound for the v2.1 deterministic fact path."""

from __future__ import annotations

import re

from contexttrace.verify.evidence import find_best_evidence
from contexttrace.verify.schema import RAGTrace
from contexttrace.verify.semantic_core_v2.cascade import (
    DeterministicDecision,
    deterministic_decision,
)
from contexttrace.verify.semantic_core_v2.claims import ClaimUnit
from contexttrace.verify.semantic_core_v2.profile import V2Profile

COMPLEX_FACT_GUARD_VERSION = "complex-fact-guard-v1.0.0"
MAX_IDENTIFIER_SCOPE_TERMS = 8
MAX_SCOPE_SEPARATORS = 12

_IDENTIFIER_RE = re.compile(r"\b[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+\b")
_WORD_RE = re.compile(r"[^\W_]+", re.UNICODE)


def bounded_deterministic_decision(
    claim: ClaimUnit,
    trace: RAGTrace,
    profile: V2Profile,
) -> DeterministicDecision:
    """Route combinatorial fact scopes to NLI without touching frozen v1 code."""

    complexity = fact_scope_complexity(claim.verification_text)
    if not complexity["guarded"]:
        return deterministic_decision(claim, trace, profile)

    match = find_best_evidence(
        claim.verification_text,
        trace.contexts,
        mode="semantic",
        localize_spans=True,
    )
    confidence = 0.99 if not trace.contexts else min(0.75, max(0.45, match.score))
    signals = {
        "best_context_id": match.context_id,
        "best_score": round(float(match.score), 6),
        "exact_surface_support": False,
        "required_facts": [],
        "matched_facts": [],
        "missing_facts": [claim.verification_text],
        "conflicting_facts": [],
        "raw_verdict": "unverifiable",
        "evidence_span": match.span_dict(),
        "supporting_spans": [dict(item) for item in (match.supporting_spans or [])],
        "complex_fact_guard": complexity,
    }
    return DeterministicDecision(
        verdict="unverifiable",
        confidence=round(confidence, 6),
        reason_code="bounded_complex_fact_scope_routed_to_nli",
        requires_nli=bool(trace.contexts),
        match=match,
        signals=signals,
    )


def fact_scope_complexity(text: str) -> dict[str, int | str | bool]:
    """Return the frozen observable features used by the complexity guard."""

    value = str(text or "")
    identifier_count = len(set(_IDENTIFIER_RE.findall(value)))
    separator_count = value.count(",") + len(
        re.findall(r"\b(?:and|or)\b", value, flags=re.IGNORECASE)
    )
    word_count = len(_WORD_RE.findall(value))
    guarded = identifier_count >= MAX_IDENTIFIER_SCOPE_TERMS or (
        separator_count >= MAX_SCOPE_SEPARATORS and word_count >= 30
    )
    return {
        "version": COMPLEX_FACT_GUARD_VERSION,
        "guarded": guarded,
        "identifier_scope_terms": identifier_count,
        "scope_separators": separator_count,
        "word_count": word_count,
        "max_identifier_scope_terms": MAX_IDENTIFIER_SCOPE_TERMS,
        "max_scope_separators": MAX_SCOPE_SEPARATORS,
    }
