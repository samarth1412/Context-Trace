from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

try:  # pragma: no cover - exercised when run as a script from this directory
    from benchmarks.contexttrace_bench.run_contexttrace import (
        DEFAULT_OUTPUT_DIR,
        render_candidate_inputs_jsonl,
        run_contexttrace_benchmark,
        write_benchmark_outputs,
    )
except ModuleNotFoundError:  # pragma: no cover
    from run_contexttrace import (  # type: ignore
        DEFAULT_OUTPUT_DIR,
        render_candidate_inputs_jsonl,
        run_contexttrace_benchmark,
        write_benchmark_outputs,
    )


DEFAULT_AUDIT_OUTPUT_DIR = DEFAULT_OUTPUT_DIR / "public_holdout"
DEFAULT_RELEASE_BUNDLE_DIR = DEFAULT_OUTPUT_DIR / "diag150_release_bundle"
DEFAULT_RESULTS_PATH = DEFAULT_AUDIT_OUTPUT_DIR / "contexttrace_bench_results.json"
DEFAULT_CANDIDATE_INPUTS_PATH = DEFAULT_AUDIT_OUTPUT_DIR / "candidate_inputs.jsonl"
DEFAULT_CANONICAL_REPORT_PATH = Path(__file__).with_name("AUDIT_REPORT.md")
REQUIRED_CASE_COUNT = 150
REQUIRED_LABELS = {
    "no_failure_detected",
    "partial_support",
    "contradicted_answer",
    "should_have_abstained",
    "citation_mismatch",
}
ALLOWED_ROOT_CAUSES = {
    "no_failure_detected",
    "answer_overreach",
    "conflicting_contexts",
    "wrong_source_cited",
    "missing_cited_source",
    "should_have_abstained",
}
LEAKAGE_KEYS = {
    "benchmark_pass",
    "citation_error_counts",
    "citation_match",
    "evidence_span_overlap",
    "exact_match",
    "expected",
    "expected_citation_statuses",
    "expected_evidence_spans",
    "expected_labels",
    "expected_primary_root_cause",
    "expected_should_abstain",
    "expected_verdict_counts",
    "label",
    "labels",
    "note",
    "predicted",
    "predicted_citation_statuses",
    "predicted_evidence_spans",
    "predicted_labels",
    "predicted_primary_root_cause",
    "predicted_should_abstain",
    "predicted_verdict_counts",
    "root_cause_match",
    "verdict_match",
}
HUMAN_SIGNOFF_FIELDS = (
    "source_url_opened",
    "context_fair",
    "label_correct",
    "evidence_span_minimal",
    "reviewer",
    "reviewed_at",
    "notes",
)
HUMAN_SIGNOFF_BOOLEAN_FIELDS = (
    "source_url_opened",
    "context_fair",
    "label_correct",
    "evidence_span_minimal",
)
HUMAN_REVIEW_BLOCKING_STATUSES = {"needs_changes", "rejected"}
RELEASE_BUNDLE_ARTIFACTS = (
    "contexttrace_bench_results.json",
    "results.md",
    "leaderboard.md",
    "report.html",
    "error_analysis.json",
    "error_analysis.md",
    "candidate_inputs.jsonl",
    "diag150_audit_packet.json",
    "diag150_audit_packet.md",
    "diag150_human_review_template.json",
    "diag150_audit_validation.json",
    "AUDIT_REPORT.md",
)
OPTIONAL_RELEASE_BUNDLE_ARTIFACTS = (
    "baseline_results.json",
    "openai_diagnostic_judge_predictions.json",
    "openai_diagnostic_judge_raw_results.json",
)


