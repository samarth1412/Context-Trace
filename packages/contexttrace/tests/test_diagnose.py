import json

from contexttrace.cli import main
from contexttrace.diagnose import diagnose_payload


def test_diagnose_agent_trace_flags_tool_result_final_answer_contradiction():
    result = diagnose_payload(
        {
            "goal": "Book a meeting with Alex",
            "steps": [
                {
                    "type": "tool_call",
                    "tool": "calendar.search",
                    "args": {"date": "Friday"},
                    "result": "No availability",
                },
                {
                    "type": "final_answer",
                    "content": "I booked it for Friday.",
                },
            ],
        }
    )

    assert result["trace_type"] == "agent"
    assert result["summary"]["status"] == "failed"
    assert result["summary"]["primary_issue"] == "tool_result_contradicted_by_final_answer"
    assert result["summary"]["high_risk_findings"] == 1
    assert result["agent"]["negative_tool_results"] == 1
    finding = result["findings"][0]
    assert finding["type"] == "tool_result_contradicted_by_final_answer"
    assert finding["tool"] == "calendar.search"
    assert "No availability" in finding["evidence"]


def test_diagnose_agent_trace_passes_when_final_answer_reflects_failed_tool():
    result = diagnose_payload(
        {
            "goal": "Book a meeting with Alex",
            "steps": [
                {
                    "type": "tool_call",
                    "tool": "calendar.search",
                    "args": {"date": "Friday"},
                    "result": "No availability",
                },
                {
                    "type": "final_answer",
                    "content": "I could not book it for Friday because there is no availability.",
                },
            ],
        }
    )

    assert result["summary"]["status"] == "passed"
    assert result["findings"] == []


def test_diagnose_cli_json_report_and_fail_on(tmp_path, capsys):
    trace_path = tmp_path / "agent_rag_trace.json"
    report_path = tmp_path / "diagnose.html"
    trace_path.write_text(
        json.dumps(
            {
                "query": "Can I get a refund?",
                "answer": "Refunds are processed within 5 business days.",
                "contexts": [
                    {
                        "id": "refund_policy",
                        "text": "Customers may request refunds within 30 days of purchase.",
                    }
                ],
                "steps": [
                    {
                        "type": "tool_call",
                        "tool": "refund.lookup",
                        "args": {"topic": "processing time"},
                        "result": {"found": False, "matches": []},
                    },
                    {
                        "type": "final_answer",
                        "content": "Refunds are processed within 5 business days.",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    assert main(["diagnose", str(trace_path), "--json", "--report", "--out", str(report_path)]) == 0

    output = json.loads(capsys.readouterr().out)
    assert output["trace_type"] == "agent_rag"
    assert output["summary"]["status"] == "failed"
    assert "rag_failure" not in output["summary"]
    assert any(item["source"] == "rag" for item in output["findings"])
    assert any(item["source"] == "agent" for item in output["findings"])
    assert report_path.exists()
    assert "ContextTrace Diagnosis Report" in report_path.read_text(encoding="utf-8")

    assert main(["diagnose", str(trace_path), "--fail-on", "high_risk"]) == 1
    assert "Diagnosis failed: high-risk diagnosis finding detected" in capsys.readouterr().err
