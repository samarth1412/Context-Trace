import json

from contexttrace.cli import main
from contexttrace.verify.audit import audit_failures, audit_trace, load_corpus
from contexttrace.verify.audit_report import AuditReportGenerator
from contexttrace.verify.schema import RAGTrace, TraceCitation, TraceContext


def _write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_load_corpus_reads_supported_text_files(tmp_path):
    _write(tmp_path / "docs" / "policy.md", "Refunds are processed within 5 business days.")
    _write(tmp_path / "docs" / "ignored.bin", "Refunds are not relevant.")

    corpus = load_corpus(tmp_path / "docs")

    assert len(corpus) == 1
    assert corpus[0].id == "policy.md"
    assert corpus[0].metadata["kind"] == "corpus_document"


def test_audit_detects_retrieval_miss_when_corpus_has_support(tmp_path):
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

    result = audit_trace(trace, corpus_path=tmp_path / "corpus")

    assert result["summary"]["primary_audit_label"] == "retrieval_miss"
    assert result["summary"]["retrieval_miss"] == 1
    assert result["claims"][0]["corpus"]["verdict"] == "supported"
    assert "broader corpus contains evidence" in result["claims"][0]["reason"]


def test_audit_detects_chunking_issue_when_same_source_omits_span(tmp_path):
    _write(
        tmp_path / "corpus" / "refund_policy.md",
        "Refunds are processed within 5 business days.",
    )
    trace = RAGTrace(
        query="How long does refund processing take?",
        answer="Refunds are processed within 5 business days.",
        contexts=[
            TraceContext(
                id="refund_chunk",
                text="Customers may request refunds within 30 days of purchase.",
                metadata={"source": "refund_policy.md"},
            )
        ],
    )

    result = audit_trace(trace, corpus_path=tmp_path / "corpus")

    assert result["summary"]["primary_audit_label"] == "chunking_issue"
    assert result["summary"]["chunking_issue"] == 1
    assert "omitted the supporting span" in result["claims"][0]["reason"]


def test_audit_detects_corpus_gap_when_no_source_supports_claim(tmp_path):
    _write(
        tmp_path / "corpus" / "shipping.md",
        "Standard shipping takes 3 to 5 business days.",
    )
    trace = RAGTrace(
        query="What refund exception applies to VIP customers?",
        answer="VIP customers receive cash refunds up to 90 days after purchase.",
        contexts=[
            TraceContext(
                id="shipping",
                text="Shipping labels are sent after checkout.",
            )
        ],
    )

    result = audit_trace(trace, corpus_path=tmp_path / "corpus")

    assert result["summary"]["primary_audit_label"] == "corpus_gap"
    assert result["summary"]["corpus_gap"] == 1
    assert result["claims"][0]["corpus"]["verdict"] == "unsupported"


def test_audit_detects_answer_overreach_for_partially_supported_claim(tmp_path):
    _write(
        tmp_path / "corpus" / "refund_policy.md",
        "Customers may request refunds within 30 days of purchase.",
    )
    trace = RAGTrace(
        query="Can customers request refunds within 30 days?",
        answer="Refunds within 30 days require manager approval.",
        contexts=[
            TraceContext(
                id="policy",
                text="Customers may request refunds within 30 days of purchase.",
                metadata={"source": "refund_policy.md"},
            )
        ],
    )

    result = audit_trace(trace, corpus_path=tmp_path / "corpus")

    assert result["summary"]["primary_audit_label"] == "answer_overreach"
    assert result["summary"]["answer_overreach"] == 1
    assert "supports part of the claim" in result["claims"][0]["reason"]


def test_audit_does_not_treat_citation_only_failure_as_retrieval_failure(tmp_path):
    _write(
        tmp_path / "corpus" / "refund_policy.md",
        "Customers may request refunds within 30 days of purchase.",
    )
    trace = RAGTrace(
        query="What is the refund policy?",
        answer="Refunds are allowed within 30 days of purchase.",
        contexts=[
            TraceContext(
                id="policy_2024",
                text="Customers may exchange eligible items within 14 days.",
            ),
            TraceContext(
                id="policy_2026",
                text="Customers may request refunds within 30 days of purchase.",
                metadata={"source": "refund_policy.md"},
            ),
        ],
        citations=[
            TraceCitation(
                claim="Refunds are allowed within 30 days of purchase.",
                source_id="policy_2024",
            )
        ],
    )

    result = audit_trace(trace, corpus_path=tmp_path / "corpus")

    assert result["verification"]["summary"]["failure_type"] == "citation_mismatch"
    assert result["summary"]["primary_audit_label"] == "no_failure_detected"
    assert result["summary"]["has_audit_failures"] is False
    assert result["claims"][0]["audit_label"] == "no_failure_detected"
    assert "citation-level" in result["claims"][0]["reason"]


def test_audit_failures_flags_requested_rules(tmp_path):
    _write(
        tmp_path / "corpus" / "policy.md",
        "Refunds are processed within 5 business days.",
    )
    trace = RAGTrace(
        query="How long does refund processing take?",
        answer="Refunds are processed within 5 business days.",
        contexts=[
            TraceContext(
                id="shipping",
                text="Shipping labels are sent after checkout.",
            )
        ],
    )
    result = audit_trace(trace, corpus_path=tmp_path / "corpus")

    failures = audit_failures(result, ("retrieval_miss", "any_failure"))

    assert "retrieval miss detected" in failures
    assert "audit failure detected" in failures


def test_audit_report_generation(tmp_path):
    _write(
        tmp_path / "corpus" / "policy.md",
        "Refunds are processed within 5 business days.",
    )
    trace = RAGTrace(
        query="How long does refund processing take?",
        answer="Refunds are processed within 5 business days.",
        contexts=[
            TraceContext(
                id="shipping",
                text="Standard shipping takes 3 to 5 business days.",
            )
        ],
    )
    result = audit_trace(trace, corpus_path=tmp_path / "corpus")
    report_path = tmp_path / "audit.html"

    written = AuditReportGenerator().generate(result, trace, path=str(report_path))

    assert written == str(report_path)
    html = report_path.read_text(encoding="utf-8")
    assert "ContextTrace Retrieval Audit Report" in html
    assert "Audit Summary" in html
    assert "Retrieval Misses" in html
    assert "Raw JSON Summary" in html


def test_audit_cli_json_report_and_fail_on(tmp_path, capsys):
    trace_path = tmp_path / "trace.json"
    report_path = tmp_path / "audit.html"
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
            "audit",
            str(trace_path),
            "--corpus",
            str(tmp_path / "corpus"),
            "--json",
            "--report",
            "--out",
            str(report_path),
            "--fail-on",
            "retrieval_miss",
        ]
    )

    assert exit_code == 1
    output = json.loads(capsys.readouterr().out)
    assert output["summary"]["primary_audit_label"] == "retrieval_miss"
    assert report_path.exists()


def test_audit_cli_plain_output(tmp_path, capsys):
    trace_path = tmp_path / "trace.json"
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

    assert main(["audit", str(trace_path), "--corpus", str(tmp_path / "corpus")]) == 0

    output = capsys.readouterr().out
    assert "Primary audit label: retrieval_miss" in output
    assert "Retrieval misses: 1" in output
