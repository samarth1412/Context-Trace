from __future__ import annotations

import argparse
import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
PACKAGE_ROOT = REPO_ROOT / "packages" / "contexttrace"
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

try:
    from benchmarks.contexttrace_bench.run_contexttrace import (
        run_contexttrace_benchmark,
        write_benchmark_outputs,
    )
except ModuleNotFoundError:  # pragma: no cover - direct script execution
    from run_contexttrace import run_contexttrace_benchmark, write_benchmark_outputs  # type: ignore

from contexttrace.verify.runner import VerificationProfile


DEFAULT_SPEC_PATH = Path(__file__).with_name("ARR_EXPERIMENTS.json")
DEFAULT_OUTPUT_DIR = Path(__file__).with_name("out") / "arr_ablations"
TABLE_METRICS = (
    ("failure_label_macro_f1", "Failure F1"),
    ("claim_verdict_macro_f1", "Claim F1"),
    ("citation_error_f1", "Citation F1"),
    ("root_cause_accuracy", "Root cause"),
    ("evidence_span_overlap", "Span overlap"),
    ("dangerous_false_green_rate", "False green"),
    ("latency_p95_ms", "p95 ms"),
)


def load_experiment_spec(path: str | Path = DEFAULT_SPEC_PATH) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or int(payload.get("schema_version") or 0) != 1:
        raise ValueError("ARR experiment spec must use schema_version 1.")
    profiles = ((payload.get("ablation") or {}).get("profiles") or [])
    if not profiles:
        raise ValueError("ARR experiment spec must define at least one ablation profile.")
    profile_ids = [str(profile.get("id") or "") for profile in profiles]
    if any(not profile_id for profile_id in profile_ids) or len(profile_ids) != len(set(profile_ids)):
        raise ValueError("ARR ablation profile IDs must be non-empty and unique.")
    return payload


def verification_profile(profile: dict[str, Any]) -> VerificationProfile:
    return VerificationProfile(
        citation_alignment=bool(profile.get("citation_alignment")),
        abstention_logic=bool(profile.get("abstention_logic")),
        source_assessment=bool(profile.get("source_assessment")),
        root_cause_inference=bool(profile.get("root_cause_inference")),
        evidence_span_localization=bool(profile.get("evidence_span_localization")),
    )


def run_arr_ablations(
    *,
    spec_path: str | Path = DEFAULT_SPEC_PATH,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    case_set: str | None = None,
    case_pack_path: str | Path | None = None,
    quick: bool = False,
) -> dict[str, Any]:
    spec = load_experiment_spec(spec_path)
    ablation = dict(spec["ablation"])
    resolved_case_set = case_set or str(ablation.get("default_case_set") or "all")
    include_generated = bool(ablation.get("include_generated_cases")) and not quick and case_pack_path is None
    target_cases = int(ablation.get("target_cases") or 500)
    bootstrap_samples = 50 if quick else int(ablation.get("bootstrap_samples") or 400)
    bootstrap_seed = int(ablation.get("bootstrap_seed") or 20260612)
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)

    records: list[dict[str, Any]] = []
    reference_ids: list[str] | None = None
    for profile_spec in ablation["profiles"]:
        profile_id = str(profile_spec["id"])
        result = run_contexttrace_benchmark(
            mode=str(profile_spec.get("mode") or "semantic"),
            case_set=resolved_case_set,
            case_pack_path=case_pack_path,
            include_generated_cases=include_generated,
            target_cases=target_cases,
            bootstrap_samples=bootstrap_samples,
            bootstrap_seed=bootstrap_seed,
            verification_profile=verification_profile(profile_spec),
        )
        case_ids = [str(row.get("id") or "") for row in result.get("rows") or []]
        if reference_ids is None:
            reference_ids = case_ids
        elif case_ids != reference_ids:
            raise ValueError("Ablation profiles did not run on identical ordered case IDs.")
        run_dir = destination / "runs" / profile_id
        paths = write_benchmark_outputs(result, output_dir=run_dir)
        records.append(
            {
                "id": profile_id,
                "label": str(profile_spec.get("label") or profile_id),
                "mode": str(profile_spec.get("mode") or "semantic"),
                "profile": verification_profile(profile_spec).to_dict(),
                "reported_summary": reported_summary(result["summary"], profile_spec),
                "raw_summary": dict(result["summary"]),
                "confidence_intervals": dict(result.get("confidence_intervals") or {}),
                "paths": {key: _portable_path(value) for key, value in paths.items()},
            }
        )

    aggregate = {
        "schema_version": 1,
        "experiment": "ContextTrace ARR cumulative ablations",
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "commit": _git_commit(),
        "quick": quick,
        "paper_result_eligible": not quick,
        "case_set": "external_case_pack" if case_pack_path else resolved_case_set,
        "case_pack_path": _portable_path(case_pack_path) if case_pack_path else None,
        "case_count": len(reference_ids or []),
        "case_ids_sha256": _case_id_hash(reference_ids or []),
        "bootstrap_samples": bootstrap_samples,
        "bootstrap_seed": bootstrap_seed,
        "runtime": {
            "python": platform.python_version(),
            "platform": platform.platform(),
        },
        "spec_path": _portable_path(spec_path),
        "profiles": records,
        "claim_policy": dict(spec.get("claim_policy") or {}),
    }
    results_path = destination / "ablation_results.json"
    table_path = destination / "ablation_table.md"
    matrix_path = destination / "experiment_matrix.json"
    results_path.write_text(json.dumps(aggregate, indent=2, sort_keys=True), encoding="utf-8")
    table_path.write_text(render_ablation_table(aggregate), encoding="utf-8")
    matrix_path.write_text(json.dumps(spec, indent=2, sort_keys=True), encoding="utf-8")
    return {
        **aggregate,
        "outputs": {
            "results": _portable_path(results_path),
            "table": _portable_path(table_path),
            "matrix": _portable_path(matrix_path),
        },
    }


