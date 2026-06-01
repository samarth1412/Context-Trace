from contexttrace import ContextTrace
from contexttrace.regression import run_local_benchmark
from contexttrace.thresholds import parse_threshold, parse_thresholds, threshold_failures


def test_threshold_parser_and_failures():
    threshold = parse_threshold("failure_rate>0.25")
    assert threshold.metric == "failure_rate"
    assert threshold.operator == ">"
    assert threshold.value == 0.25

    failures = threshold_failures(
        {"failure_rate": 0.5, "citation_support": 0.7},
        parse_thresholds(["failure_rate>0.25", "citation_support<0.80"]),
    )
    assert len(failures) == 2


def test_local_benchmark_writes_outputs_and_thresholds(tmp_path):
    ct = ContextTrace(project="benchmark-rag", storage_path=str(tmp_path / "contexttrace.db"))

    result = run_local_benchmark(
        dataset="refund_policy",
        contexttrace=ct,
        output_dir=str(tmp_path / "benchmarks"),
        strategies=("adaptive",),
        fail_on=("failure_rate>0.01",),
    )

    assert result["status"] == "failed"
    assert result["threshold_failures"]
    assert (tmp_path / "benchmarks" / "benchmark_results.json").exists()
    assert (tmp_path / "benchmarks" / "benchmark_summary.md").exists()
    assert (tmp_path / "benchmarks" / "benchmark_report.html").exists()
