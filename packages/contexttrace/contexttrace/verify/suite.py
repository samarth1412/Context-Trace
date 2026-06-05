from __future__ import annotations

import glob
import json
import re
import time
from pathlib import Path
from typing import Any

from contexttrace.capture_endpoint import capture_endpoint_trace
from contexttrace.endpoint_eval import EndpointCaller
from contexttrace.verify.compare import compare_verifications
from contexttrace.verify.qa import qa_trace
from contexttrace.verify.schema import RAGTrace, VerificationInputError, load_trace, load_trace_file


SUITE_SCHEMA_VERSION = "0.1"
RISK_ORDER = {"pass": 0, "low": 1, "medium": 2, "high": 3}


def create_suite_from_trace_files(
    trace_paths: list[str] | tuple[str, ...],
    *,
    name: str | None = None,
    mode: str = "lexical",
    corpus_path: str | Path | None = None,
) -> dict[str, Any]:
    """Create a portable regression suite from existing RAG trace JSON files."""

    resolved_paths = _resolve_trace_paths(trace_paths)
    if not resolved_paths:
        raise VerificationInputError("No trace files matched the provided suite inputs.")

    cases = []
    used_ids: set[str] = set()
    for path in resolved_paths:
        trace = load_trace_file(path)
        case_id = _unique_case_id(_case_id_from_trace(path, trace), used_ids)
        baseline_qa = qa_trace(trace, trace_path=str(path), corpus_path=corpus_path, mode=mode)
        cases.append(
            {
                "id": case_id,
                "query": trace.query,
                "source_trace": str(path),
                "baseline_trace": trace.to_dict(),
                "baseline_qa": _qa_snapshot(baseline_qa),
                "expected": {
                    "policy": "must_pass",
                    "max_risk_level": "low",
                    "max_unsupported_claim_rate": 0.0,
                    "max_bad_citation_mismatches": 0,
                    "allow_should_abstain": False,
                    "allow_regression": False,
                },
                "metadata": {
                    "baseline_primary_issue": baseline_qa["summary"].get("primary_issue"),
                    "baseline_risk_level": baseline_qa["summary"].get("risk_level"),
                    "baseline_support_rate": baseline_qa["summary"].get("support_rate"),
                },
            }
        )

    return {
        "schema_version": SUITE_SCHEMA_VERSION,
        "name": name or "contexttrace-regression-suite",
        "description": "Replay saved RAG traces against a live endpoint and fail when evidence quality regresses or a saved failure still reproduces.",
        "mode": mode,
        "cases": cases,
        "metadata": {
            "created_by": "contexttrace suite create",
            "case_count": len(cases),
            "corpus_path": str(corpus_path) if corpus_path else None,
        },
    }


def run_suite(
    suite: dict[str, Any],
    *,
    endpoint: str,
    method: str = "POST",
    headers: dict[str, str] | None = None,
    body_template: dict[str, Any] | None = None,
    input_key: str = "question",
    answer_path: str = "$.answer",
    contexts_path: str = "$.contexts",
    citations_path: str = "$.citations",
    metadata_path: str = "$.metadata",
    timeout: float = 30.0,
    corpus_path: str | Path | None = None,
    mode: str | None = None,
    caller: EndpointCaller | None = None,
) -> dict[str, Any]:
    """Replay every suite case against a RAG endpoint and evaluate the current output."""

    _validate_suite(suite)
    resolved_mode = mode or str(suite.get("mode") or "lexical")
    cases = []
    for index, case in enumerate(suite.get("cases") or []):
        cases.append(
            _run_case(
                case,
                case_index=index,
                endpoint=endpoint,
                method=method,
                headers=headers or {},
                body_template=body_template,
                input_key=input_key,
                answer_path=answer_path,
                contexts_path=contexts_path,
                citations_path=citations_path,
                metadata_path=metadata_path,
                timeout=timeout,
                corpus_path=corpus_path,
                mode=resolved_mode,
                caller=caller,
            )
        )

    summary = _suite_summary(cases)
    return {
        "schema_version": SUITE_SCHEMA_VERSION,
        "suite_name": suite.get("name") or "contexttrace-regression-suite",
        "mode": resolved_mode,
        "endpoint": endpoint,
        "summary": summary,
        "cases": cases,
        "metadata": {
            "suite_schema_version": suite.get("schema_version"),
            "corpus_path": str(corpus_path) if corpus_path else None,
        },
    }


