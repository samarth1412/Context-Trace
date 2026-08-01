"""Audit and run hash-locked external development comparisons.

This runner never downloads a model, calls a provider, or reads sealed labels.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
import time
from collections.abc import Callable
from importlib.metadata import version
from pathlib import Path
from typing import Any

from contexttrace.verify.schema import load_trace
from contexttrace.verify.semantic_core_v2 import build_pinned_nli, verify_nli_artifact
from contexttrace.verify.semantic_core_v2_1 import (
    SELECTIVE_V2_1_PROFILE,
    verify_trace_v2_1,
)

from benchmarks.contexttrace_bench.adapt_candidate import adapt_candidate_rows
from benchmarks.contexttrace_bench.run_contexttrace import score_candidate_predictions

HERE = Path(__file__).resolve().parent
DEFAULT_LOCK = HERE / "baseline-lock.json"


class BaselineAuditError(ValueError):
    """Raised when a locked comparison artifact is incomplete or changed."""


def audit_matrix(lock_path: Path, artifact_root: Path) -> dict[str, Any]:
    lock = _read_object(lock_path)
    comparisons = [
        _audit_comparison(item, artifact_root)
        for item in _object_list(lock, "comparisons")
    ]
    return {
        "schema_version": "1.0",
        "status": "ready",
        "evidence_class": lock.get("evidence_class"),
        "lock": {
            "path": str(lock_path),
            "sha256": _file_sha256(lock_path),
        },
        "artifact_root": str(artifact_root),
        "systems": lock.get("systems") or [],
        "comparisons": comparisons,
    }


def run_matrix(
    lock_path: Path,
    artifact_root: Path,
    model_path: Path,
    *,
    progress: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    audit = audit_matrix(lock_path, artifact_root)
    if progress:
        progress("Artifact audit passed for all locked comparisons.")
    model_lock = verify_nli_artifact(model_path)
    nli = build_pinned_nli(model_path)
    comparisons = []
    for audited in audit["comparisons"]:
        item = audited["lock_entry"]
        if progress:
            progress(f"Running {item['id']} ({item['expected_cases']} cases).")
        case_pack = _read_object(artifact_root / item["case_pack"]["path"])
        candidate_inputs = _read_jsonl(artifact_root / item["candidate_inputs"]["path"])
        baseline_candidate = _read_object(
            artifact_root / item["baseline_candidate"]["path"]
        )
        reference = _reference_result(item, case_pack, candidate_inputs)
        contexttrace_candidate, runtime = _run_contexttrace_candidate(
            item,
            candidate_inputs,
            nli=nli,
        )
        contexttrace_score = score_candidate_predictions(
            reference, contexttrace_candidate
        )
        baseline_score = score_candidate_predictions(reference, baseline_candidate)
        comparison = {
            "id": item["id"],
            "dataset": item["dataset"],
            "evaluation_kind": item["evaluation_kind"],
            "cases": item["expected_cases"],
            "artifact_audit": {
                key: value for key, value in audited.items() if key != "lock_entry"
            },
            "contexttrace": _compact_score(contexttrace_score, runtime),
            "contexttrace_predictions": contexttrace_candidate,
            "baseline": _compact_score(baseline_score),
            "limitations": item.get("limitations") or [],
        }
        if item["evaluation_kind"] == "visible_label_accuracy":
            comparison["failure_label_macro_f1_delta"] = _metric_delta(
                contexttrace_score,
                baseline_score,
                "failure_label_macro_f1",
            )
        else:
            comparison["proxy_agreement"] = _binary_agreement(
                contexttrace_candidate,
                baseline_candidate,
            )
        comparisons.append(comparison)
        if progress:
            progress(f"Completed {item['id']} with exact coverage.")
    return {
        "schema_version": "1.0",
        "evidence_class": audit["evidence_class"],
        "claim_status": "development_measurement_not_sota_evidence",
        "lock_sha256": audit["lock"]["sha256"],
        "runtime": {
            "id": "semantic_core_v2_1_selective_pinned_nli",
            "profile_id": SELECTIVE_V2_1_PROFILE.id,
            "profile_sha256": SELECTIVE_V2_1_PROFILE.sha256,
            "model_id": model_lock["model_id"],
            "model_revision": model_lock["model_revision"],
            "artifact_manifest_sha256": model_lock["artifact_manifest_sha256"],
            "versions": {
                "torch": version("torch"),
                "transformers": version("transformers"),
            },
        },
        "system_availability": audit["systems"],
        "comparisons": comparisons,
        "interpretation": [
            "All datasets and labels in this report are visible development evidence.",
            "Cached baseline outputs are accepted only after exact hash, ID, coverage, error, and adapter checks.",
            "RefChecker and MiniCheck have no local same-ID run and therefore receive no score.",
            "CRAG is evaluator agreement on a gold-answer grounding proxy, not labeled accuracy.",
            "No result in this report establishes an untouched or state-of-the-art claim.",
        ],
    }


def _audit_comparison(item: dict[str, Any], artifact_root: Path) -> dict[str, Any]:
    comparison_id = _required_text(item, "id")
    expected_cases = int(item.get("expected_cases") or 0)
    if expected_cases <= 0:
        raise BaselineAuditError(f"{comparison_id}: expected_cases must be positive.")
    paths = {}
    for name in (
        "case_pack",
        "candidate_inputs",
        "baseline_raw",
        "baseline_candidate",
    ):
        artifact = item.get(name)
        if not isinstance(artifact, dict):
            raise BaselineAuditError(f"{comparison_id}: missing {name} lock.")
        path = _resolve_artifact(artifact_root, _required_text(artifact, "path"))
        expected_hash = _required_text(artifact, "sha256")
        if not path.is_file():
            raise BaselineAuditError(f"{comparison_id}: missing artifact {path}.")
        actual_hash = _file_sha256(path)
        if actual_hash != expected_hash:
            raise BaselineAuditError(
                f"{comparison_id}: SHA-256 mismatch for {name}: "
                f"expected {expected_hash}, found {actual_hash}."
            )
        paths[name] = path

    case_pack = _read_object(paths["case_pack"])
    candidate_inputs = _read_jsonl(paths["candidate_inputs"])
    baseline_raw = _read_object(paths["baseline_raw"])
    baseline_candidate = _read_object(paths["baseline_candidate"])
    id_groups = {
        "case_pack": _unique_ids(_object_list(case_pack, "cases"), comparison_id),
        "candidate_inputs": _unique_ids(candidate_inputs, comparison_id),
        "baseline_raw": _unique_ids(
            _object_list(baseline_raw, "rows"),
            comparison_id,
        ),
        "baseline_candidate": _unique_ids(
            _object_list(baseline_candidate, "predictions"),
            comparison_id,
        ),
    }
    expected_ids = id_groups["candidate_inputs"]
    for name, ids in id_groups.items():
        if len(ids) != expected_cases:
            raise BaselineAuditError(
                f"{comparison_id}: {name} has {len(ids)} unique IDs, expected "
                f"{expected_cases}."
            )
        if ids != expected_ids:
            raise BaselineAuditError(
                f"{comparison_id}: {name} IDs do not exactly match candidate inputs."
            )
    errors = [
        row
        for row in _object_list(baseline_raw, "rows")
        if str(row.get("error") or "").strip()
    ]
    if errors:
        raise BaselineAuditError(
            f"{comparison_id}: baseline raw output contains {len(errors)} errors."
        )
    regenerated = adapt_candidate_rows(
        _object_list(baseline_raw, "rows"),
        system=str(baseline_candidate.get("system") or ""),
        version=str(baseline_candidate.get("version") or ""),
        preset=_required_text(item, "adapter_preset"),
    )
    if regenerated != baseline_candidate:
        raise BaselineAuditError(
            f"{comparison_id}: baseline candidate does not exactly regenerate "
            "from the locked raw output."
        )
    _validate_candidate_traces(candidate_inputs, comparison_id)
    input_binding = _validate_raw_input_binding(
        candidate_inputs,
        _object_list(baseline_raw, "rows"),
        system=_required_text(item, "baseline_system"),
        comparison_id=comparison_id,
    )
    return {
        "id": comparison_id,
        "status": "ready",
        "cases": expected_cases,
        "exact_id_coverage": True,
        "zero_baseline_errors": True,
        "candidate_regenerates_from_raw": True,
        "raw_input_binding": input_binding,
        "artifact_sha256": {name: _file_sha256(path) for name, path in paths.items()},
        "lock_entry": item,
    }


def _reference_result(
    item: dict[str, Any],
    case_pack: dict[str, Any],
    candidate_inputs: list[dict[str, Any]],
) -> dict[str, Any]:
    by_id = {_row_id(case): case for case in _object_list(case_pack, "cases")}
    rows = []
    for candidate_input in candidate_inputs:
        case_id = _row_id(candidate_input)
        case = by_id[case_id]
        rows.append(
            {
                "id": case_id,
                "expected": list(
                    case.get("expected_labels") or ["no_failure_detected"]
                ),
                "expected_primary_root_cause": case.get("expected_primary_root_cause"),
                "expected_citation_statuses": list(
                    case.get("expected_citation_statuses") or []
                ),
                "expected_evidence_spans": list(
                    case.get("expected_evidence_spans") or []
                ),
                "expected_verdict_counts": dict(
                    case.get("expected_verdict_counts") or {}
                ),
                "expected_verdict_scope": case.get("expected_verdict_scope")
                or "answer_label",
            }
        )
    return {
        "benchmark": item["dataset"],
        "rows": rows,
    }


def _run_contexttrace_candidate(
    item: dict[str, Any],
    candidate_inputs: list[dict[str, Any]],
    *,
    nli: Any,
) -> tuple[dict[str, Any], dict[str, Any]]:
    predictions = []
    latencies = []
    runtime_failures = []
    total_claims = 0
    nli_invocations = 0
    unresolved_claims = 0
    truncated_cases = 0
    for row in candidate_inputs:
        case_id = _row_id(row)
        started = time.perf_counter()
        try:
            result = verify_trace_v2_1(load_trace(row.get("trace")), nli=nli)
        except (OSError, RuntimeError, ValueError) as exc:  # pragma: no cover
            runtime_failures.append({"id": case_id, "error": str(exc)})
            continue
        latency_ms = round((time.perf_counter() - started) * 1000, 3)
        latencies.append(latency_ms)
        claims = [
            claim for claim in result.get("claims") or [] if isinstance(claim, dict)
        ]
        total_claims += len(claims)
        summary = result.get("summary") or {}
        nli_invocations += int(summary.get("nli_invocations") or 0)
        unresolved_claims += sum(claim.get("route") == "unresolved" for claim in claims)
        truncated_cases += bool((result.get("truncation") or {}).get("applied"))
        raw_labels = {
            str(claim.get("failure_label"))
            for claim in claims
            if claim.get("failure_label") not in {None, "", "none"}
        }
        raw_labels = raw_labels or {"no_failure_detected"}
        labels = _project_labels(
            raw_labels,
            dataset=str(item["dataset"]),
        )
        prediction = {
            "id": case_id,
            "predicted": sorted(labels),
            "predicted_primary_root_cause": _project_root(labels),
            "latency_ms": latency_ms,
            "native_failure_labels": sorted(raw_labels),
            "native_root_causes": sorted(
                {
                    str(claim.get("primary_root_cause"))
                    for claim in claims
                    if claim.get("primary_root_cause") not in {None, "", "none"}
                }
            ),
            "prediction_payload_sha256": result.get("prediction_payload_sha256"),
        }
        predictions.append(prediction)
    if runtime_failures:
        raise BaselineAuditError(
            f"{item['id']}: ContextTrace failed on {len(runtime_failures)} cases: "
            f"{runtime_failures[:3]}"
        )
    if len(predictions) != int(item["expected_cases"]):
        raise BaselineAuditError(
            f"{item['id']}: ContextTrace emitted {len(predictions)} predictions, "
            f"expected {item['expected_cases']}."
        )
    runtime = {
        "cases": len(predictions),
        "claims": total_claims,
        "nli_invocations": nli_invocations,
        "nli_invocation_rate": _ratio(nli_invocations, total_claims),
        "unresolved_claims": unresolved_claims,
        "unresolved_rate": _ratio(unresolved_claims, total_claims),
        "truncated_cases": truncated_cases,
        "latency_ms": {
            "p50": _percentile(latencies, 0.50),
            "p95": _percentile(latencies, 0.95),
            "mean": round(statistics.fmean(latencies), 3) if latencies else 0.0,
        },
        "runtime_failures": 0,
    }
    return {
        "system": "ContextTrace",
        "version": "semantic_core_v2_1_selective_pinned_nli",
        "predictions": predictions,
    }, runtime


def _compact_score(
    score: dict[str, Any],
    runtime: dict[str, Any] | None = None,
) -> dict[str, Any]:
    summary = score.get("summary") or {}
    compact = {
        "system": score.get("system"),
        "version": score.get("version"),
        "coverage": score.get("coverage"),
        "metrics": {
            key: summary.get(key)
            for key in (
                "failure_label_exact_match_rate",
                "failure_label_macro_f1",
                "root_cause_accuracy",
                "dangerous_false_green_rate",
                "latency_p50_ms",
                "latency_p95_ms",
            )
        },
        "failure_label_macro_f1_95ci": (score.get("confidence_intervals") or {}).get(
            "failure_label_macro_f1"
        ),
    }
    if runtime is not None:
        compact["runtime"] = runtime
    return compact


def _binary_agreement(
    left: dict[str, Any],
    right: dict[str, Any],
) -> dict[str, Any]:
    left_index = _prediction_index(left)
    right_index = _prediction_index(right)
    if left_index.keys() != right_index.keys():
        raise BaselineAuditError("Cannot calculate agreement for mismatched IDs.")
    agree = 0
    left_flags = 0
    right_flags = 0
    for case_id in left_index:
        left_flag = _is_flagged(left_index[case_id])
        right_flag = _is_flagged(right_index[case_id])
        agree += left_flag == right_flag
        left_flags += left_flag
        right_flags += right_flag
    total = len(left_index)
    return {
        "cases": total,
        "agreement_rate": _ratio(agree, total),
        "contexttrace_flagged": left_flags,
        "baseline_flagged": right_flags,
    }


def _prediction_index(candidate: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {_row_id(row): row for row in _object_list(candidate, "predictions")}


def _is_flagged(prediction: dict[str, Any]) -> bool:
    labels = prediction.get("predicted") or prediction.get("predicted_labels") or []
    if isinstance(labels, str):
        labels = [labels]
    normalized = {str(label) for label in labels}
    return bool(normalized - {"no_failure_detected"})


def _metric_delta(left: dict[str, Any], right: dict[str, Any], key: str) -> float:
    left_value = float((left.get("summary") or {}).get(key) or 0.0)
    right_value = float((right.get("summary") or {}).get(key) or 0.0)
    return round(left_value - right_value, 6)


def _project_labels(raw_labels: set[str], *, dataset: str) -> set[str]:
    labels = set(raw_labels)
    if not labels or labels == {"no_failure_detected"}:
        return {"no_failure_detected"}
    dataset_key = dataset.lower()
    if dataset_key.startswith("ares"):
        return {"should_have_abstained", "unsupported_answer"}
    if dataset_key == "ragtruth":
        if "citation_mismatch" in labels:
            return {"citation_mismatch"}
        if "contradicted_answer" in labels:
            return {"contradicted_answer"}
        if labels.intersection(
            {"unsupported_answer", "insufficient_context", "should_have_abstained"}
        ):
            return {"partial_support"}
        if "partial_support" in labels:
            return {"partial_support"}
    return labels


def _project_root(labels: set[str]) -> str:
    if "no_failure_detected" in labels:
        return "no_failure_detected"
    if "citation_mismatch" in labels:
        return "wrong_source_cited"
    if "contradicted_answer" in labels:
        return "conflicting_contexts"
    if "should_have_abstained" in labels:
        return "should_have_abstained"
    if "partial_support" in labels or "unsupported_answer" in labels:
        return "answer_overreach"
    return "not_reported"


def _validate_candidate_traces(
    candidate_inputs: list[dict[str, Any]], comparison_id: str
) -> None:
    for row in candidate_inputs:
        try:
            load_trace(row.get("trace"), source=f"{comparison_id}:{_row_id(row)}")
        except Exception as exc:
            raise BaselineAuditError(
                f"{comparison_id}: invalid candidate trace for {_row_id(row)}: {exc}"
            ) from exc


def _validate_raw_input_binding(
    candidate_inputs: list[dict[str, Any]],
    raw_rows: list[dict[str, Any]],
    *,
    system: str,
    comparison_id: str,
) -> str:
    raw_by_id = {_row_id(row): row for row in raw_rows}
    if system == "RAGAS":
        for candidate in candidate_inputs:
            trace = candidate["trace"]
            expected_count = len(trace.get("contexts") or [])
            actual_count = int(
                raw_by_id[_row_id(candidate)].get("retrieved_context_count") or 0
            )
            if actual_count != expected_count:
                raise BaselineAuditError(
                    f"{comparison_id}: RAGAS context count changed for "
                    f"{_row_id(candidate)}."
                )
        return "exact_ids_and_retrieved_context_counts"
    if system == "RAGChecker":
        for candidate in candidate_inputs:
            case_id = _row_id(candidate)
            trace = candidate["trace"]
            raw = raw_by_id[case_id]
            expected_contexts = [
                {"doc_id": context["id"], "text": context["text"]}
                for context in trace.get("contexts") or []
            ]
            if (
                raw.get("query") != trace.get("query")
                or raw.get("response") != trace.get("answer")
                or raw.get("retrieved_context") != expected_contexts
            ):
                raise BaselineAuditError(
                    f"{comparison_id}: RAGChecker raw input changed for {case_id}."
                )
        return "exact_query_response_and_retrieved_contexts"
    raise BaselineAuditError(
        f"{comparison_id}: unsupported baseline system for input binding: {system}."
    )


def _unique_ids(rows: list[dict[str, Any]], comparison_id: str) -> set[str]:
    ids = [_row_id(row) for row in rows]
    duplicates = sorted({case_id for case_id in ids if ids.count(case_id) > 1})
    if duplicates:
        raise BaselineAuditError(
            f"{comparison_id}: duplicate IDs found: {duplicates[:5]}."
        )
    return set(ids)


def _row_id(row: dict[str, Any]) -> str:
    value = row.get("id") or row.get("query_id") or row.get("case_id")
    if value is None or not str(value).strip():
        raise BaselineAuditError("Artifact row is missing a non-empty ID.")
    return str(value)


def _read_object(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise BaselineAuditError(f"{path} must contain a JSON object.")
    return payload


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8-sig").splitlines()
        if line.strip()
    ]
    if not all(isinstance(row, dict) for row in rows):
        raise BaselineAuditError(f"{path} must contain only JSON objects.")
    return rows


def _object_list(payload: dict[str, Any], field: str) -> list[dict[str, Any]]:
    value = payload.get(field)
    if not isinstance(value, list) or not all(isinstance(row, dict) for row in value):
        raise BaselineAuditError(f"{field} must be a list of objects.")
    return value


def _required_text(payload: dict[str, Any], field: str) -> str:
    value = payload.get(field)
    if value is None or not str(value).strip():
        raise BaselineAuditError(f"Missing non-empty {field}.")
    return str(value)


def _resolve_artifact(root: Path, relative_path: str) -> Path:
    if Path(relative_path).is_absolute():
        raise BaselineAuditError("Artifact paths in the lock must be relative.")
    resolved_root = root.resolve()
    resolved = (resolved_root / relative_path).resolve()
    if not resolved.is_relative_to(resolved_root):
        raise BaselineAuditError(
            f"Artifact path escapes the configured artifact root: {relative_path}."
        )
    return resolved


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _ratio(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 6) if denominator else 0.0


def _percentile(values: list[float], quantile: float) -> float:
    if not values:
        return 0.0
    index = max(0, math.ceil(quantile * len(values)) - 1)
    return round(sorted(values)[index], 3)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lock", type=Path, default=DEFAULT_LOCK)
    parser.add_argument("--artifact-root", type=Path, required=True)
    parser.add_argument("--model-path", type=Path)
    parser.add_argument("--audit-only", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if not args.audit_only and args.model_path is None:
        parser.error("--model-path is required unless --audit-only is used")
    result = (
        audit_matrix(args.lock, args.artifact_root)
        if args.audit_only
        else run_matrix(
            args.lock,
            args.artifact_root,
            args.model_path,
            progress=lambda message: print(message, flush=True),
        )
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
