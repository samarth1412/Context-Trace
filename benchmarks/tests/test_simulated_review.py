from __future__ import annotations

import asyncio
import json
from pathlib import Path

from benchmarks.contexttrace_bench.simulated_review.common import (
    AGENTS,
    annotation_prompt,
    load_response_schema,
    rq4_prompt,
    validate_review_response,
    write_jsonl,
)
from benchmarks.contexttrace_bench.simulated_review.run_simulated_review import (
    build_rq4_tasks,
    request_review_with_retries,
)
from benchmarks.contexttrace_bench.simulated_review.finalize_after_review import finalize_after_review
from benchmarks.contexttrace_bench.simulated_review.score_simulated_review import (
    generate_sensitivity_analysis,
    score_annotation_review,
)


def _response(case_id: str, agent_id: str, *, label: str = "unsupported") -> dict:
    return {
        "case_id": case_id,
        "agent_id": agent_id,
        "failure_label": label,
        "root_cause": "answer_overreach",
        "evidence_span": "Evidence text",
        "citation_status": "not_applicable",
        "dangerous_false_green_risk": "medium",
        "fix_recommendation": "Remove the unsupported claim and add a regression case.",
        "actionability_score": 4,
        "confidence": 0.8,
        "rationale": "The answer exceeds the supplied evidence.",
        "overclaim_warning": None,
    }


def _case() -> dict:
    return {
        "blind_id": "ARR-0001",
        "query": "What is supported?",
        "answer": "An unsupported answer.",
        "contexts": [{"id": "s1", "text": "Different evidence."}],
        "citations": [],
        "annotation": {"expected_labels": ["no_failure_detected"]},
    }


def test_review_schema_and_manual_validation_agree() -> None:
    schema = load_response_schema()
    value = _response("ARR-0001", "strict_evidence")

    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == set(value)
    assert validate_review_response(
        value, expected_case_id="ARR-0001", expected_agent_id="strict_evidence"
    ) == []
    value["confidence"] = 2
    assert "confidence must be a number from 0 to 1" in validate_review_response(value)


def test_malformed_review_retries_then_succeeds() -> None:
    calls = []

    async def fake(feedback: str | None):
        calls.append(feedback)
        if len(calls) == 1:
            return "not json", {}
        if len(calls) == 2:
            return json.dumps({"case_id": "ARR-0001"}), {}
        return json.dumps(_response("ARR-0001", "strict_evidence")), {"input_tokens": 10, "output_tokens": 20}

    response, meta, failure = asyncio.run(
        request_review_with_retries(fake, case_id="ARR-0001", agent_id="strict_evidence")
    )

    assert response is not None
    assert failure is None
    assert meta["attempts"] == 3
    assert calls[0] is None
    assert calls[1]
    assert calls[2]


def test_annotation_prompt_excludes_gold_and_predictions() -> None:
    _, user, payload = annotation_prompt(_case(), "strict_evidence")
    lowered = user.lower()

    assert payload["trace"]["case_id"] == "ARR-0001"
    assert "expected_labels" not in lowered
    assert '"annotation"' not in lowered
    assert '"predicted"' not in lowered
    assert "contexttrace" not in lowered


def test_rq4_settings_are_separated_and_condition_key_is_not_prompted() -> None:
    case = {
        "blind_id": "ACT-0001",
        "query": "Q",
        "answer": "A",
        "contexts": [],
        "citations": [],
        "option_1": {"claims": [], "overall": {"support_score": 0.2}},
        "option_2": {
            "claims": [{"root_cause": "answer_overreach", "evidence_span": {"text": "E"}}],
            "overall": {"primary_root_cause": "answer_overreach", "suggested_fix": "Fix it"},
        },
    }
    key = {
        "cases": [
            {
                "blind_id": "ACT-0001",
                "condition_by_option": {"option_1": "semantic_core", "option_2": "evidence_chain"},
                "expected": ["unsupported_answer"],
            }
        ]
    }
    tasks = build_rq4_tasks({"cases": [case]}, key)

    assert len(tasks) == 9
    raw = [task for task in tasks if task.group == "raw_trace"][0].user.lower()
    score = [task for task in tasks if task.group == "score_only"][0].user.lower()
    treatment = [task for task in tasks if task.group == "contexttrace"][0].user.lower()
    assert "evaluation_output" not in raw
    assert "root_cause" not in raw
    assert "root_cause" not in score
    assert "evidence_span" not in score
    assert "condition_by_option" not in treatment
    assert "root_cause" in treatment


