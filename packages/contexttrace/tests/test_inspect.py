from __future__ import annotations

import json

from contexttrace.cli import main
from contexttrace.verify.schema import RAGTrace, TraceCitation, TraceContext
from contexttrace.verify.trace_inspect import inspect_trace


def test_inspect_trace_reports_claims_contexts_citations_and_warnings():
    trace = RAGTrace(
        query="What is the refund policy?",
        answer="Refunds are available within 30 days.",
        contexts=[
            TraceContext(id="policy", text="Refunds are available within 30 days."),
            TraceContext(id="policy", text="Refund processing varies."),
        ],
        citations=[
            TraceCitation(
                claim="Refunds are available within 30 days.",
                source_id="missing_policy",
            )
        ],
        metadata={"model": "local-rag"},
    )

    result = inspect_trace(trace, trace_path="trace.json")

    assert result["claims"] == [{"id": "claim_1", "text": "Refunds are available within 30 days."}]
    assert result["contexts"]["count"] == 2
    assert result["contexts"]["duplicate_ids"] == ["policy"]
    assert result["citations"]["missing_source_ids"] == ["missing_policy"]
    assert result["metadata_keys"] == ["model"]
    assert "Duplicate context IDs found: policy." in result["warnings"]
    assert "Citations reference missing context IDs: missing_policy." in result["warnings"]
    assert result["suggested_next_commands"][0] == "contexttrace verify trace.json --report"


def test_inspect_cli_plain_output(tmp_path, capsys):
    trace_path = tmp_path / "trace.json"
    trace_path.write_text(
        json.dumps(
            {
                "query": "What is the refund policy?",
                "answer": "Refunds are available within 30 days.",
                "contexts": [
                    {"id": "policy", "text": "Refunds are available within 30 days."},
                    {"id": "policy", "text": "Refund processing varies."},
                ],
                "citations": [
                    {
                        "claim": "Refunds are available within 30 days.",
                        "source_id": "missing_policy",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    assert main(["inspect", str(trace_path)]) == 0

    output = capsys.readouterr().out
    assert "Claims extracted: 1" in output
    assert "Duplicate context IDs: policy" in output
    assert "Missing citation source IDs: missing_policy" in output
    assert "contexttrace verify %s --report" % trace_path in output


def test_inspect_cli_json_output(tmp_path, capsys):
    trace_path = tmp_path / "trace.json"
    trace_path.write_text(
        json.dumps(
            {
                "query": "What is the refund policy?",
                "answer": "Refunds are available within 30 days.",
                "contexts": [{"id": "policy", "text": "Refunds are available within 30 days."}],
            }
        ),
        encoding="utf-8",
    )

    assert main(["inspect", str(trace_path), "--json"]) == 0

    output = json.loads(capsys.readouterr().out)
    assert output["contexts"]["count"] == 1
    assert output["claims"][0]["id"] == "claim_1"
    assert "Trace has factual claims but no citations" in output["warnings"][0]