def add_trace_files_to_suite(
    suite: dict[str, Any],
    trace_paths: list[str] | tuple[str, ...],
    *,
    mode: str | None = None,
    corpus_path: str | Path | None = None,
    replace: bool = False,
) -> dict[str, Any]:
    """Add saved trace files as new suite cases."""

    _validate_suite(suite)
    resolved_mode = mode or str(suite.get("mode") or "lexical")
    created = create_suite_from_trace_files(
        trace_paths,
        name=str(suite.get("name") or "contexttrace-regression-suite"),
        mode=resolved_mode,
        corpus_path=corpus_path,
    )
    existing_cases = [dict(case) for case in suite.get("cases") or []]
    new_cases = [dict(case) for case in created.get("cases") or []]
    replaced = 0

    if replace:
        new_ids = {str(case.get("id")) for case in new_cases}
        kept_cases = []
        for case in existing_cases:
            if str(case.get("id")) in new_ids:
                replaced += 1
            else:
                kept_cases.append(case)
        existing_cases = kept_cases

    used_ids = {str(case.get("id")) for case in existing_cases}
    added_ids = []
    resolved_new_cases = []
    for case in new_cases:
        original_id = str(case.get("id") or "case")
        case_id = original_id if replace else _unique_case_id(original_id, used_ids)
        case["id"] = case_id
        if case_id != original_id:
            metadata = dict(case.get("metadata") or {})
            metadata["original_case_id"] = original_id
            case["metadata"] = metadata
        added_ids.append(case_id)
        resolved_new_cases.append(case)

    updated = _suite_copy(suite)
    updated["mode"] = resolved_mode
    updated["cases"] = existing_cases + resolved_new_cases
    _refresh_suite_metadata(updated, updated_by="contexttrace suite add", corpus_path=corpus_path)
    return {
        "suite": updated,
        "added_case_ids": added_ids,
        "replaced": replaced,
    }


def list_suite_cases(suite: dict[str, Any]) -> list[dict[str, Any]]:
    _validate_suite(suite)
    rows = []
    for index, case in enumerate(suite.get("cases") or [], start=1):
        baseline = case.get("baseline_qa") or {}
        summary = baseline.get("summary") or {}
        rows.append(
            {
                "position": index,
                "id": case.get("id"),
                "query": case.get("query"),
                "source_trace": case.get("source_trace"),
                "baseline_risk_level": summary.get("risk_level") or (case.get("metadata") or {}).get("baseline_risk_level"),
                "baseline_primary_issue": summary.get("primary_issue") or (case.get("metadata") or {}).get("baseline_primary_issue"),
                "baseline_support_rate": summary.get("support_rate") or (case.get("metadata") or {}).get("baseline_support_rate"),
            }
        )
    return rows


def remove_suite_cases(suite: dict[str, Any], case_ids: list[str] | tuple[str, ...]) -> dict[str, Any]:
    _validate_suite(suite)
    requested = [str(case_id) for case_id in case_ids if str(case_id).strip()]
    if not requested:
        raise VerificationInputError("At least one case ID is required.")
    requested_set = set(requested)
    existing_cases = [dict(case) for case in suite.get("cases") or []]
    kept_cases = [case for case in existing_cases if str(case.get("id")) not in requested_set]
    removed_ids = [str(case.get("id")) for case in existing_cases if str(case.get("id")) in requested_set]
    missing_ids = [case_id for case_id in requested if case_id not in set(removed_ids)]
    if not kept_cases:
        raise VerificationInputError("Refusing to remove every case from the suite.")
    updated = _suite_copy(suite)
    updated["cases"] = kept_cases
    _refresh_suite_metadata(updated, updated_by="contexttrace suite remove")
    return {
        "suite": updated,
        "removed_case_ids": removed_ids,
        "missing_case_ids": missing_ids,
    }