def load_benchmark_result(path: str | Path) -> dict[str, Any]:
    result_path = Path(path)
    payload = json.loads(result_path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError("Benchmark result must contain a JSON object.")
    return payload


def load_candidate_inputs(path: str | Path) -> list[dict[str, Any]]:
    input_path = Path(path)
    rows = []
    for line_number, line in enumerate(input_path.read_text(encoding="utf-8-sig").splitlines(), start=1):
        if not line.strip():
            continue
        payload = json.loads(line)
        if not isinstance(payload, dict):
            raise ValueError("Candidate input row %s must be a JSON object." % line_number)
        rows.append(payload)
    return rows


def load_human_review_file(path: str | Path) -> dict[str, dict[str, Any]]:
    review_path = Path(path)
    payload = json.loads(review_path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError("Human review file must contain a JSON object.")
    cases = payload.get("cases") or []
    if not isinstance(cases, list):
        raise ValueError("Human review file must contain a cases list.")
    reviews: dict[str, dict[str, Any]] = {}
    for index, item in enumerate(cases, start=1):
        if not isinstance(item, dict):
            raise ValueError("Human review case %s must be a JSON object." % index)
        case_id = str(item.get("id") or "").strip()
        if not case_id:
            raise ValueError("Human review case %s is missing id." % index)
        if case_id in reviews:
            raise ValueError("Human review file repeats case id %s." % case_id)
        reviews[case_id] = dict(item)
    return reviews


def build_diag150_audit_packet(
    result: dict[str, Any],
    *,
    candidate_inputs: list[dict[str, Any]] | None = None,
    human_reviews: dict[str, dict[str, Any]] | None = None,
    artifact_paths: dict[str, str] | None = None,
    reviewer: str = "Pending",
    audit_status: str = "pending_human_signoff",
    commit: str | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    rows = [row for row in result.get("rows") or [] if isinstance(row, dict)]
    cases = []
    for row in rows:
        case = _audit_case(row)
        review = (human_reviews or {}).get(str(case.get("id") or ""))
        if review is not None:
            case["human_review"] = _normalized_human_review(review)
        cases.append(case)
    label_distribution = Counter(label for row in rows for label in row.get("expected") or [])
    label_set_distribution = Counter(_label_set_key(row.get("expected") or []) for row in rows)
    source_family_distribution = Counter(
        context.get("source_family") or case.get("source_family")
        for case in cases
        for context in case.get("contexts") or []
        if context.get("source_family") or case.get("source_family")
    )
    candidate_ids = [str(row.get("id") or "") for row in candidate_inputs or []]
    return {
        "benchmark": "ContextTrace-Diag-150",
        "case_set": result.get("case_set"),
        "status": audit_status,
        "human_signoff_required": True,
        "reviewer": reviewer,
        "generated_at": generated_at or datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "commit": commit or current_git_commit(),
        "artifact_paths": artifact_paths or {},
        "summary": result.get("summary") or {},
        "confidence_intervals": result.get("confidence_intervals") or {},
        "base_cases": result.get("base_cases"),
        "generated_cases": result.get("generated_cases"),
        "case_count": len(cases),
        "candidate_input_rows": len(candidate_ids),
        "candidate_input_ids": candidate_ids,
        "label_distribution": dict(sorted(label_distribution.items())),
        "label_set_distribution": dict(sorted(label_set_distribution.items())),
        "source_family_distribution": dict(sorted(source_family_distribution.items())),
        "required_labels": sorted(REQUIRED_LABELS),
        "allowed_root_causes": sorted(ALLOWED_ROOT_CAUSES),
        "human_signoff_fields": list(HUMAN_SIGNOFF_FIELDS),
        "cases": cases,
    }


def validate_diag150_audit_packet(
    packet: dict[str, Any],
    *,
    result: dict[str, Any] | None = None,
    candidate_inputs: list[dict[str, Any]] | None = None,
    required_case_count: int = REQUIRED_CASE_COUNT,
    require_human_signoff: bool = False,
) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    cases = [case for case in packet.get("cases") or [] if isinstance(case, dict)]
    case_ids = [str(case.get("id") or "") for case in cases]

    _add_check(checks, "case_set_public_holdout", packet.get("case_set") == "public_holdout", "error", packet.get("case_set"))
    _add_check(checks, "case_count", len(cases) == required_case_count, "error", {"expected": required_case_count, "actual": len(cases)})
    _add_check(checks, "unique_case_ids", len(set(case_ids)) == len(case_ids), "error", _duplicates(case_ids))
    _add_check(checks, "no_generated_cases", int(packet.get("generated_cases") or 0) == 0 and all(not case.get("generated") for case in cases), "error", packet.get("generated_cases"))

    observed_labels = set(packet.get("label_distribution") or {})
    _add_check(checks, "required_label_coverage", REQUIRED_LABELS.issubset(observed_labels), "error", sorted(REQUIRED_LABELS - observed_labels))

    root_causes = {str(case.get("expected_primary_root_cause") or "") for case in cases}
    unknown_root_causes = sorted(root_causes - ALLOWED_ROOT_CAUSES - {""})
    _add_check(checks, "root_cause_taxonomy", not unknown_root_causes, "error", unknown_root_causes)

    source_url_missing = [
        {"case_id": case.get("id"), "context_id": context.get("id")}
        for case in cases
        for context in case.get("contexts") or []
        if not context.get("source_url")
    ]
    _add_check(checks, "source_urls_present", not source_url_missing, "error", source_url_missing[:25])

    span_misses = []
    for case in cases:
        context_text = "\n".join(str(context.get("text") or "") for context in case.get("contexts") or [])
        normalized_context = _normalize_text(context_text)
        for span in case.get("expected_evidence_spans") or []:
            if _normalize_text(str(span)) not in normalized_context:
                span_misses.append({"case_id": case.get("id"), "span": str(span)})
    _add_check(checks, "evidence_spans_grounded_in_context", not span_misses, "error", span_misses[:25])

    failed_cases = [case.get("id") for case in cases if case.get("benchmark_pass") is False]
    _add_check(checks, "contexttrace_benchmark_passes", not failed_cases, "error", failed_cases[:25])

    if result is not None:
        result_rows = [row for row in result.get("rows") or [] if isinstance(row, dict)]
        result_ids = {str(row.get("id") or "") for row in result_rows}
        _add_check(checks, "result_case_ids_match_packet", set(case_ids) == result_ids, "error", sorted(set(case_ids) ^ result_ids)[:25])
        result_summary_cases = int((result.get("summary") or {}).get("cases") or 0)
        _add_check(checks, "result_summary_case_count", result_summary_cases == len(cases), "error", {"summary_cases": result_summary_cases, "packet_cases": len(cases)})

    if candidate_inputs is not None:
        candidate_ids = [str(row.get("id") or "") for row in candidate_inputs]
        leakage_paths = []
        for index, row in enumerate(candidate_inputs):
            leakage_paths.extend(_candidate_leakage_paths(row, path="$[%s]" % index))
        _add_check(checks, "candidate_input_count", len(candidate_inputs) == len(cases), "error", {"candidate_inputs": len(candidate_inputs), "packet_cases": len(cases)})
        _add_check(checks, "candidate_input_ids_match_packet", set(candidate_ids) == set(case_ids), "error", sorted(set(candidate_ids) ^ set(case_ids))[:25])
        _add_check(checks, "candidate_inputs_hide_labels", not leakage_paths, "error", leakage_paths[:25])

    signed_cases = [
        case.get("id")
        for case in cases
        if _human_review_signed_off(case.get("human_review") or {})
    ]
    review_blockers = [
        {
            "case_id": case.get("id"),
            "status": (case.get("human_review") or {}).get("status"),
            "notes": (case.get("human_review") or {}).get("notes"),
        }
        for case in cases
        if _human_review_blocked(case.get("human_review") or {})
    ]
    _add_check(
        checks,
        "human_review_blockers",
        not review_blockers,
        "error",
        review_blockers[:25],
    )
    _add_check(
        checks,
        "independent_human_signoff_complete",
        len(signed_cases) == len(cases),
        "error" if require_human_signoff else "warning",
        {"signed_off": len(signed_cases), "required": len(cases)},
    )

    errors = [check for check in checks if check["severity"] == "error" and check["status"] == "failed"]
    warnings = [check for check in checks if check["severity"] == "warning" and check["status"] == "failed"]
    return {
        "benchmark": packet.get("benchmark"),
        "case_set": packet.get("case_set"),
        "status": "failed" if errors else "passed",
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "summary": {
            "checks": len(checks),
            "errors": len(errors),
            "warnings": len(warnings),
            "case_count": len(cases),
        },
        "checks": checks,
        "errors": errors,
        "warnings": warnings,
    }


def build_human_review_template(packet: dict[str, Any]) -> dict[str, Any]:
    return {
        "benchmark": packet.get("benchmark"),
        "case_set": packet.get("case_set"),
        "audit_packet_commit": packet.get("commit"),
        "audit_packet_generated_at": packet.get("generated_at"),
        "instructions": (
            "Fill every case with status signed_off only after opening the source URL, "
            "checking context fairness, confirming labels, and confirming the evidence span. "
            "Use status needs_changes for any blocker; do not edit benchmark labels in this file."
        ),
        "cases": [
            {
                "id": case.get("id"),
                "status": "pending",
                "source_url_opened": None,
                "context_fair": None,
                "label_correct": None,
                "evidence_span_minimal": None,
                "reviewer": "",
                "reviewed_at": "",
                "notes": "",
            }
            for case in packet.get("cases") or []
        ],
    }


def render_audit_packet_markdown(packet: dict[str, Any]) -> str:
    lines = [
        "# ContextTrace-Diag-150 Audit Packet",
        "",
        "Generated: `%s`" % packet.get("generated_at"),
        "Commit: `%s`" % packet.get("commit"),
        "Status: `%s`" % packet.get("status"),
        "Reviewer: `%s`" % packet.get("reviewer"),
        "",
        "This packet is for independent human review of the `public_holdout` split. Do not call the split frozen until every case is signed off.",
        "",
        "## Summary",
        "",
        "| Field | Value |",
        "| --- | ---: |",
        "| Cases | %s |" % packet.get("case_count"),
        "| Generated cases | %s |" % packet.get("generated_cases"),
        "| Candidate input rows | %s |" % packet.get("candidate_input_rows"),
        "| Failure macro-F1 | %s |" % _metric(packet, "failure_label_macro_f1"),
        "| Root-cause accuracy | %s |" % _metric(packet, "root_cause_accuracy"),
        "| Citation error F1 | %s |" % _metric(packet, "citation_error_f1"),
        "| Evidence span overlap | %s |" % _metric(packet, "evidence_span_overlap"),
        "",
        "## Label Distribution",
        "",
        "| Label | Count |",
        "| --- | ---: |",
    ]
    for label, count in (packet.get("label_distribution") or {}).items():
        lines.append("| `%s` | %s |" % (label, count))

    lines.extend(["", "## Source Family Balance", "", "| Source family | Contexts |", "| --- | ---: |"])
    for family, count in sorted((packet.get("source_family_distribution") or {}).items(), key=lambda item: (-item[1], item[0])):
        lines.append("| `%s` | %s |" % (family, count))

    lines.extend(
        [
            "",
            "## Reviewer Instructions",
            "",
            "For each case, verify that the source URL opens, the context is fair to the source, the expected labels are correct, and the evidence span is the minimum source text needed to justify the label.",
            "",
            "Required signoff fields: %s." % ", ".join("`%s`" % field for field in packet.get("human_signoff_fields") or []),
            "",
            "## Cases",
            "",
        ]
    )
    for index, case in enumerate(packet.get("cases") or [], start=1):
        lines.extend(_case_markdown(index, case))
    return "\n".join(lines) + "\n"


def render_audit_report_markdown(packet: dict[str, Any], validation: dict[str, Any]) -> str:
    status = "Passed automated validation; independent human sign-off still required."
    if validation.get("status") != "passed":
        status = "Failed automated validation; fix blockers before human sign-off."
    elif _validation_check_passed(validation, "independent_human_signoff_complete"):
        status = "Passed automated validation and independent human sign-off is complete."
    lines = [
        "# ContextTrace-Diag-150 Automated Audit Report",
        "",
        "Date: %s" % str(packet.get("generated_at") or "").split("T")[0],
        "Commit audited: `%s`" % packet.get("commit"),
        "Scope: `public_holdout` %s-case machine-checkable audit packet" % packet.get("case_count"),
        "Status: %s" % status,
        "",
        "## Generated Artifacts",
        "",
        "| Artifact | Path |",
        "| --- | --- |",
    ]
    for name, path in sorted((packet.get("artifact_paths") or {}).items()):
        lines.append("| `%s` | `%s` |" % (name, path))

    lines.extend(["", "## Automated Checks", "", "| Check | Severity | Result | Details |", "| --- | --- | --- | --- |"])
    for check in validation.get("checks") or []:
        lines.append(
            "| `%s` | `%s` | `%s` | %s |"
            % (
                check.get("name"),
                check.get("severity"),
                check.get("status"),
                _markdown_detail(check.get("details")),
            )
        )

    lines.extend(["", "## Label Distribution", "", "| Label | Count |", "| --- | ---: |"])
    for label, count in (packet.get("label_distribution") or {}).items():
        lines.append("| `%s` | %s |" % (label, count))

    lines.extend(["", "## Source Family Balance", "", "| Source Family | Contexts |", "| --- | ---: |"])
    for family, count in sorted((packet.get("source_family_distribution") or {}).items(), key=lambda item: (-item[1], item[0])):
        lines.append("| `%s` | %s |" % (family, count))

    lines.extend(
        [
            "",
            "## Reproducibility Results",
            "",
            "ContextTrace semantic verifier on `public_holdout`:",
            "",
            "- Cases: `%s`" % _metric(packet, "cases"),
            "- Failure macro-F1: `%s`" % _metric(packet, "failure_label_macro_f1"),
            "- Claim-verdict macro-F1: `%s`" % _metric(packet, "claim_verdict_macro_f1"),
            "- Root-cause accuracy: `%s`" % _metric(packet, "root_cause_accuracy"),
            "- Citation error F1: `%s`" % _metric(packet, "citation_error_f1"),
            "- Evidence span overlap: `%s`" % _metric(packet, "evidence_span_overlap"),
            "",
            "## Remaining Human Audit",
            "",
            "The validator proves structural consistency, label leakage prevention, source URL presence, evidence-span grounding, and artifact alignment. It does not prove every label is the best human label or every source excerpt is semantically fair. Complete the case-level packet review before using frozen-split language.",
        ]
    )
    return "\n".join(lines) + "\n"


def write_diag150_audit_artifacts(
    result: dict[str, Any],
    *,
    output_dir: str | Path = DEFAULT_AUDIT_OUTPUT_DIR,
    candidate_inputs: list[dict[str, Any]] | None = None,
    human_reviews: dict[str, dict[str, Any]] | None = None,
    artifact_paths: dict[str, str] | None = None,
    reviewer: str = "Pending",
    audit_status: str = "pending_human_signoff",
    commit: str | None = None,
    update_report_path: str | Path | None = None,
    require_human_signoff: bool = False,
) -> dict[str, str]:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    if candidate_inputs is None:
        candidate_inputs = [
            json.loads(line)
            for line in render_candidate_inputs_jsonl(result).splitlines()
            if line.strip()
        ]
    packet = build_diag150_audit_packet(
        result,
        candidate_inputs=candidate_inputs,
        human_reviews=human_reviews,
        artifact_paths=artifact_paths,
        reviewer=reviewer,
        audit_status=audit_status,
        commit=commit,
    )
    if human_reviews is not None:
        packet["status"] = (
            "human_signed_off"
            if all(_human_review_signed_off(case.get("human_review") or {}) for case in packet.get("cases") or [])
            else "human_review_incomplete"
        )
    validation = validate_diag150_audit_packet(
        packet,
        result=result,
        candidate_inputs=candidate_inputs,
        require_human_signoff=require_human_signoff,
    )
    packet_json_path = output_path / "diag150_audit_packet.json"
    packet_md_path = output_path / "diag150_audit_packet.md"
    review_template_path = output_path / "diag150_human_review_template.json"
    validation_path = output_path / "diag150_audit_validation.json"
    report_path = output_path / "AUDIT_REPORT.md"
    packet_json_path.write_text(json.dumps(packet, indent=2, sort_keys=True), encoding="utf-8")
    packet_md_path.write_text(render_audit_packet_markdown(packet), encoding="utf-8")
    review_template_path.write_text(json.dumps(build_human_review_template(packet), indent=2, sort_keys=True), encoding="utf-8")
    validation_path.write_text(json.dumps(validation, indent=2, sort_keys=True), encoding="utf-8")
    report = render_audit_report_markdown(packet, validation)
    report_path.write_text(report, encoding="utf-8")
    paths = {
        "audit_packet_json": str(packet_json_path),
        "audit_packet_md": str(packet_md_path),
        "human_review_template_json": str(review_template_path),
        "audit_validation_json": str(validation_path),
        "audit_report_md": str(report_path),
    }
    if update_report_path is not None:
        canonical_path = Path(update_report_path)
        canonical_path.write_text(report, encoding="utf-8")
        paths["canonical_audit_report_md"] = str(canonical_path)
    return paths


def write_diag150_release_bundle(
    *,
    output_dir: str | Path = DEFAULT_AUDIT_OUTPUT_DIR,
    bundle_dir: str | Path = DEFAULT_RELEASE_BUNDLE_DIR,
    review_file: str | Path | None = None,
    require_human_signoff: bool = False,
) -> dict[str, str]:
    source_dir = Path(output_dir)
    bundle_path = Path(bundle_dir)
    bundle_path.mkdir(parents=True, exist_ok=True)
    validation_path = source_dir / "diag150_audit_validation.json"
    packet_path = source_dir / "diag150_audit_packet.json"
    if not validation_path.exists():
        raise FileNotFoundError("Missing audit validation artifact: %s" % validation_path)
    if not packet_path.exists():
        raise FileNotFoundError("Missing audit packet artifact: %s" % packet_path)

    validation = json.loads(validation_path.read_text(encoding="utf-8"))
    packet = json.loads(packet_path.read_text(encoding="utf-8"))
    artifacts = []
    missing_required = []
    for name in RELEASE_BUNDLE_ARTIFACTS:
        source = source_dir / name
        if not source.exists():
            missing_required.append(name)
            continue
        artifacts.append(_copy_bundle_artifact(source, bundle_path / name, required=True))
    if review_file is not None:
        review_source = Path(review_file)
        if review_source.exists():
            artifacts.append(_copy_bundle_artifact(review_source, bundle_path / "diag150_human_review_signoff.json", required=True))
        else:
            missing_required.append(str(review_source))
    for name in OPTIONAL_RELEASE_BUNDLE_ARTIFACTS:
        source = source_dir / name
        if source.exists():
            artifacts.append(_copy_bundle_artifact(source, bundle_path / name, required=False))

    human_signoff_complete = _validation_check_passed(validation, "independent_human_signoff_complete")
    if missing_required:
        bundle_status = "validation_failed"
    elif validation.get("status") != "passed":
        bundle_status = "validation_failed"
    elif human_signoff_complete:
        bundle_status = "freeze_ready"
    else:
        bundle_status = "review_pending"
    if require_human_signoff and not human_signoff_complete:
        bundle_status = "validation_failed"

    manifest = {
        "benchmark": "ContextTrace-Diag-150",
        "bundle_version": 1,
        "bundle_status": bundle_status,
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "commit": packet.get("commit") or current_git_commit(),
        "case_set": packet.get("case_set"),
        "case_count": packet.get("case_count"),
        "source_output_dir": str(source_dir),
        "require_human_signoff": bool(require_human_signoff),
        "human_signoff_complete": bool(human_signoff_complete),
        "validation_status": validation.get("status"),
        "validation_summary": validation.get("summary") or {},
        "missing_required_artifacts": missing_required,
        "summary": packet.get("summary") or {},
        "confidence_intervals": packet.get("confidence_intervals") or {},
        "artifacts": artifacts,
        "claim_policy": _bundle_claim_policy(bundle_status),
    }
    manifest_path = bundle_path / "manifest.json"
    readme_path = bundle_path / "README.md"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    readme_path.write_text(render_release_bundle_readme(manifest), encoding="utf-8")
    return {
        "bundle_dir": str(bundle_path),
        "manifest_json": str(manifest_path),
        "readme_md": str(readme_path),
    }


def render_release_bundle_readme(manifest: dict[str, Any]) -> str:
    status = manifest.get("bundle_status")
    lines = [
        "# ContextTrace-Diag-150 Release Bundle",
        "",
        "Status: `%s`" % status,
        "Commit: `%s`" % manifest.get("commit"),
        "Case set: `%s`" % manifest.get("case_set"),
        "Cases: `%s`" % manifest.get("case_count"),
        "Generated: `%s`" % manifest.get("generated_at"),
        "",
        "## Claim Policy",
        "",
        _bundle_claim_policy(str(status)),
        "",
        "## Headline Metrics",
        "",
        "| Metric | Value |",
        "| --- | ---: |",
        "| Failure macro-F1 | %s |" % _manifest_metric(manifest, "failure_label_macro_f1"),
        "| Claim-verdict macro-F1 | %s |" % _manifest_metric(manifest, "claim_verdict_macro_f1"),
        "| Root-cause accuracy | %s |" % _manifest_metric(manifest, "root_cause_accuracy"),
        "| Citation error F1 | %s |" % _manifest_metric(manifest, "citation_error_f1"),
        "| Evidence span overlap | %s |" % _manifest_metric(manifest, "evidence_span_overlap"),
        "| Dangerous false-green rate | %s |" % _manifest_metric(manifest, "dangerous_false_green_rate"),
        "",
        "## Validation",
        "",
        "- Validation status: `%s`" % manifest.get("validation_status"),
        "- Human signoff complete: `%s`" % manifest.get("human_signoff_complete"),
        "- Required human signoff: `%s`" % manifest.get("require_human_signoff"),
        "- Missing required artifacts: `%s`" % len(manifest.get("missing_required_artifacts") or []),
        "",
        "## Artifacts",
        "",
        "| File | Bytes | SHA256 | Required |",
        "| --- | ---: | --- | --- |",
    ]
    for artifact in manifest.get("artifacts") or []:
        lines.append(
            "| `%s` | %s | `%s` | `%s` |"
            % (
                artifact.get("path"),
                artifact.get("bytes"),
                artifact.get("sha256"),
                artifact.get("required"),
            )
        )
    lines.extend(
        [
            "",
            "## Reproduce",
            "",
            "```bash",
            "python benchmarks/contexttrace_bench/run_contexttrace.py \\",
            "  --mode semantic \\",
            "  --case-set public_holdout \\",
            "  --no-generated-cases \\",
            "  --output-dir benchmarks/contexttrace_bench/out/public_holdout",
            "python benchmarks/contexttrace_bench/audit_diag150.py \\",
            "  --output-dir benchmarks/contexttrace_bench/out/public_holdout \\",
            "  --bundle-dir benchmarks/contexttrace_bench/out/diag150_release_bundle",
            "```",
            "",
        ]
    )
    return "\n".join(lines)


def _copy_bundle_artifact(source: Path, destination: Path, *, required: bool) -> dict[str, Any]:
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    return {
        "name": source.name,
        "path": destination.name,
        "source_path": str(source),
        "bytes": destination.stat().st_size,
        "sha256": _sha256_file(destination),
        "required": bool(required),
    }


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _bundle_claim_policy(status: str) -> str:
    if status == "freeze_ready":
        return (
            "This bundle passed automated validation and independent human signoff. "
            "It can support frozen ContextTrace-Diag-150 split language, but broad SOTA "
            "claims still require external dataset validation and competitor rows."
        )
    if status == "review_pending":
        return (
            "This bundle passed automated validation, but independent human signoff is pending. "
            "Use it for reviewer handoff and reproducibility, not frozen-split or broad SOTA claims."
        )
    return (
        "This bundle did not pass the required validation gates. Do not use it for public claims."
    )


def _manifest_metric(manifest: dict[str, Any], key: str) -> str:
    value = (manifest.get("summary") or {}).get(key)
    if isinstance(value, float):
        return "%.3f" % value
    return str(value)


def current_git_commit() -> str:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return "unknown"
    return completed.stdout.strip() or "unknown"


def _normalized_human_review(review: dict[str, Any]) -> dict[str, Any]:
    normalized = {
        "status": str(review.get("status") or "pending"),
        "source_url_opened": review.get("source_url_opened"),
        "context_fair": review.get("context_fair"),
        "label_correct": review.get("label_correct"),
        "evidence_span_minimal": review.get("evidence_span_minimal"),
        "reviewer": str(review.get("reviewer") or ""),
        "reviewed_at": str(review.get("reviewed_at") or ""),
        "notes": str(review.get("notes") or ""),
    }
    return normalized


def _human_review_signed_off(review: dict[str, Any]) -> bool:
    if str(review.get("status") or "") != "signed_off":
        return False
    if not str(review.get("reviewer") or "").strip():
        return False
    if not str(review.get("reviewed_at") or "").strip():
        return False
    return all(review.get(field) is True for field in HUMAN_SIGNOFF_BOOLEAN_FIELDS)


def _human_review_blocked(review: dict[str, Any]) -> bool:
    status = str(review.get("status") or "")
    if status in HUMAN_REVIEW_BLOCKING_STATUSES:
        return True
    return any(review.get(field) is False for field in HUMAN_SIGNOFF_BOOLEAN_FIELDS)


def _validation_check_passed(validation: dict[str, Any], name: str) -> bool:
    for check in validation.get("checks") or []:
        if check.get("name") == name:
            return check.get("status") == "passed"
    return False


def _audit_case(row: dict[str, Any]) -> dict[str, Any]:
    trace = row.get("trace") if isinstance(row.get("trace"), dict) else {}
    contexts = [_audit_context(context) for context in trace.get("contexts") or [] if isinstance(context, dict)]
    source_family = _source_family(row.get("source") or "")
    if contexts:
        source_family = contexts[0].get("source_family") or source_family
    return {
        "id": str(row.get("id") or ""),
        "source": str(row.get("source") or ""),
        "source_family": source_family,
        "generated": bool(row.get("generated")),
        "variant_type": row.get("variant_type"),
        "base_case_id": row.get("base_case_id"),
        "query": trace.get("query"),
        "answer": trace.get("answer"),
        "expected_labels": [str(label) for label in row.get("expected") or []],
        "predicted_labels": [str(label) for label in row.get("predicted") or []],
        "expected_primary_root_cause": str(row.get("expected_primary_root_cause") or ""),
        "predicted_primary_root_cause": str(row.get("predicted_primary_root_cause") or ""),
        "expected_citation_statuses": [str(item) for item in row.get("expected_citation_statuses") or []],
        "predicted_citation_statuses": [str(item) for item in row.get("predicted_citation_statuses") or []],
        "expected_evidence_spans": [str(item) for item in row.get("expected_evidence_spans") or []],
        "predicted_evidence_spans": [str(item) for item in row.get("predicted_evidence_spans") or []],
        "evidence_span_overlap": row.get("evidence_span_overlap"),
        "benchmark_pass": bool(row.get("benchmark_pass")),
        "contexts": contexts,
        "citations": trace.get("citations") or [],
        "human_review": {
            "status": "pending",
            "source_url_opened": None,
            "context_fair": None,
            "label_correct": None,
            "evidence_span_minimal": None,
            "reviewer": "",
            "reviewed_at": "",
            "notes": "",
        },
    }


def _audit_context(context: dict[str, Any]) -> dict[str, Any]:
    metadata = context.get("metadata") if isinstance(context.get("metadata"), dict) else {}
    source_url = str(metadata.get("source_url") or metadata.get("url") or "")
    source = str(metadata.get("source") or context.get("source") or source_url)
    return {
        "id": str(context.get("id") or ""),
        "source": source,
        "source_url": source_url,
        "source_family": _source_family(source_url or source),
        "text": str(context.get("text") or ""),
    }


def _case_markdown(index: int, case: dict[str, Any]) -> list[str]:
    source_urls = sorted({str(context.get("source_url") or "") for context in case.get("contexts") or [] if context.get("source_url")})
    lines = [
        "### Case %s: `%s`" % (index, case.get("id")),
        "",
        "- Source family: `%s`" % case.get("source_family"),
        "- Expected labels: %s" % ", ".join("`%s`" % label for label in case.get("expected_labels") or []),
        "- Expected root cause: `%s`" % case.get("expected_primary_root_cause"),
        "- Benchmark pass: `%s`" % case.get("benchmark_pass"),
        "- Source URLs: %s" % (", ".join(source_urls) if source_urls else "`missing`"),
        "",
        "**Query:** %s" % _one_line(case.get("query")),
        "",
        "**Answer:** %s" % _one_line(case.get("answer")),
        "",
        "**Expected Evidence Spans**",
        "",
    ]
    for span in case.get("expected_evidence_spans") or ["No expected evidence span recorded."]:
        lines.append("- %s" % _one_line(span))
    lines.extend(
        [
            "",
            "**Reviewer Signoff**",
            "",
            "- [ ] Source URL opens",
            "- [ ] Context excerpt is fair to source",
            "- [ ] Expected labels are correct",
            "- [ ] Evidence span is minimal and sufficient",
            "- Reviewer:",
            "- Reviewed at:",
            "- Notes:",
            "",
        ]
    )
    return lines


def _add_check(checks: list[dict[str, Any]], name: str, passed: bool, severity: str, details: Any) -> None:
    checks.append(
        {
            "name": name,
            "severity": severity,
            "status": "passed" if passed else "failed",
            "details": details,
        }
    )


def _candidate_leakage_paths(value: Any, *, path: str) -> list[str]:
    leaks = []
    if isinstance(value, dict):
        for key, nested in value.items():
            key_text = str(key)
            lowered = key_text.lower()
            nested_path = "%s.%s" % (path, key_text)
            if lowered in LEAKAGE_KEYS or lowered.startswith("expected_") or lowered.startswith("predicted_"):
                leaks.append(nested_path)
            leaks.extend(_candidate_leakage_paths(nested, path=nested_path))
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            leaks.extend(_candidate_leakage_paths(nested, path="%s[%s]" % (path, index)))
    return leaks


def _duplicates(values: list[str]) -> list[str]:
    counts = Counter(values)
    return sorted(value for value, count in counts.items() if count > 1)


def _label_set_key(labels: list[Any]) -> str:
    return " + ".join(sorted(str(label) for label in labels if str(label))) or "none"


def _source_family(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return "unknown"
    parsed = urlparse(text if "://" in text else "https://%s" % text)
    host = parsed.netloc or parsed.path.split("/")[0]
    host = host.lower()
    if host.startswith("www."):
        host = host[4:]
    return host or "unknown"


def _normalize_text(value: str) -> str:
    return " ".join(str(value or "").lower().split())


def _metric(packet: dict[str, Any], key: str) -> str:
    value = (packet.get("summary") or {}).get(key)
    if isinstance(value, float):
        return "%.3f" % value
    return str(value)


def _markdown_detail(value: Any) -> str:
    if value in (None, "", [], {}):
        return ""
    text = json.dumps(value, sort_keys=True) if not isinstance(value, str) else value
    text = text.replace("|", "\\|").replace("\n", " ")
    return "`%s`" % text[:240]


def _one_line(value: Any) -> str:
    return " ".join(str(value or "").split())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate and validate the ContextTrace-Diag-150 audit packet.")
    parser.add_argument("--output-dir", default=str(DEFAULT_AUDIT_OUTPUT_DIR))
    parser.add_argument("--results", default=None, help="Existing contexttrace_bench_results.json path.")
    parser.add_argument("--candidate-inputs", default=None, help="Existing candidate_inputs.jsonl path.")
    parser.add_argument("--review-file", default=None, help="Completed diag150_human_review_template.json with independent signoff fields filled.")
    parser.add_argument("--require-human-signoff", action="store_true", help="Fail validation unless every case has complete independent signoff.")
    parser.add_argument("--bundle-dir", default=None, help="Write a Diag-150 release bundle with copied artifacts, checksums, manifest, and README.")
    parser.add_argument("--regenerate", action="store_true", help="Regenerate the public_holdout benchmark artifacts before auditing.")
    parser.add_argument("--bootstrap-samples", default=400, type=int, help="Bootstrap samples when --regenerate is used.")
    parser.add_argument("--reviewer", default="Pending")
    parser.add_argument("--audit-status", default="pending_human_signoff")
    parser.add_argument("--update-report", action="store_true", help="Update benchmarks/contexttrace_bench/AUDIT_REPORT.md.")
    args = parser.parse_args(argv)

    output_dir = Path(args.output_dir)
    artifact_paths: dict[str, str] = {}
    if args.regenerate:
        result = run_contexttrace_benchmark(
            mode="semantic",
            case_set="public_holdout",
            include_generated_cases=False,
            bootstrap_samples=args.bootstrap_samples,
        )
        artifact_paths = write_benchmark_outputs(result, output_dir=output_dir)
    else:
        results_path = Path(args.results) if args.results else output_dir / "contexttrace_bench_results.json"
        result = load_benchmark_result(results_path)
        artifact_paths["json"] = str(results_path)

    candidate_path = Path(args.candidate_inputs) if args.candidate_inputs else output_dir / "candidate_inputs.jsonl"
    candidate_inputs = load_candidate_inputs(candidate_path) if candidate_path.exists() else None
    if candidate_path.exists():
        artifact_paths["candidate_inputs_jsonl"] = str(candidate_path)
    human_reviews = None
    if args.review_file:
        review_path = Path(args.review_file)
        human_reviews = load_human_review_file(review_path)
        artifact_paths["human_review_file"] = str(review_path)

    paths = write_diag150_audit_artifacts(
        result,
        output_dir=output_dir,
        candidate_inputs=candidate_inputs,
        human_reviews=human_reviews,
        artifact_paths=artifact_paths,
        reviewer=args.reviewer,
        audit_status=args.audit_status,
        require_human_signoff=args.require_human_signoff,
        update_report_path=DEFAULT_CANONICAL_REPORT_PATH if args.update_report else None,
    )
    validation = json.loads(Path(paths["audit_validation_json"]).read_text(encoding="utf-8"))
    print("Audit packet: %s" % paths["audit_packet_md"])
    print("Validation: %s" % paths["audit_validation_json"])
    bundle_paths = None
    if args.bundle_dir:
        bundle_paths = write_diag150_release_bundle(
            output_dir=output_dir,
            bundle_dir=args.bundle_dir,
            review_file=args.review_file,
            require_human_signoff=args.require_human_signoff,
        )
        print("Release bundle: %s" % bundle_paths["bundle_dir"])
        print("Bundle manifest: %s" % bundle_paths["manifest_json"])
    print("Status: %s" % validation.get("status"))
    return 1 if validation.get("status") != "passed" else 0


if __name__ == "__main__":
    raise SystemExit(main())
