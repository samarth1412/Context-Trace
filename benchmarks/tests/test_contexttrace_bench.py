from __future__ import annotations

import json
from pathlib import Path

from benchmarks.contexttrace_bench.adapt_candidate import adapt_candidate_rows
from benchmarks.contexttrace_bench.audit_diag150 import (
    build_diag150_audit_packet,
    build_human_review_template,
    load_human_review_file,
    render_audit_packet_markdown,
    validate_diag150_audit_packet,
    write_diag150_audit_artifacts,
    write_diag150_release_bundle,
)
from benchmarks.contexttrace_bench.baseline_common import load_candidate_inputs, write_json
from benchmarks.contexttrace_bench.diag150_release_workflow import (
    render_workflow_summary,
    run_diag150_release_workflow,
)
from benchmarks.contexttrace_bench.run_deepeval import build_deepeval_rows
from benchmarks.contexttrace_bench.run_contexttrace import (
    build_error_analysis,
    main as run_contexttrace_main,
    render_candidate_inputs_jsonl,
    quality_gate_failures,
    render_error_analysis_markdown,
    render_html_report,
    render_leaderboard_markdown,
    render_results_markdown,
    run_contexttrace_case_pack,
    run_contexttrace_benchmark,
    score_candidate_predictions,
    write_benchmark_outputs,
)
from benchmarks.contexttrace_bench.ragtruth_adapter import adapt_ragtruth_rows
from benchmarks.contexttrace_bench.ragtruth_error_analysis import (
    build_ragtruth_error_analysis,
    render_ragtruth_error_analysis_markdown,
)
from benchmarks.contexttrace_bench.ragtruth_review import (
    apply_review_mappings,
    build_review_packet,
    build_review_queue,
    validate_review_mappings,
)
from benchmarks.contexttrace_bench.ragtruth_workflow import run_ragtruth_review_workflow
from benchmarks.contexttrace_bench.ragtruth_release_workflow import (
    render_workflow_summary as render_ragtruth_release_summary,
    run_ragtruth_release_workflow,
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
    assert result["confidence_intervals"]["failure_label_macro_f1"]["low"] <= summary["failure_label_macro_f1"]
    assert result["confidence_intervals"]["failure_label_macro_f1"]["high"] >= summary["failure_label_macro_f1"]
    assert result["confidence_intervals"]["failure_label_macro_f1"]["samples"] == 400
    assert result["per_label"]["no_failure_detected"]["f1"] >= 0.8
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


def test_diag150_audit_packet_validates_public_holdout() -> None:
    result = run_contexttrace_benchmark(
        mode="semantic",
        case_set="public_holdout",
        include_generated_cases=False,
        bootstrap_samples=10,
    )
    candidate_inputs = [
        json.loads(line)
        for line in render_candidate_inputs_jsonl(result).splitlines()
        if line.strip()
    ]

    packet = build_diag150_audit_packet(
        result,
        candidate_inputs=candidate_inputs,
        commit="test-sha",
        generated_at="2026-06-18T00:00:00+00:00",
    )
    validation = validate_diag150_audit_packet(packet, result=result, candidate_inputs=candidate_inputs)
    markdown = render_audit_packet_markdown(packet)

    assert packet["benchmark"] == "ContextTrace-Diag-150"
    assert packet["case_set"] == "public_holdout"
    assert packet["case_count"] == 150
    assert packet["generated_cases"] == 0
    assert packet["label_distribution"]["no_failure_detected"] >= 1
    assert packet["label_distribution"]["citation_mismatch"] >= 1
    assert packet["candidate_input_rows"] == 150
    assert validation["status"] == "passed"
    assert validation["summary"]["errors"] == 0
    assert validation["summary"]["warnings"] == 1
    assert validation["warnings"][0]["name"] == "independent_human_signoff_complete"
    assert "ContextTrace-Diag-150 Audit Packet" in markdown
    assert "Reviewer Signoff" in markdown


def test_diag150_audit_accepts_complete_independent_signoff(tmp_path) -> None:
    result = run_contexttrace_benchmark(
        mode="semantic",
        case_set="public_holdout",
        include_generated_cases=False,
        bootstrap_samples=10,
    )
    candidate_inputs = [
        json.loads(line)
        for line in render_candidate_inputs_jsonl(result).splitlines()
        if line.strip()
    ]
    packet = build_diag150_audit_packet(
        result,
        candidate_inputs=candidate_inputs,
        commit="test-sha",
        generated_at="2026-06-18T00:00:00+00:00",
    )
    review_template = build_human_review_template(packet)
    for case in review_template["cases"]:
        case.update(
            {
                "status": "signed_off",
                "source_url_opened": True,
                "context_fair": True,
                "label_correct": True,
                "evidence_span_minimal": True,
                "reviewer": "independent-reviewer",
                "reviewed_at": "2026-06-18",
                "notes": "",
            }
        )
    review_path = tmp_path / "diag150_human_review_template.json"
    review_path.write_text(json.dumps(review_template), encoding="utf-8")
    human_reviews = load_human_review_file(review_path)

    signed_packet = build_diag150_audit_packet(
        result,
        candidate_inputs=candidate_inputs,
        human_reviews=human_reviews,
        commit="test-sha",
        generated_at="2026-06-18T00:00:00+00:00",
    )
    validation = validate_diag150_audit_packet(
        signed_packet,
        result=result,
        candidate_inputs=candidate_inputs,
        require_human_signoff=True,
    )

    assert validation["status"] == "passed"
    assert validation["summary"]["errors"] == 0
    assert validation["summary"]["warnings"] == 0
    assert all(case["human_review"]["status"] == "signed_off" for case in signed_packet["cases"])


def test_diag150_audit_rejects_human_review_blockers() -> None:
    result = run_contexttrace_benchmark(
        mode="semantic",
        case_set="public_holdout",
        include_generated_cases=False,
        bootstrap_samples=10,
    )
    candidate_inputs = [
        json.loads(line)
        for line in render_candidate_inputs_jsonl(result).splitlines()
        if line.strip()
    ]
    packet = build_diag150_audit_packet(
        result,
        candidate_inputs=candidate_inputs,
        commit="test-sha",
        generated_at="2026-06-18T00:00:00+00:00",
    )
    review_template = build_human_review_template(packet)
    for case in review_template["cases"]:
        case.update(
            {
                "status": "signed_off",
                "source_url_opened": True,
                "context_fair": True,
                "label_correct": True,
                "evidence_span_minimal": True,
                "reviewer": "independent-reviewer",
                "reviewed_at": "2026-06-18",
                "notes": "",
            }
        )
    review_template["cases"][0]["status"] = "needs_changes"
    review_template["cases"][0]["context_fair"] = False
    review_template["cases"][0]["notes"] = "Source excerpt needs review."
    human_reviews = {case["id"]: case for case in review_template["cases"]}

    signed_packet = build_diag150_audit_packet(
        result,
        candidate_inputs=candidate_inputs,
        human_reviews=human_reviews,
        commit="test-sha",
        generated_at="2026-06-18T00:00:00+00:00",
    )
    validation = validate_diag150_audit_packet(
        signed_packet,
        result=result,
        candidate_inputs=candidate_inputs,
        require_human_signoff=True,
    )

    assert validation["status"] == "failed"
    assert any(check["name"] == "human_review_blockers" for check in validation["errors"])
    assert any(check["name"] == "independent_human_signoff_complete" for check in validation["errors"])


def test_diag150_audit_validator_rejects_candidate_label_leakage() -> None:
    result = run_contexttrace_benchmark(
        mode="semantic",
        case_set="public_holdout",
        include_generated_cases=False,
        bootstrap_samples=10,
    )
    candidate_inputs = [
        json.loads(line)
        for line in render_candidate_inputs_jsonl(result).splitlines()
        if line.strip()
    ]
    candidate_inputs[0]["expected_labels"] = ["no_failure_detected"]
    packet = build_diag150_audit_packet(
        result,
        candidate_inputs=candidate_inputs,
        commit="test-sha",
        generated_at="2026-06-18T00:00:00+00:00",
    )

    validation = validate_diag150_audit_packet(packet, result=result, candidate_inputs=candidate_inputs)

    assert validation["status"] == "failed"
    assert any(check["name"] == "candidate_inputs_hide_labels" for check in validation["errors"])


def test_diag150_audit_artifacts_are_written(tmp_path) -> None:
    result = run_contexttrace_benchmark(
        mode="semantic",
        case_set="public_holdout",
        include_generated_cases=False,
        bootstrap_samples=10,
    )
    candidate_inputs = [
        json.loads(line)
        for line in render_candidate_inputs_jsonl(result).splitlines()
        if line.strip()
    ]

    paths = write_diag150_audit_artifacts(
        result,
        output_dir=tmp_path,
        candidate_inputs=candidate_inputs,
        commit="test-sha",
    )

    assert "audit_packet_json" in paths
    assert "audit_packet_md" in paths
    assert "audit_validation_json" in paths
    assert "audit_report_md" in paths
    packet = json.loads((tmp_path / "diag150_audit_packet.json").read_text(encoding="utf-8"))
    validation = json.loads((tmp_path / "diag150_audit_validation.json").read_text(encoding="utf-8"))
    assert packet["case_count"] == 150
    assert validation["status"] == "passed"
    assert "Automated Audit Report" in (tmp_path / "AUDIT_REPORT.md").read_text(encoding="utf-8")


def test_diag150_release_bundle_marks_review_pending(tmp_path) -> None:
    result = run_contexttrace_benchmark(
        mode="semantic",
        case_set="public_holdout",
        include_generated_cases=False,
        bootstrap_samples=10,
    )
    artifact_dir = tmp_path / "artifacts"
    write_benchmark_outputs(result, output_dir=artifact_dir)
    write_diag150_audit_artifacts(result, output_dir=artifact_dir, commit="test-sha")

    paths = write_diag150_release_bundle(
        output_dir=artifact_dir,
        bundle_dir=tmp_path / "bundle",
    )

    manifest = json.loads((tmp_path / "bundle" / "manifest.json").read_text(encoding="utf-8"))
    readme = (tmp_path / "bundle" / "README.md").read_text(encoding="utf-8")
    assert paths["manifest_json"].endswith("manifest.json")
    assert manifest["bundle_status"] == "review_pending"
    assert manifest["human_signoff_complete"] is False
    assert manifest["missing_required_artifacts"] == []
    assert any(artifact["path"] == "diag150_audit_packet.md" for artifact in manifest["artifacts"])
    assert all(len(artifact["sha256"]) == 64 for artifact in manifest["artifacts"])
    assert "reviewer handoff" in readme


def test_diag150_release_bundle_marks_freeze_ready_with_signoff(tmp_path) -> None:
    result = run_contexttrace_benchmark(
        mode="semantic",
        case_set="public_holdout",
        include_generated_cases=False,
        bootstrap_samples=10,
    )
    candidate_inputs = [
        json.loads(line)
        for line in render_candidate_inputs_jsonl(result).splitlines()
        if line.strip()
    ]
    packet = build_diag150_audit_packet(
        result,
        candidate_inputs=candidate_inputs,
        commit="test-sha",
        generated_at="2026-06-18T00:00:00+00:00",
    )
    review_template = build_human_review_template(packet)
    for case in review_template["cases"]:
        case.update(
            {
                "status": "signed_off",
                "source_url_opened": True,
                "context_fair": True,
                "label_correct": True,
                "evidence_span_minimal": True,
                "reviewer": "independent-reviewer",
                "reviewed_at": "2026-06-18",
                "notes": "",
            }
        )
    review_path = tmp_path / "completed_review.json"
    review_path.write_text(json.dumps(review_template), encoding="utf-8")
    human_reviews = load_human_review_file(review_path)
    artifact_dir = tmp_path / "artifacts"
    write_benchmark_outputs(result, output_dir=artifact_dir)
    write_diag150_audit_artifacts(
        result,
        output_dir=artifact_dir,
        candidate_inputs=candidate_inputs,
        human_reviews=human_reviews,
        commit="test-sha",
        require_human_signoff=True,
    )

    write_diag150_release_bundle(
        output_dir=artifact_dir,
        bundle_dir=tmp_path / "bundle",
        review_file=review_path,
        require_human_signoff=True,
    )

    manifest = json.loads((tmp_path / "bundle" / "manifest.json").read_text(encoding="utf-8"))
    readme = (tmp_path / "bundle" / "README.md").read_text(encoding="utf-8")
    assert manifest["bundle_status"] == "freeze_ready"
    assert manifest["human_signoff_complete"] is True
    assert any(artifact["path"] == "diag150_human_review_signoff.json" for artifact in manifest["artifacts"])
    assert "passed automated validation and independent human signoff" in readme


def test_diag150_release_workflow_generates_review_pending_bundle(tmp_path) -> None:
    summary = run_diag150_release_workflow(
        output_dir=tmp_path / "public_holdout",
        bundle_dir=tmp_path / "bundle",
        auto_candidates=False,
        bootstrap_samples=10,
    )
    rendered = render_workflow_summary(summary)

    assert summary["status"] == "review_pending"
    assert summary["case_count"] == 150
    assert summary["baseline_count"] == 0
    assert summary["manifest"]["bundle_status"] == "review_pending"
    assert Path(summary["bundle_paths"]["manifest_json"]).exists()
    assert "ContextTrace-Diag-150 release workflow" in rendered
    assert "Status: review_pending" in rendered


def test_diag150_release_workflow_scores_existing_candidate_rows(tmp_path) -> None:
    seed_result = run_contexttrace_benchmark(
        mode="semantic",
        case_set="public_holdout",
        include_generated_cases=False,
        bootstrap_samples=10,
    )
    output_dir = tmp_path / "public_holdout"
    output_dir.mkdir(parents=True)
    candidate = {
        "system": "Example diagnostic judge",
        "version": "fixture",
        "predictions": [
            {
                "id": row["id"],
                "predicted": row["expected"],
                "predicted_verdict_counts": row["expected_verdict_counts"],
                "predicted_citation_statuses": row["expected_citation_statuses"],
                "predicted_primary_root_cause": row["expected_primary_root_cause"],
                "predicted_evidence_spans": row["expected_evidence_spans"],
            }
            for row in seed_result["rows"]
        ],
    }
    candidate_path = output_dir / "openai_diagnostic_judge_predictions.json"
    candidate_path.write_text(json.dumps(candidate), encoding="utf-8")

    summary = run_diag150_release_workflow(
        output_dir=output_dir,
        bundle_dir=tmp_path / "bundle",
        bootstrap_samples=10,
    )

    assert summary["status"] == "review_pending"
    assert summary["baseline_count"] == 1
    assert summary["candidate_files"] == [str(candidate_path)]
    baseline_results = json.loads((output_dir / "baseline_results.json").read_text(encoding="utf-8"))
    assert baseline_results[0]["system"] == "Example diagnostic judge"
    assert any(artifact["path"] == "baseline_results.json" for artifact in summary["manifest"]["artifacts"])


def test_contexttrace_bench_markdown_outputs(tmp_path) -> None:
    result = run_contexttrace_benchmark(mode="semantic", case_set="external")
    paths = write_benchmark_outputs(result, output_dir=tmp_path)

    payload = json.loads((tmp_path / "contexttrace_bench_results.json").read_text(encoding="utf-8"))
    assert payload["benchmark"] == "ContextTrace-Bench"
    assert paths["results_md"].endswith("results.md")
    assert paths["leaderboard_md"].endswith("leaderboard.md")
    assert paths["report_html"].endswith("report.html")
    assert paths["error_analysis_json"].endswith("error_analysis.json")
    assert paths["error_analysis_md"].endswith("error_analysis.md")
    assert paths["candidate_inputs_jsonl"].endswith("candidate_inputs.jsonl")

    results_md = render_results_markdown(result)
    leaderboard_md = render_leaderboard_markdown(result)
    html_report = render_html_report(result)
    assert "ContextTrace-Bench Results" in results_md
    assert "failure_label_macro_f1" in results_md
    assert "Confidence Intervals" in results_md
    assert "Failure Label Breakdown" in results_md
    assert "SOTA Readiness Gates" in results_md
    assert "ContextTrace-Bench Leaderboard" in leaderboard_md
    assert "ContextTrace" in leaderboard_md
    assert "ContextTrace-Bench" in html_report
    assert "Confidence Intervals" in html_report
    assert "Failure Label Breakdown" in html_report
    assert "SOTA Readiness Gates" in html_report

    assert "ContextTrace-Bench Results" in (tmp_path / "results.md").read_text(encoding="utf-8")
    assert "ContextTrace-Bench Leaderboard" in (tmp_path / "leaderboard.md").read_text(encoding="utf-8")
    assert "SOTA Readiness Gates" in (tmp_path / "report.html").read_text(encoding="utf-8")
    assert "ContextTrace-Bench Error Analysis" in (tmp_path / "error_analysis.md").read_text(encoding="utf-8")
    error_analysis = json.loads((tmp_path / "error_analysis.json").read_text(encoding="utf-8"))
    assert "confusion" in error_analysis
    assert "cases_to_review" in error_analysis
    candidate_inputs = (tmp_path / "candidate_inputs.jsonl").read_text(encoding="utf-8").splitlines()
    assert candidate_inputs
    candidate_input = json.loads(candidate_inputs[0])
    assert "expected" not in candidate_input
    assert "note" not in candidate_input


def test_contexttrace_bench_error_analysis_summarizes_misses() -> None:
    result = run_contexttrace_benchmark(mode="semantic", case_set="external")
    analysis = build_error_analysis(result)
    markdown = render_error_analysis_markdown(analysis)

    assert analysis["case_count"] == result["summary"]["cases"]
    assert analysis["confusion"]
    assert analysis["root_cause_confusion"]
    assert "ContextTrace-Bench Error Analysis" in markdown
    assert "Confusion Matrix" in markdown
    assert "Cases To Review" in markdown


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
    assert baseline["confidence_intervals"]["failure_label_macro_f1"]["low"] == 1.0
    assert baseline["confidence_intervals"]["failure_label_macro_f1"]["high"] == 1.0
    assert baseline["per_label"]["no_failure_detected"]["f1"] == 1.0
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


def test_ragtruth_adapter_builds_contexttrace_case_pack() -> None:
    case_pack = adapt_ragtruth_rows(
        [
            {
                "id": "1472",
                "source_id": "11316",
                "model": "mistral-7B-instruct",
                "labels": [
                    {
                        "start": 219,
                        "end": 229,
                        "text": "Gaza Strip",
                        "label_type": "Evident Baseless Info",
                    }
                ],
                "split": "train",
                "quality": "good",
                "response": "The answer adds Gaza Strip.",
            },
            {
                "id": "skip-quality",
                "source_id": "11316",
                "labels": [],
                "quality": "truncated",
                "response": "truncated",
            },
        ],
        source_rows=[
            {
                "source_id": "11316",
                "task_type": "Summary",
                "source": "CNN/DM",
                "source_info": "The source article mentions East Jerusalem.",
                "prompt": "Summarize the following news.",
            }
        ],
    )

    assert case_pack["dataset"] == "RAGTruth"
    assert case_pack["stats"]["input_responses"] == 2
    assert case_pack["stats"]["output_cases"] == 1
    assert case_pack["stats"]["skipped_filtered"] == 1
    case = case_pack["cases"][0]
    assert case["id"] == "ragtruth_1472"
    assert case["query"] == "Summarize the following news."
    assert case["contexts"][0]["text"] == "The source article mentions East Jerusalem."
    assert case["expected_labels"] == ["partial_support"]
    assert case["expected_verdict_counts"]["partially_supported"] == 1
    assert case["expected_evidence_spans"] == []
    assert case["ragtruth_metadata"]["answer_hallucination_spans"][0]["text"] == "Gaza Strip"


def test_ragtruth_adapter_builds_deterministic_stratified_sample() -> None:
    response_rows = [
        {
            "id": str(index),
            "source_id": "summary" if index % 2 == 0 else "qa",
            "model": "model-a" if index < 4 else "model-b",
            "labels": (
                [
                    {
                        "start": 0,
                        "end": 5,
                        "text": "wrong",
                        "label_type": "Evident Conflict" if index in {2, 6} else "Evident Baseless Info",
                    }
                ]
                if index in {1, 2, 5, 6}
                else []
            ),
            "split": "test",
            "quality": "good",
            "response": "Response %s" % index,
        }
        for index in range(8)
    ]
    source_rows = [
        {
            "source_id": "summary",
            "task_type": "Summary",
            "source": "CNN/DM",
            "source_info": "Summary source text.",
            "prompt": "Summarize.",
        },
        {
            "source_id": "qa",
            "task_type": "QA",
            "source": "MARCO",
            "source_info": {"question": "Question?", "passages": "QA source text."},
        },
    ]

    first = adapt_ragtruth_rows(
        response_rows,
        source_rows=source_rows,
        split="test",
        sample_size=3,
        sample_seed=99,
        stratify_by=["expected_label"],
    )
    second = adapt_ragtruth_rows(
        response_rows,
        source_rows=source_rows,
        split="test",
        sample_size=3,
        sample_seed=99,
        stratify_by=["expected_label"],
    )

    assert [case["id"] for case in first["cases"]] == [case["id"] for case in second["cases"]]
    assert first["stats"]["output_cases"] == 3
    assert first["stats"]["eligible_cases"] == 8
    assert first["stats"]["sampling"]["method"] == "stratified"
    assert first["stats"]["sampling"]["sample_seed"] == 99
    labels = {tuple(case["expected_labels"]) for case in first["cases"]}
    assert ("no_failure_detected",) in labels
    assert ("partial_support",) in labels
    assert ("contradicted_answer",) in labels


def test_ragtruth_review_queue_and_mapping_updates_case_pack() -> None:
    case_pack = adapt_ragtruth_rows(
        [
            {
                "id": "1472",
                "source_id": "11316",
                "labels": [
                    {
                        "start": 219,
                        "end": 229,
                        "text": "Gaza Strip",
                        "label_type": "Evident Baseless Info",
                    }
                ],
                "quality": "good",
                "response": "The answer adds Gaza Strip.",
            }
        ],
        source_rows=[
            {
                "source_id": "11316",
                "task_type": "Summary",
                "source": "CNN/DM",
                "source_info": "The source article mentions East Jerusalem, not Gaza Strip.",
                "prompt": "Summarize the following news.",
            }
        ],
    )

    queue = build_review_queue(case_pack)
    assert len(queue) == 1
    assert queue[0]["case_id"] == "ragtruth_1472"
    assert queue[0]["review_status"] == "needs_review"
    assert queue[0]["answer_hallucination_spans"][0]["text"] == "Gaza Strip"
    assert queue[0]["source_contexts"][0]["source_id"] == "11316"
    assert queue[0]["source_evidence_span_suggestions"] == []

    suggested_queue = build_review_queue(case_pack, suggest_source_spans=True, max_suggestions=1)
    assert suggested_queue[0]["source_evidence_span_suggestions"]
    assert suggested_queue[0]["source_evidence_span_suggestions"][0]["source_id"] == "11316"
    assert "East Jerusalem" in suggested_queue[0]["source_evidence_span_suggestions"][0]["text"]
    assert suggested_queue[0]["source_evidence_spans"] == []

    queue[0]["review_status"] = "reviewed"
    queue[0]["reviewer"] = "unit-test"
    queue[0]["reviewed_at"] = "2026-06-12"
    queue[0]["source_evidence_spans"] = ["The source article mentions East Jerusalem, not Gaza Strip."]
    reviewed = apply_review_mappings(case_pack, queue, require_reviewed=True, review_file="review.jsonl")

    assert reviewed["review"]["status"] == "reviewed"
    assert reviewed["review"]["reviewed_cases"] == 1
    reviewed_case = reviewed["cases"][0]
    assert reviewed_case["expected_evidence_spans"] == ["The source article mentions East Jerusalem, not Gaza Strip."]
    assert reviewed_case["review_metadata"]["reviewed"] is True
    assert reviewed_case["review_metadata"]["reviewer"] == "unit-test"
    assert "human review artifacts" in reviewed["limitations"][0]


def test_ragtruth_review_packet_renders_human_checklist() -> None:
    case_pack = adapt_ragtruth_rows(
        [
            {
                "id": "1472",
                "source_id": "11316",
                "labels": [
                    {
                        "start": 219,
                        "end": 229,
                        "text": "Gaza Strip",
                        "label_type": "Evident Baseless Info",
                    }
                ],
                "quality": "good",
                "response": "The answer adds Gaza Strip.",
            }
        ],
        source_rows=[
            {
                "source_id": "11316",
                "task_type": "Summary",
                "source": "CNN/DM",
                "source_info": "The source article mentions East Jerusalem, not Gaza Strip. More source text follows.",
                "prompt": "Summarize the following news.",
            }
        ],
    )
    queue = build_review_queue(case_pack, suggest_source_spans=True, max_suggestions=1)

    packet = build_review_packet(
        queue,
        title="Unit Review Packet",
        generated_at="2026-06-12T00:00:00+00:00",
        context_char_limit=48,
    )

    assert "# Unit Review Packet" in packet
    assert "Review rows: `1`" in packet
    assert "## Reviewer Checklist" in packet
    assert "## Case 1: `ragtruth_1472`" in packet
    assert "Gaza Strip" in packet
    assert "East Jerusalem" in packet
    assert "source_evidence_spans" in packet
    assert "Truncated in packet: `yes`" in packet


def test_ragtruth_review_validation_checks_signoff_and_source_spans() -> None:
    case_pack = adapt_ragtruth_rows(
        [
            {
                "id": "1472",
                "source_id": "11316",
                "labels": [
                    {
                        "start": 219,
                        "end": 229,
                        "text": "Gaza Strip",
                        "label_type": "Evident Baseless Info",
                    }
                ],
                "quality": "good",
                "response": "The answer adds Gaza Strip.",
            }
        ],
        source_rows=[
            {
                "source_id": "11316",
                "task_type": "Summary",
                "source": "CNN/DM",
                "source_info": "The source article mentions East Jerusalem, not Gaza Strip.",
                "prompt": "Summarize the following news.",
            }
        ],
    )
    queue = build_review_queue(case_pack)
    queue[0]["review_status"] = "reviewed"
    queue[0]["reviewer"] = "reviewer-a"
    queue[0]["reviewed_at"] = "2026-06-13"
    queue[0]["source_evidence_spans"] = ["The source article mentions East Jerusalem, not Gaza Strip."]

    valid = validate_review_mappings(
        case_pack,
        queue,
        require_reviewed=True,
        require_source_spans=True,
    )

    assert valid["valid"] is True
    assert valid["reviewed_rows"] == 1
    assert valid["source_span_rows"] == 1
    assert valid["errors"] == []

    invalid_queue = build_review_queue(case_pack)
    invalid_queue[0]["review_status"] = "reviewed"
    invalid_queue[0]["source_evidence_spans"] = ["A span that is not in the source."]
    invalid = validate_review_mappings(
        case_pack,
        invalid_queue,
        require_reviewed=True,
        require_source_spans=True,
    )

    assert invalid["valid"] is False
    messages = [error["message"] for error in invalid["errors"]]
    assert "Reviewed row must include reviewer." in messages
    assert "Reviewed row must include reviewed_at." in messages
    assert any("not found in the source contexts" in message for message in messages)


def test_ragtruth_review_workflow_builds_manifest_and_packet(tmp_path) -> None:
    response_path = tmp_path / "response.jsonl"
    source_path = tmp_path / "source_info.jsonl"
    response_rows = [
        {
            "id": "supported",
            "source_id": "policy",
            "labels": [],
            "split": "test",
            "quality": "good",
            "response": "Refunds are available within 30 days.",
        },
        {
            "id": "overreach",
            "source_id": "policy",
            "labels": [
                {
                    "start": 0,
                    "end": 10,
                    "text": "cash refund",
                    "label_type": "Evident Baseless Info",
                }
            ],
            "split": "test",
            "quality": "good",
            "response": "Cash refunds are available.",
        },
    ]
    source_rows = [
        {
            "source_id": "policy",
            "task_type": "QA",
            "source": "fixture",
            "source_info": {
                "question": "What does the policy say?",
                "passages": "Store credit is available within 30 days.",
            },
        }
    ]
    response_path.write_text("\n".join(json.dumps(row) for row in response_rows) + "\n", encoding="utf-8")
    source_path.write_text("\n".join(json.dumps(row) for row in source_rows) + "\n", encoding="utf-8")

    manifest = run_ragtruth_review_workflow(
        response_path=response_path,
        source_info_path=source_path,
        output_dir=tmp_path / "workflow",
        sample_size=2,
        sample_seed=7,
        stratify_by=["expected_label"],
        bootstrap_samples=10,
    )

    assert manifest["status"] == "needs_review"
    assert manifest["case_pack"]["cases"] == 2
    assert manifest["review"]["review_rows"] == 1
    assert Path(manifest["artifacts"]["case_pack"]).exists()
    assert Path(manifest["artifacts"]["review_queue"]).exists()
    assert Path(manifest["artifacts"]["review_packet"]).exists()
    assert Path(manifest["artifacts"]["manifest"]).exists()


def test_ragtruth_review_workflow_validates_and_applies_review(tmp_path) -> None:
    response_path = tmp_path / "response.jsonl"
    source_path = tmp_path / "source_info.jsonl"
    review_path = tmp_path / "review.jsonl"
    response_rows = [
        {
            "id": "supported",
            "source_id": "policy",
            "labels": [],
            "split": "test",
            "quality": "good",
            "response": "Store credit is available within 30 days.",
        },
        {
            "id": "overreach",
            "source_id": "policy",
            "labels": [
                {
                    "start": 0,
                    "end": 10,
                    "text": "cash refund",
                    "label_type": "Evident Baseless Info",
                }
            ],
            "split": "test",
            "quality": "good",
            "response": "Cash refunds are available.",
        },
    ]
    response_path.write_text("\n".join(json.dumps(row) for row in response_rows) + "\n", encoding="utf-8")
    source_path.write_text(
        json.dumps(
            {
                "source_id": "policy",
                "task_type": "QA",
                "source": "fixture",
                "source_info": {
                    "question": "What does the policy say?",
                    "passages": "Store credit is available within 30 days.",
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    review_path.write_text(
        json.dumps(
            {
                "case_id": "ragtruth_overreach",
                "review_status": "reviewed",
                "reviewer": "unit-test",
                "reviewed_at": "2026-06-13",
                "source_evidence_spans": ["Store credit is available within 30 days."],
                "expected_labels": ["partial_support"],
                "expected_primary_root_cause": "answer_overreach",
                "expected_verdict_counts": {"partially_supported": 1},
            }
        )
        + "\n",
        encoding="utf-8",
    )

    manifest = run_ragtruth_review_workflow(
        response_path=response_path,
        source_info_path=source_path,
        output_dir=tmp_path / "workflow_reviewed",
        sample_size=2,
        sample_seed=7,
        stratify_by=["expected_label"],
        review_path=review_path,
        skip_score=True,
    )

    assert manifest["status"] == "review_validated"
    assert manifest["review"]["valid"] is True
    assert manifest["review"]["errors"] == 0
    assert Path(manifest["artifacts"]["review_validation"]).exists()
    reviewed = json.loads(Path(manifest["artifacts"]["reviewed_case_pack"]).read_text(encoding="utf-8"))
    assert reviewed["review"]["status"] == "reviewed"
    assert reviewed["review"]["reviewed_cases"] == 1
    assert reviewed["review"]["required_review_cases"] == 1
    reviewed_cases = {case["id"]: case for case in reviewed["cases"]}
    assert reviewed_cases["ragtruth_overreach"]["expected_evidence_spans"] == ["Store credit is available within 30 days."]
    assert "review_metadata" not in reviewed_cases["ragtruth_supported"]


def test_ragtruth_release_workflow_builds_review_pending_bundle(tmp_path) -> None:
    response_path = tmp_path / "response.jsonl"
    source_path = tmp_path / "source_info.jsonl"
    response_path.write_text(
        "\n".join(
            json.dumps(row)
            for row in [
                {
                    "id": "supported",
                    "source_id": "policy",
                    "labels": [],
                    "split": "test",
                    "quality": "good",
                    "response": "Store credit is available within 30 days.",
                },
                {
                    "id": "overreach",
                    "source_id": "policy",
                    "labels": [
                        {
                            "start": 0,
                            "end": 10,
                            "text": "cash refund",
                            "label_type": "Evident Baseless Info",
                        }
                    ],
                    "split": "test",
                    "quality": "good",
                    "response": "Cash refunds are available.",
                },
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    source_path.write_text(
        json.dumps(
            {
                "source_id": "policy",
                "task_type": "QA",
                "source": "fixture",
                "source_info": {
                    "question": "What does the policy say?",
                    "passages": "Store credit is available within 30 days.",
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )

    summary = run_ragtruth_release_workflow(
        response_path=response_path,
        source_info_path=source_path,
        output_dir=tmp_path / "ragtruth",
        bundle_dir=tmp_path / "bundle",
        sample_size=2,
        sample_seed=7,
        stratify_by=["expected_label"],
        bootstrap_samples=10,
    )
    rendered = render_ragtruth_release_summary(summary)
    manifest = json.loads((tmp_path / "bundle" / "manifest.json").read_text(encoding="utf-8"))

    assert summary["status"] == "review_pending"
    assert summary["workflow_status"] == "needs_review"
    assert summary["case_count"] == 2
    assert manifest["bundle_status"] == "review_pending"
    assert any(artifact["path"] == "ragtruth_review_packet.md" for artifact in manifest["artifacts"])
    assert "RAGTruth release workflow" in rendered


def test_ragtruth_release_workflow_scores_reviewed_calibration_bundle(tmp_path) -> None:
    response_path = tmp_path / "response.jsonl"
    source_path = tmp_path / "source_info.jsonl"
    review_path = tmp_path / "review.jsonl"
    response_path.write_text(
        "\n".join(
            json.dumps(row)
            for row in [
                {
                    "id": "supported",
                    "source_id": "policy",
                    "labels": [],
                    "split": "test",
                    "quality": "good",
                    "response": "Store credit is available within 30 days.",
                },
                {
                    "id": "overreach",
                    "source_id": "policy",
                    "labels": [
                        {
                            "start": 0,
                            "end": 10,
                            "text": "cash refund",
                            "label_type": "Evident Baseless Info",
                        }
                    ],
                    "split": "test",
                    "quality": "good",
                    "response": "Cash refunds are available.",
                },
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    source_path.write_text(
        json.dumps(
            {
                "source_id": "policy",
                "task_type": "QA",
                "source": "fixture",
                "source_info": {
                    "question": "What does the policy say?",
                    "passages": "Store credit is available within 30 days.",
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    review_path.write_text(
        json.dumps(
            {
                "case_id": "ragtruth_overreach",
                "review_status": "reviewed",
                "reviewer": "unit-test",
                "reviewed_at": "2026-06-18",
                "source_evidence_spans": ["Store credit is available within 30 days."],
                "expected_labels": ["partial_support"],
                "expected_primary_root_cause": "answer_overreach",
                "expected_verdict_counts": {"partially_supported": 1},
            }
        )
        + "\n",
        encoding="utf-8",
    )

    summary = run_ragtruth_release_workflow(
        response_path=response_path,
        source_info_path=source_path,
        output_dir=tmp_path / "ragtruth",
        bundle_dir=tmp_path / "bundle",
        review_path=review_path,
        sample_size=2,
        sample_seed=7,
        stratify_by=["expected_label"],
        bootstrap_samples=10,
    )
    manifest = json.loads((tmp_path / "bundle" / "manifest.json").read_text(encoding="utf-8"))

    assert summary["status"] == "calibration_only"
    assert summary["workflow_status"] == "scored"
    assert summary["baseline_count"] == 0
    assert manifest["bundle_status"] == "calibration_only"
    assert manifest["score"]["summary"]["cases"] == 2
    assert any(artifact["path"] == "scored/contexttrace_bench_results.json" for artifact in manifest["artifacts"])
    assert any(artifact["path"] == "scored/ragtruth_error_analysis.json" for artifact in manifest["artifacts"])
    assert any(artifact["path"] == "scored/ragtruth_error_analysis.md" for artifact in manifest["artifacts"])
    assert any(artifact["path"] == "ragtruth_review_signoff.jsonl" for artifact in manifest["artifacts"])


def test_ragtruth_error_analysis_groups_calibration_targets() -> None:
    case_pack = {
        "dataset": "RAGTruth",
        "cases": [
            {
                "id": "ragtruth_supported",
                "source": "RAGTruth/QA/fixture",
                "contexts": [{"task_type": "QA", "text": "Store credit is available within 30 days."}],
                "ragtruth_metadata": {
                    "response_id": "supported",
                    "source_id": "policy",
                    "model": "gpt-fixture",
                    "answer_hallucination_spans": [],
                },
            },
            {
                "id": "ragtruth_overreach",
                "source": "RAGTruth/QA/fixture",
                "contexts": [{"task_type": "QA", "text": "Store credit is available within 30 days."}],
                "expected_evidence_spans": ["Store credit is available within 30 days."],
                "ragtruth_metadata": {
                    "response_id": "overreach",
                    "source_id": "policy",
                    "model": "gpt-fixture",
                    "answer_hallucination_spans": [
                        {
                            "start": 0,
                            "end": 10,
                            "text": "cash refund",
                            "label_type": "Evident Baseless Info",
                        }
                    ],
                },
                "review_metadata": {
                    "review_status": "reviewed",
                    "reviewer": "unit-test",
                    "source_evidence_span_count": 1,
                },
            },
        ],
    }
    result = {
        "summary": {
            "failure_label_macro_f1": 0.25,
            "root_cause_accuracy": 0.5,
            "evidence_span_overlap": 0.1,
            "dangerous_false_green_rate": 0.5,
        },
        "rows": [
            {
                "id": "ragtruth_supported",
                "expected": ["no_failure_detected"],
                "predicted": ["no_failure_detected"],
                "expected_primary_root_cause": "no_failure_detected",
                "predicted_primary_root_cause": "no_failure_detected",
                "expected_evidence_spans": [],
                "predicted_evidence_spans": [],
                "evidence_span_overlap": None,
                "verdict_match": True,
                "benchmark_pass": True,
            },
            {
                "id": "ragtruth_overreach",
                "expected": ["partial_support"],
                "predicted": ["no_failure_detected"],
                "expected_primary_root_cause": "answer_overreach",
                "predicted_primary_root_cause": "no_failure_detected",
                "expected_evidence_spans": ["Store credit is available within 30 days."],
                "predicted_evidence_spans": ["Cash refunds are available."],
                "evidence_span_overlap": 0.1,
                "verdict_match": False,
                "benchmark_pass": False,
            },
        ],
    }

    analysis = build_ragtruth_error_analysis(result, case_pack, max_cases=5)
    rendered = render_ragtruth_error_analysis_markdown(analysis)

    assert analysis["case_count"] == 2
    assert analysis["summary"]["misses"] == 1
    assert analysis["summary"]["dangerous_false_greens"] == 1
    assert analysis["summary"]["root_cause_misses"] == 1
    assert analysis["summary"]["span_localization_misses"] == 1
    assert analysis["calibration_targets"]["dangerous_false_greens"][0]["id"] == "ragtruth_overreach"
    assert any(group["value"] == "QA" and group["misses"] == 1 for group in analysis["groups"]["task_type"])
    assert any(group["value"] == "Evident Baseless Info" for group in analysis["groups"]["label_type"])
    assert {
        "expected": "answer_overreach",
        "predicted": "no_failure_detected",
        "count": 1,
    } in analysis["groups"]["root_cause_confusion"]
    assert "RAGTruth Error Analysis" in rendered
    assert "Top Calibration Targets" in rendered


def test_contexttrace_bench_runs_external_case_pack(tmp_path) -> None:
    case_pack = adapt_ragtruth_rows(
        [
            {
                "id": "supported",
                "source_id": "policy",
                "labels": [],
                "quality": "good",
                "response": "Refunds are available within 30 days.",
            }
        ],
        source_rows=[
            {
                "source_id": "policy",
                "task_type": "QA",
                "source": "fixture",
                "source_info": {
                    "question": "What does the policy say about refunds?",
                    "passages": "Refunds are available within 30 days.",
                },
                "prompt": "Answer from the policy.",
            }
        ],
    )
    case_pack_path = tmp_path / "ragtruth_case_pack.json"
    case_pack_path.write_text(json.dumps(case_pack), encoding="utf-8")

    result = run_contexttrace_case_pack(
        mode="semantic",
        case_pack_path=case_pack_path,
        bootstrap_samples=25,
    )
    paths = write_benchmark_outputs(result, output_dir=tmp_path / "out")

    assert result["case_set"] == "external_case_pack"
    assert result["case_pack_dataset"] == "RAGTruth"
    assert result["summary"]["cases"] == 1
    assert result["summary"]["failure_label_macro_f1"] == 1.0
    assert result["limitations"]
    assert result["confidence_intervals"]["failure_label_macro_f1"]["samples"] == 25
    assert result["rows"][0]["variant_type"] == "external_case_pack"
    assert result["rows"][0]["case_pack_metadata"]["ragtruth_metadata"]["response_id"] == "supported"

    candidate_inputs = (tmp_path / "out" / "candidate_inputs.jsonl").read_text(encoding="utf-8").splitlines()
    assert candidate_inputs
    candidate_input = json.loads(candidate_inputs[0])
    assert candidate_input["trace"]["contexts"][0]["metadata"]["source_id"] == "policy"
    assert "ragtruth_metadata" not in json.dumps(candidate_input)
    assert "Limitations" in (tmp_path / "out" / "results.md").read_text(encoding="utf-8")
    assert "Limitations" in (tmp_path / "out" / "report.html").read_text(encoding="utf-8")
    assert paths["results_md"].endswith("results.md")


def test_contexttrace_bench_cli_scores_external_case_pack(tmp_path) -> None:
    case_pack = {
        "description": "Tiny external case pack fixture.",
        "dataset": "fixture",
        "adapter": "unit_test",
        "cases": [
            {
                "id": "case-supported",
                "source": "fixture",
                "query": "What does the policy say about refunds?",
                "answer": "Refunds are available within 30 days.",
                "contexts": [
                    {
                        "id": "policy",
                        "text": "Refunds are available within 30 days.",
                        "source_id": "policy",
                    }
                ],
                "expected_labels": ["no_failure_detected"],
                "expected_verdict_counts": {"supported": 1},
                "expected_primary_root_cause": "no_failure_detected",
                "expected_evidence_spans": ["Refunds are available within 30 days."],
            }
        ],
    }
    case_pack_path = tmp_path / "case_pack.json"
    output_dir = tmp_path / "out"
    case_pack_path.write_text(json.dumps(case_pack), encoding="utf-8")

    assert run_contexttrace_main(
        [
            "--mode",
            "semantic",
            "--case-pack",
            str(case_pack_path),
            "--output-dir",
            str(output_dir),
            "--bootstrap-samples",
            "10",
        ]
    ) == 0

    payload = json.loads((output_dir / "contexttrace_bench_results.json").read_text(encoding="utf-8"))
    assert payload["case_set"] == "external_case_pack"
    assert payload["case_pack_dataset"] == "fixture"
    assert payload["summary"]["failure_label_macro_f1"] == 1.0
    assert "Confidence Intervals" in (output_dir / "results.md").read_text(encoding="utf-8")


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