def prune_suite_cases(
    suite: dict[str, Any],
    result: dict[str, Any],
    *,
    statuses: list[str] | tuple[str, ...] = ("passed",),
) -> dict[str, Any]:
    _validate_suite(suite)
    status_set = {str(status).strip().lower() for status in statuses if str(status).strip()}
    if not status_set:
        raise VerificationInputError("At least one status is required for pruning.")
    result_cases = {
        str(case.get("id")): str(case.get("status") or "").lower()
        for case in result.get("cases") or []
        if isinstance(case, dict)
    }
    prune_ids = {
        case_id
        for case_id, status in result_cases.items()
        if status in status_set
    }
    existing_cases = [dict(case) for case in suite.get("cases") or []]
    kept_cases = [case for case in existing_cases if str(case.get("id")) not in prune_ids]
    removed_ids = [str(case.get("id")) for case in existing_cases if str(case.get("id")) in prune_ids]
    if removed_ids and not kept_cases:
        raise VerificationInputError("Refusing to prune every case from the suite.")
    updated = _suite_copy(suite)
    updated["cases"] = kept_cases
    _refresh_suite_metadata(updated, updated_by="contexttrace suite prune")
    return {
        "suite": updated,
        "removed_case_ids": removed_ids,
        "statuses": sorted(status_set),
    }


def suite_failures(result: dict[str, Any], fail_on: tuple[str, ...]) -> list[str]:
    if not fail_on:
        return []
    summary = result.get("summary") or {}
    messages = []
    for raw_rule in fail_on:
        rule = raw_rule.strip().lower().replace("-", "_")
        if rule in {"failed_case", "case_failure"} and int(summary.get("failed") or 0) > 0:
            messages.append("suite case failed")
        elif rule == "error" and int(summary.get("errors") or 0) > 0:
            messages.append("suite case errored")
        elif rule == "regression" and int(summary.get("regressions") or 0) > 0:
            messages.append("claim-level regression detected")
        elif rule == "unsupported" and int(summary.get("unsupported_cases") or 0) > 0:
            messages.append("unsupported claim detected in suite")
        elif rule == "should_abstain" and int(summary.get("should_abstain_cases") or 0) > 0:
            messages.append("should-abstain case detected in suite")
        elif rule == "high_risk" and int(summary.get("high_risk_cases") or 0) > 0:
            messages.append("high-risk suite case detected")
        elif rule == "medium_risk" and (
            int(summary.get("high_risk_cases") or 0) + int(summary.get("medium_risk_cases") or 0)
        ) > 0:
            messages.append("medium-or-higher-risk suite case detected")
        elif rule in {"any_failure", "failure"} and (
            int(summary.get("failed") or 0) + int(summary.get("errors") or 0)
        ) > 0:
            messages.append("suite failure detected")
        elif rule not in {
            "failed_case",
            "case_failure",
            "error",
            "regression",
            "unsupported",
            "should_abstain",
            "high_risk",
            "medium_risk",
            "any_failure",
            "failure",
        }:
            messages.append("unknown --fail-on rule %s" % raw_rule)
    return messages


def load_suite_file(path: str | Path) -> dict[str, Any]:
    payload = _load_json_object(path, label="suite")
    _validate_suite(payload)
    return payload


def load_suite_result_file(path: str | Path) -> dict[str, Any]:
    payload = _load_json_object(path, label="suite result")
    if not isinstance(payload.get("summary"), dict) or not isinstance(payload.get("cases"), list):
        raise VerificationInputError("%s must be a ContextTrace suite result JSON object." % path)
    return payload


def write_suite_file(suite: dict[str, Any], path: str | Path) -> str:
    return _write_json(suite, path)


def write_suite_result(result: dict[str, Any], path: str | Path) -> str:
    return _write_json(result, path)


