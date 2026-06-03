import json

import pytest

from contexttrace.cli import main
from contexttrace.verify import verify_trace
from contexttrace.verify.benchmark import run_verify_benchmark
from contexttrace.verify.claims import extract_claims
from contexttrace.verify.evidence import find_best_evidence
from contexttrace.verify.report import VerifyReportGenerator
from contexttrace.verify.schema import (
    RAGTrace,
    TraceCitation,
    TraceContext,
    VerificationInputError,
    load_trace,
    load_trace_file,
)


def test_verify_schema_loads_valid_trace(tmp_path):
    path = tmp_path / "trace.json"
    path.write_text(
        json.dumps(
            {
                "query": "What is the refund policy?",
                "answer": "Refunds are allowed within 30 days.",
                "contexts": [
                    {
                        "id": "policy_2026",
                        "text": "Customers may request refunds within 30 days.",
                        "metadata": {"source": "refund_policy.pdf"},
                    }
                ],
                "citations": [
                    {
                        "claim": "Refunds are allowed within 30 days.",
                        "source_id": "policy_2026",
                    }
                ],
                "metadata": {"run_id": "demo"},
            }
        ),
        encoding="utf-8",
    )

    trace = load_trace_file(path)

    assert trace.query == "What is the refund policy?"
    assert trace.contexts[0].id == "policy_2026"
    assert trace.citations[0].source_id == "policy_2026"
    assert trace.metadata["run_id"] == "demo"


def test_verify_schema_rejects_invalid_trace():
    with pytest.raises(VerificationInputError, match="contexts"):
        load_trace({"query": "Q", "answer": "A"})

    with pytest.raises(VerificationInputError, match="contexts\\[0\\].*text"):
        load_trace({"query": "Q", "answer": "A", "contexts": [{"id": "ctx"}]})


def test_verify_cli_reports_invalid_json(tmp_path, capsys):
    path = tmp_path / "bad.json"
    path.write_text("{not-json", encoding="utf-8")

    assert main(["verify", str(path)]) == 1

    assert "Invalid JSON" in capsys.readouterr().err


def test_claim_extraction_splits_sentences_and_skips_filler():
    claims = extract_claims(
        "Sure. Refunds are allowed within 30 days. Refunds are processed in 5 business days."
    )

    assert [claim.id for claim in claims] == ["claim_1", "claim_2"]
    assert [claim.text for claim in claims] == [
        "Refunds are allowed within 30 days.",
        "Refunds are processed in 5 business days.",
    ]


def test_claim_extraction_decomposes_simple_compound_claims():
    claims = extract_claims(
        "Refunds are allowed within 30 days and processed within 5 business days."
    )

    assert [claim.text for claim in claims] == [
        "Refunds are allowed within 30 days.",
        "Refunds are processed within 5 business days.",
    ]


def test_claim_extraction_does_not_split_noun_lists():
    claims = extract_claims("Customers can request refunds and exchanges within 30 days.")

    assert [claim.text for claim in claims] == [
        "Customers can request refunds and exchanges within 30 days."
    ]


def test_evidence_matching_finds_best_context_and_terms():
    contexts = [
        TraceContext(id="shipping", text="Standard shipping takes 3 to 5 business days."),
        TraceContext(id="policy", text="Customers may request refunds within 30 days of purchase."),
    ]

    match = find_best_evidence("Refunds are allowed within 30 days.", contexts)

    assert match.context_id == "policy"
    assert match.score >= 0.6
    assert "refunds" in match.matched_terms
    assert "30" in match.matched_terms


def test_supported_claim_classification():
    result = verify_trace(
        RAGTrace(
            query="What is the refund policy?",
            answer="Refunds are allowed within 30 days.",
            contexts=[
                TraceContext(
                    id="policy",
                    text="Customers may request refunds within 30 days of purchase.",
                )
            ],
            citations=[
                TraceCitation(
                    claim="Refunds are allowed within 30 days.",
                    source_id="policy",
                )
            ],
        )
    )

    assert result["summary"]["supported"] == 1
    assert result["summary"]["support_rate"] == 1.0
    assert result["summary"]["unsupported_claim_rate"] == 0.0
    assert result["summary"]["failure_type"] == "no_failure_detected"
    assert result["claims"][0]["verdict"] == "supported"
    assert result["claims"][0]["citation_status"] == "citation_ok"


