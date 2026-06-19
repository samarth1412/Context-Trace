from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:  # pragma: no cover - exercised when run as a script from this directory
    from benchmarks.contexttrace_bench.ragtruth_error_analysis import write_ragtruth_error_analysis
    from benchmarks.contexttrace_bench.ragtruth_workflow import run_ragtruth_review_workflow
    from benchmarks.contexttrace_bench.run_contexttrace import (
        score_candidate_file,
        run_contexttrace_case_pack,
        write_benchmark_outputs,
    )
    from benchmarks.contexttrace_bench.ragtruth_review import write_json
except ModuleNotFoundError:  # pragma: no cover
    from ragtruth_error_analysis import write_ragtruth_error_analysis  # type: ignore
    from ragtruth_workflow import run_ragtruth_review_workflow  # type: ignore
    from run_contexttrace import (  # type: ignore
        score_candidate_file,
        run_contexttrace_case_pack,
        write_benchmark_outputs,
    )
    from ragtruth_review import write_json  # type: ignore


DEFAULT_OUTPUT_DIR = Path(__file__).with_name("out") / "ragtruth_release"
DEFAULT_BUNDLE_DIR = Path(__file__).with_name("out") / "ragtruth_release_bundle"
DEFAULT_STRATIFY_BY = ["task_type", "source", "expected_label", "model"]
DEFAULT_CANDIDATE_FILENAMES = (
    "openai_diagnostic_judge_predictions.json",
    "ragas_predictions.json",
    "deepeval_predictions.json",
    "ragchecker_predictions.json",
    "local_judge_predictions.json",
)
BUNDLE_REQUIRED_BASE = (
    "ragtruth_workflow_manifest.json",
    "ragtruth_case_pack.json",
    "ragtruth_review_queue.jsonl",
    "ragtruth_review_packet.md",
)
BUNDLE_REVIEWED = (
    "ragtruth_review_validation.json",
    "ragtruth_reviewed_case_pack.json",
)
BUNDLE_SCORED = (
    "contexttrace_bench_results.json",
    "results.md",
    "leaderboard.md",
    "report.html",
    "error_analysis.json",
    "error_analysis.md",
    "ragtruth_error_analysis.json",
    "ragtruth_error_analysis.md",
    "candidate_inputs.jsonl",
)


