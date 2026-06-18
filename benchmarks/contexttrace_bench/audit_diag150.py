from __future__ import annotations

import argparse
import json
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


def build_diag150_audit_packet(
    result: dict[str, Any],
    *,
    candidate_inputs: list[dict[str, Any]] | None = None,
    artifact_paths: dict[str, str] | None = None,
    reviewer: str = "Pending",
    audit_status: str = "pending_human_signoff",
    commit: str | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    rows = [row for row in result.get("rows") or [] if isinstance(row, dict)]
    cases = [_audit_case(row) for row in rows]
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
        if (case.get("human_review") or {}).get("status") == "signed_off"
    ]
    _add_check(
        checks,
        "independent_human_signoff_pending",
        len(signed_cases) == len(cases),
        "warning",
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
    artifact_paths: dict[str, str] | None = None,
    reviewer: str = "Pending",
    audit_status: str = "pending_human_signoff",
    commit: str | None = None,
    update_report_path: str | Path | None = None,
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
        artifact_paths=artifact_paths,
        reviewer=reviewer,
        audit_status=audit_status,
        commit=commit,
    )
    validation = validate_diag150_audit_packet(packet, result=result, candidate_inputs=candidate_inputs)
    packet_json_path = output_path / "diag150_audit_packet.json"
    packet_md_path = output_path / "diag150_audit_packet.md"
    validation_path = output_path / "diag150_audit_validation.json"
    report_path = output_path / "AUDIT_REPORT.md"
    packet_json_path.write_text(json.dumps(packet, indent=2, sort_keys=True), encoding="utf-8")
    packet_md_path.write_text(render_audit_packet_markdown(packet), encoding="utf-8")
    validation_path.write_text(json.dumps(validation, indent=2, sort_keys=True), encoding="utf-8")
    report = render_audit_report_markdown(packet, validation)
    report_path.write_text(report, encoding="utf-8")
    paths = {
        "audit_packet_json": str(packet_json_path),
        "audit_packet_md": str(packet_md_path),
        "audit_validation_json": str(validation_path),
        "audit_report_md": str(report_path),
    }
    if update_report_path is not None:
        canonical_path = Path(update_report_path)
        canonical_path.write_text(report, encoding="utf-8")
        paths["canonical_audit_report_md"] = str(canonical_path)
    return paths


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

    paths = write_diag150_audit_artifacts(
        result,
        output_dir=output_dir,
        candidate_inputs=candidate_inputs,
        artifact_paths=artifact_paths,
        reviewer=args.reviewer,
        audit_status=args.audit_status,
        update_report_path=DEFAULT_CANONICAL_REPORT_PATH if args.update_report else None,
    )
    validation = json.loads(Path(paths["audit_validation_json"]).read_text(encoding="utf-8"))
    print("Audit packet: %s" % paths["audit_packet_md"])
    print("Validation: %s" % paths["audit_validation_json"])
    print("Status: %s" % validation.get("status"))
    return 1 if validation.get("status") != "passed" else 0


if __name__ == "__main__":
    raise SystemExit(main())
