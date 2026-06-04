from __future__ import annotations

from pathlib import Path
from typing import Any

from contexttrace.verify.audit import audit_trace
from contexttrace.verify.runner import verify_trace
from contexttrace.verify.schema import RAGTrace
from contexttrace.verify.trace_inspect import inspect_trace


HIGH_RISK_LABELS = {"contradicted", "should_abstain", "corpus_gap", "stale_source"}
MEDIUM_RISK_LABELS = {
    "unsupported",
    "partially_supported",
    "retrieval_miss",
    "answer_overreach",
    "chunking_issue",
    "reranking_failure",
}
LOW_RISK_LABELS = {"unverifiable", "insufficient_context", "citation_mismatch", "inspect_warning"}


def qa_trace(
    trace: RAGTrace,
    *,
    trace_path: str | None = None,
    corpus_path: str | Path | None = None,
    mode: str = "lexical",
) -> dict[str, Any]:
    """Run the complete local evidence QA workflow for a portable RAG trace."""

    inspection = inspect_trace(trace, trace_path=trace_path)
    verification = verify_trace(trace, mode=mode)
    audit = audit_trace(trace, corpus_path=corpus_path, mode=mode) if corpus_path else None
    summary = _summary(
        inspection=inspection,
        verification=verification,
        audit=audit,
        mode=mode,
        corpus_path=str(corpus_path) if corpus_path else None,
    )
    return {
        "query": trace.query,
        "answer": trace.answer,
        "summary": summary,
        "inspection": inspection,
        "verification": verification,
        "audit": audit,
        "next_actions": _next_actions(inspection, verification, audit),
        "metadata": dict(trace.metadata),
    }


def qa_failures(result: dict[str, Any], fail_on: tuple[str, ...]) -> list[str]:
    if not fail_on:
        return []
    summary = result.get("summary") or {}
    messages = []
    for raw_rule in fail_on:
        rule = raw_rule.strip().lower().replace("-", "_")
        if rule in {"any_risk", "risk"} and summary.get("risk_level") != "pass":
            messages.append("QA risk detected")
        elif rule == "high_risk" and summary.get("risk_level") == "high":
            messages.append("high QA risk detected")
        elif rule == "medium_risk" and summary.get("risk_level") in {"high", "medium"}:
            messages.append("medium-or-higher QA risk detected")
        elif rule == "unsupported" and int(summary.get("unsupported") or 0) > 0:
            messages.append("unsupported claim detected")
        elif rule == "should_abstain" and bool(summary.get("should_abstain")):
            messages.append("answer should have abstained")
        elif rule == "audit_failure" and bool(summary.get("has_audit_failures")):
            messages.append("audit failure detected")
        elif rule == "inspect_warning" and int(summary.get("inspect_warnings") or 0) > 0:
            messages.append("trace inspection warning detected")
        elif rule not in {
            "any_risk",
            "risk",
            "high_risk",
            "medium_risk",
            "unsupported",
            "should_abstain",
            "audit_failure",
            "inspect_warning",
        }:
            messages.append("unknown --fail-on rule %s" % raw_rule)
    return messages


def _summary(
    *,
    inspection: dict[str, Any],
    verification: dict[str, Any],
    audit: dict[str, Any] | None,
    mode: str,
    corpus_path: str | None,
) -> dict[str, Any]:
    verify_summary = verification.get("summary") or {}
    audit_summary = (audit or {}).get("summary") or {}
    signals = _risk_signals(inspection, verify_summary, audit_summary)
    risk_score = min(100, sum(int(signal["points"]) for signal in signals))
    risk_level = _risk_level(risk_score)
    primary_issue = _primary_issue(signals, verify_summary, audit_summary)
    return {
        "mode": mode,
        "risk_score": risk_score,
        "risk_level": risk_level,
        "severity": risk_level,
        "primary_issue": primary_issue,
        "corpus_audited": audit is not None,
        "corpus_path": corpus_path,
        "total_claims": verify_summary.get("total_claims", 0),
        "support_rate": verify_summary.get("support_rate", 0),
        "unsupported_claim_rate": verify_summary.get("unsupported_claim_rate", 0),
        "supported": verify_summary.get("supported", 0),
        "partially_supported": verify_summary.get("partially_supported", 0),
        "unsupported": verify_summary.get("unsupported", 0),
        "unverifiable": verify_summary.get("unverifiable", 0),
        "contradicted": verify_summary.get("contradicted", 0),
        "citation_mismatches": verify_summary.get("citation_mismatches", 0),
        "should_abstain": verify_summary.get("should_abstain", False),
        "verification_failure_type": verify_summary.get("failure_type"),
        "verification_primary_root_cause": verify_summary.get("primary_root_cause"),
        "inspect_warnings": len(inspection.get("warnings") or []),
        "audit_primary_label": audit_summary.get("primary_audit_label"),
        "has_audit_failures": audit_summary.get("has_audit_failures", False),
        "failure_stages": audit_summary.get("failure_stages", {}),
        "top_recommended_actions": audit_summary.get("top_recommended_actions", []),
        "risk_signals": signals,
    }