def test_score_annotation_creates_unapplied_high_priority_suggestion(tmp_path: Path) -> None:
    review_dir = tmp_path / "review"
    for agent_id, config in AGENTS.items():
        write_jsonl(review_dir / str(config["file"]), [_response("ARR-0001", agent_id)])
    key_path = tmp_path / "key.json"
    key_path.write_text(
        json.dumps(
            {
                "cases": [
                    {
                        "blind_id": "ARR-0001",
                        "original_id": "case-1",
                        "expected": ["no_failure_detected"],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    report = score_annotation_review(
        dataset="fixture",
        review_dir=review_dir,
        key_path=key_path,
        corrections_dir=tmp_path / "corrections",
    )
    suggestion = json.loads(
        (tmp_path / "corrections" / "suggested_corrections.jsonl").read_text(encoding="utf-8")
    )

    assert report["recommended_corrections"] == 1
    assert suggestion["priority"] == "high_priority_author_review"
    assert suggestion["applied"] is False
    assert suggestion["status"] == "suggested_for_author_review"
    assert (tmp_path / "corrections" / "applied_corrections.jsonl").read_text(encoding="utf-8") == ""


def test_sensitivity_analysis_does_not_apply_simulated_labels(tmp_path: Path) -> None:
    corrections = tmp_path / "corrections.jsonl"
    write_jsonl(
        corrections,
        [
            {
                "original_id": "case-1",
                "new_suggested_label": "unsupported",
                "applied": False,
            }
        ],
    )
    results = tmp_path / "results.json"
    results.write_text(
        json.dumps(
            {
                "rows": [
                    {
                        "id": "case-1",
                        "expected": ["no_failure_detected"],
                        "predicted": ["unsupported_answer"],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    report = generate_sensitivity_analysis(
        corrections_path=corrections,
        result_paths=[results],
        output_json=tmp_path / "sensitivity.json",
        output_md=tmp_path / "sensitivity.md",
    )

    assert report["corrections_applied"] == 0
    assert report["scenarios"]["frozen_labels"]["accuracy"] == 0
    assert report["scenarios"]["simulated_majority_suggestions"]["accuracy"] == 1
    assert report["paper_result_eligible"] is False


def test_finalize_after_review_preserves_frozen_labels(tmp_path: Path) -> None:
    output = tmp_path / "arr_full_after_review"
    output.mkdir()
    (output / "manifest.json").write_text(json.dumps({"schema_version": 2}), encoding="utf-8")
    sensitivity_json = tmp_path / "sensitivity.json"
    sensitivity_md = tmp_path / "sensitivity.md"
    status = tmp_path / "status.json"
    sensitivity_json.write_text(json.dumps({"paper_result_eligible": False}), encoding="utf-8")
    sensitivity_md.write_text("# Sensitivity\n", encoding="utf-8")
    status.write_text(json.dumps({"human_review": False}), encoding="utf-8")

    result = finalize_after_review(
        output_dir=output,
        sensitivity_json=sensitivity_json,
        sensitivity_md=sensitivity_md,
        simulated_status=status,
    )
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))

    assert result["frozen_labels_preserved"] is True
    assert result["corrections_applied"] == 0
    assert result["paper_result_eligible"] is False
    assert len(manifest["after_review_status"]["artifacts"]) == 3
