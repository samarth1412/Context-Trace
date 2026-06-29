from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[1]
DEFAULT_PRIMARY_MANIFEST = SCRIPT_DIR / "out" / "ragtruth_release_bundle" / "manifest.json"
DEFAULT_DIAG150_MANIFEST = SCRIPT_DIR / "out" / "diag150_release_bundle" / "manifest.json"
DEFAULT_OUTPUT_JSON = SCRIPT_DIR / "out" / "sota_readiness" / "sota_readiness.json"
DEFAULT_OUTPUT_MD = SCRIPT_DIR / "out" / "sota_readiness" / "sota_readiness.md"
PRIMARY_THRESHOLDS = {
    "failure_label_macro_f1": (">=", 0.75),
    "dangerous_false_green_rate": ("<=", 0.01),
    "root_cause_accuracy": (">=", 0.70),
    "evidence_span_overlap": (">=", 0.70),
}
INTERVAL_METRICS = tuple(PRIMARY_THRESHOLDS)
EXTERNAL_REQUIRED_ARTIFACTS = (
    "case_pack.json",
    "contexttrace_bench_results.json",
    "candidate_inputs.jsonl",
)
DIAG150_REQUIRED_ARTIFACTS = (
    "contexttrace_bench_results.json",
    "candidate_inputs.jsonl",
    "diag150_audit_packet.json",
    "diag150_audit_validation.json",
)
DIAGNOSTIC_COVERAGE_FIELDS = (
    ("root_cause_reported_cases", "root_cause_accuracy"),
    ("citation_status_reported_cases", "citation_error_f1"),
    ("evidence_span_reported_cases", "evidence_span_overlap"),
)


@dataclass(frozen=True)
class ExternalTrack:
    name: str
    manifest_path: Path
    documentation_path: Path
    command_token: str


DEFAULT_EXTERNAL_TRACKS = (
    ExternalTrack(
        name="RAGTruth",
        manifest_path=DEFAULT_PRIMARY_MANIFEST,
        documentation_path=SCRIPT_DIR / "README.md",
        command_token="ragtruth_release_workflow.py",
    ),
    ExternalTrack(
        name="ARES-NQ-example",
        manifest_path=SCRIPT_DIR / "out" / "ares_nq_example" / "smoke200_compared_bundle" / "manifest.json",
        documentation_path=SCRIPT_DIR / "BASELINES.md",
        command_token="ares_adapter.py",
    ),
    ExternalTrack(
        name="CRAG-Task1-v5",
        manifest_path=SCRIPT_DIR / "out" / "crag_official" / "review200_ragchecker_bundle" / "manifest.json",
        documentation_path=SCRIPT_DIR / "CRAG.md",
        command_token="crag_adapter.py",
    ),
)


