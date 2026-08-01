"""Product runners that apply the v2.1 NLI-only green-promotion guard."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from contexttrace.verify.judges import ClaimJudge
from contexttrace.verify.schema import RAGTrace
from contexttrace.verify.semantic_core_v2.limits import DEFAULT_V2_LIMITS, V2Limits
from contexttrace.verify.semantic_core_v2.runner import (
    verify_trace_file_v2,
    verify_trace_v2,
    verify_traces_v2,
)

from .profile import SELECTIVE_V2_1_PROFILE, V21Profile


def verify_trace_v2_1(
    trace: RAGTrace,
    *,
    profile: V21Profile = SELECTIVE_V2_1_PROFILE,
    nli: ClaimJudge | None = None,
    limits: V2Limits = DEFAULT_V2_LIMITS,
) -> dict[str, Any]:
    """Verify one trace and prevent ambiguous NLI-only support from going green."""

    result = verify_trace_v2(trace, profile=profile, nli=nli, limits=limits)
    return _apply_safety_policy(result, profile)


def verify_trace_file_v2_1(
    path: str | Path,
    *,
    profile: V21Profile = SELECTIVE_V2_1_PROFILE,
    nli: ClaimJudge | None = None,
    limits: V2Limits = DEFAULT_V2_LIMITS,
) -> dict[str, Any]:
    result = verify_trace_file_v2(path, profile=profile, nli=nli, limits=limits)
    return _apply_safety_policy(result, profile)


def verify_traces_v2_1(
    traces: list[RAGTrace],
    *,
    profile: V21Profile = SELECTIVE_V2_1_PROFILE,
    nli: ClaimJudge | None = None,
    limits: V2Limits = DEFAULT_V2_LIMITS,
    max_workers: int = 4,
) -> list[dict[str, Any]]:
    results = verify_traces_v2(
        traces,
        profile=profile,
        nli=nli,
        limits=limits,
        max_workers=max_workers,
    )
    return [_apply_safety_policy(result, profile) for result in results]


def _apply_safety_policy(
    result: dict[str, Any],
    profile: V21Profile,
) -> dict[str, Any]:
    if profile.prevent_nli_only_green_promotion:
        for claim in result["claims"]:
            if not _is_ambiguous_nli_only_support(claim):
                continue
            claim["green"] = False
            claim["qualification_required"] = True
            claim["flags"]["nli_only_green_promotion_blocked"] = True

    claims = list(result["claims"])
    result["summary"]["green_claims"] = sum(bool(claim["green"]) for claim in claims)
    result["summary"]["overall_status"] = _overall_status(claims)
    result.pop("prediction_payload_sha256", None)
    result["prediction_payload_sha256"] = _canonical_sha256(result)
    return result


def _is_ambiguous_nli_only_support(claim: dict[str, Any]) -> bool:
    deterministic = dict(claim.get("deterministic") or {})
    return bool(
        claim.get("route") == "nli"
        and claim.get("claim_verdict") == "supported"
        and deterministic.get("verdict") == "unverifiable"
    )


def _overall_status(claims: list[dict[str, Any]]) -> str:
    if not claims:
        return "insufficient_input"
    if any(claim["diagnostic_abstention"] for claim in claims):
        return "abstained"
    if all(claim["green"] for claim in claims):
        return "green"
    return "warning"


def _canonical_sha256(value: Any) -> str:
    raw = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()