def _run_case(
    case: dict[str, Any],
    *,
    case_index: int,
    endpoint: str,
    method: str,
    headers: dict[str, str],
    body_template: dict[str, Any] | None,
    input_key: str,
    answer_path: str,
    contexts_path: str,
    citations_path: str,
    metadata_path: str,
    timeout: float,
    corpus_path: str | Path | None,
    mode: str,
    caller: EndpointCaller | None,
) -> dict[str, Any]:
    started = time.perf_counter()
    case_id = str(case.get("id") or "case_%s" % (case_index + 1))
    query = str(case.get("query") or "")
    try:
        baseline_trace = _case_baseline_trace(case, case_id=case_id)
        baseline_qa = _case_baseline_qa(case, baseline_trace, mode=mode)
        captured = capture_endpoint_trace(
            endpoint=endpoint,
            query=query or baseline_trace.query,
            method=method,
            headers=headers,
            body_template=body_template,
            input_key=input_key,
            answer_path=answer_path,
            contexts_path=contexts_path,
            citations_path=citations_path,
            metadata_path=metadata_path,
            timeout=timeout,
            caller=caller,
        )
        current_qa = qa_trace(
            captured.trace,
            trace_path=None,
            corpus_path=corpus_path,
            mode=mode,
        )
        comparison = compare_verifications(
            baseline_qa["verification"],
            current_qa["verification"],
            mode=mode,
        )
        failures = _case_failures(case, current_qa, comparison)
        status = "failed" if failures else "passed"
        return {
            "id": case_id,
            "query": query or baseline_trace.query,
            "status": status,
            "duration_ms": round((time.perf_counter() - started) * 1000, 2),
            "failures": failures,
            "baseline": _case_run_snapshot(baseline_qa),
            "current": _case_run_snapshot(current_qa),
            "comparison": comparison,
            "current_trace": captured.trace.to_dict(),
            "request_body": captured.request_body,
            "next_actions": current_qa.get("next_actions") or [],
            "expected": dict(case.get("expected") or {}),
        }
    except Exception as exc:  # Keep long suite runs useful even when one case is malformed.
        return {
            "id": case_id,
            "query": query,
            "status": "error",
            "duration_ms": round((time.perf_counter() - started) * 1000, 2),
            "failures": [str(exc)],
            "baseline": None,
            "current": None,
            "comparison": None,
            "current_trace": None,
            "request_body": None,
            "next_actions": [],
            "expected": dict(case.get("expected") or {}),
        }


def _case_baseline_trace(case: dict[str, Any], *, case_id: str) -> RAGTrace:
    if isinstance(case.get("baseline_trace"), dict):
        return load_trace(case["baseline_trace"], source="suite case %s baseline_trace" % case_id)
    source_trace = case.get("source_trace")
    if source_trace:
        return load_trace_file(str(source_trace))
    raise VerificationInputError("suite case %s must include baseline_trace or source_trace." % case_id)


def _case_baseline_qa(case: dict[str, Any], trace: RAGTrace, *, mode: str) -> dict[str, Any]:
    baseline_qa = case.get("baseline_qa")
    if isinstance(baseline_qa, dict) and isinstance(baseline_qa.get("verification"), dict):
        return baseline_qa
    return _qa_snapshot(qa_trace(trace, mode=mode))


