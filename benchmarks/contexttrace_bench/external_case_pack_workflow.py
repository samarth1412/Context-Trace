from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:  # pragma: no cover - exercised when run as a script from this directory
    from benchmarks.contexttrace_bench.external_case_pack import (
        adapt_external_rows,
        load_rows,
        write_case_pack,
    )
    from benchmarks.contexttrace_bench.run_contexttrace import (
        score_candidate_file,
        run_contexttrace_case_pack,
        write_benchmark_outputs,
    )
except ModuleNotFoundError:  # pragma: no cover
    from external_case_pack import adapt_external_rows, load_rows, write_case_pack  # type: ignore
    from run_contexttrace import (  # type: ignore
        score_candidate_file,
        run_contexttrace_case_pack,
        write_benchmark_outputs,
    )


DEFAULT_OUTPUT_DIR = Path(__file__).with_name("out") / "external_case_pack"
DEFAULT_BUNDLE_DIR = Path(__file__).with_name("out") / "external_case_pack_bundle"
DEFAULT_CANDIDATE_FILENAMES = (
    "openai_diagnostic_judge_predictions.json",
    "ragas_predictions.json",
    "deepeval_predictions.json",
    "ragchecker_predictions.json",
    "local_judge_predictions.json",
    "phoenix_predictions.json",
    "trulens_predictions.json",
)
REVIEWED_STATUSES = {"reviewed", "accepted", "approved"}
BUNDLE_BASE_ARTIFACTS = (
    "external_workflow_manifest.json",
    "external_case_pack.json",
    "external_review_template.jsonl",
    "external_review_packet.md",
)
BUNDLE_REVIEW_ARTIFACTS = (
    "external_review_validation.json",
    "external_reviewed_case_pack.json",
)
BUNDLE_SCORED_ARTIFACTS = (
    "contexttrace_bench_results.json",
    "results.md",
    "leaderboard.md",
    "report.html",
    "error_analysis.json",
    "error_analysis.md",
    "candidate_inputs.jsonl",
)


