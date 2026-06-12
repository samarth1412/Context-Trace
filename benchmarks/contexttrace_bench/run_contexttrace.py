from __future__ import annotations

import argparse
import json
import random
import sys
import time
from html import escape
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
PACKAGE_ROOT = REPO_ROOT / "packages" / "contexttrace"
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

from contexttrace.verify.benchmark import benchmark_cases, run_verify_benchmark  # noqa: E402
from contexttrace.verify.runner import verify_trace  # noqa: E402
from contexttrace.verify.schema import RAGTrace, TraceCitation, TraceContext, load_trace  # noqa: E402


DEFAULT_LABELS_PATH = Path(__file__).with_name("labels.json")
DEFAULT_OUTPUT_DIR = Path(__file__).with_name("out")
DEFAULT_TARGET_CASES = 500
DEFAULT_BOOTSTRAP_SAMPLES = 400
DEFAULT_BOOTSTRAP_SEED = 20260612
BAD_CITATION_STATUSES = {
    "cited_source_missing",
    "cited_source_does_not_support_claim",
    "claim_supported_by_different_source",
}
VERDICT_NAMES = ("supported", "partially_supported", "unsupported", "contradicted", "unverifiable")
SUMMARY_KEYS = (
    "cases",
    "failure_label_exact_match_rate",
    "failure_label_macro_f1",
    "claim_verdict_macro_f1",
    "claim_verdict_match_rate",
    "root_cause_accuracy",
    "citation_error_precision",
    "citation_error_recall",
    "citation_error_f1",
    "evidence_span_overlap",
    "root_cause_reported_cases",
    "citation_status_reported_cases",
    "evidence_span_reported_cases",
    "latency_p50_ms",
    "latency_p95_ms",
    "cost_per_100_traces_usd",
    "dangerous_false_green_rate",
)
DEFAULT_QUALITY_GATES = {
    "failure_label_macro_f1": (">=", 0.95),
    "claim_verdict_macro_f1": (">=", 0.95),
    "root_cause_accuracy": (">=", 0.90),
    "citation_error_f1": (">=", 0.90),
    "evidence_span_overlap": (">=", 0.75),
    "dangerous_false_green_rate": ("<=", 0.01),
}
CONFIDENCE_INTERVAL_METRICS = (
    "failure_label_macro_f1",
    "claim_verdict_macro_f1",
    "root_cause_accuracy",
    "citation_error_f1",
    "evidence_span_overlap",
    "dangerous_false_green_rate",
)


def run_contexttrace_benchmark(
    *,
    mode: str = "semantic",
    case_set: str = "all",
    case_pack_path: str | Path | None = None,
    labels_path: str | Path = DEFAULT_LABELS_PATH,
    estimated_cost_per_trace_usd: float = 0.0,
    include_generated_cases: bool = True,
    target_cases: int = DEFAULT_TARGET_CASES,
    bootstrap_samples: int = DEFAULT_BOOTSTRAP_SAMPLES,
    bootstrap_seed: int = DEFAULT_BOOTSTRAP_SEED,
) -> dict[str, Any]:
    if case_pack_path is not None:
        return run_contexttrace_case_pack(
            case_pack_path=case_pack_path,
            mode=mode,
            labels_path=labels_path,
            estimated_cost_per_trace_usd=estimated_cost_per_trace_usd,
            bootstrap_samples=bootstrap_samples,
            bootstrap_seed=bootstrap_seed,
        )

    verifier_result = run_verify_benchmark(
        mode=mode,
        case_set=case_set,
        time_cases=True,
    )
    trace_index = _base_trace_index(case_set)
    base_rows = [
        {
            **row,
            "generated": False,
            "variant_type": "curated",
            "base_case_id": str(row.get("id")),
            "trace": trace_index.get(str(row.get("id"))) or {},
        }
        for row in verifier_result.get("rows") or []
    ]
    generated_rows = (
        _generated_rows(
            mode=mode,
            case_set=case_set,
            current_case_count=len(base_rows),
            target_cases=target_cases,
        )
        if include_generated_cases
        else []
    )
    labels = _load_labels(labels_path)
    rows = [
        _enrich_row(row, labels.get(str(row.get("id"))) or {})
        for row in [*base_rows, *generated_rows]
    ]
    verifier_like = _verifier_like_from_rows(rows)
    summary = _summary(
        verifier_like,
        rows,
        estimated_cost_per_trace_usd=estimated_cost_per_trace_usd,
    )
    confidence_intervals = _confidence_intervals(
        rows,
        estimated_cost_per_trace_usd=estimated_cost_per_trace_usd,
        samples=bootstrap_samples,
        seed=bootstrap_seed,
    )
    case_source = verifier_result.get("case_source")
    if generated_rows:
        case_source = "%s plus deterministic generated variants from the same traces" % case_source
    return {
        "benchmark": "ContextTrace-Bench",
        "version": 2,
        "mode": mode,
        "case_set": verifier_result.get("case_set"),
        "case_source": case_source,
        "base_cases": len(base_rows),
        "generated_cases": len(generated_rows),
        "target_cases": target_cases if include_generated_cases else len(base_rows),
        "summary": summary,
        "confidence_intervals": confidence_intervals,
        "per_label": verifier_like["per_label"],
        "rows": rows,
        "labels_path": str(labels_path),
        "verifier_result": {
            key: value
            for key, value in verifier_result.items()
            if key not in {"rows"}
        },
    }


def run_contexttrace_case_pack(
    *,
    case_pack_path: str | Path,
    mode: str = "semantic",
    labels_path: str | Path = DEFAULT_LABELS_PATH,
    estimated_cost_per_trace_usd: float = 0.0,
    bootstrap_samples: int = DEFAULT_BOOTSTRAP_SAMPLES,
    bootstrap_seed: int = DEFAULT_BOOTSTRAP_SEED,
) -> dict[str, Any]:
    payload = _load_case_pack(case_pack_path)
    raw_cases = payload.get("cases") or []
    if not isinstance(raw_cases, list):
        raise ValueError("ContextTrace case pack must contain a cases list.")
    base_rows = [
        _run_case_pack_case(item, mode=mode, dataset=str(payload.get("dataset") or "external_case_pack"))
        for item in raw_cases
        if isinstance(item, dict)
    ]
    labels = _load_labels(labels_path)
    rows = [
        _enrich_row(row, labels.get(str(row.get("id"))) or {})
        for row in base_rows
    ]
    verifier_like = _verifier_like_from_rows(rows)
    summary = _summary(
        verifier_like,
        rows,
        estimated_cost_per_trace_usd=estimated_cost_per_trace_usd,
    )
    confidence_intervals = _confidence_intervals(
        rows,
        estimated_cost_per_trace_usd=estimated_cost_per_trace_usd,
        samples=bootstrap_samples,
        seed=bootstrap_seed,
    )
    return {
        "benchmark": "ContextTrace-Bench",
        "version": 2,
        "mode": mode,
        "case_set": "external_case_pack",
        "case_source": _case_pack_source(payload, case_pack_path),
        "case_pack_path": str(case_pack_path),
        "case_pack_dataset": str(payload.get("dataset") or ""),
        "case_pack_adapter": str(payload.get("adapter") or ""),
        "base_cases": len(base_rows),
        "generated_cases": 0,
        "target_cases": len(base_rows),
        "summary": summary,
        "confidence_intervals": confidence_intervals,
        "per_label": verifier_like["per_label"],
        "rows": rows,
        "labels_path": str(labels_path),
        "verifier_result": {
            "mode": mode,
            "case_set": "external_case_pack",
            "case_source": _case_pack_source(payload, case_pack_path),
            "cases": len(base_rows),
            "exact_match_rate": verifier_like["exact_match_rate"],
            "verdict_match_rate": verifier_like["verdict_match_rate"],
            "per_label": verifier_like["per_label"],
        },
    }


def write_benchmark_outputs(
    result: dict[str, Any],
    *,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    baseline_results: list[dict[str, Any]] | None = None,
) -> dict[str, str]:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    result_path = output_path / "contexttrace_bench_results.json"
    results_md_path = output_path / "results.md"
    leaderboard_path = output_path / "leaderboard.md"
    report_html_path = output_path / "report.html"
    baselines_path = output_path / "baseline_results.json"
    candidate_inputs_path = output_path / "candidate_inputs.jsonl"
    result_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    results_md_path.write_text(render_results_markdown(result), encoding="utf-8")
    leaderboard_path.write_text(render_leaderboard_markdown(result, baseline_results=baseline_results), encoding="utf-8")
    report_html_path.write_text(render_html_report(result, baseline_results=baseline_results), encoding="utf-8")
    candidate_inputs_path.write_text(render_candidate_inputs_jsonl(result), encoding="utf-8")
    paths = {
        "json": str(result_path),
        "results_md": str(results_md_path),
        "leaderboard_md": str(leaderboard_path),
        "report_html": str(report_html_path),
        "candidate_inputs_jsonl": str(candidate_inputs_path),
    }
    if baseline_results is not None:
        baselines_path.write_text(json.dumps(baseline_results, indent=2, sort_keys=True), encoding="utf-8")
        paths["baseline_results_json"] = str(baselines_path)
    elif baselines_path.exists():
        baselines_path.unlink()
    return paths