def build_sota_readiness_report(
    *,
    primary_manifest_path: str | Path = DEFAULT_PRIMARY_MANIFEST,
    external_tracks: tuple[ExternalTrack, ...] | list[ExternalTrack] | None = None,
    diag150_manifest_path: str | Path = DEFAULT_DIAG150_MANIFEST,
    minimum_external_datasets: int = 2,
    minimum_competitors: int = 1,
) -> dict[str, Any]:
    tracks = list(external_tracks or DEFAULT_EXTERNAL_TRACKS)
    primary_path = Path(primary_manifest_path)
    diag150_path = Path(diag150_manifest_path)
    checks: list[dict[str, Any]] = []

    primary_evidence = validate_bundle(primary_path, required_artifacts=EXTERNAL_REQUIRED_ARTIFACTS)
    _append_check(
        checks,
        name="primary_bundle_integrity",
        passed=primary_evidence["valid"],
        requirement="The primary external bundle and every listed artifact pass checksum and structure validation.",
        evidence=_bundle_evidence(primary_evidence),
    )

    track_evidence = [validate_external_track(track) for track in tracks]
    scored_datasets = sorted(
        {
            str(item.get("dataset") or item.get("name"))
            for item in track_evidence
            if item.get("valid") and item.get("scored")
        }
    )
    _append_check(
        checks,
        name="external_dataset_count",
        passed=len(scored_datasets) >= minimum_external_datasets,
        requirement="At least %s external datasets are scored end to end with frozen artifacts and documented commands."
        % minimum_external_datasets,
        evidence={
            "required": minimum_external_datasets,
            "actual": len(scored_datasets),
            "datasets": scored_datasets,
            "tracks": track_evidence,
        },
    )

    primary_manifest = primary_evidence.get("manifest") or {}
    primary_review = primary_manifest.get("review") or {}
    independently_reviewed = (
        primary_evidence["valid"]
        and primary_manifest.get("bundle_status") == "publishable"
        and str(primary_manifest.get("review_kind") or "").lower() == "independent"
        and bool(primary_review.get("valid"))
        and int(primary_review.get("errors") or 0) == 0
        and int(primary_review.get("warnings") or 0) == 0
    )
    _append_check(
        checks,
        name="primary_independent_review",
        passed=independently_reviewed,
        requirement="The primary external run has complete independent review with zero validation errors or warnings.",
        evidence={
            "bundle_status": primary_manifest.get("bundle_status"),
            "review_kind": primary_manifest.get("review_kind"),
            "review_valid": primary_review.get("valid"),
            "reviewed_rows": primary_review.get("reviewed_rows"),
            "review_rows": primary_review.get("review_rows"),
            "errors": primary_review.get("errors"),
            "warnings": primary_review.get("warnings"),
        },
    )

    primary_summary = ((primary_manifest.get("score") or {}).get("summary") or {})
    for metric, (operator, threshold) in PRIMARY_THRESHOLDS.items():
        value = _number_or_none(primary_summary.get(metric))
        passed = value is not None and (value >= threshold if operator == ">=" else value <= threshold)
        _append_check(
            checks,
            name="primary_%s" % metric,
            passed=passed,
            requirement="Primary external `%s` must be %s %.2f." % (metric, operator, threshold),
            evidence={"metric": metric, "operator": operator, "threshold": threshold, "value": value},
        )

    primary_result = _load_bundle_artifact(primary_evidence, "contexttrace_bench_results.json")
    score_alignment = _summary_matches(primary_summary, (primary_result or {}).get("summary") or {})
    interval_evidence = validate_confidence_intervals(primary_result or {})
    _append_check(
        checks,
        name="primary_confidence_intervals",
        passed=bool(primary_result) and score_alignment["valid"] and interval_evidence["valid"],
        requirement="Primary point metrics match the scored artifact and include valid 95% case-bootstrap intervals.",
        evidence={"summary_alignment": score_alignment, "intervals": interval_evidence},
    )

    competitor_evidence = validate_competitor_coverage(primary_evidence, minimum_competitors=minimum_competitors)
    _append_check(
        checks,
        name="primary_same_id_competitors",
        passed=competitor_evidence["valid"],
        requirement="At least %s full competitor row set is scored on the exact primary IDs with unsupported diagnostics as N/A."
        % minimum_competitors,
        evidence=competitor_evidence,
    )

    diag150_evidence = validate_bundle(diag150_path, required_artifacts=DIAG150_REQUIRED_ARTIFACTS)
    diag150_manifest = diag150_evidence.get("manifest") or {}
    diag150_ready = (
        diag150_evidence["valid"]
        and diag150_manifest.get("bundle_status") == "freeze_ready"
        and bool(diag150_manifest.get("human_signoff_complete"))
        and diag150_manifest.get("validation_status") == "passed"
    )
    _append_check(
        checks,
        name="diag150_human_audit",
        passed=diag150_ready,
        requirement="ContextTrace-Diag-150 is checksum-valid, independently signed off, and freeze-ready.",
        evidence={
            **_bundle_evidence(diag150_evidence),
            "bundle_status": diag150_manifest.get("bundle_status"),
            "human_signoff_complete": diag150_manifest.get("human_signoff_complete"),
            "validation_status": diag150_manifest.get("validation_status"),
        },
    )

    passed_checks = sum(1 for check in checks if check["passed"])
    status = "claim_ready" if passed_checks == len(checks) else "not_ready"
    return {
        "gate": "ContextTrace broad SOTA claim",
        "gate_version": 1,
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "status": status,
        "claim_allowed": status == "claim_ready",
        "claim_policy": (
            "All documented SOTA evidence gates passed. Preserve dataset-specific limitations in public claims."
            if status == "claim_ready"
            else "Do not claim broad SOTA; use the benchmarked, local-first evidence-chain forensics positioning."
        ),
        "summary": {
            "checks": len(checks),
            "passed": passed_checks,
            "failed": len(checks) - passed_checks,
        },
        "checks": checks,
    }


