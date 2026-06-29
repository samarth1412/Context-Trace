from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
PACKAGE_ROOT = REPO_ROOT / "packages" / "contexttrace"
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

try:
    from benchmarks.contexttrace_bench.artifact_runtime import repository_revision
    from benchmarks.contexttrace_bench.arr_ablation import (
        DEFAULT_SPEC_PATH,
        load_experiment_spec,
        run_arr_ablations,
    )
    from benchmarks.contexttrace_bench.run_contexttrace import (
        build_error_analysis,
        run_contexttrace_benchmark,
        score_candidate_file,
        write_benchmark_outputs,
    )
except ModuleNotFoundError:  # pragma: no cover - direct script execution
    from artifact_runtime import repository_revision  # type: ignore
    from arr_ablation import DEFAULT_SPEC_PATH, load_experiment_spec, run_arr_ablations  # type: ignore
    from run_contexttrace import (  # type: ignore
        build_error_analysis,
        run_contexttrace_benchmark,
        score_candidate_file,
        write_benchmark_outputs,
    )


DEFAULT_OUTPUT_DIR = Path(__file__).with_name("out") / "arr_reproduction"
DEFAULT_RAGTRUTH_PACK = (
    Path(__file__).with_name("out")
    / "ragtruth_release_bundle"
    / "ragtruth_reviewed_case_pack.json"
)
DEFAULT_RAGTRUTH_CANDIDATE = (
    Path(__file__).with_name("out")
    / "ragtruth_release_bundle"
    / "candidates"
    / "ragas_predictions.json"
)
QUICK_RAGTRUTH_CASES = 25
QUICK_SEED = 20260612
TABLE_FILENAMES = {
    "external_results": "table_1_external_results.md",
    "ablations": "table_2_ablations.md",
    "baselines": "table_3_baselines.md",
    "error_analysis": "table_4_error_analysis.md",
}


