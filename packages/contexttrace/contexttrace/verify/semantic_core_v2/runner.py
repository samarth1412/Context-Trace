"""Public semantic_core_v2 verification runners."""

from __future__ import annotations

import hashlib
import json
import threading
from collections import Counter
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from contexttrace.verify.judges import ClaimJudge
from contexttrace.verify.schema import RAGTrace, load_trace_file

from .cascade import deterministic_decision, resolve_cascade
from .citations import assess_citation
from .claims import ClaimUnit, unitize_claims
from .constants import (
    CAPABILITIES,
    LIMITATIONS,
    SCHEMA_VERSION,
    TAXONOMY_VERSION,
    VERIFIER_VERSION,
)
from .diagnosis import diagnose
from .limits import DEFAULT_V2_LIMITS, V2Limits, apply_limits
from .profile import SELECTIVE_V2_PROFILE, V2Profile
from .rulepacks import load_rulepacks
from .source import assess_source_condition

ClaimUnitizer = Callable[..., tuple[list[ClaimUnit], bool]]


def verify_trace_v2(
    trace: RAGTrace,
    *,
    profile: V2Profile = SELECTIVE_V2_PROFILE,
    nli: ClaimJudge | None = None,
    limits: V2Limits = DEFAULT_V2_LIMITS,
    _claim_unitizer: ClaimUnitizer = unitize_claims,
) -> dict[str, Any]:
    """Verify one trace without changing semantic_v1_calibrated behavior."""

    if not isinstance(trace, RAGTrace):
        raise TypeError("verify_trace_v2 requires a RAGTrace.")
    bounded, truncation = apply_limits(trace, limits)
    claims, claim_limit_hit = _claim_unitizer(
        bounded.answer,
        query=bounded.query,
        max_claims=limits.max_claims,
    )
    insufficient_input = {
        "no_contexts": not bool(bounded.contexts),
        "no_verifiable_claims": not bool(claims),
        "claim_limit_hit": claim_limit_hit,
        "input_truncated": bool(truncation["applied"]),
    }
    claim_results = [
        _verify_claim(
            claim=claim,
            trace=bounded,
            profile=profile,
            nli=nli,
            truncation=truncation,
        )
        for claim in claims
    ]
    summary = _summary(claim_results)
    safe_metadata = {
        key: bounded.metadata[key]
        for key in ("case_id", "dataset_id", "trace_id", "run_id")
        if key in bounded.metadata
        and isinstance(bounded.metadata[key], (str, int, float, bool, type(None)))
    }
    rulepacks = load_rulepacks()
    result: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "taxonomy_version": TAXONOMY_VERSION,
        "verifier_version": VERIFIER_VERSION,
        "profile_id": profile.id,
        "profile_version": profile.version,
        "profile_sha256": profile.sha256,
        "input_identity": {
            "query_sha256": _text_sha256(trace.query),
            "answer_sha256": _text_sha256(trace.answer),
            "context_ids_sha256": _canonical_sha256(
                [context.id for context in trace.contexts]
            ),
            "metadata": safe_metadata,
        },
        "claims": claim_results,
        "summary": summary,
        "truncation": truncation,
        "insufficient_input": insufficient_input,
        "capabilities": dict(CAPABILITIES),
        "limitations": list(LIMITATIONS),
        "verification_profile": profile.to_dict(),
        "rulepacks": [
            {"id": item["id"], "version": item["version"]} for item in rulepacks
        ],
    }
    result["prediction_payload_sha256"] = _canonical_sha256(result)
    return result


def verify_trace_file_v2(
    path: str | Path,
    *,
    profile: V2Profile = SELECTIVE_V2_PROFILE,
    nli: ClaimJudge | None = None,
    limits: V2Limits = DEFAULT_V2_LIMITS,
    _claim_unitizer: ClaimUnitizer = unitize_claims,
) -> dict[str, Any]:
    return verify_trace_v2(
        load_trace_file(path),
        profile=profile,
        nli=nli,
        limits=limits,
        _claim_unitizer=_claim_unitizer,
    )


def verify_traces_v2(
    traces: list[RAGTrace],
    *,
    profile: V2Profile = SELECTIVE_V2_PROFILE,
    nli: ClaimJudge | None = None,
    limits: V2Limits = DEFAULT_V2_LIMITS,
    max_workers: int = 4,
    _claim_unitizer: ClaimUnitizer = unitize_claims,
) -> list[dict[str, Any]]:
    """Verify a batch with bounded workers and stable input ordering."""

    if not 1 <= max_workers <= 8:
        raise ValueError("max_workers must be between 1 and 8.")
    safe_nli: ClaimJudge | None = _LockedJudge(nli) if nli is not None else None

    def run(trace: RAGTrace) -> dict[str, Any]:
        return verify_trace_v2(
            trace,
            profile=profile,
            nli=safe_nli,
            limits=limits,
            _claim_unitizer=_claim_unitizer,
        )

    with ThreadPoolExecutor(
        max_workers=max_workers,
        thread_name_prefix="contexttrace-v2",
    ) as executor:
        return list(executor.map(run, traces))


