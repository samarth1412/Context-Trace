from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

try:  # pragma: no cover - exercised when run as a script from this directory
    from benchmarks.contexttrace_bench.audit_diag150 import (
        DEFAULT_AUDIT_OUTPUT_DIR,
        DEFAULT_RELEASE_BUNDLE_DIR,
        load_candidate_inputs,
        load_human_review_file,
        write_diag150_audit_artifacts,
        write_diag150_release_bundle,
    )
    from benchmarks.contexttrace_bench.run_contexttrace import (
        DEFAULT_BOOTSTRAP_SAMPLES,
        render_candidate_inputs_jsonl,
        run_contexttrace_benchmark,
        score_candidate_file,
        write_benchmark_outputs,
    )
except ModuleNotFoundError:  # pragma: no cover
    from audit_diag150 import (  # type: ignore
        DEFAULT_AUDIT_OUTPUT_DIR,
        DEFAULT_RELEASE_BUNDLE_DIR,
        load_candidate_inputs,
        load_human_review_file,
        write_diag150_audit_artifacts,
        write_diag150_release_bundle,
    )
    from run_contexttrace import (  # type: ignore
        DEFAULT_BOOTSTRAP_SAMPLES,
        render_candidate_inputs_jsonl,
        run_contexttrace_benchmark,
        score_candidate_file,
        write_benchmark_outputs,
    )


DEFAULT_CANDIDATE_FILENAMES = (
    "openai_diagnostic_judge_predictions.json",
    "ragas_predictions.json",
    "deepeval_predictions.json",
    "local_judge_predictions.json",
    "phoenix_predictions.json",
    "trulens_predictions.json",
)


def run_diag150_release_workflow(
    *,
    output_dir: str | Path = DEFAULT_AUDIT_OUTPUT_DIR,
    bundle_dir: str | Path = DEFAULT_RELEASE_BUNDLE_DIR,
    candidate_paths: list[str | Path] | None = None,
    auto_candidates: bool = True,
    review_file: str | Path | None = None,
    require_human_signoff: bool = False,
    bootstrap_samples: int = DEFAULT_BOOTSTRAP_SAMPLES,
    reviewer: str = "Pending",
    audit_status: str = "pending_human_signoff",
) -> dict[str, Any]:
    output_path = Path(output_dir)
    bundle_path = Path(bundle_dir)
    candidate_files = _candidate_files(output_path, candidate_paths or [], auto_candidates=auto_candidates)
    result = run_contexttrace_benchmark(
        mode="semantic",
        case_set="public_holdout",
        include_generated_cases=False,
        bootstrap_samples=bootstrap_samples,
    )
    baseline_results = [score_candidate_file(result, path) for path in candidate_files]
    benchmark_paths = write_benchmark_outputs(
        result,
        output_dir=output_path,
        baseline_results=baseline_results or None,
    )
    candidate_inputs_path = output_path / "candidate_inputs.jsonl"
    candidate_inputs = (
        load_candidate_inputs(candidate_inputs_path)
        if candidate_inputs_path.exists()
        else [json.loads(line) for line in render_candidate_inputs_jsonl(result).splitlines() if line.strip()]
    )
    human_reviews = load_human_review_file(review_file) if review_file else None
    audit_paths = write_diag150_audit_artifacts(
        result,
        output_dir=output_path,
        candidate_inputs=candidate_inputs,
        human_reviews=human_reviews,
        artifact_paths=benchmark_paths,
        reviewer=reviewer,
        audit_status=audit_status,
        require_human_signoff=require_human_signoff,
    )
    bundle_paths = write_diag150_release_bundle(
        output_dir=output_path,
        bundle_dir=bundle_path,
        review_file=review_file,
        require_human_signoff=require_human_signoff,
    )
    validation = json.loads(Path(audit_paths["audit_validation_json"]).read_text(encoding="utf-8"))
    manifest = json.loads(Path(bundle_paths["manifest_json"]).read_text(encoding="utf-8"))
    return {
        "status": _workflow_status(validation, manifest),
        "case_count": (result.get("summary") or {}).get("cases"),
        "candidate_files": [str(path) for path in candidate_files],
        "candidate_count": len(candidate_files),
        "baseline_count": len(baseline_results),
        "benchmark_paths": benchmark_paths,
        "audit_paths": audit_paths,
        "bundle_paths": bundle_paths,
        "validation": validation,
        "manifest": manifest,
    }


def render_workflow_summary(summary: dict[str, Any]) -> str:
    manifest = summary.get("manifest") or {}
    validation = summary.get("validation") or {}
    validation_summary = validation.get("summary") or {}
    lines = [
        "ContextTrace-Diag-150 release workflow",
        "Status: %s" % summary.get("status"),
        "Bundle status: %s" % manifest.get("bundle_status"),
        "Cases: %s" % summary.get("case_count"),
        "Candidate rows scored: %s" % summary.get("baseline_count"),
        "Validation errors: %s" % validation_summary.get("errors"),
        "Validation warnings: %s" % validation_summary.get("warnings"),
        "Bundle: %s" % ((summary.get("bundle_paths") or {}).get("bundle_dir")),
        "Manifest: %s" % ((summary.get("bundle_paths") or {}).get("manifest_json")),
    ]
    candidates = summary.get("candidate_files") or []
    if candidates:
        lines.append("Candidate files:")
        lines.extend("- %s" % path for path in candidates)
    return "\n".join(lines)


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


def _workflow_status(validation: dict[str, Any], manifest: dict[str, Any]) -> str:
    if validation.get("status") != "passed":
        return "validation_failed"
    return str(manifest.get("bundle_status") or "validation_failed")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the one-command ContextTrace-Diag-150 release evidence workflow.")
    parser.add_argument("--output-dir", default=str(DEFAULT_AUDIT_OUTPUT_DIR))
    parser.add_argument("--bundle-dir", default=str(DEFAULT_RELEASE_BUNDLE_DIR))
    parser.add_argument("--candidate", action="append", default=[], help="Candidate prediction JSON file to score into the bundle. Can be repeated.")
    parser.add_argument("--no-auto-candidates", action="store_true", help="Do not auto-score known candidate files already present in --output-dir.")
    parser.add_argument("--review-file", default=None, help="Completed human review JSON file.")
    parser.add_argument("--require-human-signoff", action="store_true", help="Fail unless every Diag-150 case has complete independent signoff.")
    parser.add_argument("--bootstrap-samples", default=DEFAULT_BOOTSTRAP_SAMPLES, type=int)
    parser.add_argument("--reviewer", default="Pending")
    parser.add_argument("--audit-status", default="pending_human_signoff")
    args = parser.parse_args(argv)

    summary = run_diag150_release_workflow(
        output_dir=args.output_dir,
        bundle_dir=args.bundle_dir,
        candidate_paths=args.candidate,
        auto_candidates=not args.no_auto_candidates,
        review_file=args.review_file,
        require_human_signoff=args.require_human_signoff,
        bootstrap_samples=args.bootstrap_samples,
        reviewer=args.reviewer,
        audit_status=args.audit_status,
    )
    print(render_workflow_summary(summary))
    return 1 if summary.get("status") == "validation_failed" else 0


if __name__ == "__main__":
    raise SystemExit(main())