def run_ragtruth_release_workflow(
    *,
    response_path: str | Path,
    source_info_path: str | Path,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    bundle_dir: str | Path = DEFAULT_BUNDLE_DIR,
    review_path: str | Path | None = None,
    review_kind: str = "assisted",
    require_reviewed: bool = True,
    allow_missing_source_spans: bool = False,
    split: str | None = "test",
    quality: str | None = "good",
    limit: int | None = None,
    sample_size: int | None = 200,
    sample_seed: int = 13,
    stratify_by: list[str] | None = None,
    include_supported: bool = False,
    max_suggestions: int = 3,
    context_char_limit: int = 6000,
    mode: str = "semantic",
    bootstrap_samples: int = 100,
    candidate_paths: list[str | Path] | None = None,
    auto_candidates: bool = True,
) -> dict[str, Any]:
    output_path = Path(output_dir)
    bundle_path = Path(bundle_dir)
    manifest = run_ragtruth_review_workflow(
        response_path=response_path,
        source_info_path=source_info_path,
        output_dir=output_path,
        split=split,
        quality=quality,
        limit=limit,
        sample_size=sample_size,
        sample_seed=sample_seed,
        stratify_by=stratify_by or DEFAULT_STRATIFY_BY,
        include_supported=include_supported,
        max_suggestions=max_suggestions,
        context_char_limit=context_char_limit,
        review_path=review_path,
        require_reviewed=require_reviewed,
        require_source_spans=not allow_missing_source_spans,
        mode=mode,
        bootstrap_samples=bootstrap_samples,
        skip_score=True,
    )
    baseline_results: list[dict[str, Any]] = []
    candidate_files: list[Path] = []
    if manifest.get("status") == "review_validated":
        reviewed_case_pack = manifest.get("artifacts", {}).get("reviewed_case_pack")
        if reviewed_case_pack:
            score_output_dir = output_path / "scored"
            score_result = run_contexttrace_case_pack(
                case_pack_path=reviewed_case_pack,
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
            reviewed_case_pack_payload = json.loads(Path(reviewed_case_pack).read_text(encoding="utf-8"))
            ragtruth_error_paths = write_ragtruth_error_analysis(
                score_result,
                reviewed_case_pack_payload,
                output_dir=score_output_dir,
            )
            score_paths.update(ragtruth_error_paths)
            manifest["status"] = "scored"
            manifest["artifacts"]["score_output_dir"] = str(score_output_dir)
            manifest["artifacts"]["score_paths"] = dict(score_paths)
            manifest["score"] = {
                "summary": dict(score_result.get("summary") or {}),
                "case_set": score_result.get("case_set"),
                "case_pack_dataset": score_result.get("case_pack_dataset"),
                "baselines": len(baseline_results),
            }
            write_json(manifest, output_path / "ragtruth_workflow_manifest.json")

    release_status = _release_status(
        manifest,
        review_kind=review_kind,
        allow_missing_source_spans=allow_missing_source_spans,
    )
    bundle_paths = write_ragtruth_release_bundle(
        output_dir=output_path,
        bundle_dir=bundle_path,
        manifest=manifest,
        release_status=release_status,
        review_path=review_path,
        review_kind=review_kind,
        require_reviewed=require_reviewed,
        allow_missing_source_spans=allow_missing_source_spans,
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


def write_ragtruth_release_bundle(
    *,
    output_dir: str | Path,
    bundle_dir: str | Path,
    manifest: dict[str, Any],
    release_status: str,
    review_path: str | Path | None = None,
    review_kind: str = "assisted",
    require_reviewed: bool = True,
    allow_missing_source_spans: bool = False,
    candidate_files: list[Path] | None = None,
) -> dict[str, str]:
    output_path = Path(output_dir)
    bundle_path = Path(bundle_dir)
    bundle_path.mkdir(parents=True, exist_ok=True)
    artifacts: list[dict[str, Any]] = []
    missing_required: list[str] = []

    for name in BUNDLE_REQUIRED_BASE:
        _copy_if_present(output_path / name, bundle_path / name, bundle_path, artifacts, missing_required, required=True)
    if review_path:
        _copy_if_present(Path(review_path), bundle_path / "ragtruth_review_signoff.jsonl", bundle_path, artifacts, missing_required, required=True)
        for name in BUNDLE_REVIEWED:
            _copy_if_present(output_path / name, bundle_path / name, bundle_path, artifacts, missing_required, required=True)
    score_dir = output_path / "scored"
    if manifest.get("status") == "scored":
        for name in BUNDLE_SCORED:
            _copy_if_present(score_dir / name, bundle_path / "scored" / name, bundle_path, artifacts, missing_required, required=True)
    for candidate in candidate_files or []:
        _copy_if_present(candidate, bundle_path / "candidates" / candidate.name, bundle_path, artifacts, missing_required, required=False)

    if missing_required:
        release_status = "validation_failed"
    bundle_manifest = {
        "dataset": "RAGTruth",
        "bundle_version": 1,
        "bundle_status": release_status,
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "workflow_status": manifest.get("status"),
        "case_count": (manifest.get("case_pack") or {}).get("cases"),
        "review": manifest.get("review") or {},
        "review_kind": review_kind,
        "require_reviewed": bool(require_reviewed),
        "allow_missing_source_spans": bool(allow_missing_source_spans),
        "score": manifest.get("score") or {},
        "missing_required_artifacts": missing_required,
        "artifacts": artifacts,
        "claim_policy": _claim_policy(release_status),
    }
    manifest_path = bundle_path / "manifest.json"
    readme_path = bundle_path / "README.md"
    manifest_path.write_text(json.dumps(bundle_manifest, indent=2, sort_keys=True), encoding="utf-8")
    readme_path.write_text(render_ragtruth_bundle_readme(bundle_manifest), encoding="utf-8")
    return {
        "bundle_dir": str(bundle_path),
        "manifest_json": str(manifest_path),
        "readme_md": str(readme_path),
    }


def render_ragtruth_bundle_readme(manifest: dict[str, Any]) -> str:
    score = manifest.get("score") or {}
    summary = score.get("summary") or {}
    lines = [
        "# RAGTruth Release Bundle",
        "",
        "Status: `%s`" % manifest.get("bundle_status"),
        "Workflow status: `%s`" % manifest.get("workflow_status"),
        "Cases: `%s`" % manifest.get("case_count"),
        "Review kind: `%s`" % manifest.get("review_kind"),
        "Generated: `%s`" % manifest.get("generated_at"),
        "",
        "## Claim Policy",
        "",
        _claim_policy(str(manifest.get("bundle_status") or "")),
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
        "RAGTruth release workflow",
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


def _release_status(
    manifest: dict[str, Any],
    *,
    review_kind: str,
    allow_missing_source_spans: bool,
) -> str:
    status = str(manifest.get("status") or "")
    if status == "invalid_review":
        return "validation_failed"
    if status == "needs_review":
        return "review_pending"
    if status != "scored":
        return "validation_failed"
    review = manifest.get("review") or {}
    if not review.get("valid"):
        return "validation_failed"
    if allow_missing_source_spans or str(review_kind).lower() != "independent":
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


def _claim_policy(status: str) -> str:
    if status == "publishable":
        return (
            "This RAGTruth bundle passed strict independent review and scoring. "
            "It can support RAGTruth-specific external validation claims, not broad SOTA claims by itself."
        )
    if status == "calibration_only":
        return (
            "This RAGTruth bundle is useful for calibration, but it is not publishable external validation. "
            "Reasons can include assisted review or intentionally missing source-side spans."
        )
    if status == "review_pending":
        return "This RAGTruth bundle is awaiting source-evidence review and should not be used for public claims."
    return "This RAGTruth bundle failed validation and should not be used for claims."


def _metric(summary: dict[str, Any], key: str) -> str:
    value = summary.get(key)
    if isinstance(value, float):
        return "%.3f" % value
    return str(value)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the RAGTruth external validation release workflow.")
    parser.add_argument("--response", required=True)
    parser.add_argument("--source-info", required=True)
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--bundle-dir", default=str(DEFAULT_BUNDLE_DIR))
    parser.add_argument("--review")
    parser.add_argument("--review-kind", default="assisted", choices=["assisted", "independent"])
    parser.add_argument("--allow-unreviewed", action="store_true")
    parser.add_argument("--allow-missing-source-spans", action="store_true")
    parser.add_argument("--split", default="test")
    parser.add_argument("--quality", default="good")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--sample-size", type=int, default=200)
    parser.add_argument("--sample-seed", type=int, default=13)
    parser.add_argument("--stratify-by", default="task_type,source,expected_label,model")
    parser.add_argument("--include-supported", action="store_true")
    parser.add_argument("--max-suggestions", type=int, default=3)
    parser.add_argument("--context-char-limit", type=int, default=6000)
    parser.add_argument("--mode", default="semantic")
    parser.add_argument("--bootstrap-samples", type=int, default=100)
    parser.add_argument("--candidate", action="append", default=[])
    parser.add_argument("--no-auto-candidates", action="store_true")
    args = parser.parse_args(argv)

    stratify_by = [field.strip() for field in str(args.stratify_by or "").split(",") if field.strip()]
    summary = run_ragtruth_release_workflow(
        response_path=args.response,
        source_info_path=args.source_info,
        output_dir=args.output_dir,
        bundle_dir=args.bundle_dir,
        review_path=args.review,
        review_kind=args.review_kind,
        require_reviewed=not args.allow_unreviewed,
        allow_missing_source_spans=args.allow_missing_source_spans,
        split=args.split,
        quality=args.quality,
        limit=args.limit,
        sample_size=args.sample_size,
        sample_seed=args.sample_seed,
        stratify_by=stratify_by or DEFAULT_STRATIFY_BY,
        include_supported=args.include_supported,
        max_suggestions=args.max_suggestions,
        context_char_limit=args.context_char_limit,
        mode=args.mode,
        bootstrap_samples=args.bootstrap_samples,
        candidate_paths=args.candidate,
        auto_candidates=not args.no_auto_candidates,
    )
    print(render_workflow_summary(summary))
    return 1 if summary.get("status") == "validation_failed" else 0


if __name__ == "__main__":
    raise SystemExit(main())
