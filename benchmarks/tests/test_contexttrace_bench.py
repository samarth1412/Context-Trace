from __future__ import annotations

import json

from benchmarks.contexttrace_bench.adapt_candidate import adapt_candidate_rows
from benchmarks.contexttrace_bench.baseline_common import load_candidate_inputs, write_json
from benchmarks.contexttrace_bench.run_deepeval import build_deepeval_rows
from benchmarks.contexttrace_bench.run_contexttrace import (
    quality_gate_failures,
    render_html_report,
    render_leaderboard_markdown,
    render_results_markdown,
    run_contexttrace_benchmark,
    score_candidate_predictions,
    write_benchmark_outputs,
)
from benchmarks.contexttrace_bench.run_ragas import build_ragas_rows
from benchmarks.contexttrace_bench.run_local_judge import _judge_prompt, _normalize_judge_output


def test_contexttrace_bench_reports_sota_metrics() -> None:
    result = run_contexttrace_benchmark(mode="semantic", case_set="all")
    summary = result["summary"]

    assert result["benchmark"] == "ContextTrace-Bench"
    assert result["base_cases"] >= 50
    assert result["generated_cases"] >= 400
    assert summary["cases"] >= 500
    assert summary["failure_label_macro_f1"] >= 0.8
    assert summary["claim_verdict_macro_f1"] >= 0.8
    assert summary["claim_verdict_match_rate"] >= 0.8
    assert summary["root_cause_labeled_cases"] >= 5
    assert 0.0 <= summary["root_cause_accuracy"] <= 1.0
    assert summary["citation_error_precision"] >= 0.8
    assert summary["citation_error_recall"] >= 0.8
    assert summary["evidence_span_labeled_cases"] >= 5
    assert summary["evidence_span_overlap"] > 0.5
    assert summary["latency_p50_ms"] >= 0.0
    assert summary["latency_p95_ms"] >= summary["latency_p50_ms"]
    assert summary["cost_per_100_traces_usd"] == 0.0
    assert summary["dangerous_false_green_rate"] == 0.0
    assert quality_gate_failures(result) == []

    labeled = [row for row in result["rows"] if row["expected_evidence_spans"]]
    assert labeled
    assert all(row["predicted_evidence_spans"] for row in labeled)


def test_contexttrace_bench_runs_public_holdout_without_generated_cases() -> None:
    result = run_contexttrace_benchmark(
        mode="semantic",
        case_set="public_holdout",
        include_generated_cases=False,
    )
    summary = result["summary"]

    assert result["case_set"] == "public_holdout"
    assert result["base_cases"] >= 30
    assert result["generated_cases"] == 0
    assert summary["cases"] == result["base_cases"]
    assert summary["failure_label_macro_f1"] >= 0.92
    assert summary["root_cause_accuracy"] >= 0.92
    assert summary["citation_error_f1"] >= 0.92
    assert summary["evidence_span_labeled_cases"] >= 25
    assert summary["dangerous_false_green_rate"] == 0.0
    assert any(row["id"] == "holdout_milvus_wrong_source_citation" for row in result["rows"])


def test_contexttrace_bench_markdown_outputs(tmp_path) -> None:
    result = run_contexttrace_benchmark(mode="semantic", case_set="external")
    paths = write_benchmark_outputs(result, output_dir=tmp_path)

    payload = json.loads((tmp_path / "contexttrace_bench_results.json").read_text(encoding="utf-8"))
    assert payload["benchmark"] == "ContextTrace-Bench"
    assert paths["results_md"].endswith("results.md")
    assert paths["leaderboard_md"].endswith("leaderboard.md")
    assert paths["report_html"].endswith("report.html")
    assert paths["candidate_inputs_jsonl"].endswith("candidate_inputs.jsonl")

    results_md = render_results_markdown(result)
    leaderboard_md = render_leaderboard_markdown(result)
    html_report = render_html_report(result)
    assert "ContextTrace-Bench Results" in results_md
    assert "failure_label_macro_f1" in results_md
    assert "SOTA Readiness Gates" in results_md
    assert "ContextTrace-Bench Leaderboard" in leaderboard_md
    assert "ContextTrace" in leaderboard_md
    assert "ContextTrace-Bench" in html_report
    assert "SOTA Readiness Gates" in html_report

    assert "ContextTrace-Bench Results" in (tmp_path / "results.md").read_text(encoding="utf-8")
    assert "ContextTrace-Bench Leaderboard" in (tmp_path / "leaderboard.md").read_text(encoding="utf-8")
    assert "SOTA Readiness Gates" in (tmp_path / "report.html").read_text(encoding="utf-8")
    candidate_inputs = (tmp_path / "candidate_inputs.jsonl").read_text(encoding="utf-8").splitlines()
    assert candidate_inputs
    assert "expected" not in json.loads(candidate_inputs[0])