def validate_external_track(track: ExternalTrack) -> dict[str, Any]:
    bundle = validate_bundle(track.manifest_path, required_artifacts=EXTERNAL_REQUIRED_ARTIFACTS)
    manifest = bundle.get("manifest") or {}
    summary = ((manifest.get("score") or {}).get("summary") or {})
    case_count = _integer_or_none(manifest.get("case_count"))
    summary_cases = _integer_or_none(summary.get("cases"))
    documentation_valid = False
    documentation_error = ""
    if not track.documentation_path.exists():
        documentation_error = "missing documentation: %s" % track.documentation_path
    else:
        documentation_valid = track.command_token in track.documentation_path.read_text(encoding="utf-8")
        if not documentation_valid:
            documentation_error = "documentation does not contain %s" % track.command_token
    workflow_status = str(manifest.get("workflow_status") or "")
    scored = (
        workflow_status in {"scored", "scored_review_pending"}
        and case_count is not None
        and case_count > 0
        and case_count == summary_cases
    )
    errors = list(bundle["errors"])
    if not documentation_valid:
        errors.append(documentation_error)
    if not scored:
        errors.append("workflow is not a scored, case-count-aligned run")
    return {
        "name": track.name,
        "dataset": manifest.get("dataset"),
        "manifest": _display_path(track.manifest_path),
        "documentation": _display_path(track.documentation_path),
        "command_token": track.command_token,
        "bundle_status": manifest.get("bundle_status"),
        "workflow_status": workflow_status,
        "case_count": case_count,
        "scored": scored,
        "valid": not errors,
        "errors": errors,
    }


def validate_bundle(manifest_path: str | Path, *, required_artifacts: tuple[str, ...]) -> dict[str, Any]:
    path = Path(manifest_path)
    evidence: dict[str, Any] = {
        "manifest_path": _display_path(path),
        "bundle_root": str(path.parent.resolve()),
        "manifest": {},
        "artifact_count": 0,
        "valid": False,
        "errors": [],
    }
    if not path.is_file():
        evidence["errors"].append("missing manifest: %s" % path)
        return evidence
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        evidence["errors"].append("invalid manifest: %s" % exc)
        return evidence
    if not isinstance(manifest, dict):
        evidence["errors"].append("manifest root must be an object")
        return evidence
    evidence["manifest"] = manifest
    artifacts = manifest.get("artifacts") or []
    if not isinstance(artifacts, list):
        evidence["errors"].append("manifest artifacts must be a list")
        return evidence
    evidence["artifact_count"] = len(artifacts)
    if manifest.get("missing_required_artifacts"):
        evidence["errors"].append("manifest reports missing required artifacts")

    artifact_names = []
    bundle_root = path.parent.resolve()
    for artifact in artifacts:
        if not isinstance(artifact, dict):
            evidence["errors"].append("artifact entry is not an object")
            continue
        relative_path = str(artifact.get("path") or "")
        artifact_names.append(relative_path.replace("\\", "/"))
        artifact_path = (bundle_root / relative_path).resolve()
        try:
            artifact_path.relative_to(bundle_root)
        except ValueError:
            evidence["errors"].append("artifact escapes bundle root: %s" % relative_path)
            continue
        if not artifact_path.is_file():
            evidence["errors"].append("missing artifact: %s" % relative_path)
            continue
        expected_bytes = _integer_or_none(artifact.get("bytes"))
        if expected_bytes is None or artifact_path.stat().st_size != expected_bytes:
            evidence["errors"].append("byte count mismatch: %s" % relative_path)
        expected_sha = str(artifact.get("sha256") or "").lower()
        if len(expected_sha) != 64 or _sha256_file(artifact_path) != expected_sha:
            evidence["errors"].append("SHA256 mismatch: %s" % relative_path)

    for required_name in required_artifacts:
        if not any(name.endswith(required_name) for name in artifact_names):
            evidence["errors"].append("required artifact is not declared: %s" % required_name)
    if not any(name.endswith("workflow_manifest.json") for name in artifact_names) and required_artifacts == EXTERNAL_REQUIRED_ARTIFACTS:
        evidence["errors"].append("required workflow manifest is not declared")
    evidence["valid"] = not evidence["errors"]
    return evidence


