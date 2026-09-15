"""Opt-in entry points for metadata-free evidence-relation reasoning."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from contexttrace.verify.judges import ClaimJudge
from contexttrace.verify.runner import (
    FULL_VERIFICATION_PROFILE,
    VerificationLimits,
    VerificationProfile,
    _apply_limits,
    _normalize_mode,
    _verify_trace_with_profile,
)
from contexttrace.verify.schema import RAGTrace, load_trace_file
from contexttrace.verify.semantic_normalization import semantic_normalization

from .constants import (
    CAPABILITIES,
    DIAGNOSTIC_REASONER_VERSION,
    LIMITATIONS,
    PROFILE_ID,
    SCHEMA_VERSION,
    TAXONOMY_VERSION,
    VERIFIER_VERSION,
)
from .relations import refine_relational_verifications


def verify_trace_hybrid_v2(
    trace: RAGTrace,
    *,
    mode: str = "semantic",
    judge: ClaimJudge | None = None,
    nli: ClaimJudge | None = None,
    profile: VerificationProfile | None = None,
    limits: VerificationLimits | None = None,
) -> dict[str, Any]:
    """Verify one trace with the experimental hybrid_v2 reasoning layer."""

    mode = _normalize_mode(mode)
    profile = profile or FULL_VERIFICATION_PROFILE
    bounded_trace, truncation = _apply_limits(trace, limits)
    with semantic_normalization(profile.semantic_normalization):
        result = _verify_trace_with_profile(
            bounded_trace,
            mode=mode,
            judge=judge,
            nli=nli,
            profile=profile,
            reasoning_mode="hybrid_v2",
            verification_refiner=refine_relational_verifications,
        )
    result.update(
        {
            "schema_version": SCHEMA_VERSION,
            "taxonomy_version": TAXONOMY_VERSION,
            "verifier_version": VERIFIER_VERSION,
            "profile_id": _profile_id(profile),
            "diagnostic_reasoner_version": DIAGNOSTIC_REASONER_VERSION,
            "experimental": True,
            "capabilities": dict(CAPABILITIES),
            "limitations": list(LIMITATIONS),
            "truncation": truncation,
        }
    )
    return result


def verify_trace_file_hybrid_v2(
    path: str | Path,
    *,
    mode: str = "semantic",
    judge: ClaimJudge | None = None,
    nli: ClaimJudge | None = None,
    profile: VerificationProfile | None = None,
    limits: VerificationLimits | None = None,
) -> dict[str, Any]:
    return verify_trace_hybrid_v2(
        load_trace_file(path),
        mode=mode,
        judge=judge,
        nli=nli,
        profile=profile,
        limits=limits,
    )


def verify_traces_hybrid_v2(
    traces: list[RAGTrace],
    *,
    mode: str = "semantic",
    judge: ClaimJudge | None = None,
    nli: ClaimJudge | None = None,
    profile: VerificationProfile | None = None,
    limits: VerificationLimits | None = None,
) -> list[dict[str, Any]]:
    return [
        verify_trace_hybrid_v2(
            trace,
            mode=mode,
            judge=judge,
            nli=nli,
            profile=profile,
            limits=limits,
        )
        for trace in traces
    ]


def _profile_id(profile: VerificationProfile) -> str:
    if profile == FULL_VERIFICATION_PROFILE:
        return PROFILE_ID
    from contexttrace.contracts import verification_profile_id

    return "%s_%s" % (PROFILE_ID, verification_profile_id(profile.to_dict()))
