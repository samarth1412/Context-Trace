from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from ragtruth_adapter import adapt_ragtruth_rows, load_rows, write_case_pack
from ragtruth_review import (
    apply_review_mappings,
    build_review_packet,
    build_review_queue,
    load_jsonl,
    validate_review_mappings,
    write_json,
    write_jsonl,
    write_text,
)
from run_contexttrace import run_contexttrace_case_pack, write_benchmark_outputs


def run_ragtruth_review_workflow(
    *,
    response_path: str | Path,
    source_info_path: str | Path,
    output_dir: str | Path,
    split: str | None = "test",
    quality: str | None = "good",
    limit: int | None = None,
    sample_size: int | None = 200,
    sample_seed: int = 13,
    stratify_by: list[str] | None = None,
    include_supported: bool = False,
    max_suggestions: int = 3,
    context_char_limit: int = 6000,
    review_path: str | Path | None = None,
    require_reviewed: bool = True,
    require_source_spans: bool = True,
    mode: str = "semantic",
    bootstrap_samples: int = 100,
    skip_score: bool = False,
) -> dict[str, Any]:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    started_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    quality_filter = None if quality is not None and str(quality).lower() == "any" else quality
    strata = stratify_by or ["task_type", "source", "expected_label", "model"]

    case_pack = adapt_ragtruth_rows(
        load_rows(response_path),
        source_rows=load_rows(source_info_path),
        split=split,
        quality=quality_filter,
        limit=limit,
        sample_size=sample_size,
        sample_seed=sample_seed,
        stratify_by=strata,
    )
    case_pack_path = output_path / "ragtruth_case_pack.json"
    write_case_pack(case_pack, case_pack_path)

    review_queue = build_review_queue(
        case_pack,
        include_supported=include_supported,
        suggest_source_spans=True,
        max_suggestions=max_suggestions,
    )
    review_queue_path = output_path / "ragtruth_review_queue.jsonl"
    write_jsonl(review_queue, review_queue_path)

    review_packet_path = output_path / "ragtruth_review_packet.md"
    write_text(
        build_review_packet(review_queue, context_char_limit=context_char_limit),
        review_packet_path,
    )

    manifest: dict[str, Any] = {
        "workflow": "ragtruth_review_workflow",
        "started_at": started_at,
        "status": "needs_review",
        "inputs": {
            "response_path": str(response_path),
            "source_info_path": str(source_info_path),
            "review_path": str(review_path) if review_path else "",
        },
        "options": {
            "split": split or "",
            "quality": quality if quality is not None else "any",
            "limit": limit,
            "sample_size": sample_size,
            "sample_seed": sample_seed,
            "stratify_by": strata,
            "include_supported": include_supported,
            "max_suggestions": max_suggestions,
            "context_char_limit": context_char_limit,
            "require_reviewed": require_reviewed,
            "require_source_spans": require_source_spans,
            "mode": mode,
            "bootstrap_samples": bootstrap_samples,
            "skip_score": skip_score,
        },
        "artifacts": {
            "case_pack": str(case_pack_path),
            "review_queue": str(review_queue_path),
            "review_packet": str(review_packet_path),
            "manifest": str(output_path / "ragtruth_workflow_manifest.json"),
        },
        "case_pack": {
            "cases": len(case_pack.get("cases") or []),
            "eligible_cases": (case_pack.get("stats") or {}).get("eligible_cases"),
            "sampling": (case_pack.get("stats") or {}).get("sampling") or {},
        },
        "review": {
            "review_rows": len(review_queue),
            "requires_human_review": True,
        },
    }

    if review_path:
        review_rows = load_jsonl(review_path)
        validation_report = validate_review_mappings(
            case_pack,
            review_rows,
            require_reviewed=require_reviewed,
            require_source_spans=require_source_spans,
        )
        validation_path = output_path / "ragtruth_review_validation.json"
        write_json(validation_report, validation_path)
        manifest["artifacts"]["review_validation"] = str(validation_path)
        manifest["review"].update(
            {
                "reviewed_rows": validation_report["reviewed_rows"],
                "valid": validation_report["valid"],
                "errors": len(validation_report["errors"]),
                "warnings": len(validation_report["warnings"]),
            }
        )
        if not validation_report["valid"]:
            manifest["status"] = "invalid_review"
            write_json(manifest, output_path / "ragtruth_workflow_manifest.json")
            return manifest

        reviewed_case_pack = apply_review_mappings(
            case_pack,
            review_rows,
            require_reviewed=require_reviewed,
            review_file=review_path,
        )
        reviewed_case_pack_path = output_path / "ragtruth_reviewed_case_pack.json"
        write_json(reviewed_case_pack, reviewed_case_pack_path)
        manifest["status"] = "review_validated"
        manifest["artifacts"]["reviewed_case_pack"] = str(reviewed_case_pack_path)

        if not skip_score:
            score_output_dir = output_path / "scored"
            score_result = run_contexttrace_case_pack(
                case_pack_path=reviewed_case_pack_path,
                mode=mode,
                bootstrap_samples=bootstrap_samples,
            )
            score_paths = write_benchmark_outputs(score_result, output_dir=score_output_dir)
            manifest["status"] = "scored"
            manifest["artifacts"]["score_output_dir"] = str(score_output_dir)
            manifest["artifacts"]["score_paths"] = dict(score_paths)
            manifest["score"] = {
                "summary": dict(score_result.get("summary") or {}),
                "case_set": score_result.get("case_set"),
                "case_pack_dataset": score_result.get("case_pack_dataset"),
            }

    write_json(manifest, output_path / "ragtruth_workflow_manifest.json")
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the reproducible RAGTruth review workflow.")
    parser.add_argument("--response", required=True, help="RAGTruth response.jsonl or equivalent JSON rows.")
    parser.add_argument("--source-info", required=True, help="RAGTruth source_info.jsonl or equivalent JSON rows.")
    parser.add_argument("--output-dir", required=True, help="Directory for workflow artifacts.")
    parser.add_argument("--split", default="test")
    parser.add_argument("--quality", default="good", help="Quality filter. Use 'any' to keep all rows.")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--sample-size", type=int, default=200)
    parser.add_argument("--sample-seed", type=int, default=13)
    parser.add_argument("--stratify-by", default="task_type,source,expected_label,model")
    parser.add_argument("--include-supported", action="store_true")
    parser.add_argument("--max-suggestions", type=int, default=3)
    parser.add_argument("--context-char-limit", type=int, default=6000)
    parser.add_argument("--review")
    parser.add_argument("--allow-unreviewed", action="store_true")
    parser.add_argument("--allow-missing-source-spans", action="store_true")
    parser.add_argument("--mode", default="semantic")
    parser.add_argument("--bootstrap-samples", type=int, default=100)
    parser.add_argument("--skip-score", action="store_true")
    args = parser.parse_args(argv)

    stratify_by = [field.strip() for field in str(args.stratify_by or "").split(",") if field.strip()]
    manifest = run_ragtruth_review_workflow(
        response_path=args.response,
        source_info_path=args.source_info,
        output_dir=args.output_dir,
        split=args.split,
        quality=args.quality,
        limit=args.limit,
        sample_size=args.sample_size,
        sample_seed=args.sample_seed,
        stratify_by=stratify_by or None,
        include_supported=args.include_supported,
        max_suggestions=args.max_suggestions,
        context_char_limit=args.context_char_limit,
        review_path=args.review,
        require_reviewed=not args.allow_unreviewed,
        require_source_spans=not args.allow_missing_source_spans,
        mode=args.mode,
        bootstrap_samples=args.bootstrap_samples,
        skip_score=args.skip_score,
    )
    print("Status: %s" % manifest["status"])
    print("Cases: %s" % manifest["case_pack"]["cases"])
    print("Review rows: %s" % manifest["review"]["review_rows"])
    print("Manifest: %s" % manifest["artifacts"]["manifest"])
    return 0 if manifest["status"] != "invalid_review" else 1


if __name__ == "__main__":
    raise SystemExit(main())