def validate_confidence_intervals(result: dict[str, Any]) -> dict[str, Any]:
    intervals = result.get("confidence_intervals") or {}
    summary = result.get("summary") or {}
    errors = []
    rows = {}
    for metric in INTERVAL_METRICS:
        interval = intervals.get(metric) if isinstance(intervals, dict) else None
        point = _number_or_none(summary.get(metric))
        if not isinstance(interval, dict):
            errors.append("missing interval: %s" % metric)
            continue
        low = _number_or_none(interval.get("low"))
        high = _number_or_none(interval.get("high"))
        estimate = _number_or_none(interval.get("estimate"))
        samples = _integer_or_none(interval.get("samples"))
        level = _number_or_none(interval.get("level"))
        rows[metric] = {"estimate": estimate, "low": low, "high": high, "samples": samples, "level": level}
        if None in {point, low, high, estimate, level} or samples is None:
            errors.append("incomplete interval: %s" % metric)
        elif not (low <= point <= high and estimate == point and samples > 0 and level == 0.95):
            errors.append("invalid interval: %s" % metric)
    return {"valid": not errors, "metrics": rows, "errors": errors}


def validate_competitor_coverage(bundle: dict[str, Any], *, minimum_competitors: int) -> dict[str, Any]:
    reference = _load_bundle_artifact(bundle, "contexttrace_bench_results.json")
    baselines = _load_bundle_artifact(bundle, "baseline_results.json")
    errors = []
    if not isinstance(reference, dict):
        errors.append("primary scored result is missing or invalid")
        reference = {}
    reference_rows = [row for row in reference.get("rows") or [] if isinstance(row, dict)]
    reference_ids = [str(row.get("id") or "") for row in reference_rows]
    if not reference_ids or len(reference_ids) != len(set(reference_ids)) or any(not case_id for case_id in reference_ids):
        errors.append("primary result IDs are empty or non-unique")
    if not isinstance(baselines, list):
        errors.append("primary baseline_results.json is missing or invalid")
        baselines = []

    systems = []
    valid_competitors = 0
    for baseline in baselines:
        if not isinstance(baseline, dict):
            errors.append("competitor entry is not an object")
            continue
        system = str(baseline.get("system") or "candidate")
        baseline_errors = []
        rows = [row for row in baseline.get("rows") or [] if isinstance(row, dict)]
        ids = [str(row.get("id") or "") for row in rows]
        coverage = baseline.get("coverage") or {}
        summary = baseline.get("summary") or {}
        if baseline.get("status") != "scored":
            baseline_errors.append("status is not scored")
        if ids != reference_ids:
            baseline_errors.append("row IDs or order do not exactly match the primary result")
        if any(_integer_or_none(coverage.get(key)) != len(reference_ids) for key in ("reference_cases", "submitted_predictions", "matched_predictions")):
            baseline_errors.append("coverage is not complete")
        if _integer_or_none(summary.get("cases")) != len(reference_ids):
            baseline_errors.append("summary case count does not match")
        for coverage_field, metric_field in DIAGNOSTIC_COVERAGE_FIELDS:
            reported = _integer_or_none(summary.get(coverage_field))
            metric_value = summary.get(metric_field)
            if reported == 0 and metric_value is not None:
                baseline_errors.append("unsupported %s must be null/N/A" % metric_field)
        systems.append({"system": system, "rows": len(rows), "valid": not baseline_errors, "errors": baseline_errors})
        if not baseline_errors:
            valid_competitors += 1
    if valid_competitors < minimum_competitors:
        errors.append("valid full competitors %s is below required %s" % (valid_competitors, minimum_competitors))
    return {
        "valid": not errors,
        "required_competitors": minimum_competitors,
        "valid_competitors": valid_competitors,
        "reference_cases": len(reference_ids),
        "systems": systems,
        "errors": errors,
    }


def render_sota_readiness_markdown(report: dict[str, Any]) -> str:
    summary = report.get("summary") or {}
    lines = [
        "# ContextTrace SOTA Readiness Gate",
        "",
        "Status: `%s`" % report.get("status"),
        "Generated: `%s`" % report.get("generated_at"),
        "Claim allowed: `%s`" % str(bool(report.get("claim_allowed"))).lower(),
        "Checks passed: `%s/%s`" % (summary.get("passed"), summary.get("checks")),
        "",
        "## Claim Policy",
        "",
        str(report.get("claim_policy") or ""),
        "",
        "## Gate Results",
        "",
        "| Gate | Result | Requirement |",
        "| --- | --- | --- |",
    ]
    for check in report.get("checks") or []:
        lines.append(
            "| `%s` | `%s` | %s |"
            % (
                check.get("name"),
                "passed" if check.get("passed") else "failed",
                _markdown_text(check.get("requirement")),
            )
        )
    failed = [check for check in report.get("checks") or [] if not check.get("passed")]
    lines.extend(["", "## Remaining Blockers", ""])
    if not failed:
        lines.append("No gate blockers remain.")
    for check in failed:
        lines.append("- `%s`: %s" % (check.get("name"), _short_evidence(check.get("evidence") or {})))
    return "\n".join(lines) + "\n"


