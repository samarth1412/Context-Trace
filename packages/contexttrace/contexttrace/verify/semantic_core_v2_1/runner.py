"""Product runners that apply the v2.1 NLI-only green-promotion guard."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from contexttrace.verify.judges import ClaimJudge
from contexttrace.verify.schema import RAGTrace, TraceContext
from contexttrace.verify.semantic_core_v2.claims import unitize_claims
from contexttrace.verify.semantic_core_v2.limits import DEFAULT_V2_LIMITS, V2Limits
from contexttrace.verify.semantic_core_v2.runner import (
    ClaimUnitizer,
    verify_trace_file_v2,
    verify_trace_v2,
    verify_traces_v2,
)

from .claims import unitize_atomic_claims
from .profile import SELECTIVE_V2_1_PROFILE, V21Profile


def verify_trace_v2_1(
    trace: RAGTrace,
    *,
    profile: V21Profile = SELECTIVE_V2_1_PROFILE,
    nli: ClaimJudge | None = None,
    limits: V2Limits = DEFAULT_V2_LIMITS,
) -> dict[str, Any]:
    """Verify one trace and prevent ambiguous NLI-only support from going green."""

    result = verify_trace_v2(
        trace,
        profile=profile,
        nli=_composing_nli(nli, profile),
        limits=limits,
        _claim_unitizer=_claim_unitizer(profile),
    )
    return _apply_safety_policy(result, profile)


def verify_trace_file_v2_1(
    path: str | Path,
    *,
    profile: V21Profile = SELECTIVE_V2_1_PROFILE,
    nli: ClaimJudge | None = None,
    limits: V2Limits = DEFAULT_V2_LIMITS,
) -> dict[str, Any]:
    result = verify_trace_file_v2(
        path,
        profile=profile,
        nli=_composing_nli(nli, profile),
        limits=limits,
        _claim_unitizer=_claim_unitizer(profile),
    )
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
        nli=_composing_nli(nli, profile),
        limits=limits,
        max_workers=max_workers,
        _claim_unitizer=_claim_unitizer(profile),
    )
    return [_apply_safety_policy(result, profile) for result in results]


class _ComposingNLI:
    def __init__(self, judge: ClaimJudge, profile: V21Profile) -> None:
        self._judge = judge
        self._profile = profile

    def verify_claim(
        self,
        *,
        query: str,
        claim: str,
        contexts: list[TraceContext],
    ) -> Any:
        composed = _compose_contexts(query, contexts, self._profile)
        return self._judge.verify_claim(
            query=query,
            claim=claim,
            contexts=composed,
        )


def _composing_nli(
    nli: ClaimJudge | None,
    profile: V21Profile,
) -> ClaimJudge | None:
    if nli is None:
        return None
    if (
        not profile.compose_same_source_nli_spans
        and not profile.include_query_cue_for_nli
    ):
        return nli
    return _ComposingNLI(nli, profile)


def _claim_unitizer(profile: V21Profile) -> ClaimUnitizer:
    if profile.atomic_claim_unitization:
        return unitize_atomic_claims
    return unitize_claims


def _compose_contexts(
    query: str,
    contexts: list[TraceContext],
    profile: V21Profile,
) -> list[TraceContext]:
    groups: dict[str, list[TraceContext]] = {}
    order: list[str] = []
    for context in contexts:
        if context.id not in groups:
            groups[context.id] = []
            order.append(context.id)
        groups[context.id].append(context)

    composed: list[TraceContext] = []
    for context_id in order:
        spans = groups[context_id]
        if profile.compose_same_source_nli_spans:
            spans = sorted(spans, key=_span_start)
        texts = list(dict.fromkeys(context.text.strip() for context in spans))
        evidence = " ".join(text for text in texts if text)
        evidence = evidence[: profile.max_composed_nli_chars].strip()
        query_cue = str(query or "")[: profile.max_nli_query_chars].strip()
        if profile.include_query_cue_for_nli and query_cue:
            premise = f"Question: {query_cue}\nEvidence: {evidence}"
        else:
            premise = evidence
        composed.append(
            TraceContext(
                id=context_id,
                text=premise,
                metadata={
                    "evidence_scope": "bounded_composed_selected_spans",
                    "composed_span_count": len(spans),
                },
            )
        )
    return composed


def _span_start(context: TraceContext) -> tuple[int, str]:
    value = context.metadata.get("start_char")
    return (value if isinstance(value, int) else 0, context.text)


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