def test_unsupported_claim_classification():
    result = verify_trace(
        RAGTrace(
            query="How long does refund processing take?",
            answer="Refunds are processed within 5 business days.",
            contexts=[
                TraceContext(
                    id="policy",
                    text="Customers may request refunds within 30 days of purchase.",
                )
            ],
        )
    )

    assert result["summary"]["unsupported"] == 1
    assert result["summary"]["unsupported_claim_rate"] == 1.0
    assert "unsupported_answer" in result["summary"]["failure_types"]
    assert result["claims"][0]["verdict"] == "unsupported"


def test_partially_supported_claim_classification():
    result = verify_trace(
        RAGTrace(
            query="Can customers request refunds within 30 days?",
            answer="Refunds within 30 days require manager approval.",
            contexts=[
                TraceContext(
                    id="policy",
                    text="Customers may request refunds within 30 days of purchase.",
                )
            ],
        )
    )

    assert result["summary"]["partially_supported"] == 1
    assert result["summary"]["support_rate"] == 0.0
    assert "partial_support" in result["summary"]["failure_types"]
    assert result["summary"]["failure_type"] == "partial_support"
    assert result["abstention"]["should_abstain"] is False
    assert result["claims"][0]["verdict"] == "partially_supported"


def test_semantic_mode_supports_paraphrased_evidence():
    trace = RAGTrace(
        query="What is the refund policy?",
        answer="Refunds are allowed within 30 days.",
        contexts=[
            TraceContext(
                id="policy",
                text="Customers can request money back within thirty days of purchase.",
            )
        ],
    )

    lexical = verify_trace(trace)
    semantic = verify_trace(trace, mode="semantic")

    assert lexical["claims"][0]["verdict"] != "supported"
    assert semantic["claims"][0]["verdict"] == "supported"
    assert semantic["summary"]["mode"] == "semantic"


def test_citation_mismatch_detection():
    result = verify_trace(
        RAGTrace(
            query="What is the current refund window?",
            answer="Refunds are allowed within 30 days of purchase.",
            contexts=[
                TraceContext(
                    id="policy_2024",
                    text="Customers may exchange eligible items within 14 days.",
                ),
                TraceContext(
                    id="policy_2026",
                    text="Customers may request refunds within 30 days of purchase.",
                ),
            ],
            citations=[
                TraceCitation(
                    claim="Refunds are allowed within 30 days of purchase.",
                    source_id="policy_2024",
                )
            ],
        )
    )

    assert result["claims"][0]["verdict"] == "supported"
    assert result["claims"][0]["best_context_id"] == "policy_2026"
    assert result["claims"][0]["citation_status"] == "cited_source_does_not_support_claim"
    assert result["summary"]["citation_mismatches"] == 1
    assert result["summary"]["failure_type"] == "citation_mismatch"


def test_should_abstain_detection_when_contexts_do_not_support_answer():
    result = verify_trace(
        RAGTrace(
            query="What refund exception applies to VIP customers?",
            answer="VIP customers receive cash refunds up to 90 days after purchase.",
            contexts=[
                TraceContext(
                    id="shipping",
                    text="Standard shipping takes 3 to 5 business days.",
                )
            ],
        )
    )

    assert result["abstention"]["should_abstain"] is True
    assert "does not appear" in result["abstention"]["reason"]
    assert result["summary"]["failure_type"] == "should_have_abstained"