def run_external_case_pack_workflow(
    *,
    input_path: str | Path,
    dataset: str,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    bundle_dir: str | Path = DEFAULT_BUNDLE_DIR,
    source_name: str | None = None,
    id_field: str = "id",
    query_field: str = "query",
    answer_field: str = "answer",
    contexts_field: str = "contexts",
    label_field: str = "expected_label",
    root_cause_field: str = "expected_primary_root_cause",
    evidence_spans_field: str = "expected_evidence_spans",
    limit: int | None = None,
    sample_size: int | None = None,
    sample_seed: int = 13,
    stratify_by: list[str] | None = None,
    review_path: str | Path | None = None,
    review_kind: str = "assisted",
    require_reviewed: bool = True,
    require_evidence_spans: bool = False,
    mode: str = "semantic",
    bootstrap_samples: int = 100,
    candidate_paths: list[str | Path] | None = None,
    auto_candidates: bool = True,
    skip_score: bool = False,
) -> dict[str, Any]:
    output_path = Path(output_dir)
    bundle_path = Path(bundle_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    started_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()

    rows = load_rows(input_path)
    case_pack = adapt_external_rows(
        rows,
        dataset=dataset,
        source_name=source_name,
        id_field=id_field,
        query_field=query_field,
        answer_field=answer_field,
        contexts_field=contexts_field,
        label_field=label_field,
        root_cause_field=root_cause_field,
        evidence_spans_field=evidence_spans_field,
        limit=limit,
        sample_size=sample_size,
        sample_seed=sample_seed,
        stratify_by=stratify_by or [],
    )
    case_pack_path = output_path / "external_case_pack.json"
    write_case_pack(case_pack, case_pack_path)

    review_rows = build_external_review_template(case_pack)
    review_template_path = output_path / "external_review_template.jsonl"
    review_packet_path = output_path / "external_review_packet.md"
    write_jsonl(review_rows, review_template_path)
    write_text(
        render_external_review_packet(review_rows, dataset=dataset),
        review_packet_path,
    )

    manifest: dict[str, Any] = {
        "workflow": "generic_external_case_pack_workflow",
        "started_at": started_at,
        "status": "needs_review",
        "dataset": dataset,
        "inputs": {
            "input_path": str(input_path),
            "input_sha256": _sha256_file(Path(input_path)) if Path(input_path).exists() else "",
            "review_path": str(review_path) if review_path else "",
        },
        "options": {
            "source_name": source_name or "",
            "id_field": id_field,
            "query_field": query_field,
            "answer_field": answer_field,
            "contexts_field": contexts_field,
            "label_field": label_field,
            "root_cause_field": root_cause_field,
            "evidence_spans_field": evidence_spans_field,
            "limit": limit,
            "sample_size": sample_size,
            "sample_seed": sample_seed,
            "stratify_by": stratify_by or [],
            "review_kind": review_kind,
            "require_reviewed": require_reviewed,
            "require_evidence_spans": require_evidence_spans,
            "mode": mode,
            "bootstrap_samples": bootstrap_samples,
            "skip_score": skip_score,
        },
        "artifacts": {
            "case_pack": str(case_pack_path),
            "review_template": str(review_template_path),
            "review_packet": str(review_packet_path),
            "manifest": str(output_path / "external_workflow_manifest.json"),
        },
        "case_pack": {
            "cases": len(case_pack.get("cases") or []),
            "eligible_cases": (case_pack.get("stats") or {}).get("eligible_cases"),
            "skipped_missing_answer": (case_pack.get("stats") or {}).get("skipped_missing_answer"),
            "skipped_missing_context": (case_pack.get("stats") or {}).get("skipped_missing_context"),
            "sampling": (case_pack.get("stats") or {}).get("sampling") or {},
        },
        "review": {
            "review_rows": len(review_rows),
            "requires_independent_review": True,
        },
    }

    case_pack_to_score = case_pack_path
    if review_path:
        supplied_review_rows = load_jsonl(review_path)
        validation_report = validate_external_review(
            case_pack,
            supplied_review_rows,
            require_reviewed=require_reviewed,
            require_evidence_spans=require_evidence_spans,
        )
        validation_path = output_path / "external_review_validation.json"
        write_json(validation_report, validation_path)
        manifest["artifacts"]["review_validation"] = str(validation_path)
        manifest["review"].update(
            {
                "reviewed_rows": validation_report["reviewed_rows"],
                "valid": validation_report["valid"],
                "errors": len(validation_report["errors"]),
                "warnings": len(validation_report["warnings"]),
                "source_span_rows": validation_report["source_span_rows"],
            }
        )
        if not validation_report["valid"]:
            manifest["status"] = "invalid_review"
        else:
            reviewed_case_pack = apply_external_review(
                case_pack,
                supplied_review_rows,
                review_file=review_path,
            )
            reviewed_case_pack_path = output_path / "external_reviewed_case_pack.json"
            write_json(reviewed_case_pack, reviewed_case_pack_path)
            case_pack_to_score = reviewed_case_pack_path
            manifest["status"] = "review_validated"
            manifest["artifacts"]["reviewed_case_pack"] = str(reviewed_case_pack_path)

    baseline_results: list[dict[str, Any]] = []
    candidate_files: list[Path] = []
    if not skip_score and manifest["status"] != "invalid_review":
        score_output_dir = output_path / "scored"
        score_result = run_contexttrace_case_pack(
            case_pack_path=case_pack_to_score,
            mode=mode,
            bootstrap_samples=bootstrap_samples,
        )
        candidate_files = _candidate_files(output_path, candidate_paths or [], auto_candidates=auto_candidates)
        baseline_results = [score_candidate_file(score_result, path) for path in candidate_files]
        score_paths = write_benchmark_outputs(
            score_result,
            output_dir=score_output_dir,
            baseline_results=baseline_results or None,
        )
        manifest["status"] = "scored" if review_path else "scored_review_pending"
        manifest["artifacts"]["score_output_dir"] = str(score_output_dir)
        manifest["artifacts"]["score_paths"] = dict(score_paths)
        manifest["score"] = {
            "summary": dict(score_result.get("summary") or {}),
            "case_set": score_result.get("case_set"),
            "case_pack_dataset": score_result.get("case_pack_dataset"),
            "baselines": len(baseline_results),
        }

    write_json(manifest, output_path / "external_workflow_manifest.json")
    release_status = _release_status(manifest, review_kind=review_kind)
    bundle_paths = write_external_release_bundle(
        output_dir=output_path,
        bundle_dir=bundle_path,
        dataset=dataset,
        manifest=manifest,
        release_status=release_status,
        review_path=review_path,
        review_kind=review_kind,
        require_reviewed=require_reviewed,
        require_evidence_spans=require_evidence_spans,
        candidate_files=candidate_files,
    )
    return {
        "status": release_status,
        "workflow_status": manifest.get("status"),
        "case_count": (manifest.get("case_pack") or {}).get("cases"),
        "review_rows": (manifest.get("review") or {}).get("review_rows"),
        "review_valid": (manifest.get("review") or {}).get("valid"),
        "baseline_count": len(baseline_results),
        "candidate_files": [str(path) for path in candidate_files],
        "workflow_manifest": manifest,
        "bundle_paths": bundle_paths,
    }


def build_external_review_template(case_pack: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for case in case_pack.get("cases") or []:
        if not isinstance(case, dict):
            continue
        rows.append(
            {
                "case_id": str(case.get("id") or ""),
                "review_status": "needs_review",
                "reviewer": "",
                "reviewed_at": "",
                "review_notes": "",
                "context_fair": None,
                "label_correct": None,
                "root_cause_correct": None,
                "evidence_span_minimal": None,
                "source": case.get("source"),
                "query": case.get("query"),
                "answer": case.get("answer"),
                "expected_labels": list(case.get("expected_labels") or []),
                "expected_primary_root_cause": case.get("expected_primary_root_cause"),
                "expected_evidence_spans": list(case.get("expected_evidence_spans") or []),
                "expected_verdict_counts": dict(case.get("expected_verdict_counts") or {}),
                "source_contexts": [
                    {
                        "id": context.get("id"),
                        "text": context.get("text"),
                        "metadata": context.get("metadata") or {},
                    }
                    for context in case.get("contexts") or []
                    if isinstance(context, dict)
                ],
                "corrected_expected_labels": [],
                "corrected_primary_root_cause": "",
                "corrected_expected_evidence_spans": [],
                "corrected_expected_verdict_counts": {},
            }
        )
    return rows


def render_external_review_packet(
    review_rows: list[dict[str, Any]],
    *,
    dataset: str,
    generated_at: str | None = None,
    context_char_limit: int = 6000,
) -> str:
    generated = generated_at or datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    lines = [
        "# %s External Dataset Review Packet" % _markdown_text(dataset),
        "",
        "- Generated at: `%s`" % _markdown_text(generated),
        "- Review rows: `%s`" % len(review_rows),
        "",
        "## Reviewer Instructions",
        "",
        "Inspect each query, answer, source context, and expected label. Mark "
        "`review_status` as `reviewed`, `accepted`, or `approved` only after direct inspection.",
        "",
        "Set `context_fair`, `label_correct`, and `root_cause_correct` to true when the row is usable as-is. "
        "Use corrected fields when the adapted label, root cause, evidence span, or verdict counts need changes.",
        "",
        "For source-span claims, keep only minimal source text in `corrected_expected_evidence_spans` or leave "
        "the existing spans if they are already minimal.",
        "",
    ]
    for index, row in enumerate(review_rows, start=1):
        lines.extend(_review_packet_case(row, index=index, context_char_limit=context_char_limit))
    return "\n".join(lines).rstrip() + "\n"


def validate_external_review(
    case_pack: dict[str, Any],
    review_rows: list[dict[str, Any]],
    *,
    require_reviewed: bool = False,
    require_evidence_spans: bool = False,
) -> dict[str, Any]:
    cases_by_id = {
        str(case.get("id") or ""): case
        for case in case_pack.get("cases") or []
        if isinstance(case, dict) and case.get("id")
    }
    required_case_ids = set(cases_by_id)
    seen_case_ids: set[str] = set()
    errors: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    row_results: list[dict[str, Any]] = []

    for index, row in enumerate(review_rows, start=1):
        if not isinstance(row, dict):
            errors.append(_validation_item("", "row_type", "Review row %s is not a JSON object." % index))
            continue
        case_id = str(row.get("case_id") or row.get("id") or "")
        row_errors: list[str] = []
        row_warnings: list[str] = []
        if not case_id:
            row_errors.append("Missing case_id.")
        elif case_id in seen_case_ids:
            row_errors.append("Duplicate review row for case_id %s." % case_id)
        else:
            seen_case_ids.add(case_id)

        case = cases_by_id.get(case_id)
        if case_id and case is None:
            row_errors.append("Review row case_id is not present in the case pack.")

        status = str(row.get("review_status") or "").strip().lower()
        reviewed = status in REVIEWED_STATUSES
        if require_reviewed and not reviewed:
            row_errors.append("Review status must be one of %s." % ", ".join(sorted(REVIEWED_STATUSES)))
        if reviewed:
            if not str(row.get("reviewer") or "").strip():
                row_errors.append("Reviewed row must include reviewer.")
            if not str(row.get("reviewed_at") or "").strip():
                row_errors.append("Reviewed row must include reviewed_at.")
            _validate_review_booleans(row, row_errors, row_warnings)

        spans = _review_evidence_spans(row, case)
        if reviewed and require_evidence_spans and not spans:
            row_errors.append("Reviewed row must include expected or corrected evidence spans.")
        if spans and case is not None:
            context_texts = _case_context_texts(case)
            for span in spans:
                if not _span_in_contexts(span, context_texts):
                    row_errors.append("Evidence span is not found in source contexts: %s" % span)

        for message in row_errors:
            errors.append(_validation_item(case_id, "row", message))
        for message in row_warnings:
            warnings.append(_validation_item(case_id, "row", message))

        row_results.append(
            {
                "case_id": case_id,
                "reviewed": reviewed,
                "evidence_span_count": len(spans),
                "error_count": len(row_errors),
                "warning_count": len(row_warnings),
            }
        )

    missing_required = sorted(required_case_ids - seen_case_ids)
    for case_id in missing_required:
        item = _validation_item(case_id, "missing_review", "Missing review row for external case.")
        if require_reviewed:
            errors.append(item)
        else:
            warnings.append(item)

    reviewed_rows = sum(1 for row in row_results if row["reviewed"])
    source_span_rows = sum(1 for row in row_results if row["evidence_span_count"] > 0)
    return {
        "valid": not errors,
        "review_rows": len(row_results),
        "reviewed_rows": reviewed_rows,
        "required_review_rows": len(required_case_ids),
        "missing_required_review_rows": missing_required,
        "source_span_rows": source_span_rows,
        "errors": errors,
        "warnings": warnings,
        "rows": row_results,
        "requirements": {
            "require_reviewed": require_reviewed,
            "require_evidence_spans": require_evidence_spans,
        },
    }


def apply_external_review(
    case_pack: dict[str, Any],
    review_rows: list[dict[str, Any]],
    *,
    review_file: str | Path | None = None,
) -> dict[str, Any]:
    reviews_by_case = {
        str(row.get("case_id") or row.get("id")): row
        for row in review_rows
        if isinstance(row, dict) and (row.get("case_id") or row.get("id"))
    }
    updated_cases = []
    reviewed_count = 0
    for case in case_pack.get("cases") or []:
        if not isinstance(case, dict):
            continue
        case_id = str(case.get("id") or "")
        review = reviews_by_case.get(case_id)
        if review is None:
            updated_cases.append(dict(case))
            continue
        reviewed = str(review.get("review_status") or "").strip().lower() in REVIEWED_STATUSES
        if not reviewed:
            updated_cases.append(dict(case))
            continue
        updated_cases.append(_case_with_external_review(case, review))
        reviewed_count += 1

    output = dict(case_pack)
    output["cases"] = updated_cases
    output["review"] = {
        "status": "reviewed" if reviewed_count == len(updated_cases) else "partial",
        "reviewed_cases": reviewed_count,
        "required_review_cases": len(updated_cases),
        "total_cases": len(updated_cases),
        "review_file": str(review_file) if review_file else "",
        "applied_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
    }
    limitations = [
        str(item)
        for item in output.get("limitations") or []
        if str(item).strip()
    ]
    limitations.append(
        "External labels and evidence spans include reviewer signoff metadata where supplied."
    )
    output["limitations"] = _dedupe(limitations)
    return output


def write_external_release_bundle(
    *,
    output_dir: str | Path,
    bundle_dir: str | Path,
    dataset: str,
    manifest: dict[str, Any],
    release_status: str,
    review_path: str | Path | None = None,
    review_kind: str = "assisted",
    require_reviewed: bool = True,
    require_evidence_spans: bool = False,
    candidate_files: list[Path] | None = None,
) -> dict[str, str]:
    output_path = Path(output_dir)
    bundle_path = Path(bundle_dir)
    bundle_path.mkdir(parents=True, exist_ok=True)
    artifacts: list[dict[str, Any]] = []
    missing_required: list[str] = []

    for name in BUNDLE_BASE_ARTIFACTS:
        _copy_if_present(
            output_path / name,
            bundle_path / name,
            bundle_path,
            artifacts,
            missing_required,
            required=True,
        )
    if review_path:
        _copy_if_present(
            Path(review_path),
            bundle_path / "external_review_signoff.jsonl",
            bundle_path,
            artifacts,
            missing_required,
            required=True,
        )
        for name in BUNDLE_REVIEW_ARTIFACTS:
            _copy_if_present(
                output_path / name,
                bundle_path / name,
                bundle_path,
                artifacts,
                missing_required,
                required=True,
            )
    if str(manifest.get("status") or "") in {"scored", "scored_review_pending"}:
        score_dir = output_path / "scored"
        for name in BUNDLE_SCORED_ARTIFACTS:
            _copy_if_present(
                score_dir / name,
                bundle_path / "scored" / name,
                bundle_path,
                artifacts,
                missing_required,
                required=True,
            )
    for candidate in candidate_files or []:
        _copy_if_present(
            candidate,
            bundle_path / "candidates" / candidate.name,
            bundle_path,
            artifacts,
            missing_required,
            required=False,
        )

    if missing_required:
        release_status = "validation_failed"
    bundle_manifest = {
        "dataset": dataset,
        "bundle_version": 1,
        "bundle_status": release_status,
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "workflow_status": manifest.get("status"),
        "case_count": (manifest.get("case_pack") or {}).get("cases"),
        "review": manifest.get("review") or {},
        "review_kind": review_kind,
        "require_reviewed": bool(require_reviewed),
        "require_evidence_spans": bool(require_evidence_spans),
        "score": manifest.get("score") or {},
        "missing_required_artifacts": missing_required,
        "artifacts": artifacts,
        "claim_policy": _claim_policy(release_status, dataset=dataset),
    }
    manifest_path = bundle_path / "manifest.json"
    readme_path = bundle_path / "README.md"
    manifest_path.write_text(json.dumps(bundle_manifest, indent=2, sort_keys=True), encoding="utf-8")
    readme_path.write_text(render_external_bundle_readme(bundle_manifest), encoding="utf-8")
    return {
        "bundle_dir": str(bundle_path),
        "manifest_json": str(manifest_path),
        "readme_md": str(readme_path),
    }


def render_external_bundle_readme(manifest: dict[str, Any]) -> str:
    score = manifest.get("score") or {}
    summary = score.get("summary") or {}
    lines = [
        "# %s External Case-Pack Bundle" % _markdown_text(manifest.get("dataset") or "External"),
        "",
        "Status: `%s`" % manifest.get("bundle_status"),
        "Workflow status: `%s`" % manifest.get("workflow_status"),
        "Cases: `%s`" % manifest.get("case_count"),
        "Review kind: `%s`" % manifest.get("review_kind"),
        "Generated: `%s`" % manifest.get("generated_at"),
        "",
        "## Claim Policy",
        "",
        _claim_policy(str(manifest.get("bundle_status") or ""), dataset=str(manifest.get("dataset") or "external")),
        "",
        "## Score Summary",
        "",
        "| Metric | Value |",
        "| --- | ---: |",
        "| Failure macro-F1 | %s |" % _metric(summary, "failure_label_macro_f1"),
        "| Root-cause accuracy | %s |" % _metric(summary, "root_cause_accuracy"),
        "| Citation error F1 | %s |" % _metric(summary, "citation_error_f1"),
        "| Evidence span overlap | %s |" % _metric(summary, "evidence_span_overlap"),
        "| Dangerous false-green rate | %s |" % _metric(summary, "dangerous_false_green_rate"),
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
    return "\n".join(lines) + "\n"


def render_workflow_summary(summary: dict[str, Any]) -> str:
    lines = [
        "Generic external case-pack workflow",
        "Status: %s" % summary.get("status"),
        "Workflow status: %s" % summary.get("workflow_status"),
        "Cases: %s" % summary.get("case_count"),
        "Review rows: %s" % summary.get("review_rows"),
        "Candidate rows scored: %s" % summary.get("baseline_count"),
        "Bundle: %s" % ((summary.get("bundle_paths") or {}).get("bundle_dir")),
        "Manifest: %s" % ((summary.get("bundle_paths") or {}).get("manifest_json")),
    ]
    candidates = summary.get("candidate_files") or []
    if candidates:
        lines.append("Candidate files:")
        lines.extend("- %s" % path for path in candidates)
    return "\n".join(lines)


def load_jsonl(path: str | Path) -> list[dict[str, Any]]:
    rows = []
    for line in Path(path).read_text(encoding="utf-8-sig").splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        if isinstance(item, dict):
            rows.append(item)
    return rows


def write_jsonl(rows: list[dict[str, Any]], path: str | Path) -> str:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        "\n".join(json.dumps(row, sort_keys=True) for row in rows) + ("\n" if rows else ""),
        encoding="utf-8",
    )
    return str(output_path)


def write_json(payload: dict[str, Any], path: str | Path) -> str:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return str(output_path)


def write_text(payload: str, path: str | Path) -> str:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(payload, encoding="utf-8")
    return str(output_path)


def _review_packet_case(row: dict[str, Any], *, index: int, context_char_limit: int) -> list[str]:
    lines = [
        "## %s. `%s`" % (index, _markdown_text(row.get("case_id") or "")),
        "",
        "- Source: `%s`" % _markdown_text(row.get("source") or ""),
        "- Expected labels: `%s`" % _markdown_text(", ".join(row.get("expected_labels") or [])),
        "- Expected root cause: `%s`" % _markdown_text(row.get("expected_primary_root_cause") or ""),
        "",
        "Query:",
        "",
        "> %s" % _markdown_quote(row.get("query") or ""),
        "",
        "Answer:",
        "",
        "> %s" % _markdown_quote(row.get("answer") or ""),
        "",
        "Contexts:",
        "",
    ]
    for context in row.get("source_contexts") or []:
        text = _truncate(str(context.get("text") or ""), context_char_limit)
        lines.extend(
            [
                "- Context `%s`:" % _markdown_text(context.get("id") or ""),
                "",
                "```text",
                text,
                "```",
                "",
            ]
        )
    return lines


def _validate_review_booleans(row: dict[str, Any], errors: list[str], warnings: list[str]) -> None:
    if row.get("context_fair") is not True:
        errors.append("Reviewed row must set context_fair to true.")
    if row.get("label_correct") is not True and not _string_list(row.get("corrected_expected_labels")):
        errors.append("Reviewed row must confirm label_correct or provide corrected_expected_labels.")
    if row.get("root_cause_correct") is not True and not str(row.get("corrected_primary_root_cause") or "").strip():
        errors.append("Reviewed row must confirm root_cause_correct or provide corrected_primary_root_cause.")
    if row.get("label_correct") is False:
        warnings.append("Reviewed row uses corrected labels.")
    if row.get("root_cause_correct") is False:
        warnings.append("Reviewed row uses a corrected root cause.")


def _review_evidence_spans(row: dict[str, Any], case: dict[str, Any] | None) -> list[str]:
    corrected = _string_list(row.get("corrected_expected_evidence_spans"))
    if corrected:
        return corrected
    row_spans = _string_list(row.get("expected_evidence_spans"))
    if row_spans:
        return row_spans
    if case is None:
        return []
    return _string_list(case.get("expected_evidence_spans"))


def _case_with_external_review(case: dict[str, Any], review: dict[str, Any]) -> dict[str, Any]:
    updated = dict(case)
    labels = _string_list(review.get("corrected_expected_labels"))
    if labels:
        updated["expected_labels"] = sorted(set(labels))
    root_cause = str(review.get("corrected_primary_root_cause") or "").strip()
    if root_cause:
        updated["expected_primary_root_cause"] = root_cause
    spans = _string_list(review.get("corrected_expected_evidence_spans"))
    if spans:
        updated["expected_evidence_spans"] = spans
    counts = review.get("corrected_expected_verdict_counts")
    if isinstance(counts, dict) and any(int(value or 0) for value in counts.values()):
        updated["expected_verdict_counts"] = {str(key): int(value or 0) for key, value in counts.items()}
        updated["expected_verdict_scope"] = "claim_counts"
    updated["review_metadata"] = {
        "review_status": str(review.get("review_status") or ""),
        "reviewer": str(review.get("reviewer") or ""),
        "reviewed_at": str(review.get("reviewed_at") or ""),
        "review_notes": str(review.get("review_notes") or ""),
        "context_fair": review.get("context_fair"),
        "label_correct": review.get("label_correct"),
        "root_cause_correct": review.get("root_cause_correct"),
        "evidence_span_minimal": review.get("evidence_span_minimal"),
    }
    return updated


def _release_status(manifest: dict[str, Any], *, review_kind: str) -> str:
    status = str(manifest.get("status") or "")
    if status == "invalid_review":
        return "validation_failed"
    if status == "scored_review_pending" or status == "needs_review":
        return "review_pending"
    if status != "scored":
        return "validation_failed"
    review = manifest.get("review") or {}
    if not review.get("valid"):
        return "validation_failed"
    if str(review_kind).lower() != "independent":
        return "calibration_only"
    if int(review.get("warnings") or 0) > 0:
        return "calibration_only"
    return "publishable"


def _candidate_files(output_dir: Path, explicit_paths: list[str | Path], *, auto_candidates: bool) -> list[Path]:
    seen = set()
    paths = []
    for candidate in explicit_paths:
        path = Path(candidate)
        if path.exists() and str(path) not in seen:
            paths.append(path)
            seen.add(str(path))
    if auto_candidates:
        for name in DEFAULT_CANDIDATE_FILENAMES:
            path = output_dir / name
            if path.exists() and str(path) not in seen:
                paths.append(path)
                seen.add(str(path))
    return paths


def _copy_if_present(
    source: Path,
    destination: Path,
    bundle_root: Path,
    artifacts: list[dict[str, Any]],
    missing_required: list[str],
    *,
    required: bool,
) -> None:
    if not source.exists():
        if required:
            missing_required.append(str(source))
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    artifacts.append(
        {
            "name": source.name,
            "path": str(destination.relative_to(bundle_root)).replace("\\", "/"),
            "source_path": str(source),
            "bytes": destination.stat().st_size,
            "sha256": _sha256_file(destination),
            "required": bool(required),
        }
    )


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _claim_policy(status: str, *, dataset: str) -> str:
    if status == "publishable":
        return (
            "This %s bundle passed independent review and scoring. It can support "
            "%s-specific external validation claims, not broad SOTA claims by itself."
        ) % (dataset, dataset)
    if status == "calibration_only":
        return (
            "This %s bundle is useful for calibration, but it is not publishable external validation. "
            "Reasons can include assisted review, reviewer warnings, or incomplete span review."
        ) % dataset
    if status == "review_pending":
        return "This %s bundle is awaiting independent review and should not be used for public claims." % dataset
    return "This %s bundle failed validation and should not be used for claims." % dataset


def _metric(summary: dict[str, Any], key: str) -> str:
    value = summary.get(key)
    if isinstance(value, float):
        return "%.3f" % value
    return str(value)


def _validation_item(case_id: str, category: str, message: str) -> dict[str, str]:
    return {"case_id": case_id, "category": category, "message": message}


def _case_context_texts(case: dict[str, Any]) -> list[str]:
    return [
        str(context.get("text") or "")
        for context in case.get("contexts") or []
        if isinstance(context, dict)
    ]


def _span_in_contexts(span: str, context_texts: list[str]) -> bool:
    normalized_span = " ".join(str(span).split()).lower()
    return any(normalized_span in " ".join(text.split()).lower() for text in context_texts)


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value.strip() else []
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    return [str(value)]


def _dedupe(values: list[str]) -> list[str]:
    seen = set()
    output = []
    for value in values:
        normalized = " ".join(str(value).split())
        if normalized and normalized not in seen:
            seen.add(normalized)
            output.append(normalized)
    return output


def _truncate(text: str, limit: int) -> str:
    if limit <= 0 or len(text) <= limit:
        return text
    return text[: max(0, limit - 20)].rstrip() + "\n...[truncated]"


def _markdown_text(value: object) -> str:
    return str(value).replace("`", "'").replace("|", "\\|")


def _markdown_quote(value: object) -> str:
    return str(value).replace("\n", "\n> ")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run a generic external case-pack validation workflow.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--bundle-dir", default=str(DEFAULT_BUNDLE_DIR))
    parser.add_argument("--source-name", default=None)
    parser.add_argument("--id-field", default="id")
    parser.add_argument("--query-field", default="query")
    parser.add_argument("--answer-field", default="answer")
    parser.add_argument("--contexts-field", default="contexts")
    parser.add_argument("--label-field", default="expected_label")
    parser.add_argument("--root-cause-field", default="expected_primary_root_cause")
    parser.add_argument("--evidence-spans-field", default="expected_evidence_spans")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--sample-size", type=int, default=None)
    parser.add_argument("--sample-seed", type=int, default=13)
    parser.add_argument("--stratify-by", default="")
    parser.add_argument("--review", default=None)
    parser.add_argument("--review-kind", default="assisted", choices=["assisted", "independent"])
    parser.add_argument("--allow-unreviewed", action="store_true")
    parser.add_argument("--require-evidence-spans", action="store_true")
    parser.add_argument("--mode", default="semantic")
    parser.add_argument("--bootstrap-samples", type=int, default=100)
    parser.add_argument("--candidate", action="append", default=[])
    parser.add_argument("--no-auto-candidates", action="store_true")
    parser.add_argument("--skip-score", action="store_true")
    args = parser.parse_args(argv)

    summary = run_external_case_pack_workflow(
        input_path=args.input,
        dataset=args.dataset,
        output_dir=args.output_dir,
        bundle_dir=args.bundle_dir,
        source_name=args.source_name,
        id_field=args.id_field,
        query_field=args.query_field,
        answer_field=args.answer_field,
        contexts_field=args.contexts_field,
        label_field=args.label_field,
        root_cause_field=args.root_cause_field,
        evidence_spans_field=args.evidence_spans_field,
        limit=args.limit,
        sample_size=args.sample_size,
        sample_seed=args.sample_seed,
        stratify_by=[item.strip() for item in args.stratify_by.split(",") if item.strip()],
        review_path=args.review,
        review_kind=args.review_kind,
        require_reviewed=not args.allow_unreviewed,
        require_evidence_spans=args.require_evidence_spans,
        mode=args.mode,
        bootstrap_samples=args.bootstrap_samples,
        candidate_paths=args.candidate,
        auto_candidates=not args.no_auto_candidates,
        skip_score=args.skip_score,
    )
    print(render_workflow_summary(summary))
    return 1 if summary.get("status") == "validation_failed" else 0


if __name__ == "__main__":
    raise SystemExit(main())