def _risk_signals(
    inspection: dict[str, Any],
    verify_summary: dict[str, Any],
    audit_summary: dict[str, Any],
) -> list[dict[str, Any]]:
    signals: list[dict[str, Any]] = []
    inspect_warnings = len(inspection.get("warnings") or [])
    if inspect_warnings:
        signals.append(
            _signal("inspect_warning", "Trace inspection warning", min(15, inspect_warnings * 5))
        )
    if bool(verify_summary.get("should_abstain")):
        signals.append(_signal("should_abstain", "Answer should have abstained", 30))
    contradicted = int(verify_summary.get("contradicted") or 0)
    if contradicted:
        signals.append(_signal("contradicted", "Contradicted claim", contradicted * 35))
    unsupported = int(verify_summary.get("unsupported") or 0)
    if unsupported:
        signals.append(_signal("unsupported", "Unsupported claim", unsupported * 20))
    partial = int(verify_summary.get("partially_supported") or 0)
    if partial:
        signals.append(_signal("partially_supported", "Partially supported claim", partial * 12))
    unverifiable = int(verify_summary.get("unverifiable") or 0)
    if unverifiable:
        signals.append(_signal("unverifiable", "Unverifiable claim", unverifiable * 10))
    citation_mismatches = int(verify_summary.get("citation_mismatches") or 0)
    if citation_mismatches:
        signals.append(_signal("citation_mismatch", "Citation mismatch", citation_mismatches * 8))

    for label, points, title in [
        ("stale_source", 35, "Stale or conflicting source"),
        ("corpus_gap", 30, "Corpus coverage gap"),
        ("retrieval_miss", 20, "Retrieval miss"),
        ("answer_overreach", 18, "Answer overreach"),
        ("chunking_issue", 15, "Chunking issue"),
        ("reranking_failure", 15, "Reranking failure"),
        ("insufficient_context", 12, "Insufficient context"),
    ]:
        count = int(audit_summary.get(label) or 0)
        if count:
            signals.append(_signal(label, title, count * points))
    return signals


def _signal(label: str, title: str, points: int) -> dict[str, Any]:
    return {
        "label": label,
        "title": title,
        "points": int(points),
        "risk_band": _signal_band(label),
    }


def _signal_band(label: str) -> str:
    if label in HIGH_RISK_LABELS:
        return "high"
    if label in MEDIUM_RISK_LABELS:
        return "medium"
    if label in LOW_RISK_LABELS:
        return "low"
    return "low"


def _risk_level(score: int) -> str:
    if score >= 50:
        return "high"
    if score >= 20:
        return "medium"
    if score > 0:
        return "low"
    return "pass"


def _primary_issue(
    signals: list[dict[str, Any]],
    verify_summary: dict[str, Any],
    audit_summary: dict[str, Any],
) -> str:
    priority = [
        "contradicted",
        "should_abstain",
        "stale_source",
        "corpus_gap",
        "unsupported",
        "retrieval_miss",
        "answer_overreach",
        "chunking_issue",
        "reranking_failure",
        "insufficient_context",
        "citation_mismatch",
        "unverifiable",
        "inspect_warning",
    ]
    labels = {str(signal.get("label")) for signal in signals}
    for label in priority:
        if label in labels:
            return label
    return (
        str(audit_summary.get("primary_audit_label") or "")
        or str(verify_summary.get("failure_type") or "")
        or "no_failure_detected"
    )


def _next_actions(
    inspection: dict[str, Any],
    verification: dict[str, Any],
    audit: dict[str, Any] | None,
) -> list[str]:
    actions = []
    audit_summary = (audit or {}).get("summary") or {}
    for item in audit_summary.get("top_recommended_actions") or []:
        action = str(item.get("action") or "").strip()
        if action and action not in actions:
            actions.append(action)
    verify_fix = str((verification.get("summary") or {}).get("suggested_fix") or "").strip()
    if verify_fix and "no fix is needed" not in verify_fix.lower() and verify_fix not in actions:
        actions.append(verify_fix)
    for warning in inspection.get("warnings") or []:
        action = _action_from_warning(str(warning))
        if action and action not in actions:
            actions.append(action)
    return actions[:5]


def _action_from_warning(warning: str) -> str:
    lowered = warning.lower()
    if "duplicate context ids" in lowered:
        return "Deduplicate context IDs before verification so citations map to a single source."
    if "missing context ids" in lowered:
        return "Preserve source IDs through retrieval and generation so citations reference retrieved contexts."
    if "no retrieved contexts" in lowered:
        return "Return an insufficient-context answer unless retrieval returns evidence."
    if "no citations" in lowered:
        return "Add claim-level citations or run verification without citation assumptions."
    return "Inspect the trace warning before relying on verification output."
