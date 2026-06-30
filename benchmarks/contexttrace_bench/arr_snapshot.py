from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REPRODUCTION_DIR = Path(__file__).with_name("out") / "arr_reproduction_full"
DEFAULT_JSON_PATH = Path(__file__).with_name("ARR_PRE_REVIEW_STATUS.json")
DEFAULT_MARKDOWN_PATH = Path(__file__).with_name("ARR_PRE_REVIEW_STATUS.md")
EXPECTED_CASES = {
    "ragtruth_primary": 200,
    "diag150_primary": 150,
}
EXPECTED_ABLATION_CASES = 500
EXPECTED_ABLATION_PROFILES = 11
EXPECTED_AVAILABLE_ABLATION_PROFILES = 9
EXPECTED_BOOTSTRAP_SAMPLES = 400
MIN_VALID_BOOTSTRAP_SAMPLES = 380
EXPECTED_GATES = {
    "independent_diag150_review_complete": False,
    "independent_ragtruth_review_complete": False,
    "matched_external_baseline_available": True,
    "non_quick_run": True,
    "ragtruth_case_pack_available": True,
}


def write_pre_review_snapshot(
    *,
    reproduction_dir: str | Path = DEFAULT_REPRODUCTION_DIR,
    json_path: str | Path = DEFAULT_JSON_PATH,
    markdown_path: str | Path = DEFAULT_MARKDOWN_PATH,
) -> dict[str, Any]:
    source_dir = Path(reproduction_dir)
    manifest_path = source_dir / "reproduction_manifest.json"
    tables_path = source_dir / "arr_tables.json"
    manifest = _load_object(manifest_path)
    tables = _load_object(tables_path)
    ablation_path = _manifest_output_path(manifest, "ablations", "results")
    ablation_run = _load_object(ablation_path)
    _validate_pre_review_run(manifest, tables, ablation_run)
    _validate_input_records(manifest)

    external = [
        {
            "dataset": row.get("dataset"),
            "dataset_id": row.get("dataset_id"),
            "role": row.get("role"),
            "review_status": row.get("review_status"),
            "summary": dict(row.get("summary") or {}),
            "confidence_intervals": dict(row.get("confidence_intervals") or {}),
        }
        for row in tables.get("external_results") or []
    ]
    ablations = [
        {
            "id": row.get("id"),
            "label": row.get("label"),
            "mode": row.get("mode"),
            "availability": row.get("availability") or "available",
            "unavailable_reason": row.get("unavailable_reason"),
            "profile": dict(row.get("profile") or {}),
            "summary": dict(row.get("reported_summary") or {}),
            "confidence_intervals": dict(row.get("confidence_intervals") or {}),
        }
        for row in tables.get("ablation_results") or []
    ]
    baselines = [
        {
            "system": row.get("system"),
            "version": row.get("version"),
            "summary": dict(row.get("summary") or {}),
            "confidence_intervals": dict(row.get("confidence_intervals") or {}),
            "coverage": dict(row.get("coverage") or {}),
            "cost_reported": row.get("cost_reported"),
        }
        for row in tables.get("baseline_results") or []
    ]
    error = dict(tables.get("error_analysis") or {})
    snapshot = {
        "schema_version": 1,
        "status": "pre_review_paper_candidate",
        "paper_result_eligible": False,
        "broad_sota_claim_allowed": False,
        "claim_boundary": (
            "These are frozen pre-review results. Independent Diag-150 and RAGTruth review must pass "
            "before paper-result claims; broad state-of-the-art language remains blocked."
        ),
        "source_commit": manifest.get("commit"),
        "source_generated_at": manifest.get("generated_at"),
        "bootstrap_samples": manifest.get("bootstrap_samples"),
        "bootstrap_seed": manifest.get("bootstrap_seed"),
        "bootstrap_valid_draw_policy": {
            "requested": EXPECTED_BOOTSTRAP_SAMPLES,
            "minimum_valid": MIN_VALID_BOOTSTRAP_SAMPLES,
            "note": "Class-sensitive metrics may be undefined when a resample omits the evaluated class.",
        },
        "ablation_case_ids_sha256": ablation_run.get("case_ids_sha256"),
        "eligibility_gates": dict(manifest.get("eligibility_gates") or {}),
        "inputs": dict(manifest.get("inputs") or {}),
        "external_results": external,
        "ablation_results": ablations,
        "baseline_results": baselines,
        "error_analysis": {
            "case_set": error.get("case_set"),
            "case_count": error.get("case_count"),
            "benchmark_miss_count": error.get("benchmark_miss_count"),
            "label_miss_count": error.get("label_miss_count"),
            "confusion": list(error.get("confusion") or []),
            "root_cause_confusion": list(error.get("root_cause_confusion") or []),
            "false_positive_labels": list(error.get("false_positive_labels") or []),
            "dangerous_false_green_count": len(error.get("dangerous_false_greens") or []),
        },
        "source_artifacts": _artifact_records(manifest_path, tables_path, manifest),
    }
    output_json = Path(json_path)
    output_markdown = Path(markdown_path)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_markdown.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    output_markdown.write_text(render_pre_review_snapshot(snapshot), encoding="utf-8")
    return {
        **snapshot,
        "outputs": {
            "json": str(output_json),
            "markdown": str(output_markdown),
        },
    }