def write_sota_readiness_report(
    report: dict[str, Any],
    *,
    output_json: str | Path = DEFAULT_OUTPUT_JSON,
    output_md: str | Path = DEFAULT_OUTPUT_MD,
) -> dict[str, str]:
    json_path = Path(output_json)
    md_path = Path(output_md)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    md_path.write_text(render_sota_readiness_markdown(report), encoding="utf-8")
    return {"json": str(json_path), "markdown": str(md_path)}


def _load_bundle_artifact(bundle: dict[str, Any], suffix: str) -> Any:
    manifest = bundle.get("manifest") or {}
    root = Path(str(bundle.get("bundle_root") or "."))
    for artifact in manifest.get("artifacts") or []:
        if not isinstance(artifact, dict):
            continue
        relative_path = str(artifact.get("path") or "")
        if relative_path.replace("\\", "/").endswith(suffix):
            path = root / relative_path
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                return None
    return None


def _summary_matches(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    mismatches = []
    for metric in PRIMARY_THRESHOLDS:
        if _number_or_none(left.get(metric)) != _number_or_none(right.get(metric)):
            mismatches.append(metric)
    return {"valid": not mismatches, "mismatches": mismatches}


def _bundle_evidence(bundle: dict[str, Any]) -> dict[str, Any]:
    return {
        "manifest": bundle.get("manifest_path"),
        "artifact_count": bundle.get("artifact_count"),
        "errors": bundle.get("errors") or [],
    }


def _append_check(
    checks: list[dict[str, Any]],
    *,
    name: str,
    passed: bool,
    requirement: str,
    evidence: dict[str, Any],
) -> None:
    checks.append({"name": name, "passed": bool(passed), "requirement": requirement, "evidence": evidence})


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _number_or_none(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _integer_or_none(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _markdown_text(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def _display_path(path: str | Path) -> str:
    resolved = Path(path).resolve()
    try:
        return resolved.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return str(resolved)


def _short_evidence(evidence: dict[str, Any]) -> str:
    if "human_signoff_complete" in evidence:
        return "human sign-off `%s`, bundle status `%s`." % (
            evidence.get("human_signoff_complete"),
            evidence.get("bundle_status"),
        )
    if "bundle_status" in evidence:
        return "bundle status `%s`, review kind `%s`." % (
            evidence.get("bundle_status"),
            evidence.get("review_kind"),
        )
    if "valid_competitors" in evidence:
        return "%s valid full competitor rows; %s required." % (
            evidence.get("valid_competitors"),
            evidence.get("required_competitors"),
        )
    if "value" in evidence:
        return "value `%s`; required `%s %s`." % (
            evidence.get("value"),
            evidence.get("operator"),
            evidence.get("threshold"),
        )
    return _markdown_text(json.dumps(evidence, sort_keys=True))[:300]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate the fail-closed ContextTrace broad-SOTA evidence gate.")
    parser.add_argument("--primary-manifest", default=str(DEFAULT_PRIMARY_MANIFEST))
    parser.add_argument("--diag150-manifest", default=str(DEFAULT_DIAG150_MANIFEST))
    parser.add_argument("--output-json", default=str(DEFAULT_OUTPUT_JSON))
    parser.add_argument("--output-md", default=str(DEFAULT_OUTPUT_MD))
    parser.add_argument("--minimum-external-datasets", type=int, default=2)
    parser.add_argument("--minimum-competitors", type=int, default=1)
    parser.add_argument("--allow-not-ready", action="store_true", help="Write the report but return zero while gates remain open.")
    args = parser.parse_args(argv)
    report = build_sota_readiness_report(
        primary_manifest_path=args.primary_manifest,
        diag150_manifest_path=args.diag150_manifest,
        minimum_external_datasets=args.minimum_external_datasets,
        minimum_competitors=args.minimum_competitors,
    )
    paths = write_sota_readiness_report(report, output_json=args.output_json, output_md=args.output_md)
    print("SOTA readiness: %s" % report["status"])
    print("Checks: %s/%s passed" % (report["summary"]["passed"], report["summary"]["checks"]))
    print("JSON: %s" % paths["json"])
    print("Markdown: %s" % paths["markdown"])
    return 0 if report["claim_allowed"] or args.allow_not_ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
