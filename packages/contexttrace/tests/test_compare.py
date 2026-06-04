import json

from contexttrace.cli import main
from contexttrace.verify import compare_failures, compare_trace_files, compare_verifications, verify_trace
from contexttrace.verify.compare_report import CompareReportGenerator
from contexttrace.verify.schema import RAGTrace, TraceContext


def _baseline_trace() -> dict:
    return {
        "query": "What is the refund policy?",
        "answer": "Refunds are allowed within 30 days.",
        "contexts": [
            {
                "id": "policy",
                "text": "Customers may request refunds within 30 days of purchase.",
            }
        ],
    }


def _regressed_trace() -> dict:
    return {
        "query": "What is the refund policy?",
        "answer": (
            "Refunds are allowed within 30 days. "
            "Refunds are processed within 5 business days."
        ),
        "contexts": [
            {
                "id": "policy",
                "text": "Customers may request refunds within 30 days of purchase.",
            }
        ],
    }


def test_compare_raw_traces_detects_new_unsupported_claim(tmp_path):
    baseline_path = tmp_path / "baseline.json"
    current_path = tmp_path / "current.json"
    baseline_path.write_text(json.dumps(_baseline_trace()), encoding="utf-8")
    current_path.write_text(json.dumps(_regressed_trace()), encoding="utf-8")

    result = compare_trace_files(baseline_path, current_path)

    assert result["summary"]["regression"] is True
    assert result["summary"]["support_rate_delta"] < 0
    assert result["summary"]["new_failures"] == 1
    assert result["summary"]["new_unsupported"] == 1
    assert result["changes"][0]["status"] == "added_failure"
    assert "5 business days" in result["changes"][0]["claim"]


def test_compare_accepts_verified_result_json(tmp_path):
    baseline = verify_trace(
        RAGTrace(
            query="What is the refund policy?",
            answer="Refunds are allowed within 30 days.",
            contexts=[
                TraceContext(
                    id="policy",
                    text="Customers may request refunds within 30 days of purchase.",
                )
            ],
        )
    )
    current = verify_trace(
        RAGTrace(
            query="What is the refund policy?",
            answer="Refunds are allowed within 30 days.",
            contexts=[
                TraceContext(
                    id="policy",
                    text="Customers may request refunds within 30 days of purchase.",
                )
            ],
        )
    )
    baseline_path = tmp_path / "baseline_verified.json"
    current_path = tmp_path / "current_verified.json"
    baseline_path.write_text(json.dumps(baseline), encoding="utf-8")
    current_path.write_text(json.dumps(current), encoding="utf-8")

    result = compare_trace_files(baseline_path, current_path)

    assert result["summary"]["regression"] is False
    assert result["summary"]["changed_claims"] == 0
    assert result["baseline"]["metadata"]["compare_input_type"] == "verification_result"


def test_compare_verifications_detects_resolved_failure():
    baseline = verify_trace(
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
    current = verify_trace(
        RAGTrace(
            query="How long does refund processing take?",
            answer="Refunds are processed within 5 business days.",
            contexts=[
                TraceContext(
                    id="policy",
                    text="Refunds are processed within 5 business days.",
                )
            ],
        )
    )

    result = compare_verifications(baseline, current)

    assert result["summary"]["regression"] is False
    assert result["summary"]["improved"] is True
    assert result["summary"]["resolved_failures"] >= 1


def test_compare_failures_flags_configured_gate(tmp_path):
    baseline_path = tmp_path / "baseline.json"
    current_path = tmp_path / "current.json"
    baseline_path.write_text(json.dumps(_baseline_trace()), encoding="utf-8")
    current_path.write_text(json.dumps(_regressed_trace()), encoding="utf-8")
    result = compare_trace_files(baseline_path, current_path)

    failures = compare_failures(result, ("new_failure", "support_rate_drop"))

    assert "new verification failure detected" in failures
    assert "support rate dropped" in failures


def test_compare_report_generation(tmp_path):
    baseline_path = tmp_path / "baseline.json"
    current_path = tmp_path / "current.json"
    report_path = tmp_path / "compare.html"
    baseline_path.write_text(json.dumps(_baseline_trace()), encoding="utf-8")
    current_path.write_text(json.dumps(_regressed_trace()), encoding="utf-8")
    result = compare_trace_files(baseline_path, current_path)

    written = CompareReportGenerator().generate(result, path=str(report_path))

    assert written == str(report_path)
    html = report_path.read_text(encoding="utf-8")
    assert "ContextTrace Regression Report" in html
    assert "Regression Summary" in html
    assert "New Failures" in html
    assert "5 business days" in html


def test_compare_cli_json_report_and_fail_on(tmp_path, capsys):
    baseline_path = tmp_path / "baseline.json"
    current_path = tmp_path / "current.json"
    report_path = tmp_path / "compare.html"
    baseline_path.write_text(json.dumps(_baseline_trace()), encoding="utf-8")
    current_path.write_text(json.dumps(_regressed_trace()), encoding="utf-8")

    exit_code = main(
        [
            "compare",
            str(baseline_path),
            str(current_path),
            "--json",
            "--report",
            "--out",
            str(report_path),
            "--fail-on",
            "new_failure",
        ]
    )

    assert exit_code == 1
    output = json.loads(capsys.readouterr().out)
    assert output["summary"]["regression"] is True
    assert output["summary"]["new_failures"] == 1
    assert report_path.exists()


def test_compare_cli_plain_output(tmp_path, capsys):
    baseline_path = tmp_path / "baseline.json"
    current_path = tmp_path / "current.json"
    baseline_path.write_text(json.dumps(_baseline_trace()), encoding="utf-8")
    current_path.write_text(json.dumps(_regressed_trace()), encoding="utf-8")

    assert main(["compare", str(baseline_path), str(current_path)]) == 0

    output = capsys.readouterr().out
    assert "Regression: true" in output
    assert "New failures: 1" in output