def render_pre_review_snapshot(snapshot: dict[str, Any]) -> str:
    lines = [
        "# ARR Pre-Review Experiment Snapshot",
        "",
        "Status: `pre_review_paper_candidate`",
        "",
        "Paper result eligible: `False`. Broad SOTA claim allowed: `False`.",
        "",
        str(snapshot.get("claim_boundary") or ""),
        "",
        "Source commit: `%s`; bootstrap samples: `%s`; ablation case-ID SHA-256: `%s`."
        % (
            snapshot.get("source_commit"),
            snapshot.get("bootstrap_samples"),
            snapshot.get("ablation_case_ids_sha256"),
        ),
        "Class-sensitive intervals retain at least 95% of requested draws; always-defined ablation intervals retain all 400.",
        "",
        "## External Results",
        "",
        "| Dataset | Review status | Cases | Failure F1 [95% CI] | Claim F1 | Root cause | Citation F1 | Span overlap | False green [95% CI] |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in snapshot.get("external_results") or []:
        summary = row.get("summary") or {}
        lines.append(
            "| %s | %s | %s | %s | %s | %s | %s | %s | %s |"
            % (
                row.get("dataset"),
                row.get("review_status"),
                summary.get("cases"),
                _metric_ci(row, "failure_label_macro_f1"),
                _metric(summary.get("claim_verdict_macro_f1")),
                _metric(summary.get("root_cause_accuracy")),
                _metric(summary.get("citation_error_f1")),
                _metric(summary.get("evidence_span_overlap")),
                _metric_ci(row, "dangerous_false_green_rate"),
            )
        )
    lines.extend(
        [
            "",
            "## Cumulative Ablations",
            "",
            "| Profile | Availability | Cases | Failure F1 [95% CI] | Claim F1 | Citation F1 | Root cause | Span overlap | False green [95% CI] |",
            "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in snapshot.get("ablation_results") or []:
        summary = row.get("summary") or {}
        lines.append(
            "| %s | %s | %s | %s | %s | %s | %s | %s | %s |"
            % (
                row.get("label"),
                row.get("availability"),
                summary.get("cases"),
                _metric_ci(row, "failure_label_macro_f1"),
                _metric(summary.get("claim_verdict_macro_f1")),
                _metric(summary.get("citation_error_f1")),
                _metric(summary.get("root_cause_accuracy")),
                _metric(summary.get("evidence_span_overlap")),
                _metric_ci(row, "dangerous_false_green_rate"),
            )
        )
    lines.extend(
        [
            "",
            "## Same-ID Baseline",
            "",
            "| System | Cases | Failure F1 [95% CI] | Claim F1 | Root cause | Citation F1 | Span overlap | False green [95% CI] |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    contexttrace = next(
        (
            row
            for row in snapshot.get("external_results") or []
            if row.get("dataset_id") == "ragtruth_primary"
        ),
        {},
    )
    context_summary = contexttrace.get("summary") or {}
    lines.append(
        "| ContextTrace | %s | %s | %s | %s | %s | %s | %s |"
        % (
            context_summary.get("cases"),
            _metric_ci(contexttrace, "failure_label_macro_f1"),
            _metric(context_summary.get("claim_verdict_macro_f1")),
            _metric(context_summary.get("root_cause_accuracy")),
            _metric(context_summary.get("citation_error_f1")),
            _metric(context_summary.get("evidence_span_overlap")),
            _metric_ci(contexttrace, "dangerous_false_green_rate"),
        )
    )
    for row in snapshot.get("baseline_results") or []:
        summary = row.get("summary") or {}
        lines.append(
            "| %s | %s | %s | %s | %s | %s | %s | %s |"
            % (
                row.get("system"),
                summary.get("cases"),
                _metric_ci(row, "failure_label_macro_f1"),
                _metric(summary.get("claim_verdict_macro_f1")),
                _metric(summary.get("root_cause_accuracy")),
                _metric(summary.get("citation_error_f1")),
                _metric(summary.get("evidence_span_overlap")),
                _metric_ci(row, "dangerous_false_green_rate"),
            )
        )
    error = snapshot.get("error_analysis") or {}
    lines.extend(
        [
            "",
            "## Error Analysis",
            "",
            "Cases: `%s`; label misses: `%s`; dangerous false greens: `%s`."
            % (error.get("case_count"), error.get("label_miss_count"), error.get("dangerous_false_green_count")),
            "",
            "## Remaining Gates",
            "",
        ]
    )
    for gate, passed in sorted((snapshot.get("eligibility_gates") or {}).items()):
        lines.append("- `%s`: `%s`" % (gate, "passed" if passed else "pending"))
    lines.extend(
        [
            "",
            "The RAGTruth claim-verdict metric is lower than the matched RAGAS row; the systems expose different diagnostic coverage, so report overlapping outputs and `N/A` fields without a broad dominance claim.",
            "",
        ]
    )
    return "\n".join(lines)


def _validate_pre_review_run(
    manifest: dict[str, Any],
    tables: dict[str, Any],
    ablation_run: dict[str, Any],
) -> None:
    if manifest.get("quick") is not False or manifest.get("result_scope") != "pre_review_paper_candidate":
        raise ValueError("Snapshot source must be a full pre-review paper-candidate run.")
    if manifest.get("paper_run_candidate") is not True or manifest.get("paper_result_eligible") is not False:
        raise ValueError("Snapshot source must be a candidate that remains ineligible pending review.")
    if int(manifest.get("bootstrap_samples") or 0) != EXPECTED_BOOTSTRAP_SAMPLES:
        raise ValueError("Snapshot source must use 400 bootstrap samples.")
    gates = manifest.get("eligibility_gates") or {}
    for gate, expected in EXPECTED_GATES.items():
        if gates.get(gate) is not expected:
            raise ValueError("Unexpected eligibility gate state for %s." % gate)
    external = {str(row.get("dataset_id")): row for row in tables.get("external_results") or []}
    if set(external) != set(EXPECTED_CASES):
        raise ValueError("Snapshot source must contain exactly the frozen external datasets.")
    for dataset_id, expected in EXPECTED_CASES.items():
        row = external[dataset_id]
        actual = int((row.get("summary") or {}).get("cases") or 0)
        if actual != expected:
            raise ValueError("%s must contain %s cases, found %s." % (dataset_id, expected, actual))
        _validate_intervals(
            row,
            label=dataset_id,
            expected_seed=manifest.get("bootstrap_seed"),
            allow_class_filtered=True,
        )
    if (
        ablation_run.get("quick") is not False
        or ablation_run.get("paper_run_candidate") is not True
        or ablation_run.get("paper_result_eligible") is not False
    ):
        raise ValueError("Ablation source must be a full ineligible pre-review candidate.")
    if int(ablation_run.get("case_count") or 0) != EXPECTED_ABLATION_CASES:
        raise ValueError("Ablation source must contain 500 aligned cases.")
    if int(ablation_run.get("bootstrap_samples") or 0) != EXPECTED_BOOTSTRAP_SAMPLES:
        raise ValueError("Ablation source must use 400 bootstrap samples.")
    if ablation_run.get("bootstrap_seed") != manifest.get("bootstrap_seed"):
        raise ValueError("Ablation and reproduction bootstrap seeds must match.")
    case_ids_sha256 = str(ablation_run.get("case_ids_sha256") or "")
    if len(case_ids_sha256) != 64:
        raise ValueError("Ablation source must record the aligned case-ID SHA-256.")
    profiles = tables.get("ablation_results") or []
    source_profiles = ablation_run.get("profiles") or []
    if len(profiles) != EXPECTED_ABLATION_PROFILES or len(source_profiles) != EXPECTED_ABLATION_PROFILES:
        raise ValueError("Snapshot source must contain all eleven required ablation variants.")
    if [row.get("id") for row in profiles] != [row.get("id") for row in source_profiles]:
        raise ValueError("Ablation table profiles must match the raw ablation source.")
    for profile in source_profiles:
        if profile.get("availability") == "not_available":
            if not profile.get("unavailable_reason"):
                raise ValueError("Unavailable ablation variants must explain why they were not run.")
            continue
        if int((profile.get("reported_summary") or {}).get("cases") or 0) != EXPECTED_ABLATION_CASES:
            raise ValueError("Every raw ablation profile must contain 500 aligned cases.")
        _validate_intervals(
            profile,
            label=str(profile.get("id") or "raw ablation profile"),
            expected_seed=manifest.get("bootstrap_seed"),
        )
    for profile in profiles:
        if profile.get("availability") == "not_available":
            if not profile.get("unavailable_reason"):
                raise ValueError("Unavailable ablation table variants must include a reason.")
            continue
        if int((profile.get("reported_summary") or {}).get("cases") or 0) != EXPECTED_ABLATION_CASES:
            raise ValueError("Every ablation profile must contain 500 aligned cases.")
        _validate_intervals(
            profile,
            label=str(profile.get("id") or "ablation profile"),
            expected_seed=manifest.get("bootstrap_seed"),
        )
    if len([profile for profile in profiles if profile.get("availability") != "not_available"]) != EXPECTED_AVAILABLE_ABLATION_PROFILES:
        raise ValueError("Snapshot source must contain nine executable ablation variants.")
    baselines = tables.get("baseline_results") or []
    if not baselines:
        raise ValueError("Snapshot source requires a same-ID baseline.")
    for baseline in baselines:
        coverage = baseline.get("coverage") or {}
        if any(
            int(coverage.get(key) or 0) != EXPECTED_CASES["ragtruth_primary"]
            for key in ("reference_cases", "submitted_predictions", "matched_predictions")
        ):
            raise ValueError("Every baseline must cover all 200 RAGTruth IDs.")
        _validate_intervals(
            baseline,
            label=str(baseline.get("system") or "baseline"),
            expected_seed=manifest.get("bootstrap_seed"),
            allow_class_filtered=True,
        )
    error = tables.get("error_analysis") or {}
    if int(error.get("case_count") or 0) != EXPECTED_CASES["ragtruth_primary"]:
        raise ValueError("Error analysis must cover all 200 RAGTruth cases.")


def _validate_intervals(
    row: dict[str, Any],
    *,
    label: str,
    expected_seed: Any,
    allow_class_filtered: bool = False,
) -> None:
    intervals = row.get("confidence_intervals") or {}
    if not intervals:
        raise ValueError("%s must contain confidence intervals." % label)
    for metric, interval in intervals.items():
        samples = int((interval or {}).get("samples") or 0)
        minimum = MIN_VALID_BOOTSTRAP_SAMPLES if allow_class_filtered else EXPECTED_BOOTSTRAP_SAMPLES
        if samples < minimum or samples > EXPECTED_BOOTSTRAP_SAMPLES:
            raise ValueError(
                "%s %s must retain %s-%s bootstrap draws."
                % (label, metric, minimum, EXPECTED_BOOTSTRAP_SAMPLES)
            )
        if (interval or {}).get("seed") != expected_seed:
            raise ValueError("%s %s must use the frozen bootstrap seed." % (label, metric))


def _validate_input_records(manifest: dict[str, Any]) -> None:
    inputs = manifest.get("inputs") or {}
    for required in ("experiment_spec", "selected_ragtruth_case_pack"):
        if not isinstance(inputs.get(required), dict) or inputs[required].get("available") is not True:
            raise ValueError("Snapshot source requires available input metadata for %s." % required)
    candidates = inputs.get("candidate_predictions") or []
    if not candidates or any(record.get("available") is not True for record in candidates):
        raise ValueError("Snapshot source requires an available matched-baseline input.")
    for record in _iter_file_records(inputs):
        if record.get("available") is not True:
            continue
        path = _resolve_path(str(record.get("path") or ""))
        if not path.is_file():
            raise ValueError("Snapshot input is missing: %s" % path)
        if path.stat().st_size != int(record.get("bytes") or -1):
            raise ValueError("Snapshot input byte count changed: %s" % path)
        if _sha256(path) != record.get("sha256"):
            raise ValueError("Snapshot input SHA-256 changed: %s" % path)


def _artifact_records(manifest_path: Path, tables_path: Path, manifest: dict[str, Any]) -> list[dict[str, Any]]:
    paths = [manifest_path, tables_path]
    paths.extend(_resolve_path(path) for path in _iter_output_paths(manifest.get("outputs") or {}))
    unique = sorted({path.resolve() for path in paths})
    missing = [path for path in unique if not path.is_file()]
    if missing:
        raise ValueError("Snapshot output is missing: %s" % missing[0])
    return [
        {
            "path": _portable_path(path),
            "bytes": path.stat().st_size,
            "sha256": _sha256(path),
        }
        for path in unique
    ]


def _manifest_output_path(manifest: dict[str, Any], *keys: str) -> Path:
    value: Any = manifest.get("outputs") or {}
    for key in keys:
        value = value.get(key) if isinstance(value, dict) else None
    if not isinstance(value, str) or not value:
        raise ValueError("Missing reproduction output: %s" % ".".join(keys))
    return _resolve_path(value)


def _iter_output_paths(value: Any):
    if isinstance(value, dict):
        for nested in value.values():
            yield from _iter_output_paths(nested)
    elif isinstance(value, str) and value:
        yield value


def _iter_file_records(value: Any):
    if isinstance(value, dict):
        if {"path", "bytes", "sha256"} <= set(value):
            yield value
        else:
            for nested in value.values():
                yield from _iter_file_records(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from _iter_file_records(nested)


def _resolve_path(path: str | Path) -> Path:
    candidate = Path(path)
    return candidate if candidate.is_absolute() else REPO_ROOT / candidate


def _portable_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return str(path.resolve())


def _load_object(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError("Expected a JSON object: %s" % path)
    return payload


def _metric(value: Any) -> str:
    if value is None:
        return "N/A"
    if isinstance(value, float):
        return "%.3f" % value
    return str(value)


def _metric_ci(row: dict[str, Any], key: str) -> str:
    value = (row.get("summary") or {}).get(key)
    interval = (row.get("confidence_intervals") or {}).get(key) or {}
    if value is None or interval.get("low") is None or interval.get("high") is None:
        return _metric(value)
    return "%s [%s, %s]" % (_metric(value), _metric(interval.get("low")), _metric(interval.get("high")))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Record a claim-safe ARR pre-review experiment snapshot.")
    parser.add_argument("--reproduction-dir", default=str(DEFAULT_REPRODUCTION_DIR))
    parser.add_argument("--json-output", default=str(DEFAULT_JSON_PATH))
    parser.add_argument("--markdown-output", default=str(DEFAULT_MARKDOWN_PATH))
    args = parser.parse_args(argv)
    result = write_pre_review_snapshot(
        reproduction_dir=args.reproduction_dir,
        json_path=args.json_output,
        markdown_path=args.markdown_output,
    )
    print("Status: %s" % result["status"])
    print("Paper result eligible: %s" % result["paper_result_eligible"])
    print("JSON: %s" % result["outputs"]["json"])
    print("Markdown: %s" % result["outputs"]["markdown"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
