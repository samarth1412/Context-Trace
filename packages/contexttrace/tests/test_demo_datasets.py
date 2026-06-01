from contexttrace import ContextTrace
from contexttrace.demo import aggregate_trace_metrics, run_demo_dataset
from contexttrace.demo_data import load_demo_dataset, list_demo_datasets


def test_demo_datasets_load_required_files():
    assert set(list_demo_datasets()) == {"ai_paper_qa", "employee_handbook", "refund_policy"}

    for name in list_demo_datasets():
        dataset = load_demo_dataset(name)
        assert dataset["documents"]
        assert len(dataset["questions"]) >= 10
        assert dataset["expected_answers"]
        assert dataset["expected_sources"]


def test_demo_run_creates_failures_and_report(tmp_path):
    ct = ContextTrace(project="demo-rag", storage_path=str(tmp_path / "contexttrace.db"))

    result = run_demo_dataset(
        dataset="refund_policy",
        contexttrace=ct,
        report_path=str(tmp_path / "demo.html"),
    )

    assert len(result.trace_ids) == 10
    assert (tmp_path / "demo.html").exists()
    assert result.summary["failure_rate"] > 0
    failures = {((ct.get_trace(trace_id).get("evaluation") or {}).get("failure") or {}).get("failure_type") for trace_id in result.trace_ids}
    assert {"citation_mismatch", "unsupported_answer", "retrieval_miss", "should_have_abstained", "conflicting_sources"} <= failures


def test_aggregate_trace_metrics_empty():
    summary = aggregate_trace_metrics([])

    assert summary["questions_tested"] == 0
    assert summary["failure_rate"] == 0.0