def reported_summary(summary: dict[str, Any], profile: dict[str, Any]) -> dict[str, Any]:
    reported = dict(summary)
    if not bool(profile.get("citation_alignment")):
        for key in ("citation_error_precision", "citation_error_recall", "citation_error_f1"):
            reported[key] = None
        reported["citation_status_reported_cases"] = 0
    if not bool(profile.get("root_cause_inference")):
        reported["root_cause_accuracy"] = None
        reported["root_cause_reported_cases"] = 0
    if not bool(profile.get("evidence_span_localization")):
        reported["evidence_span_overlap"] = None
        reported["evidence_span_reported_cases"] = 0
    return reported


def render_ablation_table(result: dict[str, Any]) -> str:
    headers = ["Profile", "Mode", *[label for _, label in TABLE_METRICS]]
    lines = [
        "# ARR Ablation Results",
        "",
        "Status: `%s`" % ("quick_non_paper_run" if result.get("quick") else "paper_eligible_run"),
        "",
        "Cases: `%s`" % result.get("case_count"),
        "",
        "| %s |" % " | ".join(headers),
        "| %s |" % " | ".join(["---", "---", *(["---:"] * len(TABLE_METRICS))]),
    ]
    for profile in result.get("profiles") or []:
        summary = profile.get("reported_summary") or {}
        lines.append(
            "| %s | %s | %s |"
            % (
                profile.get("label"),
                profile.get("mode"),
                " | ".join(_metric(summary.get(key)) for key, _ in TABLE_METRICS),
            )
        )
    lines.extend(
        [
            "",
            "Unsupported outputs are reported as `N/A`; they are never imputed from the full system.",
            "Quick runs validate the harness and are not paper results.",
            "",
        ]
    )
    return "\n".join(lines)


def _metric(value: Any) -> str:
    if value is None:
        return "N/A"
    if isinstance(value, float):
        return "%.3f" % value
    return str(value)


def _case_id_hash(case_ids: list[str]) -> str:
    import hashlib

    return hashlib.sha256("\n".join(case_ids).encode("utf-8")).hexdigest()


def _git_commit() -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return completed.stdout.strip()


def _portable_path(path: str | Path | None) -> str | None:
    if path is None:
        return None
    resolved = Path(path).resolve()
    try:
        return resolved.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return str(resolved)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the frozen ARR cumulative ablation matrix.")
    parser.add_argument("--spec", default=str(DEFAULT_SPEC_PATH))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--case-set", default=None, choices=["contexttrace", "external", "public_holdout", "all"])
    parser.add_argument("--case-pack", default=None)
    parser.add_argument("--quick", action="store_true", help="Run curated cases with 50 bootstrap samples; never use as paper results.")
    args = parser.parse_args(argv)
    result = run_arr_ablations(
        spec_path=args.spec,
        output_dir=args.output_dir,
        case_set=args.case_set,
        case_pack_path=args.case_pack,
        quick=args.quick,
    )
    print("ARR ablations: %s profiles, %s cases" % (len(result["profiles"]), result["case_count"]))
    print("Paper eligible: %s" % result["paper_result_eligible"])
    print("Results: %s" % result["outputs"]["results"])
    print("Table: %s" % result["outputs"]["table"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