def run_arr_reproduction(
    *,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    spec_path: str | Path = DEFAULT_SPEC_PATH,
    ragtruth_case_pack_path: str | Path | None = None,
    candidate_paths: list[str | Path] | None = None,
    quick: bool = False,
    discover_defaults: bool = True,
) -> dict[str, Any]:
    spec = load_experiment_spec(spec_path)
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    bootstrap_samples = 50 if quick else int(spec["ablation"].get("bootstrap_samples") or 400)
    bootstrap_seed = int(spec["ablation"].get("bootstrap_seed") or QUICK_SEED)

    ragtruth_path = _resolve_optional_path(
        ragtruth_case_pack_path,
        DEFAULT_RAGTRUTH_PACK if discover_defaults else None,
    )
    candidates = _resolve_candidate_paths(
        candidate_paths,
        discover_default=discover_defaults,
    )
    if not quick and ragtruth_path is None:
        raise ValueError("Paper-candidate reproduction requires --ragtruth-case-pack.")
    if not quick and not candidates:
        raise ValueError("Paper-candidate reproduction requires at least one --candidate prediction file.")

    diag_result = run_contexttrace_benchmark(
        mode="semantic",
        case_set="public_holdout",
        include_generated_cases=False,
        target_cases=150,
        bootstrap_samples=bootstrap_samples,
        bootstrap_seed=bootstrap_seed,
    )
    diag_paths = write_benchmark_outputs(
        diag_result,
        output_dir=destination / "runs" / "diag150",
    )

    ragtruth_result: dict[str, Any] | None = None
    ragtruth_paths: dict[str, str] = {}
    scored_baselines: list[dict[str, Any]] = []
    rejected_baselines: list[dict[str, str]] = []
    selected_ragtruth_path: Path | None = None
    if ragtruth_path is not None:
        selected_ragtruth_path = (
            _write_quick_case_pack(
                ragtruth_path,
                destination / "inputs" / "ragtruth_quick_case_pack.json",
                sample_size=QUICK_RAGTRUTH_CASES,
                seed=bootstrap_seed,
            )
            if quick
            else ragtruth_path
        )
        ragtruth_result = run_contexttrace_benchmark(
            mode="semantic",
            case_pack_path=selected_ragtruth_path,
            include_generated_cases=False,
            bootstrap_samples=bootstrap_samples,
            bootstrap_seed=bootstrap_seed,
        )
        for candidate_path in candidates:
            scored = score_candidate_file(
                ragtruth_result,
                candidate_path,
                bootstrap_samples=bootstrap_samples,
                bootstrap_seed=bootstrap_seed,
            )
            scored["cost_reported"] = _candidate_cost_reported(candidate_path)
            coverage = dict(scored.get("coverage") or {})
            if int(coverage.get("matched_predictions") or 0) != len(ragtruth_result.get("rows") or []):
                rejected_baselines.append(
                    {
                        "path": _portable_path(candidate_path),
                        "reason": "candidate predictions do not cover every selected RAGTruth case ID",
                    }
                )
                continue
            scored_baselines.append(scored)
        if not quick and not scored_baselines:
            raise ValueError("No candidate prediction file covered every RAGTruth case ID.")
        ragtruth_paths = write_benchmark_outputs(
            ragtruth_result,
            output_dir=destination / "runs" / "ragtruth",
            baseline_results=scored_baselines or None,
        )

    ablation = run_arr_ablations(
        spec_path=spec_path,
        output_dir=destination / "ablations",
        case_set="all",
        quick=quick,
    )
    primary_result = ragtruth_result or diag_result
    error_analysis = build_error_analysis(primary_result)
    external_rows = _external_rows(spec, diag_result=diag_result, ragtruth_result=ragtruth_result, quick=quick)

    table_text = {
        "external_results": render_external_results_table(external_rows, quick=quick),
        "ablations": _render_table_2(ablation["outputs"]["table"]),
        "baselines": render_baseline_table(
            primary_result,
            scored_baselines,
            rejected_baselines=rejected_baselines,
            quick=quick,
        ),
        "error_analysis": render_error_analysis_table(error_analysis, quick=quick),
    }
    table_paths: dict[str, str] = {}
    for table_id, filename in TABLE_FILENAMES.items():
        path = destination / filename
        path.write_text(table_text[table_id], encoding="utf-8")
        table_paths[table_id] = _portable_path(path)

    gates = {
        "non_quick_run": not quick,
        "ragtruth_case_pack_available": ragtruth_result is not None,
        "matched_external_baseline_available": bool(scored_baselines),
        "independent_diag150_review_complete": False,
        "independent_ragtruth_review_complete": False,
    }
    manifest_path = destination / "reproduction_manifest.json"
    results_path = destination / "arr_tables.json"
    manifest = {
        "schema_version": 1,
        "workflow": "ContextTrace ARR table reproduction",
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "commit": _git_commit(),
        "quick": quick,
        "result_scope": "harness_validation_only" if quick else "pre_review_paper_candidate",
        "paper_run_candidate": bool(not quick and ragtruth_result and scored_baselines),
        "paper_result_eligible": all(gates.values()),
        "eligibility_gates": gates,
        "bootstrap_samples": bootstrap_samples,
        "bootstrap_seed": bootstrap_seed,
        "inputs": {
            "experiment_spec": _input_record(spec_path),
            "ragtruth_case_pack": _input_record(ragtruth_path),
            "selected_ragtruth_case_pack": _input_record(selected_ragtruth_path),
            "candidate_predictions": [_input_record(path) for path in candidates],
        },
        "datasets": external_rows,
        "baselines": [
            {
                "system": baseline.get("system"),
                "version": baseline.get("version"),
                "coverage": baseline.get("coverage"),
                "cost_reported": baseline.get("cost_reported"),
            }
            for baseline in scored_baselines
        ],
        "rejected_baselines": rejected_baselines,
        "outputs": {
            "tables": table_paths,
            "diag150": {key: _portable_path(value) for key, value in diag_paths.items()},
            "ragtruth": {key: _portable_path(value) for key, value in ragtruth_paths.items()},
            "ablations": dict(ablation["outputs"]),
            "manifest": _portable_path(manifest_path),
            "machine_readable_tables": _portable_path(results_path),
        },
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    results_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "external_results": external_rows,
                "ablation_results": ablation["profiles"],
                "baseline_results": scored_baselines,
                "error_analysis": error_analysis,
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    return manifest


def render_external_results_table(rows: list[dict[str, Any]], *, quick: bool) -> str:
    lines = [
        "# Table 1: External Evaluation",
        "",
        "Status: `%s`." % ("quick_non_paper_run" if quick else "pre_review_paper_candidate"),
        "",
        "| Dataset | Role | Review status | Cases | Failure F1 [95% CI] | Claim F1 | Root cause | Citation F1 | Span overlap | False green [95% CI] | p95 ms | Cost / 100 |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in rows:
        summary = dict(row.get("summary") or {})
        lines.append(
            "| %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s |"
            % (
                _cell(row.get("dataset")),
                _cell(row.get("role")),
                _cell(row.get("review_status")),
                _metric(summary.get("cases")),
                _metric_with_ci(row, "failure_label_macro_f1"),
                _metric(summary.get("claim_verdict_macro_f1")),
                _metric(summary.get("root_cause_accuracy")),
                _metric(summary.get("citation_error_f1")),
                _metric(summary.get("evidence_span_overlap")),
                _metric_with_ci(row, "dangerous_false_green_rate"),
                _metric(summary.get("latency_p95_ms")),
                _metric(summary.get("cost_per_100_traces_usd")),
            )
        )
    lines.extend(
        [
            "",
            "Review status is part of the result: assisted or pending review is calibration evidence, not independent validation.",
            (
                "Quick rows may use deterministic subsets and are never paper results."
                if quick
                else "These full estimates remain pre-review candidates until independent review gates pass."
            ),
            "",
        ]
    )
    return "\n".join(lines)


def render_baseline_table(
    contexttrace_result: dict[str, Any],
    baselines: list[dict[str, Any]],
    *,
    rejected_baselines: list[dict[str, str]],
    quick: bool,
) -> str:
    rows = [
        {
            "system": "ContextTrace",
            "version": contexttrace_result.get("mode"),
            "summary": contexttrace_result.get("summary") or {},
            "confidence_intervals": contexttrace_result.get("confidence_intervals") or {},
            "cost_reported": True,
        },
        *baselines,
    ]
    lines = [
        "# Table 3: Same-ID Baseline Comparison",
        "",
        "Status: `%s`." % ("quick_non_paper_run" if quick else "pre_review_paper_candidate"),
        "",
        "| System | Version | Cases | Failure F1 [95% CI] | Claim F1 | Root cause | Citation F1 | Span overlap | False green [95% CI] | p95 ms | Cost / 100 |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in rows:
        summary = dict(row.get("summary") or {})
        lines.append(
            "| %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s |"
            % (
                _cell(row.get("system")),
                _cell(row.get("version")),
                _metric(summary.get("cases")),
                _metric_with_ci(row, "failure_label_macro_f1"),
                _metric(summary.get("claim_verdict_macro_f1")),
                _metric(summary.get("root_cause_accuracy")),
                _metric(summary.get("citation_error_f1")),
                _metric(summary.get("evidence_span_overlap")),
                _metric_with_ci(row, "dangerous_false_green_rate"),
                _metric(summary.get("latency_p95_ms")),
                _reported_cost(row),
            )
        )
    if not baselines:
        lines.append(
            "| No matched baseline artifact | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A |"
        )
    lines.extend(
        [
            "",
            "Unsupported diagnostic fields are `N/A`; they are not imputed from ContextTrace.",
            "Unreported API cost is `N/A`, not zero. Latency is descriptive unless measured on matched hardware.",
            "Only candidates covering every selected case ID appear in this table.",
        ]
    )
    if rejected_baselines:
        lines.extend(
            [
                "",
                "Rejected candidate artifacts: %s."
                % ", ".join("`%s` (%s)" % (row["path"], row["reason"]) for row in rejected_baselines),
            ]
        )
    lines.append("")
    return "\n".join(lines)


def render_error_analysis_table(analysis: dict[str, Any], *, quick: bool) -> str:
    clusters: list[dict[str, Any]] = []
    for row in analysis.get("confusion") or []:
        if row.get("expected") == row.get("predicted"):
            continue
        clusters.append(
            {
                "cluster": "Failure-label confusion",
                "signal": "%s -> %s" % (row.get("expected"), row.get("predicted")),
                "count": row.get("count"),
                "follow_up": "Inspect claim decomposition and verdict thresholds.",
            }
        )
    for row in analysis.get("root_cause_confusion") or []:
        if row.get("expected_root_cause") == row.get("predicted_root_cause"):
            continue
        clusters.append(
            {
                "cluster": "Root-cause confusion",
                "signal": "%s -> %s"
                % (row.get("expected_root_cause"), row.get("predicted_root_cause")),
                "count": row.get("count"),
                "follow_up": "Review evidence available to the root-cause classifier.",
            }
        )
    for row in analysis.get("false_positive_labels") or []:
        clusters.append(
            {
                "cluster": "False-positive failure",
                "signal": row.get("label"),
                "count": row.get("count"),
                "follow_up": "Calibrate precision without increasing false greens.",
            }
        )
    false_green_count = len(analysis.get("dangerous_false_greens") or [])
    if false_green_count:
        clusters.append(
            {
                "cluster": "Dangerous false green",
                "signal": "failure predicted as no_failure_detected",
                "count": false_green_count,
                "follow_up": "Prioritize recall and inspect missing evidence signals.",
            }
        )
    clusters.sort(key=lambda row: (-int(row.get("count") or 0), str(row.get("cluster"))))
    lines = [
        "# Table 4: Error Analysis",
        "",
        "Status: `%s`." % ("quick_non_paper_run" if quick else "pre_review_paper_candidate"),
        "",
        "Dataset: `%s`; cases: `%s`; label misses: `%s`."
        % (analysis.get("case_set"), analysis.get("case_count"), analysis.get("label_miss_count")),
        "",
        "| Error cluster | Observed signal | Count | Follow-up analysis |",
        "| --- | --- | ---: | --- |",
    ]
    if clusters:
        for row in clusters:
            lines.append(
                "| %s | `%s` | %s | %s |"
                % (
                    _cell(row["cluster"]),
                    _cell(row["signal"]),
                    row["count"],
                    _cell(row["follow_up"]),
                )
            )
    else:
        lines.append("| No observed errors | N/A | 0 | Expand independent external evaluation. |")
    lines.extend(
        [
            "",
            "Clusters are observed benchmark outcomes, not inferred causal explanations.",
            (
                "Quick-run counts are harness checks and must not be copied into the paper."
                if quick
                else "These full-run clusters remain pre-review findings until independent review gates pass."
            ),
            "",
        ]
    )
    return "\n".join(lines)


def _external_rows(
    spec: dict[str, Any],
    *,
    diag_result: dict[str, Any],
    ragtruth_result: dict[str, Any] | None,
    quick: bool,
) -> list[dict[str, Any]]:
    datasets = {str(row.get("id")): row for row in spec.get("datasets") or []}
    ragtruth_spec = datasets.get("ragtruth_primary") or {}
    diag_spec = datasets.get("diag150_primary") or {}
    rows = []
    if ragtruth_result is not None:
        rows.append(
            {
                "dataset": "RAGTruth%s" % (" quick subset" if quick else ""),
                "dataset_id": "ragtruth_primary",
                "role": ragtruth_spec.get("role"),
                "review_status": ragtruth_spec.get("review_status"),
                "summary": dict(ragtruth_result.get("summary") or {}),
                "confidence_intervals": dict(ragtruth_result.get("confidence_intervals") or {}),
            }
        )
    else:
        rows.append(
            {
                "dataset": "RAGTruth",
                "dataset_id": "ragtruth_primary",
                "role": ragtruth_spec.get("role"),
                "review_status": "not_run_missing_case_pack",
                "summary": {},
                "confidence_intervals": {},
            }
        )
    rows.append(
        {
            "dataset": "ContextTrace-Diag-150",
            "dataset_id": "diag150_primary",
            "role": diag_spec.get("role"),
            "review_status": diag_spec.get("review_status"),
            "summary": dict(diag_result.get("summary") or {}),
            "confidence_intervals": dict(diag_result.get("confidence_intervals") or {}),
        }
    )
    return rows


def _write_quick_case_pack(
    source_path: Path,
    destination: Path,
    *,
    sample_size: int,
    seed: int,
) -> Path:
    payload = json.loads(source_path.read_text(encoding="utf-8-sig"))
    cases = [case for case in payload.get("cases") or [] if isinstance(case, dict)]
    if not cases:
        raise ValueError("RAGTruth case pack contains no cases.")
    count = min(sample_size, len(cases))
    selected_indexes = sorted(random.Random(seed).sample(range(len(cases)), count))
    selected = [cases[index] for index in selected_indexes]
    destination.parent.mkdir(parents=True, exist_ok=True)
    quick_payload = {
        **payload,
        "dataset": "%s quick-%s" % (payload.get("dataset") or "RAGTruth", count),
        "cases": selected,
        "quick_sample": {
            "paper_result_eligible": False,
            "source_path": _portable_path(source_path),
            "source_sha256": _sha256(source_path),
            "sample_size": count,
            "sample_seed": seed,
            "selected_ids_sha256": _ids_sha256(selected),
        },
    }
    destination.write_text(json.dumps(quick_payload, indent=2, sort_keys=True), encoding="utf-8")
    return destination


def _resolve_optional_path(value: str | Path | None, default: Path | None) -> Path | None:
    if value is not None:
        path = Path(value)
        if not path.is_file():
            return None
        return path
    if default is not None and default.is_file():
        return default
    return None


def _resolve_candidate_paths(
    paths: list[str | Path] | None,
    *,
    discover_default: bool,
) -> list[Path]:
    if paths is not None:
        return [Path(path) for path in paths if Path(path).is_file()]
    if discover_default and DEFAULT_RAGTRUTH_CANDIDATE.is_file():
        return [DEFAULT_RAGTRUTH_CANDIDATE]
    return []


def _input_record(path: str | Path | None) -> dict[str, Any] | None:
    if path is None:
        return None
    resolved = Path(path)
    if not resolved.is_file():
        return {"path": _portable_path(resolved), "available": False}
    return {
        "path": _portable_path(resolved),
        "available": True,
        "bytes": resolved.stat().st_size,
        "sha256": _sha256(resolved),
    }


def _candidate_cost_reported(path: Path) -> bool:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if payload.get("estimated_cost_per_trace_usd") is not None:
        return True
    return any(
        isinstance(row, dict) and row.get("cost_usd") is not None
        for row in payload.get("predictions") or payload.get("rows") or []
    )


def _read_required(path: str | Path) -> str:
    resolved = REPO_ROOT / path if not Path(path).is_absolute() else Path(path)
    return resolved.read_text(encoding="utf-8")


def _render_table_2(path: str | Path) -> str:
    content = _read_required(path)
    return content.replace("# ARR Ablation Results", "# Table 2: Cumulative Ablations", 1)


def _metric(value: Any) -> str:
    if value is None:
        return "N/A"
    if isinstance(value, float):
        return "%.3f" % value
    return str(value)


def _metric_with_ci(row: dict[str, Any], key: str) -> str:
    value = (row.get("summary") or {}).get(key)
    interval = (row.get("confidence_intervals") or {}).get(key) or {}
    if value is None or interval.get("low") is None or interval.get("high") is None:
        return _metric(value)
    return "%s [%s, %s]" % (
        _metric(value),
        _metric(interval.get("low")),
        _metric(interval.get("high")),
    )


def _reported_cost(row: dict[str, Any]) -> str:
    if not bool(row.get("cost_reported")):
        return "N/A"
    return _metric((row.get("summary") or {}).get("cost_per_100_traces_usd"))


def _cell(value: Any) -> str:
    rendered = "N/A" if value is None or value == "" else str(value)
    return rendered.replace("|", "\\|").replace("\n", " ")


def _ids_sha256(cases: list[dict[str, Any]]) -> str:
    return hashlib.sha256(
        "\n".join(str(case.get("id") or "") for case in cases).encode("utf-8")
    ).hexdigest()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git_commit() -> str:
    return repository_revision(REPO_ROOT)


def _portable_path(path: str | Path) -> str:
    resolved = Path(path).resolve()
    try:
        return resolved.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return str(resolved)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Reproduce the four ContextTrace ARR result tables.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--spec", default=str(DEFAULT_SPEC_PATH))
    parser.add_argument("--ragtruth-case-pack", default=None)
    parser.add_argument("--candidate", action="append", default=None)
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Run deterministic harness checks; generated tables are never paper results.",
    )
    args = parser.parse_args(argv)
    result = run_arr_reproduction(
        output_dir=args.output_dir,
        spec_path=args.spec,
        ragtruth_case_pack_path=args.ragtruth_case_pack,
        candidate_paths=args.candidate,
        quick=args.quick,
    )
    print("ARR tables: %s" % len(result["outputs"]["tables"]))
    print("Scope: %s" % result["result_scope"])
    print("Paper result eligible: %s" % result["paper_result_eligible"])
    print("Manifest: %s" % result["outputs"]["manifest"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