def _case_failures(
    case: dict[str, Any],
    current_qa: dict[str, Any],
    comparison: dict[str, Any],
) -> list[str]:
    expected = dict(case.get("expected") or {})
    expected.setdefault("max_risk_level", "low")
    expected.setdefault("max_unsupported_claim_rate", 0.0)
    expected.setdefault("max_bad_citation_mismatches", 0)
    expected.setdefault("allow_should_abstain", False)
    expected.setdefault("allow_regression", False)

    summary = current_qa.get("summary") or {}
    comparison_summary = comparison.get("summary") or {}
    failures = []

    risk_level = str(summary.get("risk_level") or "pass")
    max_risk = str(expected.get("max_risk_level") or "pass")
    if _risk_rank(risk_level) > _risk_rank(max_risk):
        failures.append("risk level %s exceeds expected %s" % (risk_level, max_risk))

    unsupported_rate = _number(summary.get("unsupported_claim_rate"))
    max_unsupported_rate = _number(expected.get("max_unsupported_claim_rate"))
    if unsupported_rate > max_unsupported_rate:
        failures.append(
            "unsupported claim rate %.3f exceeds expected %.3f"
            % (unsupported_rate, max_unsupported_rate)
        )

    if "max_citation_mismatches" in expected:
        citation_mismatches = int(summary.get("citation_mismatches") or 0)
        max_citation_mismatches = int(expected.get("max_citation_mismatches") or 0)
        if citation_mismatches > max_citation_mismatches:
            failures.append(
                "citation mismatches %s exceed expected %s"
                % (citation_mismatches, max_citation_mismatches)
            )

    bad_citation_mismatches = _bad_citation_mismatches(current_qa)
    max_bad_citation_mismatches = int(expected.get("max_bad_citation_mismatches") or 0)
    if bad_citation_mismatches > max_bad_citation_mismatches:
        failures.append(
            "bad cited-source mismatches %s exceed expected %s"
            % (bad_citation_mismatches, max_bad_citation_mismatches)
        )

    if bool(summary.get("should_abstain")) and not bool(expected.get("allow_should_abstain")):
        failures.append("answer should have abstained")

    if bool(comparison_summary.get("regression")) and not bool(expected.get("allow_regression")):
        failures.append("claim-level regression detected")

    return failures


def _suite_summary(cases: list[dict[str, Any]]) -> dict[str, Any]:
    passed = [case for case in cases if case.get("status") == "passed"]
    failed = [case for case in cases if case.get("status") == "failed"]
    errors = [case for case in cases if case.get("status") == "error"]
    risk_counts = {"pass": 0, "low": 0, "medium": 0, "high": 0}
    support_rates = []
    unsupported_cases = 0
    should_abstain_cases = 0
    regressions = 0
    resolved_failures = 0
    new_failures = 0
    primary_issues: dict[str, int] = {}

    for case in cases:
        current = case.get("current") or {}
        current_summary = current.get("summary") or {}
        risk_level = str(current_summary.get("risk_level") or "pass")
        if risk_level in risk_counts:
            risk_counts[risk_level] += 1
        support_rates.append(_number(current_summary.get("support_rate")))
        if int(current_summary.get("unsupported") or 0) > 0:
            unsupported_cases += 1
        if bool(current_summary.get("should_abstain")):
            should_abstain_cases += 1
        issue = str(current_summary.get("primary_issue") or "unknown")
        primary_issues[issue] = primary_issues.get(issue, 0) + 1

        comparison_summary = ((case.get("comparison") or {}).get("summary") or {})
        if bool(comparison_summary.get("regression")):
            regressions += 1
        resolved_failures += int(comparison_summary.get("resolved_failures") or 0)
        new_failures += int(comparison_summary.get("new_failures") or 0)

    return {
        "status": "failed" if failed or errors else "passed",
        "total_cases": len(cases),
        "passed": len(passed),
        "failed": len(failed),
        "errors": len(errors),
        "regressions": regressions,
        "resolved_failures": resolved_failures,
        "new_failures": new_failures,
        "unsupported_cases": unsupported_cases,
        "should_abstain_cases": should_abstain_cases,
        "average_support_rate": round(sum(support_rates) / len(support_rates), 3) if support_rates else 0.0,
        "pass_risk_cases": risk_counts["pass"],
        "low_risk_cases": risk_counts["low"],
        "medium_risk_cases": risk_counts["medium"],
        "high_risk_cases": risk_counts["high"],
        "primary_issues": dict(sorted(primary_issues.items(), key=lambda item: (-item[1], item[0]))),
    }