def _verify_claim(
    *,
    claim: ClaimUnit,
    trace: RAGTrace,
    profile: V2Profile,
    nli: ClaimJudge | None,
    truncation: dict[str, Any],
) -> dict[str, Any]:
    deterministic = deterministic_decision(claim, trace, profile)
    cascade = resolve_cascade(
        claim=claim,
        trace=trace,
        profile=profile,
        deterministic=deterministic,
        nli=nli,
    )
    source = assess_source_condition(
        best_context_id=deterministic.match.context_id,
        trace=trace,
        profile=profile,
    )
    citation = assess_citation(
        claim=claim,
        verdict=cascade.verdict,
        best_context_id=deterministic.match.context_id,
        trace=trace,
        profile=profile,
    )
    diagnosis = diagnose(
        verdict=cascade.verdict,
        confidence=cascade.confidence,
        route=cascade.route,
        abstained=cascade.abstained,
        citation_state=str(citation["state"]),
        source_condition=str(source["condition"]),
        trace=trace,
        profile=profile,
    )
    if truncation["applied"]:
        diagnosis["green"] = False
        diagnosis["qualification_required"] = True

    evidence_spans = _evidence_spans(
        deterministic.signals,
        cascade.verdict,
    )
    return {
        **claim.to_dict(),
        "claim_verdict": cascade.verdict,
        "support_status": _support_status(cascade.verdict),
        "truth_status": "not_assessed",
        "source_condition": source["condition"],
        "source_assessment": source,
        "citation_state": citation["state"],
        "citation_assessment": citation,
        "failure_label": diagnosis["failure_label"],
        "primary_root_cause": diagnosis["primary_root_cause"],
        "abstention_requirement": diagnosis["abstention_requirement"],
        "diagnostic_abstention": cascade.abstained,
        "diagnostic_confidence": diagnosis["diagnostic_confidence"],
        "confidence_semantics": diagnosis["confidence_semantics"],
        "route": cascade.route,
        "route_reason_code": cascade.reason_code,
        "green": diagnosis["green"],
        "qualification_required": diagnosis["qualification_required"],
        "evidence_spans": evidence_spans,
        "evidence_context_ids": sorted(
            {
                str(span["context_id"])
                for span in evidence_spans
                if span.get("context_id")
            }
        ),
        "deterministic": {
            "verdict": deterministic.verdict,
            "confidence": deterministic.confidence,
            "reason_code": deterministic.reason_code,
            "signals": deterministic.signals,
        },
        "nli": cascade.nli,
        "nli_error_code": cascade.nli_error_code,
        "flags": {
            "query_conditioned_answer_fragment": claim.answer_fragment,
            "weak_lexical_overlap_only": bool(
                deterministic.verdict == "unverifiable"
                and deterministic.match.score > 0
            ),
            "input_truncated": bool(truncation["applied"]),
            "insufficient_evidence": cascade.verdict == "unverifiable",
        },
    }


def _evidence_spans(
    signals: dict[str, Any],
    verdict: str,
) -> list[dict[str, Any]]:
    raw = list(signals.get("supporting_spans") or [])
    if not raw and isinstance(signals.get("evidence_span"), dict):
        raw = [signals["evidence_span"]]
    role = "contradicting" if verdict == "contradicted" else "supporting"
    spans: list[dict[str, Any]] = []
    for span in raw[:3]:
        context_id = span.get("context_id")
        text = str(span.get("text") or "")
        start = span.get("start_char")
        end = span.get("end_char")
        if (
            not context_id
            or not text
            or not isinstance(start, int)
            or not isinstance(end, int)
        ):
            continue
        spans.append(
            {
                "context_id": context_id,
                "start_char": start,
                "end_char": end,
                "text": text,
                "role": role,
                "span_hash": span.get("span_hash"),
            }
        )
    return spans


def _support_status(verdict: str) -> str:
    return {
        "supported": "supported_by_selected_evidence",
        "partially_supported": "partially_supported_by_selected_evidence",
        "contradicted": "contradicted_by_selected_evidence",
        "unsupported": "unsupported_by_selected_evidence",
        "unverifiable": "insufficient_or_ambiguous_evidence",
    }[verdict]


def _summary(claims: list[dict[str, Any]]) -> dict[str, Any]:
    verdicts = Counter(str(claim["claim_verdict"]) for claim in claims)
    failures = Counter(str(claim["failure_label"]) for claim in claims)
    roots = Counter(str(claim["primary_root_cause"]) for claim in claims)
    nli_calls = sum(claim["nli"] is not None for claim in claims)
    abstentions = sum(bool(claim["diagnostic_abstention"]) for claim in claims)
    return {
        "total_claims": len(claims),
        "claim_verdicts": {key: verdicts[key] for key in sorted(verdicts)},
        "failure_labels": {key: failures[key] for key in sorted(failures)},
        "root_causes": {key: roots[key] for key in sorted(roots)},
        "diagnostic_abstentions": abstentions,
        "diagnostic_coverage": round(
            (len(claims) - abstentions) / len(claims),
            6,
        )
        if claims
        else 0.0,
        "nli_invocations": nli_calls,
        "nli_invocation_rate": round(nli_calls / len(claims), 6) if claims else 0.0,
        "green_claims": sum(bool(claim["green"]) for claim in claims),
        "truth_status": "not_assessed",
        "overall_status": _overall_status(claims),
    }


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


def _text_sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class _LockedJudge:
    def __init__(self, judge: ClaimJudge) -> None:
        self._judge = judge
        self._lock = threading.Lock()

    def verify_claim(
        self,
        *,
        query: str,
        claim: str,
        contexts: list[Any],
    ) -> Any:
        with self._lock:
            return self._judge.verify_claim(
                query=query,
                claim=claim,
                contexts=contexts,
            )
