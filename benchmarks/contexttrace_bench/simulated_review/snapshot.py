from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[3]
BENCH_DIR = REPO_ROOT / "benchmarks" / "contexttrace_bench"
DEFAULT_OUTPUT_JSON = BENCH_DIR / "SIMULATED_REVIEW_STATUS.json"
DEFAULT_OUTPUT_MD = BENCH_DIR / "SIMULATED_REVIEW_STATUS.md"


def build_simulated_review_snapshot(
    *,
    ragtruth_dir: str | Path,
    diag150_dir: str | Path,
    rq4_dir: str | Path,
    corrections_dir: str | Path,
) -> dict[str, Any]:
    ragtruth_path = Path(ragtruth_dir)
    diag_path = Path(diag150_dir)
    rq4_path = Path(rq4_dir)
    corrections_path = Path(corrections_dir)
    rag_manifest = _load(ragtruth_path / "run_manifest.json")
    diag_manifest = _load(diag_path / "run_manifest.json")
    rq4_manifest = _load(rq4_path / "run_manifest.json")
    rag_agreement = _load(ragtruth_path / "agreement.json")
    diag_agreement = _load(diag_path / "agreement.json")
    rq4_results = _load(rq4_path / "rq4_results.json")
    sensitivity = _load(corrections_path / "sensitivity_analysis.json")
    suggestions = _jsonl_count(corrections_path / "suggested_corrections.jsonl")
    applied = _jsonl_count(corrections_path / "applied_corrections.jsonl")
    manifests = [rag_manifest, diag_manifest, rq4_manifest]
    return {
        "schema_version": 1,
        "status": "simulated_pilots_complete_human_review_pending",
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "model": rag_manifest.get("model"),
        "backend": rag_manifest.get("backend"),
        "tasks": sum(int(row.get("tasks") or 0) for row in manifests),
        "completed": sum(int(row.get("completed") or 0) for row in manifests),
        "parse_failures": sum(int(row.get("parse_failures") or 0) for row in manifests),
        "estimated_cost_usd": round(sum(float(row.get("estimated_cost_usd") or 0) for row in manifests), 6),
        "ragtruth": rag_agreement,
        "diag150": diag_agreement,
        "rq4": rq4_results,
        "corrections": {
            "suggested": suggestions,
            "applied": applied,
            "status": "simulated_suggestions_only",
        },
        "sensitivity": sensitivity,
        "human_review": {
            "ragtruth": "pending",
            "diag150": "pending",
            "rq4": "pending_three_non_author_reviewers",
        },
        "paper_result_eligible": False,
        "sota_gate_eligible": False,
        "claim_policy": (
            "Report these outputs only as controlled LLM-simulated pilots. They do not replace "
            "independent human review and cannot support broad SOTA language."
        ),
    }


def render_snapshot(snapshot: dict[str, Any]) -> str:
    rq4 = snapshot["rq4"]
    lines = [
        "# Simulated review status",
        "",
        "Status: `%s`." % snapshot["status"],
        "",
        "These are controlled LLM-simulated pilots, not independent human review.",
        "",
        "- Model: `%s`" % snapshot["model"],
        "- Completed tasks: `%s/%s`" % (snapshot["completed"], snapshot["tasks"]),
        "- Parse failures: `%s`" % snapshot["parse_failures"],
        "- Estimated API cost: `$%.3f`" % snapshot["estimated_cost_usd"],
        "- Suggested corrections: `%s`" % snapshot["corrections"]["suggested"],
        "- Applied corrections: `%s`" % snapshot["corrections"]["applied"],
        "",
        "| Pilot | Cases | Unanimous | Disagreement | Frozen-label disagreement | Fleiss kappa |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for name in ("ragtruth", "diag150"):
        row = snapshot[name]
        lines.append(
            "| %s | %s | %s | %s | %s | %s |"
            % (
                name,
                row["case_count"],
                row["unanimous_cases"],
                row["disagreement_cases"],
                row["frozen_label_disagreement_cases"],
                _metric(row["fleiss_kappa"]),
            )
        )
    lines.extend(
        [
            "",
            "## RQ4 simulated settings",
            "",
            "| Setting | Root cause | Fix proxy | Actionability | False green |",
            "| --- | ---: | ---: | ---: | ---: |",
        ]
    )
    for name in ("raw_trace", "score_only", "contexttrace"):
        row = rq4["settings"][name]
        lines.append(
            "| %s | %s | %s | %s | %s |"
            % (
                name,
                _metric(row["root_cause_accuracy"]),
                _metric(row["fix_correctness_proxy"]),
                _metric(row["actionability_score"]),
                _metric(row["dangerous_false_green_rate"]),
            )
        )
    lines.extend(
        [
            "",
            "Registered positive RQ4 proxy claim supported: `%s`."
            % rq4["treatment_improved_preregistered_proxies"],
            "",
            str(snapshot["claim_policy"]),
            "",
        ]
    )
    return "\n".join(lines)


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError("%s must contain a JSON object." % path)
    return value


def _jsonl_count(path: Path) -> int:
    if not path.is_file():
        return 0
    return sum(bool(line.strip()) for line in path.read_text(encoding="utf-8-sig").splitlines())


def _metric(value: Any) -> str:
    if value is None:
        return "N/A"
    if isinstance(value, float):
        return "%.3f" % value
    return str(value)


def main() -> int:
    parser = argparse.ArgumentParser(description="Freeze aggregate simulated-review pilot status.")
    parser.add_argument("--ragtruth-dir", required=True)
    parser.add_argument("--diag150-dir", required=True)
    parser.add_argument("--rq4-dir", required=True)
    parser.add_argument("--corrections-dir", required=True)
    parser.add_argument("--output-json", default=str(DEFAULT_OUTPUT_JSON))
    parser.add_argument("--output-md", default=str(DEFAULT_OUTPUT_MD))
    args = parser.parse_args()
    snapshot = build_simulated_review_snapshot(
        ragtruth_dir=args.ragtruth_dir,
        diag150_dir=args.diag150_dir,
        rq4_dir=args.rq4_dir,
        corrections_dir=args.corrections_dir,
    )
    Path(args.output_json).write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    Path(args.output_md).write_text(render_snapshot(snapshot), encoding="utf-8")
    print("Simulated tasks: %s/%s" % (snapshot["completed"], snapshot["tasks"]))
    print("Estimated cost USD: %.6f" % snapshot["estimated_cost_usd"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