def score_candidate_predictions(reference_result: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    """Score a third-party or hand-written benchmark candidate against ContextTrace-Bench.

    The candidate format is intentionally small so RAGAS, DeepEval, Phoenix, TruLens,
    or an internal evaluator can be adapted without depending on those packages here.
    """

    predictions = _candidate_prediction_index(candidate)
    rows = []
    for reference_row in reference_result.get("rows") or []:
        prediction = predictions.get(str(reference_row.get("id"))) or {}
        rows.append(_score_candidate_row(reference_row, prediction))

    verifier_like = _verifier_like_from_rows(rows)
    estimated_cost = _candidate_cost_per_trace(candidate, rows)
    summary = _summary(verifier_like, rows, estimated_cost_per_trace_usd=estimated_cost)
    confidence_intervals = _confidence_intervals(
        rows,
        estimated_cost_per_trace_usd=estimated_cost,
    )
    return {
        "benchmark": reference_result.get("benchmark", "ContextTrace-Bench"),
        "system": str(candidate.get("system") or candidate.get("name") or "candidate"),
        "version": str(candidate.get("version") or ""),
        "status": "scored",
        "summary": summary,
        "confidence_intervals": confidence_intervals,
        "per_label": verifier_like["per_label"],
        "coverage": {
            "reference_cases": len(reference_result.get("rows") or []),
            "submitted_predictions": len(predictions),
            "matched_predictions": sum(1 for row in rows if row.get("candidate_reported")),
        },
        "rows": rows,
    }


def load_candidate_predictions(path: str | Path) -> dict[str, Any]:
    candidate_path = Path(path)
    payload = json.loads(candidate_path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError("Candidate prediction file must contain a JSON object.")
    payload.setdefault("candidate_path", str(candidate_path))
    return payload


def score_candidate_file(reference_result: dict[str, Any], path: str | Path) -> dict[str, Any]:
    return score_candidate_predictions(reference_result, load_candidate_predictions(path))


def render_candidate_inputs_jsonl(result: dict[str, Any]) -> str:
    lines = []
    for row in result.get("rows") or []:
        trace = row.get("trace") if isinstance(row.get("trace"), dict) else {}
        lines.append(
            json.dumps(
                {
                    "id": row.get("id"),
                    "source": row.get("source"),
                    "generated": bool(row.get("generated")),
                    "variant_type": row.get("variant_type"),
                    "base_case_id": row.get("base_case_id"),
                    "trace": trace,
                },
                sort_keys=True,
            )
        )
    return "\n".join(lines) + ("\n" if lines else "")


def quality_gate_results(
    result: dict[str, Any],
    gates: dict[str, tuple[str, float]] | None = None,
) -> list[dict[str, Any]]:
    summary = result.get("summary") or {}
    checks = []
    for metric, (operator, threshold) in (gates or DEFAULT_QUALITY_GATES).items():
        value = float(summary.get(metric) or 0.0)
        if operator == ">=":
            passed = value >= threshold
        elif operator == "<=":
            passed = value <= threshold
        else:
            raise ValueError("Unsupported quality gate operator %s." % operator)
        checks.append(
            {
                "metric": metric,
                "value": round(value, 3),
                "operator": operator,
                "threshold": threshold,
                "passed": passed,
            }
        )
    return checks


def quality_gate_failures(
    result: dict[str, Any],
    gates: dict[str, tuple[str, float]] | None = None,
) -> list[str]:
    return [
        "%s %s %s failed with %s"
        % (check["metric"], check["operator"], check["threshold"], check["value"])
        for check in quality_gate_results(result, gates=gates)
        if not check["passed"]
    ]


def render_results_markdown(result: dict[str, Any]) -> str:
    summary = result.get("summary") or {}
    rows = list(result.get("rows") or [])
    lines = [
        "# ContextTrace-Bench Results",
        "",
        "- Benchmark: `%s`" % result.get("benchmark"),
        "- Mode: `%s`" % result.get("mode"),
        "- Case set: `%s`" % result.get("case_set"),
        "- Case source: %s" % result.get("case_source"),
        "",
        "## Summary",
        "",
        "| Metric | Value |",
        "| --- | ---: |",
    ]
    for key in SUMMARY_KEYS:
        lines.append("| `%s` | %s |" % (key, _metric_display(summary.get(key))))

    confidence_rows = _confidence_interval_rows(result)
    lines.extend(
        [
            "",
            "## Confidence Intervals",
            "",
            "| Metric | Estimate | 95% CI | Resamples |",
            "| --- | ---: | ---: | ---: |",
        ]
    )
    if confidence_rows:
        for row in confidence_rows:
            lines.append(
                "| `%s` | %s | %s | %s |"
                % (
                    row["metric"],
                    _metric_display(row["estimate"]),
                    _confidence_interval_display(row),
                    _metric_display(row["samples"]),
                )
            )
    else:
        lines.append("| N/A | N/A | N/A | N/A |")

    per_label_rows = _per_label_rows(result)
    lines.extend(
        [
            "",
            "## Failure Label Breakdown",
            "",
            "| Label | Precision | Recall | F1 | TP | FP | FN |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    if per_label_rows:
        for row in per_label_rows:
            lines.append(
                "| `%s` | %s | %s | %s | %s | %s | %s |"
                % (
                    row["label"],
                    _metric_display(row["precision"]),
                    _metric_display(row["recall"]),
                    _metric_display(row["f1"]),
                    _metric_display(row["tp"]),
                    _metric_display(row["fp"]),
                    _metric_display(row["fn"]),
                )
            )
    else:
        lines.append("| N/A | N/A | N/A | N/A | N/A | N/A | N/A |")

    lines.extend(
        [
            "",
            "## SOTA Readiness Gates",
            "",
            "| Metric | Gate | Value | Status |",
            "| --- | ---: | ---: | --- |",
        ]
    )
    for check in quality_gate_results(result):
        lines.append(
            "| `%s` | `%s %s` | %s | %s |"
            % (
                check["metric"],
                check["operator"],
                check["threshold"],
                check["value"],
                "pass" if check["passed"] else "fail",
            )
        )

    misses = [row for row in rows if not row.get("benchmark_pass")]
    lines.extend(
        [
            "",
            "## Misses",
            "",
        ]
    )
    if not misses:
        lines.append("No benchmark misses under the current labeled checks.")
    else:
        lines.extend(["| Case | Expected | Predicted | Root Cause |", "| --- | --- | --- | --- |"])
        for row in misses:
            lines.append(
                "| `%s` | `%s` | `%s` | `%s -> %s` |"
                % (
                    row.get("id"),
                    ", ".join(row.get("expected") or []),
                    ", ".join(row.get("predicted") or []),
                    row.get("expected_primary_root_cause") or "",
                    row.get("predicted_primary_root_cause") or "",
                )
            )
    lines.append("")
    return "\n".join(lines)


def render_leaderboard_markdown(
    result: dict[str, Any],
    *,
    baseline_results: list[dict[str, Any]] | None = None,
) -> str:
    summary = result.get("summary") or {}
    baselines = baseline_results or []
    lines = [
        "# ContextTrace-Bench Leaderboard",
        "",
        "| System | Mode | Cases | Failure Macro-F1 | Root Cause Accuracy | Citation Error F1 | Span Overlap | Latency p95 ms | Cost / 100 |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        _leaderboard_markdown_row(
            "ContextTrace",
            result.get("mode"),
            summary,
        ),
    ]
    for baseline in baselines:
        lines.append(
            _leaderboard_markdown_row(
                str(baseline.get("system") or "candidate"),
                str(baseline.get("version") or "candidate"),
                baseline.get("summary") or {},
            )
        )
    lines.extend(
        [
            "",
            "`N/A` means the candidate did not report that diagnostic field; it is not counted as an attempted failure.",
            "",
            "## Diagnostic Coverage",
            "",
            "| System | Root Cause Reported | Citation Status Reported | Evidence Spans Reported |",
            "| --- | ---: | ---: | ---: |",
            _diagnostic_coverage_markdown_row("ContextTrace", summary),
        ]
    )
    for baseline in baselines:
        lines.append(
            _diagnostic_coverage_markdown_row(
                str(baseline.get("system") or "candidate"),
                baseline.get("summary") or {},
            )
        )
    lines.extend(
        [
            "",
            "Competitor rows are valid only when produced from a candidate prediction JSON scored by this harness. Shared faithfulness-style metrics are directly comparable; diagnostic attribution metrics require the candidate to report that field.",
            "",
        ]
    )
    return "\n".join(lines)


def render_html_report(
    result: dict[str, Any],
    *,
    baseline_results: list[dict[str, Any]] | None = None,
) -> str:
    summary = result.get("summary") or {}
    misses = [row for row in result.get("rows") or [] if not row.get("benchmark_pass")]
    return HTML_TEMPLATE.format(
        benchmark=escape(str(result.get("benchmark") or "")),
        mode=escape(str(result.get("mode") or "")),
        case_set=escape(str(result.get("case_set") or "")),
        case_source=escape(str(result.get("case_source") or "")),
        summary_cards=_html_summary_cards(summary),
        confidence_interval_rows=_html_confidence_interval_rows(result),
        per_label_rows=_html_per_label_rows(result),
        gate_rows=_html_gate_rows(quality_gate_results(result)),
        leaderboard_rows=_html_leaderboard_rows(result, baseline_results or []),
        diagnostic_coverage_rows=_html_diagnostic_coverage_rows(result, baseline_results or []),
        misses=_html_misses(misses),
        case_rows=_html_case_rows(result.get("rows") or []),
        raw_json=escape(json.dumps(_raw_report_summary(result), indent=2, sort_keys=True)),
    )


def _leaderboard_markdown_row(system: str, mode: Any, summary: dict[str, Any]) -> str:
    return "| %s | `%s` | %s | %s | %s | %s | %s | %s | %s |" % (
        system,
        mode,
        _metric_display(summary.get("cases")),
        _metric_display(summary.get("failure_label_macro_f1")),
        _metric_display(summary.get("root_cause_accuracy")),
        _metric_display(summary.get("citation_error_f1")),
        _metric_display(summary.get("evidence_span_overlap")),
        _metric_display(summary.get("latency_p95_ms")),
        _metric_display(summary.get("cost_per_100_traces_usd")),
    )


def _diagnostic_coverage_markdown_row(system: str, summary: dict[str, Any]) -> str:
    return "| %s | %s | %s | %s |" % (
        system,
        _coverage_display(summary, "root_cause_reported_cases"),
        _coverage_display(summary, "citation_status_reported_cases"),
        _coverage_display(summary, "evidence_span_reported_cases"),
    )


def _coverage_display(summary: dict[str, Any], field: str) -> str:
    reported = summary.get(field)
    cases = summary.get("cases")
    if reported is None:
        return "N/A"
    if cases is None:
        return str(reported)
    return "%s / %s" % (reported, cases)


def _confidence_interval_rows(result: dict[str, Any]) -> list[dict[str, Any]]:
    intervals = result.get("confidence_intervals") or {}
    rows = []
    for metric in CONFIDENCE_INTERVAL_METRICS:
        interval = intervals.get(metric)
        if not isinstance(interval, dict):
            continue
        rows.append(
            {
                "metric": metric,
                "estimate": interval.get("estimate"),
                "low": interval.get("low"),
                "high": interval.get("high"),
                "samples": interval.get("samples"),
            }
        )
    return rows


def _confidence_interval_display(row: dict[str, Any]) -> str:
    low = row.get("low")
    high = row.get("high")
    if low is None or high is None:
        return "N/A"
    return "%s to %s" % (_metric_display(low), _metric_display(high))


def _per_label_rows(result: dict[str, Any]) -> list[dict[str, Any]]:
    per_label = result.get("per_label") or _per_label_metrics(result.get("rows") or [])
    rows = []
    for label, metrics in sorted(per_label.items()):
        rows.append(
            {
                "label": label,
                "precision": metrics.get("precision"),
                "recall": metrics.get("recall"),
                "f1": metrics.get("f1"),
                "tp": metrics.get("tp"),
                "fp": metrics.get("fp"),
                "fn": metrics.get("fn"),
            }
        )
    return rows


def _candidate_prediction_index(candidate: dict[str, Any]) -> dict[str, dict[str, Any]]:
    raw_predictions = candidate.get("predictions") or candidate.get("rows") or []
    if not isinstance(raw_predictions, list):
        raise ValueError("Candidate predictions must be a list.")
    predictions = {}
    for prediction in raw_predictions:
        if not isinstance(prediction, dict):
            continue
        case_id = prediction.get("id") or prediction.get("case_id")
        if case_id is None:
            continue
        predictions[str(case_id)] = prediction
    return predictions


def _score_candidate_row(reference_row: dict[str, Any], prediction: dict[str, Any]) -> dict[str, Any]:
    predicted_labels = _candidate_predicted_labels(prediction)
    expected_labels = [str(label) for label in reference_row.get("expected") or []]
    expected_citations = [str(status) for status in reference_row.get("expected_citation_statuses") or []]
    citation_reported = _candidate_reported_any(prediction, ("predicted_citation_statuses", "citation_statuses"))
    predicted_citations = (
        [str(status) for status in prediction.get("predicted_citation_statuses") or prediction.get("citation_statuses") or []]
        if citation_reported
        else []
    )
    expected_root = str(reference_row.get("expected_primary_root_cause") or "")
    root_reported = _candidate_reported_any(prediction, ("predicted_primary_root_cause", "primary_root_cause", "root_cause"))
    predicted_root = (
        str(prediction.get("predicted_primary_root_cause") or prediction.get("primary_root_cause") or prediction.get("root_cause") or "")
        if root_reported
        else "not_reported"
    )
    expected_spans = [str(span) for span in reference_row.get("expected_evidence_spans") or []]
    span_reported = _candidate_reported_any(prediction, ("predicted_evidence_spans", "evidence_spans"))
    predicted_spans = (
        [str(span) for span in prediction.get("predicted_evidence_spans") or prediction.get("evidence_spans") or []]
        if span_reported
        else []
    )
    expected_verdict_counts = dict(reference_row.get("expected_verdict_counts") or {})
    predicted_verdict_counts = _candidate_verdict_counts(prediction)
    root_cause_match = (predicted_root == expected_root) if expected_root and root_reported else None
    span_overlap = _span_overlap(expected_spans, predicted_spans) if span_reported else None
    citation_counts = _citation_error_counts(expected_citations, predicted_citations) if citation_reported else None
    benchmark_pass = set(expected_labels) == set(predicted_labels)
    benchmark_pass = benchmark_pass and _counts_match(expected_verdict_counts, predicted_verdict_counts)
    if root_cause_match is not None:
        benchmark_pass = benchmark_pass and bool(root_cause_match)
    if expected_citations and citation_reported:
        benchmark_pass = benchmark_pass and expected_citations == predicted_citations
    return {
        "id": reference_row.get("id"),
        "candidate_reported": bool(prediction),
        "root_cause_reported": root_reported,
        "citation_statuses_reported": citation_reported,
        "evidence_spans_reported": span_reported,
        "expected": sorted(expected_labels),
        "predicted": sorted(predicted_labels),
        "exact_match": set(expected_labels) == set(predicted_labels),
        "expected_verdict_counts": expected_verdict_counts,
        "predicted_verdict_counts": predicted_verdict_counts,
        "verdict_match": _counts_match(expected_verdict_counts, predicted_verdict_counts),
        "expected_citation_statuses": expected_citations,
        "predicted_citation_statuses": predicted_citations,
        "citation_match": (expected_citations == predicted_citations) if expected_citations else None,
        "expected_primary_root_cause": expected_root,
        "predicted_primary_root_cause": predicted_root,
        "root_cause_match": root_cause_match,
        "expected_evidence_spans": expected_spans,
        "predicted_evidence_spans": predicted_spans,
        "evidence_span_overlap": span_overlap,
        "citation_error_counts": citation_counts,
        "latency_ms": prediction.get("latency_ms"),
        "cost_usd": prediction.get("cost_usd"),
        "benchmark_pass": benchmark_pass,
    }


def _candidate_reported_any(prediction: dict[str, Any], fields: tuple[str, ...]) -> bool:
    return any(field in prediction for field in fields)


def _candidate_predicted_labels(prediction: dict[str, Any]) -> list[str]:
    labels = prediction.get("predicted")
    if labels is None:
        labels = prediction.get("predicted_labels")
    if labels is None:
        labels = prediction.get("failure_labels")
    if labels is None:
        label = prediction.get("failure_label")
        labels = [label] if label else []
    if isinstance(labels, str):
        labels = [labels]
    normalized = [str(label) for label in labels or [] if str(label).strip()]
    return normalized or ["no_failure_detected"]


def _candidate_verdict_counts(prediction: dict[str, Any]) -> dict[str, int]:
    counts = prediction.get("predicted_verdict_counts") or prediction.get("verdict_counts") or {}
    output = {verdict: int(counts.get(verdict) or 0) for verdict in VERDICT_NAMES}
    verdicts = prediction.get("predicted_verdicts") or prediction.get("verdicts") or []
    if isinstance(verdicts, str):
        verdicts = [verdicts]
    for verdict in verdicts or []:
        key = str(verdict)
        if key in output:
            output[key] += 1
    return output


def _candidate_cost_per_trace(candidate: dict[str, Any], rows: list[dict[str, Any]]) -> float:
    explicit = candidate.get("estimated_cost_per_trace_usd")
    if explicit is not None:
        return float(explicit)
    costs = [float(row.get("cost_usd") or 0.0) for row in rows if row.get("cost_usd") is not None]
    return sum(costs) / len(costs) if costs else 0.0


def _verifier_like_from_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "exact_match_rate": _rate([bool(row.get("exact_match")) for row in rows]),
        "verdict_match_rate": _rate([bool(row.get("verdict_match")) for row in rows]),
        "per_label": _per_label_metrics(rows),
    }


def _confidence_intervals(
    rows: list[dict[str, Any]],
    *,
    estimated_cost_per_trace_usd: float,
    samples: int = DEFAULT_BOOTSTRAP_SAMPLES,
    seed: int = DEFAULT_BOOTSTRAP_SEED,
) -> dict[str, dict[str, Any]]:
    if not rows or int(samples or 0) <= 0:
        return {}

    rng = random.Random(seed)
    sample_count = int(samples)
    metric_values: dict[str, list[float]] = {metric: [] for metric in CONFIDENCE_INTERVAL_METRICS}
    for _ in range(sample_count):
        sample_rows = [rows[rng.randrange(len(rows))] for _ in rows]
        sample_summary = _summary(
            _verifier_like_from_rows(sample_rows),
            sample_rows,
            estimated_cost_per_trace_usd=estimated_cost_per_trace_usd,
        )
        for metric in CONFIDENCE_INTERVAL_METRICS:
            value = sample_summary.get(metric)
            if value is not None:
                metric_values[metric].append(float(value))

    point_summary = _summary(
        _verifier_like_from_rows(rows),
        rows,
        estimated_cost_per_trace_usd=estimated_cost_per_trace_usd,
    )
    intervals: dict[str, dict[str, Any]] = {}
    for metric, values in metric_values.items():
        estimate = point_summary.get(metric)
        if estimate is None or not values:
            continue
        intervals[metric] = {
            "estimate": estimate,
            "low": _percentile(values, 2.5),
            "high": _percentile(values, 97.5),
            "level": 0.95,
            "method": "case_bootstrap",
            "samples": len(values),
            "seed": seed,
        }
    return intervals


def _per_label_metrics(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    labels = sorted(
        {
            str(label)
            for row in rows
            for label in [*(row.get("expected") or []), *(row.get("predicted") or [])]
        }
    )
    metrics = {}
    for label in labels:
        tp = sum(1 for row in rows if label in row.get("expected", []) and label in row.get("predicted", []))
        fp = sum(1 for row in rows if label not in row.get("expected", []) and label in row.get("predicted", []))
        fn = sum(1 for row in rows if label in row.get("expected", []) and label not in row.get("predicted", []))
        precision = _precision(tp, fp)
        recall = _recall(tp, fn)
        metrics[label] = {
            "tp": tp,
            "fp": fp,
            "fn": fn,
            "precision": precision,
            "recall": recall,
            "f1": _f1(precision, recall),
        }
    return metrics


def _html_summary_cards(summary: dict[str, Any]) -> str:
    cards = [
        ("Cases", summary.get("cases")),
        ("Failure Macro-F1", summary.get("failure_label_macro_f1")),
        ("Verdict Macro-F1", summary.get("claim_verdict_macro_f1")),
        ("Root Cause Accuracy", summary.get("root_cause_accuracy")),
        ("Citation Error F1", summary.get("citation_error_f1")),
        ("Evidence Span Overlap", summary.get("evidence_span_overlap")),
        ("Dangerous False Green", summary.get("dangerous_false_green_rate")),
        ("Latency p95 ms", summary.get("latency_p95_ms")),
    ]
    return "\n".join(
        """
        <div class="card">
          <div class="label">{label}</div>
          <div class="value">{value}</div>
        </div>
        """.format(label=escape(str(label)), value=escape(_metric_display(value)))
        for label, value in cards
    )


def _html_confidence_interval_rows(result: dict[str, Any]) -> str:
    rows = _confidence_interval_rows(result)
    if not rows:
        return "<tr><td colspan=\"4\" class=\"muted\">No confidence intervals were computed.</td></tr>"
    return "\n".join(
        """
        <tr>
          <td>{metric}</td>
          <td>{estimate}</td>
          <td>{interval}</td>
          <td>{samples}</td>
        </tr>
        """.format(
            metric=escape(str(row["metric"])),
            estimate=escape(_metric_display(row["estimate"])),
            interval=escape(_confidence_interval_display(row)),
            samples=escape(_metric_display(row["samples"])),
        )
        for row in rows
    )


def _html_per_label_rows(result: dict[str, Any]) -> str:
    rows = _per_label_rows(result)
    if not rows:
        return "<tr><td colspan=\"7\" class=\"muted\">No label metrics.</td></tr>"
    return "\n".join(
        """
        <tr>
          <td>{label}</td>
          <td>{precision}</td>
          <td>{recall}</td>
          <td>{f1}</td>
          <td>{tp}</td>
          <td>{fp}</td>
          <td>{fn}</td>
        </tr>
        """.format(
            label=escape(str(row["label"])),
            precision=escape(_metric_display(row["precision"])),
            recall=escape(_metric_display(row["recall"])),
            f1=escape(_metric_display(row["f1"])),
            tp=escape(_metric_display(row["tp"])),
            fp=escape(_metric_display(row["fp"])),
            fn=escape(_metric_display(row["fn"])),
        )
        for row in rows
    )


def _html_gate_rows(checks: list[dict[str, Any]]) -> str:
    return "\n".join(
        """
        <tr>
          <td>{metric}</td>
          <td>{gate}</td>
          <td>{value}</td>
          <td><span class="badge {status}">{status}</span></td>
        </tr>
        """.format(
            metric=escape(str(check["metric"])),
            gate=escape("%s %s" % (check["operator"], check["threshold"])),
            value=escape(str(check["value"])),
            status="pass" if check["passed"] else "fail",
        )
        for check in checks
    )


def _html_leaderboard_rows(result: dict[str, Any], baseline_results: list[dict[str, Any]]) -> str:
    rows = [_html_leaderboard_row("ContextTrace", result.get("mode"), result.get("summary") or {})]
    for baseline in baseline_results:
        rows.append(_html_leaderboard_row(baseline.get("system"), baseline.get("version") or "candidate", baseline.get("summary") or {}))
    return "\n".join(rows)


def _html_leaderboard_row(system: Any, mode: Any, summary: dict[str, Any]) -> str:
    return """
    <tr>
      <td>{system}</td>
      <td>{mode}</td>
      <td>{cases}</td>
      <td>{failure_f1}</td>
      <td>{root}</td>
      <td>{citation}</td>
      <td>{span}</td>
      <td>{latency}</td>
    </tr>
    """.format(
        system=escape(str(system or "")),
        mode=escape(str(mode or "")),
        cases=escape(_metric_display(summary.get("cases"))),
        failure_f1=escape(_metric_display(summary.get("failure_label_macro_f1"))),
        root=escape(_metric_display(summary.get("root_cause_accuracy"))),
        citation=escape(_metric_display(summary.get("citation_error_f1"))),
        span=escape(_metric_display(summary.get("evidence_span_overlap"))),
        latency=escape(_metric_display(summary.get("latency_p95_ms"))),
    )


def _html_diagnostic_coverage_rows(result: dict[str, Any], baseline_results: list[dict[str, Any]]) -> str:
    rows = [_html_diagnostic_coverage_row("ContextTrace", result.get("summary") or {})]
    for baseline in baseline_results:
        rows.append(_html_diagnostic_coverage_row(baseline.get("system"), baseline.get("summary") or {}))
    return "\n".join(rows)


def _html_diagnostic_coverage_row(system: Any, summary: dict[str, Any]) -> str:
    return """
    <tr>
      <td>{system}</td>
      <td>{root}</td>
      <td>{citation}</td>
      <td>{span}</td>
    </tr>
    """.format(
        system=escape(str(system or "")),
        root=escape(_coverage_display(summary, "root_cause_reported_cases")),
        citation=escape(_coverage_display(summary, "citation_status_reported_cases")),
        span=escape(_coverage_display(summary, "evidence_span_reported_cases")),
    )


def _html_case_rows(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "<tr><td colspan=\"8\" class=\"muted\">No cases were run.</td></tr>"
    return "\n".join(
        """
        <tr>
          <td><span class="badge {status}">{status}</span></td>
          <td>{case_id}</td>
          <td>{expected}</td>
          <td>{predicted}</td>
          <td>{expected_root}</td>
          <td>{predicted_root}</td>
          <td>{span}</td>
          <td>{latency}</td>
        </tr>
        """.format(
            status="pass" if row.get("benchmark_pass") else "fail",
            case_id=escape(str(row.get("id"))),
            expected=escape(", ".join(row.get("expected") or [])),
            predicted=escape(", ".join(row.get("predicted") or [])),
            expected_root=escape(str(row.get("expected_primary_root_cause") or "")),
            predicted_root=escape(str(row.get("predicted_primary_root_cause") or "")),
            span=escape(str(row.get("evidence_span_overlap"))),
            latency=escape(str(row.get("latency_ms") if row.get("latency_ms") is not None else "")),
        )
        for row in rows
    )


def _html_misses(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "<p class=\"muted\">No benchmark misses under the current labeled checks.</p>"
    cards = []
    for row in rows:
        cards.append(
            """
            <article class="item">
              <div class="item-meta">{case_id}</div>
              <p><strong>Expected labels:</strong> {expected}</p>
              <p><strong>Predicted labels:</strong> {predicted}</p>
              <p><strong>Expected root cause:</strong> {expected_root}</p>
              <p><strong>Predicted root cause:</strong> {predicted_root}</p>
              <p><strong>Expected spans:</strong> {expected_spans}</p>
              <p><strong>Predicted spans:</strong> {predicted_spans}</p>
            </article>
            """.format(
                case_id=escape(str(row.get("id"))),
                expected=escape(", ".join(row.get("expected") or [])),
                predicted=escape(", ".join(row.get("predicted") or [])),
                expected_root=escape(str(row.get("expected_primary_root_cause") or "")),
                predicted_root=escape(str(row.get("predicted_primary_root_cause") or "")),
                expected_spans=escape(" | ".join(row.get("expected_evidence_spans") or []) or "none"),
                predicted_spans=escape(" | ".join(row.get("predicted_evidence_spans") or []) or "none"),
            )
        )
    return "\n".join(cards)


def _raw_report_summary(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "benchmark": result.get("benchmark"),
        "mode": result.get("mode"),
        "case_set": result.get("case_set"),
        "base_cases": result.get("base_cases"),
        "generated_cases": result.get("generated_cases"),
        "summary": result.get("summary"),
        "confidence_intervals": result.get("confidence_intervals"),
        "per_label": result.get("per_label"),
        "quality_gates": quality_gate_results(result),
        "misses": [
            {
                "id": row.get("id"),
                "expected": row.get("expected"),
                "predicted": row.get("predicted"),
                "expected_primary_root_cause": row.get("expected_primary_root_cause"),
                "predicted_primary_root_cause": row.get("predicted_primary_root_cause"),
            }
            for row in result.get("rows") or []
            if not row.get("benchmark_pass")
        ],
    }


def _base_trace_index(case_set: str) -> dict[str, dict[str, Any]]:
    return {
        case.id: case.trace.to_dict()
        for case in benchmark_cases(case_set=case_set)
    }


def _generated_rows(
    *,
    mode: str,
    case_set: str,
    current_case_count: int,
    target_cases: int,
) -> list[dict[str, Any]]:
    needed = max(int(target_cases) - current_case_count, 0)
    if needed <= 0:
        return []

    cases = benchmark_cases(case_set=case_set)
    supported_cases = [
        case
        for case in cases
        if set(case.expected_labels) == {"no_failure_detected"} and case.trace.contexts
    ]
    distractors = [
        context
        for case in cases
        for context in case.trace.contexts
    ]

    generated: list[dict[str, Any]] = []
    builders = (
        _uncited_supported_variant,
        _no_context_variant,
        _missing_citation_variant,
        _wrong_source_citation_variant,
        _stale_source_variant,
        _low_authority_source_variant,
    )
    for case in supported_cases:
        for builder in builders:
            if len(generated) >= needed:
                return generated
            variant = builder(case, distractors)
            if variant is None:
                continue
            generated.append(_run_generated_variant(variant, mode=mode))

    for case in supported_cases:
        for index, distractor in enumerate(_distractors_for_case(case, distractors)):
            if len(generated) >= needed:
                return generated
            variant = _distractor_only_context_variant(case, distractor, index)
            generated.append(_run_generated_variant(variant, mode=mode))
    return generated


def _load_case_pack(path: str | Path) -> dict[str, Any]:
    case_pack_path = Path(path)
    payload = json.loads(case_pack_path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError("ContextTrace case pack must be a JSON object.")
    return payload


def _case_pack_source(payload: dict[str, Any], path: str | Path) -> str:
    description = str(payload.get("description") or "").strip()
    dataset = str(payload.get("dataset") or "external case pack").strip()
    if description:
        return "%s from %s" % (description, path)
    return "%s from %s" % (dataset, path)


def _run_case_pack_case(item: dict[str, Any], *, mode: str, dataset: str) -> dict[str, Any]:
    trace = _trace_from_case_pack_item(item, dataset=dataset)
    started = time.perf_counter()
    result = verify_trace(trace, mode=mode)
    latency_ms = round((time.perf_counter() - started) * 1000, 3)
    predicted = _predicted_labels_from_result(result)
    expected = {str(label) for label in item.get("expected_labels") or item.get("expected") or []}
    expected = expected or {"no_failure_detected"}
    expected_verdict_counts = _expected_verdict_counts_from_item(item, expected)
    predicted_verdict_counts = {
        verdict: int((result.get("summary") or {}).get(verdict) or 0)
        for verdict in VERDICT_NAMES
    }
    expected_citations = [str(status) for status in item.get("expected_citation_statuses") or []]
    predicted_citations = [
        str(claim.get("citation_status"))
        for claim in result.get("claims") or []
        if claim.get("citation_status")
    ]
    expected_abstain = item.get("expected_should_abstain")
    predicted_abstain = bool((result.get("abstention") or {}).get("should_abstain"))
    return {
        "id": str(item.get("id") or ""),
        "source": str(item.get("source") or dataset),
        "note": str(item.get("note") or ""),
        "generated": False,
        "variant_type": "external_case_pack",
        "base_case_id": str(item.get("id") or ""),
        "trace": trace.to_dict(),
        "expected": sorted(expected),
        "predicted": sorted(predicted),
        "exact_match": predicted == expected,
        "expected_verdict_counts": expected_verdict_counts,
        "predicted_verdict_counts": {
            key: value for key, value in sorted(predicted_verdict_counts.items())
        },
        "verdict_match": _counts_match(expected_verdict_counts, predicted_verdict_counts),
        "expected_citation_statuses": expected_citations,
        "predicted_citation_statuses": predicted_citations,
        "citation_match": (expected_citations == predicted_citations) if expected_citations else None,
        "expected_should_abstain": expected_abstain,
        "predicted_should_abstain": predicted_abstain,
        "abstention_match": (expected_abstain == predicted_abstain) if expected_abstain is not None else None,
        "expected_primary_root_cause": str(
            item.get("expected_primary_root_cause")
            or _derive_expected_root_cause(
                {
                    "expected": sorted(expected),
                    "expected_citation_statuses": expected_citations,
                }
            )
        ),
        "expected_evidence_spans": [str(span) for span in item.get("expected_evidence_spans") or []],
        "summary": result.get("summary") or {},
        "claims": result.get("claims") or [],
        "abstention": result.get("abstention") or {},
        "latency_ms": latency_ms,
        "case_pack_metadata": _case_pack_metadata(item),
    }


def _trace_from_case_pack_item(item: dict[str, Any], *, dataset: str) -> RAGTrace:
    trace_payload = {
        "query": str(item.get("query") or ""),
        "answer": str(item.get("answer") or ""),
        "contexts": [
            _case_pack_context(context)
            for context in item.get("contexts") or []
            if isinstance(context, dict)
        ],
        "citations": [
            _case_pack_citation(citation)
            for citation in item.get("citations") or []
            if isinstance(citation, dict)
        ],
        "metadata": {
            "benchmark_case_id": str(item.get("id") or ""),
            "benchmark_source": str(item.get("source") or dataset),
            "external_case_pack": True,
            "external_case_pack_dataset": dataset,
        },
    }
    return load_trace(trace_payload, source="case pack case %s" % str(item.get("id") or "unknown"))


def _case_pack_context(context: dict[str, Any]) -> dict[str, Any]:
    metadata = dict(context.get("metadata") or {})
    metadata.update(
        {
            key: value
            for key, value in context.items()
            if key not in {"id", "text", "metadata"}
        }
    )
    return {
        "id": str(context.get("id") or ""),
        "text": str(context.get("text") or ""),
        "metadata": metadata,
    }


def _case_pack_citation(citation: dict[str, Any]) -> dict[str, Any]:
    metadata = dict(citation.get("metadata") or {})
    metadata.update(
        {
            key: value
            for key, value in citation.items()
            if key not in {"claim", "source_id", "source_chunk_id", "chunk_id", "metadata"}
        }
    )
    payload = {
        "claim": str(citation.get("claim") or ""),
        "source_id": str(citation.get("source_id") or citation.get("source_chunk_id") or citation.get("chunk_id") or ""),
    }
    if metadata:
        payload["metadata"] = metadata
    return payload


def _case_pack_metadata(item: dict[str, Any]) -> dict[str, Any]:
    metadata = {
        key: value
        for key, value in item.items()
        if key.endswith("_metadata") or key in {"dataset_metadata"}
    }
    return metadata


def _expected_verdict_counts_from_item(item: dict[str, Any], expected: set[str]) -> dict[str, int]:
    raw_counts = item.get("expected_verdict_counts") or {}
    counts = {verdict: int(raw_counts.get(verdict) or 0) for verdict in VERDICT_NAMES}
    if any(counts.values()):
        return counts
    if "contradicted_answer" in expected:
        counts["contradicted"] = 1
    elif "partial_support" in expected:
        counts["partially_supported"] = 1
    elif "unsupported_answer" in expected or "should_have_abstained" in expected:
        counts["unsupported"] = 1
    else:
        counts["supported"] = 1
    return counts


def _uncited_supported_variant(case: Any, distractors: list[Any]) -> dict[str, Any] | None:
    if not case.trace.contexts:
        return None
    return {
        "id": "%s__generated_uncited_supported" % case.id,
        "base_case_id": case.id,
        "variant_type": "generated_uncited_supported",
        "source": "generated from %s" % case.source,
        "note": "The original supported answer is replayed without citations; missing citations are tracked but are not grounding failures.",
        "trace": RAGTrace(
            query=case.trace.query,
            answer=case.trace.answer,
            contexts=list(case.trace.contexts),
            citations=[],
            metadata=_generated_metadata(case, "generated_uncited_supported"),
        ),
        "expected_labels": {"no_failure_detected"},
        "expected_verdict_counts": dict(case.expected_verdict_counts),
        "expected_citation_statuses": [],
        "expected_should_abstain": False,
        "expected_primary_root_cause": "no_failure_detected",
        "expected_evidence_spans": _context_texts(case.trace.contexts),
    }


def _no_context_variant(case: Any, distractors: list[Any]) -> dict[str, Any] | None:
    claim_count = _expected_claim_count(case)
    return {
        "id": "%s__generated_no_context" % case.id,
        "base_case_id": case.id,
        "variant_type": "generated_no_context",
        "source": "generated from %s" % case.source,
        "note": "The original supported answer is replayed with no retrieved context.",
        "trace": RAGTrace(
            query=case.trace.query,
            answer=case.trace.answer,
            contexts=[],
            metadata=_generated_metadata(case, "generated_no_context"),
        ),
        "expected_labels": {"should_have_abstained", "unsupported_answer"},
        "expected_verdict_counts": {"unsupported": claim_count},
        "expected_citation_statuses": [],
        "expected_should_abstain": True,
        "expected_primary_root_cause": "should_have_abstained",
        "expected_evidence_spans": [],
    }


def _missing_citation_variant(case: Any, distractors: list[Any]) -> dict[str, Any] | None:
    claim_count = _expected_claim_count(case)
    if not case.trace.contexts:
        return None
    return {
        "id": "%s__generated_missing_citation" % case.id,
        "base_case_id": case.id,
        "variant_type": "generated_missing_citation",
        "source": "generated from %s" % case.source,
        "note": "The original supported answer cites a source ID that is absent from the retrieved contexts.",
        "trace": RAGTrace(
            query=case.trace.query,
            answer=case.trace.answer,
            contexts=list(case.trace.contexts),
            citations=[
                TraceCitation(
                    claim=case.trace.answer,
                    source_id="%s_missing_source" % case.id,
                )
            ],
            metadata=_generated_metadata(case, "generated_missing_citation"),
        ),
        "expected_labels": {"citation_mismatch"},
        "expected_verdict_counts": dict(case.expected_verdict_counts),
        "expected_citation_statuses": ["cited_source_missing"] * claim_count,
        "expected_should_abstain": False,
        "expected_primary_root_cause": "missing_cited_source",
        "expected_evidence_spans": _context_texts(case.trace.contexts),
    }


def _wrong_source_citation_variant(case: Any, distractors: list[Any]) -> dict[str, Any] | None:
    claim_count = _expected_claim_count(case)
    distractor = _find_distractor(case, distractors)
    if distractor is None:
        return None
    return {
        "id": "%s__generated_wrong_source_citation" % case.id,
        "base_case_id": case.id,
        "variant_type": "generated_wrong_source_citation",
        "source": "generated from %s" % case.source,
        "note": "The original supported answer is cited to a retrieved but unrelated source.",
        "trace": RAGTrace(
            query=case.trace.query,
            answer=case.trace.answer,
            contexts=[*case.trace.contexts, distractor],
            citations=[
                TraceCitation(
                    claim=case.trace.answer,
                    source_id=distractor.id,
                )
            ],
            metadata=_generated_metadata(case, "generated_wrong_source_citation"),
        ),
        "expected_labels": {"citation_mismatch"},
        "expected_verdict_counts": dict(case.expected_verdict_counts),
        "expected_citation_statuses": ["claim_supported_by_different_source"] * claim_count,
        "expected_should_abstain": False,
        "expected_primary_root_cause": "wrong_source_cited",
        "expected_evidence_spans": _context_texts(case.trace.contexts),
    }


def _stale_source_variant(case: Any, distractors: list[Any]) -> dict[str, Any] | None:
    if not case.trace.contexts:
        return None
    return {
        "id": "%s__generated_stale_source" % case.id,
        "base_case_id": case.id,
        "variant_type": "generated_stale_source",
        "source": "generated from %s" % case.source,
        "note": "The original supported answer is grounded, but the source is explicitly marked stale.",
        "trace": RAGTrace(
            query=case.trace.query,
            answer=case.trace.answer,
            contexts=[
                TraceContext(
                    id=context.id,
                    text=context.text,
                    metadata={**context.metadata, "source_status": "stale_source"},
                )
                for context in case.trace.contexts
            ],
            citations=list(case.trace.citations),
            metadata=_generated_metadata(case, "generated_stale_source"),
        ),
        "expected_labels": {"stale_source"},
        "expected_verdict_counts": dict(case.expected_verdict_counts),
        "expected_citation_statuses": list(case.expected_citation_statuses),
        "expected_should_abstain": False,
        "expected_primary_root_cause": "stale_context",
        "expected_evidence_spans": _context_texts(case.trace.contexts),
    }


def _low_authority_source_variant(case: Any, distractors: list[Any]) -> dict[str, Any] | None:
    if not case.trace.contexts:
        return None
    return {
        "id": "%s__generated_low_authority_source" % case.id,
        "base_case_id": case.id,
        "variant_type": "generated_low_authority_source",
        "source": "generated from %s" % case.source,
        "note": "The original supported answer is grounded, but the source is marked low authority.",
        "trace": RAGTrace(
            query=case.trace.query,
            answer=case.trace.answer,
            contexts=[
                TraceContext(
                    id=context.id,
                    text=context.text,
                    metadata={**context.metadata, "source_authority": "low"},
                )
                for context in case.trace.contexts
            ],
            citations=list(case.trace.citations),
            metadata=_generated_metadata(case, "generated_low_authority_source"),
        ),
        "expected_labels": {"low_authority_source"},
        "expected_verdict_counts": dict(case.expected_verdict_counts),
        "expected_citation_statuses": list(case.expected_citation_statuses),
        "expected_should_abstain": False,
        "expected_primary_root_cause": "low_authority_source",
        "expected_evidence_spans": _context_texts(case.trace.contexts),
    }


def _distractor_only_context_variant(case: Any, distractor: Any, index: int) -> dict[str, Any]:
    claim_count = _expected_claim_count(case)
    variant_type = "generated_distractor_only_context"
    return {
        "id": "%s__%s_%03d" % (case.id, variant_type, index),
        "base_case_id": case.id,
        "variant_type": variant_type,
        "source": "generated from %s with distractor %s" % (case.source, distractor.id),
        "note": "The original supported answer is replayed with only unrelated retrieved context.",
        "trace": RAGTrace(
            query=case.trace.query,
            answer=case.trace.answer,
            contexts=[
                TraceContext(
                    id="%s__distractor_%03d" % (distractor.id, index),
                    text=distractor.text,
                    metadata={**distractor.metadata, "benchmark_distractor": True},
                )
            ],
            citations=[],
            metadata={
                **_generated_metadata(case, variant_type),
                "benchmark_distractor_source_id": distractor.id,
                "benchmark_distractor_index": index,
            },
        ),
        "expected_labels": {"should_have_abstained", "unsupported_answer"},
        "expected_verdict_counts": {"unsupported": claim_count},
        "expected_citation_statuses": [],
        "expected_should_abstain": True,
        "expected_primary_root_cause": "should_have_abstained",
        "expected_evidence_spans": [],
    }


def _run_generated_variant(variant: dict[str, Any], *, mode: str) -> dict[str, Any]:
    trace = variant["trace"]
    started = time.perf_counter()
    result = verify_trace(trace, mode=mode)
    latency_ms = round((time.perf_counter() - started) * 1000, 3)
    predicted = _predicted_labels_from_result(result)
    expected = set(variant["expected_labels"])
    expected_verdict_counts = dict(variant["expected_verdict_counts"])
    predicted_verdict_counts = {
        verdict: int((result.get("summary") or {}).get(verdict) or 0)
        for verdict in VERDICT_NAMES
    }
    expected_citations = list(variant["expected_citation_statuses"])
    predicted_citations = [
        str(claim.get("citation_status"))
        for claim in result.get("claims") or []
        if claim.get("citation_status")
    ]
    expected_abstain = variant["expected_should_abstain"]
    predicted_abstain = bool((result.get("abstention") or {}).get("should_abstain"))
    return {
        "id": variant["id"],
        "source": variant["source"],
        "note": variant["note"],
        "generated": True,
        "variant_type": variant["variant_type"],
        "base_case_id": variant["base_case_id"],
        "trace": trace.to_dict(),
        "expected": sorted(expected),
        "predicted": sorted(predicted),
        "exact_match": predicted == expected,
        "expected_verdict_counts": expected_verdict_counts,
        "predicted_verdict_counts": {
            key: value for key, value in sorted(predicted_verdict_counts.items())
        },
        "verdict_match": _counts_match(expected_verdict_counts, predicted_verdict_counts),
        "expected_citation_statuses": expected_citations,
        "predicted_citation_statuses": predicted_citations,
        "citation_match": (expected_citations == predicted_citations) if expected_citations else None,
        "expected_should_abstain": expected_abstain,
        "predicted_should_abstain": predicted_abstain,
        "abstention_match": (expected_abstain == predicted_abstain) if expected_abstain is not None else None,
        "expected_primary_root_cause": variant["expected_primary_root_cause"],
        "expected_evidence_spans": variant["expected_evidence_spans"],
        "summary": result.get("summary") or {},
        "claims": result.get("claims") or [],
        "abstention": result.get("abstention") or {},
        "latency_ms": latency_ms,
    }


def _predicted_labels_from_result(result: dict[str, Any]) -> set[str]:
    labels = set((result.get("summary") or {}).get("failure_types") or [])
    return labels or {"no_failure_detected"}


def _expected_claim_count(case: Any) -> int:
    return max(sum(int(value) for value in case.expected_verdict_counts.values()), 1)


def _generated_metadata(case: Any, variant_type: str) -> dict[str, Any]:
    return {
        **dict(case.trace.metadata),
        "benchmark_case_id": "%s__%s" % (case.id, variant_type),
        "benchmark_base_case_id": case.id,
        "benchmark_generated": True,
        "benchmark_variant_type": variant_type,
    }


def _find_distractor(case: Any, distractors: list[Any]) -> Any | None:
    case_context_ids = {context.id for context in case.trace.contexts}
    for distractor in distractors:
        if distractor.id not in case_context_ids and _token_jaccard(case.trace.answer, distractor.text) < 0.12:
            return distractor
    for distractor in distractors:
        if distractor.id not in case_context_ids:
            return distractor
    return None


def _distractors_for_case(case: Any, distractors: list[Any]) -> list[Any]:
    case_context_ids = {context.id for context in case.trace.contexts}
    case_family = _source_family(case.source)
    strict = [
        distractor
        for distractor in distractors
        if distractor.id not in case_context_ids
        and _source_family(distractor.metadata.get("source") or distractor.id) != case_family
        and _token_jaccard(case.trace.answer, distractor.text) < 0.03
    ]
    if strict:
        return strict
    return [
        distractor
        for distractor in distractors
        if distractor.id not in case_context_ids
        and _token_jaccard(case.trace.answer, distractor.text) < 0.01
    ]


def _source_family(source: Any) -> str:
    value = str(source or "").lower()
    if value.startswith("docs/") or value.startswith("release/") or "contexttrace" in value:
        return "contexttrace"
    if value.startswith(("github.com", "reference.", "python.", "platform.", "docs.")):
        return "external"
    return value.split("/")[0] if "/" in value else value


def _context_texts(contexts: list[Any]) -> list[str]:
    return [str(context.text) for context in contexts if str(context.text).strip()]


def _token_jaccard(left: str, right: str) -> float:
    left_tokens = set(_tokens(left))
    right_tokens = set(_tokens(right))
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / len(left_tokens | right_tokens)


def _load_labels(path: str | Path) -> dict[str, dict[str, Any]]:
    labels_path = Path(path)
    payload = json.loads(labels_path.read_text(encoding="utf-8"))
    cases = payload.get("cases") or {}
    if not isinstance(cases, dict):
        raise ValueError("ContextTrace-Bench labels must contain a cases object.")
    return {str(key): dict(value) for key, value in cases.items() if isinstance(value, dict)}


def _enrich_row(row: dict[str, Any], labels: dict[str, Any]) -> dict[str, Any]:
    predicted_root = _predicted_primary_root_cause(row)
    expected_root = str(
        labels.get("expected_primary_root_cause")
        or row.get("expected_primary_root_cause")
        or _derive_expected_root_cause(row)
    )
    expected_spans = [
        str(item)
        for item in (labels.get("expected_evidence_spans") or row.get("expected_evidence_spans") or [])
        if str(item).strip()
    ]
    predicted_spans = _predicted_evidence_spans(row)
    span_overlap = _span_overlap(expected_spans, predicted_spans)
    root_cause_match = predicted_root == expected_root if expected_root else None
    citation_metrics = _citation_error_counts(
        row.get("expected_citation_statuses") or [],
        row.get("predicted_citation_statuses") or [],
    )
    benchmark_pass = bool(row.get("exact_match")) and bool(row.get("verdict_match"))
    if root_cause_match is not None:
        benchmark_pass = benchmark_pass and bool(root_cause_match)
    return {
        **row,
        "expected_primary_root_cause": expected_root,
        "predicted_primary_root_cause": predicted_root,
        "root_cause_match": root_cause_match,
        "expected_evidence_spans": expected_spans,
        "predicted_evidence_spans": predicted_spans,
        "evidence_span_overlap": span_overlap,
        "citation_error_counts": citation_metrics,
        "benchmark_pass": benchmark_pass,
    }


def _summary(
    verifier_result: dict[str, Any],
    rows: list[dict[str, Any]],
    *,
    estimated_cost_per_trace_usd: float,
) -> dict[str, Any]:
    total = len(rows)
    per_label = verifier_result.get("per_label") or {}
    label_f1_values = [float(metrics.get("f1") or 0.0) for metrics in per_label.values()]
    root_rows = [row for row in rows if row.get("root_cause_match") is not None]
    root_accuracy = _rate([bool(row.get("root_cause_match")) for row in root_rows]) if root_rows else None
    citation_rows = [row for row in rows if row.get("citation_error_counts") is not None]
    if citation_rows:
        citation_counts = _sum_counts(row.get("citation_error_counts") or {} for row in citation_rows)
        citation_precision = _precision(citation_counts["tp"], citation_counts["fp"])
        citation_recall = _recall(citation_counts["tp"], citation_counts["fn"])
        citation_f1 = _f1(citation_precision, citation_recall)
    else:
        citation_precision = None
        citation_recall = None
        citation_f1 = None
    verdict_macro_f1 = _verdict_macro_f1(rows)
    span_rows = [row for row in rows if row.get("evidence_span_overlap") is not None]
    latency_values = [float(row.get("latency_ms") or 0.0) for row in rows if row.get("latency_ms") is not None]
    dangerous_false_greens = [
        row
        for row in rows
        if set(row.get("expected") or []) != {"no_failure_detected"}
        and set(row.get("predicted") or []) == {"no_failure_detected"}
    ]
    return {
        "cases": total,
        "failure_label_exact_match_rate": verifier_result.get("exact_match_rate"),
        "failure_label_macro_f1": _average(label_f1_values),
        "claim_verdict_macro_f1": verdict_macro_f1,
        "claim_verdict_match_rate": verifier_result.get("verdict_match_rate"),
        "root_cause_accuracy": root_accuracy,
        "root_cause_labeled_cases": len(root_rows),
        "root_cause_reported_cases": len(root_rows),
        "citation_error_precision": citation_precision,
        "citation_error_recall": citation_recall,
        "citation_error_f1": citation_f1,
        "citation_status_reported_cases": len(citation_rows),
        "evidence_span_overlap": (
            _average([float(row["evidence_span_overlap"]) for row in span_rows])
            if span_rows
            else None
        ),
        "evidence_span_labeled_cases": len(span_rows),
        "evidence_span_reported_cases": len(span_rows),
        "latency_p50_ms": _percentile(latency_values, 50),
        "latency_p95_ms": _percentile(latency_values, 95),
        "cost_per_100_traces_usd": round(float(estimated_cost_per_trace_usd) * 100, 6),
        "dangerous_false_green_rate": round(len(dangerous_false_greens) / total, 3) if total else 0.0,
    }


def _predicted_primary_root_cause(row: dict[str, Any]) -> str:
    summary = row.get("summary") or {}
    primary = summary.get("primary_root_cause")
    if primary:
        return str(primary)
    for claim in row.get("claims") or []:
        root = claim.get("root_cause") if isinstance(claim, dict) else None
        if isinstance(root, dict) and root.get("label"):
            return str(root["label"])
    return "unknown"


def _derive_expected_root_cause(row: dict[str, Any]) -> str:
    expected = set(row.get("expected") or [])
    citations = set(row.get("expected_citation_statuses") or [])
    if "no_failure_detected" in expected:
        return "no_failure_detected"
    if "citation_mismatch" in expected:
        if "cited_source_missing" in citations:
            return "missing_cited_source"
        return "wrong_source_cited"
    if "partial_support" in expected:
        return "answer_overreach"
    if "contradicted_answer" in expected:
        return "conflicting_contexts"
    if "should_have_abstained" in expected:
        return "should_have_abstained"
    if "unsupported_answer" in expected:
        return "answer_overreach"
    return ""


def _predicted_evidence_spans(row: dict[str, Any]) -> list[str]:
    spans: list[str] = []
    for claim in row.get("claims") or []:
        if not isinstance(claim, dict):
            continue
        evidence_span = claim.get("evidence_span")
        if isinstance(evidence_span, dict) and evidence_span.get("text"):
            spans.append(str(evidence_span["text"]))
        for span in claim.get("supporting_spans") or []:
            if isinstance(span, dict) and span.get("text"):
                spans.append(str(span["text"]))
        evidence = claim.get("evidence")
        if evidence:
            spans.append(str(evidence))
    return _dedupe(spans)


def _counts_match(expected: dict[str, Any], predicted: dict[str, Any]) -> bool:
    for key, value in expected.items():
        if int(predicted.get(key) or 0) != int(value):
            return False
    return True


def _verdict_macro_f1(rows: list[dict[str, Any]]) -> float:
    scores = []
    for verdict in VERDICT_NAMES:
        tp = 0
        fp = 0
        fn = 0
        for row in rows:
            expected = int((row.get("expected_verdict_counts") or {}).get(verdict) or 0)
            predicted = int((row.get("predicted_verdict_counts") or {}).get(verdict) or 0)
            tp += min(expected, predicted)
            fp += max(predicted - expected, 0)
            fn += max(expected - predicted, 0)
        precision = _precision(tp, fp)
        recall = _recall(tp, fn)
        scores.append(_f1(precision, recall))
    return _average(scores)


def _span_overlap(expected_spans: list[str], predicted_spans: list[str]) -> float | None:
    if not expected_spans:
        return None
    if not predicted_spans:
        return 0.0
    scores = []
    for expected in expected_spans:
        scores.append(max(_token_f1(expected, predicted) for predicted in predicted_spans))
    return _average(scores)


def _token_f1(expected: str, predicted: str) -> float:
    expected_tokens = _tokens(expected)
    predicted_tokens = _tokens(predicted)
    if not expected_tokens or not predicted_tokens:
        return 0.0
    expected_set = set(expected_tokens)
    predicted_set = set(predicted_tokens)
    overlap = len(expected_set & predicted_set)
    if not overlap:
        return 0.0
    precision = overlap / len(predicted_set)
    recall = overlap / len(expected_set)
    return _f1(precision, recall)


def _citation_error_counts(expected_statuses: list[Any], predicted_statuses: list[Any]) -> dict[str, int]:
    max_len = max(len(expected_statuses), len(predicted_statuses))
    counts = {"tp": 0, "fp": 0, "fn": 0, "tn": 0}
    for index in range(max_len):
        expected_bad = _is_bad_citation(expected_statuses[index] if index < len(expected_statuses) else None)
        predicted_bad = _is_bad_citation(predicted_statuses[index] if index < len(predicted_statuses) else None)
        if expected_bad and predicted_bad:
            counts["tp"] += 1
        elif not expected_bad and predicted_bad:
            counts["fp"] += 1
        elif expected_bad and not predicted_bad:
            counts["fn"] += 1
        else:
            counts["tn"] += 1
    return counts


def _is_bad_citation(value: Any) -> bool:
    return str(value or "") in BAD_CITATION_STATUSES


def _tokens(value: str) -> list[str]:
    return [
        token.strip(".,:;!?()[]{}\"'").lower()
        for token in str(value or "").split()
        if token.strip(".,:;!?()[]{}\"'")
    ]


def _average(values: list[float]) -> float:
    if not values:
        return 0.0
    return round(sum(values) / len(values), 3)


def _metric_display(value: Any) -> str:
    if value is None:
        return "N/A"
    return str(value)


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    ranked = sorted(values)
    index = round((len(ranked) - 1) * (percentile / 100))
    return round(float(ranked[index]), 3)


def _rate(values: list[bool]) -> float:
    if not values:
        return 0.0
    return round(sum(1 for value in values if value) / len(values), 3)


def _precision(tp: int, fp: int) -> float:
    return round(tp / (tp + fp), 3) if tp + fp else 1.0


def _recall(tp: int, fn: int) -> float:
    return round(tp / (tp + fn), 3) if tp + fn else 1.0


def _f1(precision: float, recall: float) -> float:
    return round((2 * precision * recall / (precision + recall)), 3) if precision + recall else 0.0


def _sum_counts(values: Any) -> dict[str, int]:
    totals = {"tp": 0, "fp": 0, "fn": 0, "tn": 0}
    for value in values:
        for key in totals:
            totals[key] += int(value.get(key) or 0)
    return totals


def _dedupe(values: list[str]) -> list[str]:
    seen = set()
    deduped = []
    for value in values:
        normalized = " ".join(value.split())
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(normalized)
    return deduped


HTML_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{benchmark} Report</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f7f8fa;
      --panel: #ffffff;
      --subtle: #fbfcfe;
      --text: #202832;
      --muted: #657286;
      --line: #d9e0ea;
      --ok: #176f44;
      --bad: #b42318;
      --warn: #946200;
      --accent: #2458d3;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      line-height: 1.5;
    }}
    main {{ max-width: 1200px; margin: 0 auto; padding: 32px 20px 56px; }}
    header {{ border-bottom: 1px solid var(--line); margin-bottom: 22px; padding-bottom: 18px; }}
    h1, h2 {{ margin: 0; }}
    h1 {{ font-size: 30px; }}
    h2 {{ font-size: 18px; margin-bottom: 12px; }}
    section {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      margin: 16px 0;
      padding: 18px;
    }}
    .summary {{
      display: grid;
      gap: 12px;
      grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
    }}
    .card, .item {{
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--subtle);
      padding: 12px;
    }}
    .item + .item {{ margin-top: 10px; }}
    .label, .item-meta {{
      color: var(--muted);
      font-size: 12px;
      font-weight: 700;
      text-transform: uppercase;
    }}
    .value {{ margin-top: 4px; font-size: 20px; overflow-wrap: anywhere; }}
    .muted {{ color: var(--muted); }}
    table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
    th, td {{ border-bottom: 1px solid var(--line); padding: 10px; text-align: left; vertical-align: top; }}
    th {{ color: var(--muted); font-size: 12px; text-transform: uppercase; }}
    .badge {{
      display: inline-block;
      border-radius: 999px;
      border: 1px solid var(--line);
      padding: 3px 8px;
      font-size: 12px;
      font-weight: 700;
      white-space: nowrap;
    }}
    .pass {{ color: var(--ok); background: #e9f7ef; }}
    .fail {{ color: var(--bad); background: #fdeceb; }}
    pre {{
      margin: 0;
      overflow: auto;
      background: #101828;
      color: #f8fafc;
      border-radius: 8px;
      padding: 14px;
      font-size: 13px;
    }}
  </style>
</head>
<body>
  <main>
    <header>
      <h1>{benchmark}</h1>
      <p class="muted">Mode: {mode}. Case set: {case_set}. Cases use {case_source}.</p>
    </header>

    <section>
      <h2>Summary</h2>
      <div class="summary">{summary_cards}</div>
    </section>

    <section>
      <h2>Confidence Intervals</h2>
      <table>
        <thead>
          <tr>
            <th>Metric</th>
            <th>Estimate</th>
            <th>95% CI</th>
            <th>Resamples</th>
          </tr>
        </thead>
        <tbody>{confidence_interval_rows}</tbody>
      </table>
    </section>

    <section>
      <h2>Failure Label Breakdown</h2>
      <table>
        <thead>
          <tr>
            <th>Label</th>
            <th>Precision</th>
            <th>Recall</th>
            <th>F1</th>
            <th>TP</th>
            <th>FP</th>
            <th>FN</th>
          </tr>
        </thead>
        <tbody>{per_label_rows}</tbody>
      </table>
    </section>

    <section>
      <h2>SOTA Readiness Gates</h2>
      <table>
        <thead>
          <tr>
            <th>Metric</th>
            <th>Gate</th>
            <th>Value</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>{gate_rows}</tbody>
      </table>
    </section>

    <section>
      <h2>Leaderboard</h2>
      <p class="muted">N/A means the candidate did not report that diagnostic field; it is not counted as an attempted failure.</p>
      <table>
        <thead>
          <tr>
            <th>System</th>
            <th>Mode</th>
            <th>Cases</th>
            <th>Failure Macro-F1</th>
            <th>Root Cause</th>
            <th>Citation Error F1</th>
            <th>Span Overlap</th>
            <th>Latency p95 ms</th>
          </tr>
        </thead>
        <tbody>{leaderboard_rows}</tbody>
      </table>
    </section>

    <section>
      <h2>Diagnostic Coverage</h2>
      <table>
        <thead>
          <tr>
            <th>System</th>
            <th>Root Cause Reported</th>
            <th>Citation Status Reported</th>
            <th>Evidence Spans Reported</th>
          </tr>
        </thead>
        <tbody>{diagnostic_coverage_rows}</tbody>
      </table>
    </section>

    <section>
      <h2>Misses To Inspect</h2>
      {misses}
    </section>

    <section>
      <h2>Case Results</h2>
      <table>
        <thead>
          <tr>
            <th>Status</th>
            <th>Case</th>
            <th>Expected</th>
            <th>Predicted</th>
            <th>Expected Root</th>
            <th>Predicted Root</th>
            <th>Span Overlap</th>
            <th>Latency</th>
          </tr>
        </thead>
        <tbody>{case_rows}</tbody>
      </table>
    </section>

    <section>
      <h2>Raw Summary</h2>
      <pre>{raw_json}</pre>
    </section>
  </main>
</body>
</html>
"""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run ContextTrace-Bench.")
    parser.add_argument("--mode", default="semantic", choices=["lexical", "semantic", "local_ml"])
    parser.add_argument("--case-set", default="all", choices=["contexttrace", "external", "public_holdout", "all"])
    parser.add_argument("--case-pack", default=None, help="External ContextTrace case-pack JSON to run instead of a built-in case set.")
    parser.add_argument("--labels", default=str(DEFAULT_LABELS_PATH))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--estimated-cost-per-trace-usd", default=0.0, type=float)
    parser.add_argument("--target-cases", default=DEFAULT_TARGET_CASES, type=int, help="Target case count after generated variants.")
    parser.add_argument("--bootstrap-samples", default=DEFAULT_BOOTSTRAP_SAMPLES, type=int, help="Case-bootstrap resamples for 95%% confidence intervals.")
    parser.add_argument("--bootstrap-seed", default=DEFAULT_BOOTSTRAP_SEED, type=int, help="Deterministic seed for bootstrap confidence intervals.")
    parser.add_argument("--no-generated-cases", action="store_true", help="Run only curated benchmark cases.")
    parser.add_argument(
        "--candidate",
        action="append",
        default=[],
        help="Candidate prediction JSON to score against the same benchmark. May be repeated.",
    )
    parser.add_argument(
        "--enforce-sota-gates",
        action="store_true",
        help="Fail if the default SOTA readiness gates are not met.",
    )
    parser.add_argument("--json", action="store_true", help="Print the benchmark result JSON.")
    args = parser.parse_args(argv)

    result = run_contexttrace_benchmark(
        mode=args.mode,
        case_set=args.case_set,
        case_pack_path=args.case_pack,
        labels_path=args.labels,
        estimated_cost_per_trace_usd=args.estimated_cost_per_trace_usd,
        include_generated_cases=not args.no_generated_cases,
        target_cases=args.target_cases,
        bootstrap_samples=args.bootstrap_samples,
        bootstrap_seed=args.bootstrap_seed,
    )
    baseline_results = [score_candidate_file(result, candidate_path) for candidate_path in args.candidate]
    paths = write_benchmark_outputs(result, output_dir=args.output_dir, baseline_results=baseline_results or None)
    gate_failures = quality_gate_failures(result) if args.enforce_sota_gates else []
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        summary = result["summary"]
        print("ContextTrace-Bench")
        print("Mode: %s" % result["mode"])
        print("Case set: %s" % result["case_set"])
        print("Cases: %s" % summary["cases"])
        print("Base cases: %s" % result["base_cases"])
        print("Generated cases: %s" % result["generated_cases"])
        print("Failure macro-F1: %.3f" % float(summary["failure_label_macro_f1"]))
        failure_ci = (result.get("confidence_intervals") or {}).get("failure_label_macro_f1") or {}
        if failure_ci:
            print("Failure macro-F1 95%% CI: %s to %s" % (failure_ci.get("low"), failure_ci.get("high")))
        print("Root-cause accuracy: %.3f" % float(summary["root_cause_accuracy"]))
        print("Citation error F1: %.3f" % float(summary["citation_error_f1"]))
        print("Evidence span overlap: %.3f" % float(summary["evidence_span_overlap"]))
        print("Latency p95 ms: %.3f" % float(summary["latency_p95_ms"]))
        print("Results: %s" % paths["results_md"])
        print("Leaderboard: %s" % paths["leaderboard_md"])
        print("Report: %s" % paths["report_html"])
        print("Candidate inputs: %s" % paths["candidate_inputs_jsonl"])
        for baseline in baseline_results:
            baseline_summary = baseline["summary"]
            print(
                "Baseline %s: failure macro-F1 %s, root-cause accuracy %s"
                % (
                    baseline["system"],
                    _metric_display(baseline_summary.get("failure_label_macro_f1")),
                    _metric_display(baseline_summary.get("root_cause_accuracy")),
                )
            )
    for failure in gate_failures:
        print("SOTA gate failed: %s" % failure, file=sys.stderr)
    return 1 if gate_failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