def test_contexttrace_bench_scores_candidate_predictions(tmp_path) -> None:
    result = run_contexttrace_benchmark(mode="semantic", case_set="external")
    candidate = {
        "system": "Example baseline",
        "version": "offline-fixture",
        "predictions": [
            {
                "id": row["id"],
                "predicted": row["expected"],
                "predicted_verdict_counts": row["expected_verdict_counts"],
                "predicted_citation_statuses": row["expected_citation_statuses"],
                "predicted_primary_root_cause": row["expected_primary_root_cause"],
                "predicted_evidence_spans": row["expected_evidence_spans"],
                "latency_ms": 10.0,
                "cost_usd": 0.001,
            }
            for row in result["rows"]
        ],
    }

    baseline = score_candidate_predictions(result, candidate)
    paths = write_benchmark_outputs(result, output_dir=tmp_path, baseline_results=[baseline])
    leaderboard = render_leaderboard_markdown(result, baseline_results=[baseline])

    assert baseline["system"] == "Example baseline"
    assert baseline["coverage"]["matched_predictions"] == result["summary"]["cases"]
    assert baseline["summary"]["failure_label_macro_f1"] == 1.0
    assert baseline["summary"]["root_cause_accuracy"] == 1.0
    assert baseline["summary"]["root_cause_reported_cases"] == result["summary"]["cases"]
    assert baseline["summary"]["citation_status_reported_cases"] == result["summary"]["cases"]
    assert baseline["summary"]["evidence_span_reported_cases"] == result["summary"]["evidence_span_labeled_cases"]
    assert baseline["summary"]["cost_per_100_traces_usd"] == 0.1
    assert "Example baseline" in leaderboard
    assert "baseline_results_json" in paths
    assert json.loads((tmp_path / "baseline_results.json").read_text(encoding="utf-8"))[0]["system"] == "Example baseline"


def test_contexttrace_bench_marks_missing_diagnostics_as_not_applicable() -> None:
    result = run_contexttrace_benchmark(mode="semantic", case_set="external")
    candidate = {
        "system": "Faithfulness-only baseline",
        "version": "fixture",
        "predictions": [
            {
                "id": row["id"],
                "predicted": row["expected"],
                "predicted_verdict_counts": row["expected_verdict_counts"],
            }
            for row in result["rows"]
        ],
    }

    baseline = score_candidate_predictions(result, candidate)
    leaderboard = render_leaderboard_markdown(result, baseline_results=[baseline])

    assert baseline["summary"]["failure_label_macro_f1"] == 1.0
    assert baseline["summary"]["claim_verdict_macro_f1"] == 1.0
    assert baseline["summary"]["root_cause_accuracy"] is None
    assert baseline["summary"]["citation_error_f1"] is None
    assert baseline["summary"]["evidence_span_overlap"] is None
    assert baseline["summary"]["root_cause_reported_cases"] == 0
    assert baseline["summary"]["citation_status_reported_cases"] == 0
    assert baseline["summary"]["evidence_span_reported_cases"] == 0
    assert "N/A" in leaderboard


