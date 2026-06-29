import json

from contexttrace.cli import main
from contexttrace.repair import build_repair_plan, render_repair_plan


def test_repair_plan_uses_corpus_audit_for_chunking_issue(tmp_path):
    trace_path = tmp_path / "refund_trace.json"
    corpus_path = tmp_path / "corpus"
    corpus_path.mkdir()
    (corpus_path / "refund_policy.md").write_text(
        "Refunds are processed within 5 business days.",
        encoding="utf-8",
    )
    trace_path.write_text(
        json.dumps(
            {
                "query": "How long does refund processing take?",
                "answer": "Refunds are processed within 5 business days.",
                "contexts": [
                    {
                        "id": "refund_chunk",
                        "text": "Customers may request refunds within 30 days of purchase.",
                        "metadata": {"source": "refund_policy.md"},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    plan = build_repair_plan(
        trace_path,
        corpus_path=corpus_path,
        mode="lexical",
        suite_path=tmp_path / "suite.json",
    )

    assert plan["status"] == "repair_required"
    assert plan["primary_root_cause"] == "chunking_issue"
    assert plan["corpus_audited"] is True
    assert plan["evidence"][0]["corpus_document_id"] == "refund_policy.md"
    assert "5 business days" in plan["evidence"][0]["corpus_evidence"]
    assert any("chunk boundaries" in action["action"] for action in plan["actions"])
    commands = [item["command"] for item in plan["verification"]["commands"]]
    assert any("contexttrace audit" in command for command in commands)
    assert any("contexttrace suite create" in command for command in commands)

    existing_suite = tmp_path / "existing-suite.json"
    existing_suite.write_text("{}", encoding="utf-8")
    existing_plan = build_repair_plan(
        trace_path,
        corpus_path=corpus_path,
        mode="lexical",
        suite_path=existing_suite,
    )
    assert any(
        "contexttrace suite add" in item["command"]
        for item in existing_plan["verification"]["commands"]
    )


def test_repair_plan_has_no_actions_for_supported_trace(tmp_path):
    trace_path = tmp_path / "supported.json"
    trace_path.write_text(
        json.dumps(
            {
                "query": "What is the refund window?",
                "answer": "Refunds are available within 30 days.",
                "contexts": [
                    {
                        "id": "policy",
                        "text": "Refunds are available within 30 days.",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    plan = build_repair_plan(trace_path, mode="lexical")

    assert plan["status"] == "no_repair_needed"
    assert plan["primary_root_cause"] == "no_failure_detected"
    assert plan["actions"] == []
    assert "No repair is required" in render_repair_plan(plan)


def test_repair_plan_for_agent_contradiction_includes_gate_and_replay_test(tmp_path):
    trace_path = tmp_path / "calendar_failure.json"
    trace_path.write_text(
        json.dumps(
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
        ),
        encoding="utf-8",
    )

    plan = build_repair_plan(trace_path)

    assert plan["trace_type"] == "agent"
    assert plan["primary_root_cause"] == "tool_result_contradicted_by_final_answer"
    assert any("Gate final-answer generation" in action["action"] for action in plan["actions"])
    assert any(
        "--generate-test" in item["command"]
        for item in plan["verification"]["commands"]
    )


def test_repair_cli_writes_markdown_and_json(tmp_path, capsys):
    trace_path = tmp_path / "unsupported.json"
    markdown_path = tmp_path / "repair.md"
    json_path = tmp_path / "repair.json"
    trace_path.write_text(
        json.dumps(
            {
                "query": "How long does processing take?",
                "answer": "Processing takes 5 business days.",
                "contexts": [{"id": "policy", "text": "Requests are accepted within 30 days."}],
            }
        ),
        encoding="utf-8",
    )

    assert main(
        [
            "repair",
            str(trace_path),
            "--mode",
            "lexical",
            "--out",
            str(markdown_path),
            "--json-out",
            str(json_path),
        ]
    ) == 0

    output = capsys.readouterr().out
    assert "Status: repair_required" in output
    assert "Repair plan:" in output
    assert markdown_path.is_file()
    assert json_path.is_file()
    markdown = markdown_path.read_text(encoding="utf-8")
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert markdown.startswith("# ContextTrace Repair Plan")
    assert "Apply and recapture the fix" in markdown
    assert payload["status"] == "repair_required"
