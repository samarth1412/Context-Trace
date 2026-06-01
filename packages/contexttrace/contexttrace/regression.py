from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

from contexttrace.client import ContextTrace
from contexttrace.demo import aggregate_trace_metrics, run_demo_dataset
from contexttrace.report import ReportGenerator
from contexttrace.thresholds import parse_thresholds, threshold_failures


BENCHMARK_STRATEGIES = (
    "dense_top_k",
    "bm25",
    "hybrid",
    "hybrid_rerank",
    "corrective",
    "adaptive",
)


def run_local_benchmark(
    *,
    dataset: str,
    contexttrace: ContextTrace,
    output_dir: str = ".contexttrace/benchmarks",
    strategies: Iterable[str] = BENCHMARK_STRATEGIES,
    fail_on: Iterable[str] = (),
    report_path: str | None = None,
) -> dict[str, Any]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    strategy_results: dict[str, Any] = {}
    all_traces: list[dict[str, Any]] = []

    for strategy in strategies:
        demo_run = run_demo_dataset(
            dataset=dataset,
            contexttrace=contexttrace,
            strategy=strategy,
            report_path=str(output / ("%s_%s_report.html" % (Path(str(dataset)).name, strategy))),
        )
        traces = [contexttrace.get_trace(trace_id) for trace_id in demo_run.trace_ids]
        all_traces.extend(traces)
        strategy_results[strategy] = {
            "summary": demo_run.summary,
            "trace_ids": demo_run.trace_ids,
            "report_path": demo_run.report_path,
        }

    summary = aggregate_trace_metrics(all_traces)
    thresholds = parse_thresholds(fail_on)
    failures = threshold_failures(summary, thresholds)
    result = {
        "dataset": dataset,
        "strategies": strategy_results,
        "summary": summary,
        "threshold_failures": failures,
        "status": "failed" if failures else "passed",
    }
    results_path = output / "benchmark_results.json"
    summary_path = output / "benchmark_summary.md"
    if report_path is None:
        report_path = str(output / "benchmark_report.html")
    results_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    summary_path.write_text(render_benchmark_summary(result), encoding="utf-8")
    ReportGenerator().generate_eval_report(
        {
            "id": "benchmark",
            "dataset": dataset,
            "endpoint": "contexttrace-benchmark",
            "summary": summary,
        },
        all_traces,
        path=report_path,
    )
    result["results_path"] = str(results_path)
    result["summary_path"] = str(summary_path)
    result["report_path"] = report_path
    return result


def render_benchmark_summary(result: dict[str, Any]) -> str:
    summary = result["summary"]
    lines = [
        "# ContextTrace Benchmark Summary",
        "",
        "Status: **%s**" % result["status"],
        "",
        "| Metric | Value |",
        "| --- | ---: |",
        "| Questions tested | %s |" % summary.get("questions_tested", 0),
        "| Reliability score | %s |" % summary.get("reliability_score", 0),
        "| Failure rate | %.3f |" % float(summary.get("failure_rate", 0)),
        "| Citation support | %.3f |" % float(summary.get("citation_support", 0)),
        "| Unsupported claim rate | %.3f |" % float(summary.get("unsupported_claim_rate", 0)),
        "| Retrieval miss rate | %.3f |" % float(summary.get("retrieval_miss_rate", 0)),
        "| Latency ms | %.1f |" % float(summary.get("latency_ms", 0)),
        "| Token count | %.1f |" % float(summary.get("token_count", 0)),
        "| Cost USD | %.6f |" % float(summary.get("cost_usd", 0)),
        "",
        "## Strategy Summaries",
        "",
        "| Strategy | Failure Rate | Citation Support | Unsupported Claims | Retrieval Miss Rate |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for strategy, payload in result["strategies"].items():
        metrics = payload["summary"]
        lines.append(
            "| %s | %.3f | %.3f | %.3f | %.3f |"
            % (
                strategy,
                float(metrics.get("failure_rate", 0)),
                float(metrics.get("citation_support", 0)),
                float(metrics.get("unsupported_claim_rate", 0)),
                float(metrics.get("retrieval_miss_rate", 0)),
            )
        )
    if result["threshold_failures"]:
        lines.extend(["", "## Threshold Failures", ""])
        lines.extend("- %s" % failure for failure in result["threshold_failures"])
    return "\n".join(lines) + "\n"