def test_report_generation(tmp_path):
    trace = RAGTrace(
        query="What is the refund policy?",
        answer="Refunds are allowed within 30 days.",
        contexts=[
            TraceContext(
                id="policy",
                text="Customers may request refunds within 30 days of purchase.",
            )
        ],
    )
    result = verify_trace(trace)
    report_path = tmp_path / "verify.html"

    written = VerifyReportGenerator().generate(result, trace, path=str(report_path))

    assert written == str(report_path)
    html = report_path.read_text(encoding="utf-8")
    assert "ContextTrace Verification Report" in html
    assert "Reliability Summary" in html
    assert "Claim Support Overview" in html
    assert "Raw JSON Summary" in html
    assert "<mark>refunds</mark>" in html


def test_verify_cli_json_and_report(tmp_path, capsys):
    trace_path = tmp_path / "trace.json"
    report_path = tmp_path / "report.html"
    trace_path.write_text(
        json.dumps(
            {
                "query": "What is the refund policy?",
                "answer": "Refunds are allowed within 30 days.",
                "contexts": [
                    {
                        "id": "policy",
                        "text": "Customers may request refunds within 30 days of purchase.",
                    }
                ],
                "citations": [
                    {
                        "claim": "Refunds are allowed within 30 days.",
                        "source_id": "policy",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    assert main(["verify", str(trace_path), "--json", "--report", "--out", str(report_path)]) == 0

    output = json.loads(capsys.readouterr().out)
    assert output["summary"]["support_rate"] == 1.0
    assert output["claims"][0]["citation_status"] == "citation_ok"
    assert report_path.exists()


def test_verify_demo_cli_defaults_to_unsupported_claim(capsys):
    assert main(["verify-demo", "--json"]) == 0

    output = json.loads(capsys.readouterr().out)
    assert output["metadata"]["run_id"] == "golden_unsupported_claim"
    assert output["summary"]["unsupported_claim_rate"] == 1.0
    assert output["summary"]["failure_type"] == "should_have_abstained"
    assert output["claims"][0]["verdict"] == "unsupported"


def test_verify_demo_cli_named_report(tmp_path, capsys):
    report_path = tmp_path / "citation-demo.html"

    assert main(["verify-demo", "citation_mismatch", "--report", "--out", str(report_path)]) == 0

    output = capsys.readouterr().out
    assert "Failure type: citation_mismatch" in output
    assert report_path.exists()
    html = report_path.read_text(encoding="utf-8")
    assert "cited_source_does_not_support_claim" in html
    assert "Best supporting context: policy_2026" in html


def test_verify_demo_cli_unknown_name(capsys):
    assert main(["verify-demo", "missing_demo"]) == 1

    assert "Available demos" in capsys.readouterr().err


def test_verify_cli_fail_on_unsupported_sets_exit_code(tmp_path, capsys):
    trace_path = tmp_path / "trace.json"
    trace_path.write_text(
        json.dumps(
            {
                "query": "How long does refund processing take?",
                "answer": "Refunds are processed within 5 business days.",
                "contexts": [
                    {
                        "id": "policy",
                        "text": "Customers may request refunds within 30 days of purchase.",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    assert main(["verify", str(trace_path), "--fail-on", "unsupported"]) == 1

    assert "unsupported claim detected" in capsys.readouterr().err


def test_verify_demo_fail_on_any_failure(capsys):
    assert main(["verify-demo", "supported_answer", "--fail-on", "any_failure"]) == 0
    capsys.readouterr()

    assert main(["verify-demo", "citation_mismatch", "--fail-on", "any_failure"]) == 1
    assert "verification failure detected" in capsys.readouterr().err


def test_verify_benchmark_semantic_mode_scores_curated_cases():
    result = run_verify_benchmark(mode="semantic")

    assert result["mode"] == "semantic"
    assert result["cases"] >= 5
    assert result["exact_match_rate"] >= 0.8
    assert result["per_label"]["unsupported_answer"]["recall"] >= 0.8


def test_verify_benchmark_cli_json(capsys):
    assert main(["verify-benchmark", "--mode", "semantic", "--json"]) == 0

    output = json.loads(capsys.readouterr().out)
    assert output["mode"] == "semantic"
    assert output["per_label"]["no_failure_detected"]["precision"] >= 0.8