def _case_run_snapshot(qa_result: dict[str, Any]) -> dict[str, Any]:
    return {
        "query": qa_result.get("query"),
        "answer": qa_result.get("answer"),
        "summary": qa_result.get("summary") or {},
        "verification": qa_result.get("verification") or {},
        "inspection": qa_result.get("inspection") or {},
        "audit": qa_result.get("audit"),
        "next_actions": qa_result.get("next_actions") or [],
        "metadata": qa_result.get("metadata") or {},
    }


def _bad_citation_mismatches(qa_result: dict[str, Any]) -> int:
    bad_statuses = {
        "cited_source_missing",
        "cited_source_does_not_support_claim",
        "claim_supported_by_different_source",
    }
    claims = ((qa_result.get("verification") or {}).get("claims") or [])
    return len([claim for claim in claims if str(claim.get("citation_status") or "") in bad_statuses])


def _qa_snapshot(qa_result: dict[str, Any]) -> dict[str, Any]:
    return _case_run_snapshot(qa_result)


def _validate_suite(payload: Any) -> None:
    if not isinstance(payload, dict):
        raise VerificationInputError("suite must be a JSON object.")
    cases = payload.get("cases")
    if not isinstance(cases, list) or not cases:
        raise VerificationInputError("suite must include a non-empty cases list.")
    for index, case in enumerate(cases):
        if not isinstance(case, dict):
            raise VerificationInputError("suite cases[%s] must be an object." % index)
        if not str(case.get("query") or "").strip() and not isinstance(case.get("baseline_trace"), dict):
            raise VerificationInputError("suite cases[%s] must include query or baseline_trace." % index)


def _suite_copy(suite: dict[str, Any]) -> dict[str, Any]:
    return json.loads(json.dumps(suite))


def _refresh_suite_metadata(
    suite: dict[str, Any],
    *,
    updated_by: str,
    corpus_path: str | Path | None = None,
) -> None:
    metadata = dict(suite.get("metadata") or {})
    metadata["updated_by"] = updated_by
    metadata["case_count"] = len(suite.get("cases") or [])
    if corpus_path is not None:
        metadata["corpus_path"] = str(corpus_path)
    suite["metadata"] = metadata


def _resolve_trace_paths(trace_paths: list[str] | tuple[str, ...]) -> list[Path]:
    paths: list[Path] = []
    for raw_path in trace_paths:
        matches = [Path(match) for match in glob.glob(str(raw_path))]
        if not matches:
            matches = [Path(raw_path)]
        for path in sorted(matches):
            if path not in paths:
                paths.append(path)
    return paths


def _case_id_from_trace(path: Path, trace: RAGTrace) -> str:
    raw = str(trace.metadata.get("run_id") or trace.metadata.get("id") or path.stem)
    return _slug(raw) or "case"


def _unique_case_id(case_id: str, used_ids: set[str]) -> str:
    if case_id not in used_ids:
        used_ids.add(case_id)
        return case_id
    suffix = 2
    while "%s_%s" % (case_id, suffix) in used_ids:
        suffix += 1
    resolved = "%s_%s" % (case_id, suffix)
    used_ids.add(resolved)
    return resolved


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", value.strip().lower()).strip("_")
    return slug[:80]


def _risk_rank(value: str) -> int:
    return RISK_ORDER.get(str(value or "pass").lower(), 99)


def _number(value: Any) -> float:
    try:
        return round(float(value), 3)
    except (TypeError, ValueError):
        return 0.0


def _load_json_object(path: str | Path, *, label: str) -> dict[str, Any]:
    input_path = Path(path)
    try:
        payload = json.loads(input_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise VerificationInputError("Could not read %s file %s: %s" % (label, input_path, exc)) from exc
    except json.JSONDecodeError as exc:
        raise VerificationInputError(
            "Invalid JSON in %s at line %s column %s: %s"
            % (input_path, exc.lineno, exc.colno, exc.msg)
        ) from exc
    if not isinstance(payload, dict):
        raise VerificationInputError("%s file %s must contain a JSON object." % (label, input_path))
    return payload


def _write_json(payload: dict[str, Any], path: str | Path) -> str:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return str(output_path)
