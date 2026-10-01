from __future__ import annotations

import json

import pytest

from contexttrace import audit_evidence_integrity, build_evidence_lineage
from contexttrace.cli import main
from contexttrace.verify.schema import RAGTrace, TraceContext


def _trace(selected: str, metadata: dict | None = None) -> RAGTrace:
    return RAGTrace(
        query="When are Nimbus refunds issued?",
        answer="Nimbus refunds are issued after approval.",
        contexts=[TraceContext(id="selected_1", text=selected, metadata=metadata or {})],
    )


def test_complete_linked_unit_has_no_integrity_issue() -> None:
    source = "Question: When are refunds issued? Answer: Refunds are issued after approval."
    metadata = build_evidence_lineage(
        source_unit_id="refund_qa",
        source_text=source,
        linked_parts=[
            {"id": "q", "role": "question", "text": "Question: When are refunds issued?"},
            {"id": "a", "role": "answer", "text": "Answer: Refunds are issued after approval."},
        ],
        transformation="qa_selection",
    )

    result = audit_evidence_integrity(_trace(source, metadata))

    assert result["status"] == "complete"
    assert result["issues"] == []
    assert result["network_calls"] == result["model_calls"] == 0


def test_selected_question_without_linked_answer_is_observed() -> None:
    source = "Question: When are refunds issued? Answer: Refunds are issued after approval."
    metadata = build_evidence_lineage(
        source_unit_id="refund_qa",
        source_text=source,
        linked_parts=[
            {"id": "q", "role": "question", "text": "Question: When are refunds issued?"},
            {"id": "a", "role": "answer", "text": "Answer: Refunds are issued after approval."},
        ],
    )

    result = audit_evidence_integrity(_trace("Question: When are refunds issued?", metadata))

    assert result["status"] == "issues_found"
    assert result["issues"] == [
        {
            "type": "linked_part_dropped",
            "status": "observed",
            "severity": "high",
            "selected_context_id": "selected_1",
            "source_unit_id": "refund_qa",
            "observed": "A required linked part is present in the source unit but absent from the selected text.",
            "item_id": "a",
            "item_role": "answer",
            "missing_text": "Answer: Refunds are issued after approval.",
        }
    ]


def test_declared_material_condition_dropped_from_selected_prefix() -> None:
    source = "Returns are accepted within 30 days. This applies only when unused."
    metadata = build_evidence_lineage(
        source_unit_id="returns_policy",
        source_text=source,
        material_spans=[
            {"id": "unused", "role": "condition", "text": "This applies only when unused."}
        ],
    )

    result = audit_evidence_integrity(_trace("Returns are accepted within 30 days.", metadata))

    assert result["issues"][0]["type"] == "material_span_dropped"
    assert result["issues"][0]["item_role"] == "condition"


def test_changed_or_misattached_text_is_reported_without_causal_claim() -> None:
    metadata = build_evidence_lineage(
        source_unit_id="nimbus_alerts",
        source_text="Nimbus pages the on-call engineer above 2 percent.",
    )

    result = audit_evidence_integrity(
        _trace("Nimbus pages the on-call engineer above 4 percent.", metadata)
    )

    issue = result["issues"][0]
    assert issue["type"] == "selected_text_not_in_source"
    assert "altered" not in issue["observed"].lower()
    assert "cause" not in issue["observed"].lower()


def test_uncaptured_and_invalid_lineage_remain_unknown() -> None:
    uncaptured = audit_evidence_integrity(_trace("Selected evidence"))
    assert uncaptured["status"] == "not_captured"
    assert uncaptured["summary"]["unknown_contexts"] == 1
    invalid = audit_evidence_integrity(
        _trace("Selected evidence", {"contexttrace_evidence": {"source_unit_id": "unit"}})
    )
    assert invalid["status"] == "not_captured"
    assert invalid["contexts"][0]["capture_status"] == "invalid_lineage"


def test_invalid_parts_remain_unknown_even_when_selected_text_is_not_in_source() -> None:
    result = audit_evidence_integrity(
        _trace(
            "Different selected text",
            {
                "contexttrace_evidence": {
                    "source_unit_id": "unit",
                    "source_text": "Captured source text",
                    "linked_parts": [
                        {
                            "id": "part",
                            "role": "answer",
                            "text": "Captured source text",
                            "required": "yes",
                        }
                    ],
                }
            },
        )
    )

    assert result["status"] == "not_captured"
    assert result["issues"] == []
    assert result["contexts"][0]["capture_status"] == "invalid_lineage"
    assert "required must be a boolean" in result["contexts"][0]["reason"]


def test_lineage_builder_rejects_missing_or_unbound_source_parts() -> None:
    with pytest.raises(ValueError, match="source_unit_id"):
        build_evidence_lineage(source_unit_id="", source_text="text")
    with pytest.raises(ValueError, match="present in source_text"):
        build_evidence_lineage(
            source_unit_id="unit",
            source_text="Source text",
            linked_parts=[{"id": "missing", "role": "answer", "text": "Not in source"}],
        )


def test_inspect_cli_prints_and_can_gate_integrity_issues(tmp_path, capsys) -> None:
    trace_path = tmp_path / "trace.json"
    metadata = build_evidence_lineage(
        source_unit_id="qa",
        source_text="Question: Q? Answer: A.",
        linked_parts=[
            {"id": "q", "role": "question", "text": "Question: Q?"},
            {"id": "a", "role": "answer", "text": "Answer: A."},
        ],
    )
    trace_path.write_text(
        json.dumps(_trace("Question: Q?", metadata).to_dict()), encoding="utf-8"
    )

    assert main(["inspect", str(trace_path)]) == 0
    output = capsys.readouterr().out
    assert "Evidence integrity: issues_found (1 issues, 1 assessed, 0 unknown)" in output
    assert "linked_part_dropped [selected_1]: answer" in output
    assert main(["inspect", str(trace_path), "--fail-on", "evidence_integrity"]) == 1


def test_inspect_json_exposes_unknown_instead_of_guessing(tmp_path, capsys) -> None:
    trace_path = tmp_path / "trace.json"
    trace_path.write_text(json.dumps(_trace("Selected evidence").to_dict()), encoding="utf-8")
    assert main(["inspect", str(trace_path), "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["evidence_integrity"]["status"] == "not_captured"
    assert payload["evidence_integrity"]["issues"] == []


def test_unknown_gate_fails_when_other_context_also_has_observed_issue(tmp_path) -> None:
    trace_path = tmp_path / "mixed.json"
    metadata = build_evidence_lineage(
        source_unit_id="qa",
        source_text="Question: Q? Answer: A.",
        linked_parts=[
            {"id": "q", "role": "question", "text": "Question: Q?"},
            {"id": "a", "role": "answer", "text": "Answer: A."},
        ],
    )
    trace_path.write_text(
        json.dumps(
            {
                "query": "Q?",
                "answer": "A.",
                "contexts": [
                    {"id": "observed", "text": "Question: Q?", "metadata": metadata},
                    {"id": "unknown", "text": "Other evidence"},
                ],
            }
        ),
        encoding="utf-8",
    )

    assert main(["inspect", str(trace_path), "--fail-on", "unknown_integrity"]) == 1