def test_contexttrace_bench_adapts_candidate_rows() -> None:
    candidate = adapt_candidate_rows(
        [
            {
                "case_id": "case-supported",
                "metrics": {"faithfulness": 0.96, "context_recall": 0.90},
                "latency_ms": "12.5",
            },
            {
                "case_id": "case-unsupported",
                "metrics": {"faithfulness": 0.30, "context_recall": 0.20},
                "root": "answer_overreach",
                "spans": ["closest span"],
            },
        ],
        system="External evaluator",
        version="fixture",
        id_field="case_id",
        faithfulness_field="metrics.faithfulness",
        context_recall_field="metrics.context_recall",
        root_cause_field="root",
        evidence_spans_field="spans",
    )

    assert candidate["system"] == "External evaluator"
    assert candidate["predictions"][0]["predicted"] == ["no_failure_detected"]
    assert candidate["predictions"][0]["latency_ms"] == 12.5
    assert candidate["predictions"][1]["predicted"] == ["should_have_abstained", "unsupported_answer"]
    assert candidate["predictions"][1]["predicted_primary_root_cause"] == "answer_overreach"
    assert candidate["predictions"][1]["predicted_evidence_spans"] == ["closest span"]


def test_baseline_runners_build_external_eval_rows(tmp_path) -> None:
    input_path = tmp_path / "candidate_inputs.jsonl"
    rows = [
        {
            "id": "case-1",
            "trace": {
                "query": "What does the policy say?",
                "answer": "Refunds are available within 30 days.",
                "contexts": [
                    {
                        "id": "policy",
                        "text": "Customers may request refunds within 30 days.",
                    }
                ],
            },
        }
    ]
    input_path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")

    loaded = load_candidate_inputs(input_path)
    ragas_rows = build_ragas_rows(loaded)
    deepeval_rows = build_deepeval_rows(loaded)

    assert ragas_rows == [
        {
            "id": "case-1",
            "user_input": "What does the policy say?",
            "response": "Refunds are available within 30 days.",
            "retrieved_contexts": ["Customers may request refunds within 30 days."],
        }
    ]
    assert deepeval_rows == [
        {
            "id": "case-1",
            "input": "What does the policy say?",
            "actual_output": "Refunds are available within 30 days.",
            "retrieval_context": ["Customers may request refunds within 30 days."],
        }
    ]

    raw_path = write_json({"rows": ragas_rows}, tmp_path / "raw.json")
    assert json.loads((tmp_path / "raw.json").read_text(encoding="utf-8"))["rows"][0]["id"] == "case-1"
    assert raw_path.endswith("raw.json")


def test_local_judge_output_normalization() -> None:
    normalized = _normalize_judge_output(
        {
            "predicted": ["unsupported_answer", "unknown"],
            "predicted_verdict_counts": {"unsupported": 2},
            "predicted_primary_root_cause": "answer_overreach",
            "predicted_citation_statuses": ["citation_ok", "bad-status"],
            "predicted_evidence_spans": ["Customers may request refunds within 30 days."],
        }
    )

    assert normalized["predicted"] == ["unsupported_answer"]
    assert normalized["predicted_verdict_counts"]["unsupported"] == 2
    assert normalized["predicted_primary_root_cause"] == "answer_overreach"
    assert normalized["predicted_citation_statuses"] == ["citation_ok"]
    assert normalized["predicted_evidence_spans"] == ["Customers may request refunds within 30 days."]


def test_local_judge_prompt_includes_citations_and_benchmark_taxonomy() -> None:
    prompt = _judge_prompt(
        {
            "id": "case-1",
            "trace": {
                "query": "What is supported?",
                "answer": "The cited claim is supported.",
                "contexts": [
                    {
                        "id": "source-a",
                        "text": "The cited claim is supported by this source.",
                    }
                ],
                "citations": [
                    {
                        "claim": "The cited claim is supported.",
                        "source_id": "source-a",
                    }
                ],
            },
        }
    )
    payload = json.loads(prompt)

    assert "citation_mismatch" in payload["allowed_failure_labels"]
    assert payload["contexts"][0]["id"] == "source-a"
    assert payload["citations"] == [
        {
            "claim": "The cited claim is supported.",
            "source_id": "source-a",
        }
    ]
