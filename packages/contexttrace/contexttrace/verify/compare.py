from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from contexttrace.verify.evidence import lexical_score
from contexttrace.verify.runner import verify_trace
from contexttrace.verify.schema import VerificationInputError, load_trace


FAILURE_VERDICTS = {"partially_supported", "unsupported", "contradicted", "unverifiable"}
BAD_CITATIONS = {
    "cited_source_missing",
    "cited_source_does_not_support_claim",
    "claim_supported_by_different_source",
}
NO_ROOT_CAUSE = "no_failure_detected"
MATCH_THRESHOLD = 0.58


def compare_trace_files(
    baseline_path: str | Path,
    current_path: str | Path,
    *,
    mode: str = "lexical",
) -> dict[str, Any]:
    baseline = load_compare_input(baseline_path, mode=mode)
    current = load_compare_input(current_path, mode=mode)
    return compare_verifications(baseline, current, mode=mode)


def load_compare_input(path: str | Path, *, mode: str = "lexical") -> dict[str, Any]:
    input_path = Path(path)
    try:
        payload = json.loads(input_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise VerificationInputError("Could not read compare input %s: %s" % (input_path, exc)) from exc
    except json.JSONDecodeError as exc:
        raise VerificationInputError(
            "Invalid JSON in %s at line %s column %s: %s"
            % (input_path, exc.lineno, exc.colno, exc.msg)
        ) from exc

    if _looks_like_verification_result(payload):
        return _normalize_verified_result(payload, source=str(input_path))

    trace = load_trace(payload, source=str(input_path))
    result = verify_trace(trace, mode=mode)
    result.setdefault("metadata", {})
    result["metadata"] = {
        **dict(result.get("metadata") or {}),
        "compare_input": str(input_path),
        "compare_input_type": "raw_trace",
    }
    return result


def compare_verifications(
    baseline: dict[str, Any],
    current: dict[str, Any],
    *,
    mode: str = "lexical",
) -> dict[str, Any]:
    baseline_claims = list(baseline.get("claims") or [])
    current_claims = list(current.get("claims") or [])
    matches = _match_claims(baseline_claims, current_claims, mode=mode)

    changes = []
    matched_baseline = set()
    matched_current = set()
    for baseline_index, current_index, score in matches:
        matched_baseline.add(baseline_index)
        matched_current.add(current_index)
        change = _matched_change(
            baseline_claims[baseline_index],
            current_claims[current_index],
            match_score=score,
        )
        if change["status"] != "unchanged":
            changes.append(change)

    for index, claim in enumerate(current_claims):
        if index in matched_current:
            continue
        changes.append(_single_change("added_failure" if _is_failure(claim) else "added_claim", after=claim))

    for index, claim in enumerate(baseline_claims):
        if index in matched_baseline:
            continue
        changes.append(_single_change("removed_failure" if _is_failure(claim) else "removed_claim", before=claim))

    changes = sorted(changes, key=_change_sort_key)
    summary = _summary(baseline, current, changes)
    return {
        "mode": mode,
        "summary": summary,
        "changes": changes,
        "baseline": _run_snapshot(baseline),
        "current": _run_snapshot(current),
    }


def compare_failures(result: dict[str, Any], fail_on: tuple[str, ...]) -> list[str]:
    if not fail_on:
        return []
    summary = result.get("summary") or {}
    messages = []
    for raw_rule in fail_on:
        rule = raw_rule.strip().lower().replace("-", "_")
        if rule == "new_failure" and int(summary.get("new_failures") or 0) > 0:
            messages.append("new verification failure detected")
        elif rule == "new_unsupported" and int(summary.get("new_unsupported") or 0) > 0:
            messages.append("new unsupported claim detected")
        elif rule == "new_citation_mismatch" and int(summary.get("new_citation_mismatches") or 0) > 0:
            messages.append("new citation mismatch detected")
        elif rule == "should_abstain_flip" and bool(summary.get("should_abstain_regressed")):
            messages.append("should-abstain changed from false to true")
        elif rule == "support_rate_drop" and float(summary.get("support_rate_delta") or 0.0) < 0:
            messages.append("support rate dropped")
        elif rule in {"new_root_cause", "root_cause_regression"} and summary.get("new_root_causes"):
            messages.append("new root cause detected")
        elif rule == "any_regression" and bool(summary.get("regression")):
            messages.append("verification regression detected")
        elif rule not in {
            "new_failure",
            "new_unsupported",
            "new_citation_mismatch",
            "should_abstain_flip",
            "support_rate_drop",
            "new_root_cause",
            "root_cause_regression",
            "any_regression",
        }:
            messages.append("unknown --fail-on rule %s" % raw_rule)
    return messages


def _looks_like_verification_result(payload: Any) -> bool:
    return (
        isinstance(payload, dict)
        and isinstance(payload.get("summary"), dict)
        and isinstance(payload.get("claims"), list)
    )


def _normalize_verified_result(payload: dict[str, Any], *, source: str) -> dict[str, Any]:
    result = dict(payload)
    result.setdefault("metadata", {})
    result["metadata"] = {
        **dict(result.get("metadata") or {}),
        "compare_input": source,
        "compare_input_type": "verification_result",
    }
    return result


def _match_claims(
    baseline_claims: list[dict[str, Any]],
    current_claims: list[dict[str, Any]],
    *,
    mode: str,
) -> list[tuple[int, int, float]]:
    candidates = []
    for baseline_index, baseline_claim in enumerate(baseline_claims):
        for current_index, current_claim in enumerate(current_claims):
            score = _claim_similarity(
                str(baseline_claim.get("claim") or ""),
                str(current_claim.get("claim") or ""),
                mode=mode,
            )
            if score >= MATCH_THRESHOLD:
                candidates.append((score, baseline_index, current_index))

    matches = []
    used_baseline = set()
    used_current = set()
    for score, baseline_index, current_index in sorted(candidates, reverse=True):
        if baseline_index in used_baseline or current_index in used_current:
            continue
        used_baseline.add(baseline_index)
        used_current.add(current_index)
        matches.append((baseline_index, current_index, score))
    return matches


def _claim_similarity(left: str, right: str, *, mode: str) -> float:
    if _normalize_text(left) == _normalize_text(right):
        return 1.0
    forward, _ = lexical_score(left, right, mode=mode)
    reverse, _ = lexical_score(right, left, mode=mode)
    return max(forward, reverse)


def _matched_change(
    before_claim: dict[str, Any],
    after_claim: dict[str, Any],
    *,
    match_score: float,
) -> dict[str, Any]:
    before_failure = _is_failure(before_claim)
    after_failure = _is_failure(after_claim)
    before_severity = _severity(before_claim)
    after_severity = _severity(after_claim)
    before_citation = _citation_severity(before_claim)
    after_citation = _citation_severity(after_claim)
    before_root = _root_label(before_claim)
    after_root = _root_label(after_claim)

    if not before_failure and after_failure:
        status = "new_failure"
    elif before_failure and not after_failure:
        status = "resolved_failure"
    elif after_severity > before_severity:
        status = "verdict_regressed"
    elif after_severity < before_severity:
        status = "verdict_improved"
    elif after_citation > before_citation:
        status = "citation_regressed"
    elif after_citation < before_citation:
        status = "citation_improved"
    elif before_root != after_root and after_root != NO_ROOT_CAUSE:
        status = "root_cause_regressed"
    elif before_root != after_root:
        status = "root_cause_changed"
    elif _context_id(before_claim) != _context_id(after_claim):
        status = "source_changed"
    elif _normalize_text(str(before_claim.get("claim") or "")) != _normalize_text(str(after_claim.get("claim") or "")):
        status = "claim_changed"
    else:
        status = "unchanged"

    return {
        "status": status,
        "claim": str(after_claim.get("claim") or before_claim.get("claim") or ""),
        "match_score": round(match_score, 3),
        "before": _claim_snapshot(before_claim),
        "after": _claim_snapshot(after_claim),
        "suggested_fix": _suggested_fix(after_claim, status=status),
    }


def _single_change(
    status: str,
    *,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
) -> dict[str, Any]:
    claim = after or before or {}
    return {
        "status": status,
        "claim": str(claim.get("claim") or ""),
        "match_score": None,
        "before": _claim_snapshot(before) if before else None,
        "after": _claim_snapshot(after) if after else None,
        "suggested_fix": _suggested_fix(claim, status=status),
    }


def _summary(
    baseline: dict[str, Any],
    current: dict[str, Any],
    changes: list[dict[str, Any]],
) -> dict[str, Any]:
    baseline_summary = dict(baseline.get("summary") or {})
    current_summary = dict(current.get("summary") or {})
    new_failures = [change for change in changes if change["status"] in {"new_failure", "added_failure", "verdict_regressed", "citation_regressed", "root_cause_regressed"}]
    resolved_failures = [change for change in changes if change["status"] in {"resolved_failure", "removed_failure", "verdict_improved", "citation_improved"}]
    new_unsupported = [
        change
        for change in new_failures
        if ((change.get("after") or {}).get("verdict") in {"unsupported", "contradicted"})
    ]
    new_citations = [
        change
        for change in new_failures
        if _citation_status_from_snapshot(change.get("after")) in BAD_CITATIONS
    ]
    before_abstain = bool((baseline.get("abstention") or {}).get("should_abstain") or baseline_summary.get("should_abstain"))
    after_abstain = bool((current.get("abstention") or {}).get("should_abstain") or current_summary.get("should_abstain"))
    support_delta = _delta(current_summary.get("support_rate"), baseline_summary.get("support_rate"))
    unsupported_delta = _delta(current_summary.get("unsupported_claim_rate"), baseline_summary.get("unsupported_claim_rate"))
    citation_delta = int(current_summary.get("citation_mismatches") or 0) - int(baseline_summary.get("citation_mismatches") or 0)
    new_root_causes = sorted(
        {
            _root_from_snapshot(change.get("after"))
            for change in new_failures
            if _root_from_snapshot(change.get("after")) != NO_ROOT_CAUSE
        }
    )
    resolved_root_causes = sorted(
        {
            _root_from_snapshot(change.get("before"))
            for change in resolved_failures
            if _root_from_snapshot(change.get("before")) != NO_ROOT_CAUSE
        }
    )
    regression = bool(
        new_failures
        or support_delta < 0
        or unsupported_delta > 0
        or citation_delta > 0
        or (not before_abstain and after_abstain)
    )
    return {
        "regression": regression,
        "improved": bool(resolved_failures and not regression),
        "support_rate_before": _number(baseline_summary.get("support_rate")),
        "support_rate_after": _number(current_summary.get("support_rate")),
        "support_rate_delta": support_delta,
        "unsupported_claim_rate_delta": unsupported_delta,
        "citation_mismatch_delta": citation_delta,
        "should_abstain_before": before_abstain,
        "should_abstain_after": after_abstain,
        "should_abstain_changed": before_abstain != after_abstain,
        "should_abstain_regressed": (not before_abstain and after_abstain),
        "new_failures": len(new_failures),
        "resolved_failures": len(resolved_failures),
        "new_unsupported": len(new_unsupported),
        "new_citation_mismatches": len(new_citations),
        "added_claims": len([change for change in changes if change["status"] in {"added_claim", "added_failure"}]),
        "removed_claims": len([change for change in changes if change["status"] in {"removed_claim", "removed_failure"}]),
        "changed_claims": len(changes),
        "new_root_causes": new_root_causes,
        "resolved_root_causes": resolved_root_causes,
    }


def _run_snapshot(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "query": result.get("query"),
        "answer": result.get("answer"),
        "summary": result.get("summary") or {},
        "abstention": result.get("abstention") or {},
        "metadata": result.get("metadata") or {},
    }


def _claim_snapshot(claim: dict[str, Any] | None) -> dict[str, Any] | None:
    if claim is None:
        return None
    root = claim.get("root_cause") or {}
    return {
        "claim_id": claim.get("claim_id"),
        "claim": claim.get("claim"),
        "verdict": claim.get("verdict"),
        "confidence": claim.get("confidence"),
        "best_context_id": claim.get("best_context_id"),
        "citation_status": claim.get("citation_status"),
        "root_cause": root.get("label") if isinstance(root, dict) else None,
        "missing_fact": root.get("missing_fact") if isinstance(root, dict) else None,
        "closest_evidence": root.get("closest_evidence") if isinstance(root, dict) else claim.get("evidence"),
        "suggested_fix": root.get("suggested_fix") if isinstance(root, dict) else None,
    }


def _is_failure(claim: dict[str, Any]) -> bool:
    return (
        str(claim.get("verdict") or "") in FAILURE_VERDICTS
        or str(claim.get("citation_status") or "") in BAD_CITATIONS
        or _root_label(claim) != NO_ROOT_CAUSE
    )


def _severity(claim: dict[str, Any]) -> int:
    verdict = str(claim.get("verdict") or "")
    if verdict in {"unsupported", "contradicted"}:
        return 3
    if verdict in {"partially_supported", "unverifiable"}:
        return 2
    return 0


def _citation_severity(claim: dict[str, Any]) -> int:
    return 1 if str(claim.get("citation_status") or "") in BAD_CITATIONS else 0


def _root_label(claim: dict[str, Any]) -> str:
    root = claim.get("root_cause") or {}
    if isinstance(root, dict):
        return str(root.get("label") or NO_ROOT_CAUSE)
    return NO_ROOT_CAUSE


def _context_id(claim: dict[str, Any]) -> str:
    return str(claim.get("best_context_id") or "")


def _root_from_snapshot(snapshot: dict[str, Any] | None) -> str:
    if not snapshot:
        return NO_ROOT_CAUSE
    return str(snapshot.get("root_cause") or NO_ROOT_CAUSE)


def _citation_status_from_snapshot(snapshot: dict[str, Any] | None) -> str:
    if not snapshot:
        return ""
    return str(snapshot.get("citation_status") or "")


def _suggested_fix(claim: dict[str, Any], *, status: str) -> str:
    root = claim.get("root_cause") or {}
    if isinstance(root, dict) and root.get("suggested_fix"):
        return str(root["suggested_fix"])
    if status in {"added_failure", "new_failure", "verdict_regressed"}:
        return "Inspect the new claim and remove unsupported details or retrieve supporting evidence."
    if status == "citation_regressed":
        return "Regenerate claim-level citations and require cited source IDs to support the claim."
    if status == "source_changed":
        return "Check whether the new retrieved source is intentional and still supports the claim."
    return "No automatic fix suggested."


def _change_sort_key(change: dict[str, Any]) -> tuple[int, str]:
    priority = {
        "added_failure": 0,
        "new_failure": 1,
        "verdict_regressed": 2,
        "citation_regressed": 3,
        "root_cause_regressed": 4,
        "resolved_failure": 5,
        "verdict_improved": 6,
        "citation_improved": 7,
        "removed_failure": 8,
        "added_claim": 8,
        "removed_claim": 9,
        "source_changed": 10,
        "claim_changed": 11,
    }
    return (priority.get(str(change.get("status")), 99), str(change.get("claim") or ""))


def _delta(current: Any, baseline: Any) -> float:
    return round(_number(current) - _number(baseline), 3)


def _number(value: Any) -> float:
    try:
        return round(float(value), 3)
    except (TypeError, ValueError):
        return 0.0


def _normalize_text(text: str) -> str:
    return " ".join(str(text or "").lower().strip().strip(".!?").split())
