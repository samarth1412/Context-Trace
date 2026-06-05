from __future__ import annotations

import json

from contexttrace.cli import main
from contexttrace.verify.qa import qa_failures, qa_trace
from contexttrace.verify.qa_report import QAReportGenerator
from contexttrace.verify.schema import RAGTrace, TraceCitation, TraceContext


def _write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_qa_trace_passes_for_supported_cited_trace():
    trace = RAGTrace(
        query="What is the refund policy?",
        answer="Refunds are available within 30 days.",
        contexts=[TraceContext(id="policy", text="Refunds are available within 30 days.")],
        citations=[
            TraceCitation(
                claim="Refunds are available within 30 days.",
                source_id="policy",
            )
        ],
    )

    result = qa_trace(trace, trace_path="trace.json")

    assert result["summary"]["risk_level"] == "pass"
    assert result["summary"]["risk_score"] == 0
    assert result["summary"]["primary_issue"] == "no_failure_detected"
    assert result["summary"]["corpus_audited"] is False
    assert result["next_actions"] == []


def test_qa_trace_combines_verify_and_audit_diagnosis(tmp_path):
    _write(
        tmp_path / "corpus" / "contexttrace_local_mode.md",
        "ContextTrace stores local traces in .contexttrace/contexttrace.db.",
    )
    trace = RAGTrace(
        query="Where does ContextTrace store local traces?",
        answer="ContextTrace stores local traces in .contexttrace/contexttrace.db.",
        contexts=[
            TraceContext(
                id="reports",
                text="ContextTrace writes local HTML reports under .contexttrace/reports/.",
            )
        ],
    )

    result = qa_trace(trace, trace_path="trace.json", corpus_path=tmp_path / "corpus")

    assert result["summary"]["risk_level"] in {"medium", "high"}
    assert result["summary"]["risk_score"] >= 20
    assert result["summary"]["corpus_audited"] is True
    assert result["summary"]["audit_primary_label"] == "retrieval_miss"
    assert result["summary"]["failure_stages"] == {"retrieval": 1}
    assert any(action.startswith("Increase retrieval recall") for action in result["next_actions"])


def test_qa_failures_flags_risk_rules(tmp_path):
    _write(
        tmp_path / "corpus" / "policy.md",
        "Refunds are processed within 5 business days.",
    )
    trace = RAGTrace(
        query="How long does refund processing take?",
        answer="Refunds are processed within 5 business days.",
        contexts=[TraceContext(id="shipping", text="Shipping labels are sent after checkout.")],
    )
    result = qa_trace(trace, trace_path="trace.json", corpus_path=tmp_path / "corpus")

    failures = qa_failures(result, ("medium_risk", "audit_failure", "inspect_warning"))

    assert "medium-or-higher QA risk detected" in failures
    assert "audit failure detected" in failures
    assert "trace inspection warning detected" in failures


def test_qa_report_generation(tmp_path):
    trace = RAGTrace(
        query="What is the refund policy?",
        answer="Refunds are available within 30 days.",
        contexts=[TraceContext(id="policy", text="Refunds are available within 30 days.")],
        citations=[
            TraceCitation(
                claim="Refunds are available within 30 days.",
                source_id="policy",
            )
        ],
    )
    result = qa_trace(trace, trace_path="trace.json")
    report_path = tmp_path / "qa.html"

    written = QAReportGenerator().generate(result, trace, path=str(report_path))

    assert written == str(report_path)
    html = report_path.read_text(encoding="utf-8")
    assert "ContextTrace Evidence QA Report" in html
    assert "QA Summary" in html
    assert "Risk Signals" in html
    assert "Claim Verification" in html
    assert "Grounded means supported by the selected evidence span" in html
    assert "grounded_by_span" in html
    assert "not_assessed" in html


def test_qa_cli_json_report_and_fail_on(tmp_path, capsys):
    trace_path = tmp_path / "trace.json"
    report_path = tmp_path / "qa.html"
    _write(
        tmp_path / "corpus" / "policy.md",
        "Refunds are processed within 5 business days.",
    )
    trace_path.write_text(
        json.dumps(
            {
                "query": "How long does refund processing take?",
                "answer": "Refunds are processed within 5 business days.",
                "contexts": [
                    {
                        "id": "shipping",
                        "text": "Shipping labels are sent after checkout.",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    exit_code = main(
        [
            "qa",
            str(trace_path),
            "--corpus",
            str(tmp_path / "corpus"),
            "--json",
            "--report",
            "--out",
            str(report_path),
            "--fail-on",
            "medium_risk",
        ]
    )

    output = json.loads(capsys.readouterr().out)
    assert exit_code == 1
    assert output["summary"]["audit_primary_label"] == "retrieval_miss"
    assert output["summary"]["risk_score"] >= 20
    assert report_path.exists()


def test_qa_cli_plain_output(tmp_path, capsys):
    trace_path = tmp_path / "trace.json"
    trace_path.write_text(
        json.dumps(
            {
                "query": "What is the refund policy?",
                "answer": "Refunds are available within 30 days.",
                "contexts": [{"id": "policy", "text": "Refunds are available within 30 days."}],
                "citations": [
                    {
                        "claim": "Refunds are available within 30 days.",
                        "source_id": "policy",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    assert main(["qa", str(trace_path)]) == 0

    output = capsys.readouterr().out
    assert "Risk level: pass" in output
    assert "Primary issue: no_failure_detected" in output
    assert "Audit label: not_run" in output
