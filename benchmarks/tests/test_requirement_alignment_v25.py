from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from benchmarks.requirement_alignment.v25_input_audit import (
    V25InputError,
    restore_selected_records,
)
from benchmarks.requirement_alignment.v25_joint_representation import encoder_pairs
from benchmarks.requirement_alignment.v25_review import (
    export_review,
    summarize_partial_review,
    validate_review,
)
from benchmarks.requirement_alignment.v14_fiveway_policy import _sha256_json


def test_restoration_keeps_selected_question_with_its_answer_only() -> None:
    question = "Question: When did it start?"
    qa = question + "\nAnswer: In 2020."
    state = {
        "query": "",
        "claim": "It started in 2020.",
        "evidence": [
            {"id": f"qa1:0:{len(question)}", "text": question},
            {"id": f"qa1:{len(question) + 1}:{len(qa)}", "text": "Answer: In 2020."},
        ],
    }
    repaired = restore_selected_records(
        state,
        [
            {"id": "qa1", "text": qa},
            {"id": "unselected", "text": "Do not include this."},
        ],
    )
    assert repaired["evidence"] == [{"id": "qa1", "text": qa}]
    assert len(state["evidence"]) == 2


def test_restoration_rejects_unbound_source_offsets() -> None:
    state = {
        "query": "",
        "claim": "A claim.",
        "evidence": [{"id": "qa:0:3", "text": "bad"}],
    }
    with pytest.raises(V25InputError, match="differs"):
        restore_selected_records(state, [{"id": "qa", "text": "yes"}])


def test_encoder_pairs_ignore_targets_but_reject_labels_in_inputs() -> None:
    data = {
        "split": "external_fiveway_v21_development",
        "examples": [
            {
                "id": "a",
                "input": {
                    "query": "",
                    "claim": "Claim",
                    "evidence": [{"id": "e", "text": "Evidence"}],
                },
                "target": {"verdict": "supported"},
                "source": {"dataset": "test"},
            }
        ],
    }
    changed = copy.deepcopy(data)
    changed["examples"][0]["target"]["verdict"] = "contradicted"
    assert encoder_pairs(data) == encoder_pairs(changed) == [("Evidence", "Claim")]
    changed["examples"][0]["input"]["target"] = "supported"
    with pytest.raises(ValueError, match="expects"):
        encoder_pairs(changed)


def test_audit_exposes_question_only_cases_without_relabeling() -> None:
    root = (
        Path(__file__).resolve().parents[2] / "benchmarks/requirement_alignment/results"
    )
    result = json.loads((root / "v25_input_audit.json").read_text())
    assert result["counts"]["question_only_cases"] == 32
    assert result["counts"]["orphan_question_cases"] == 181
    assert result["by_label"]["supported"]["question_only_cases"] == 11
    assert result["by_label"]["contradicted"]["question_only_cases"] == 8
    assert result["label_validity"]["automatic_relabeling_performed"] is False
    assert result["label_validity"]["release_gate_eligible"] is False


def test_review_is_blinded_and_rejects_incomplete_or_altered_evidence() -> None:
    data = {
        "split": "external_fiveway_v21_development",
        "examples": [
            {
                "id": "source-id",
                "input": {
                    "query": "",
                    "claim": "Claim",
                    "evidence": [{"id": "source-evidence", "text": "Evidence"}],
                },
                "target": {"verdict": "supported"},
                "source": {"dataset": "secret-source"},
            }
        ],
    }
    pack, key = export_review(data)
    changed = copy.deepcopy(data)
    changed["examples"][0]["target"]["verdict"] = "contradicted"
    assert pack == export_review(changed)[0]
    assert "source-id" not in json.dumps(pack)
    assert "secret-source" not in json.dumps(pack)
    with pytest.raises(ValueError, match="requires"):
        validate_review(pack, key)
    pack["rows"][0].update(
        verdict="unsupported",
        rationale="The displayed evidence does not establish the claim.",
        reviewer="test-reviewer",
    )
    validated = validate_review(pack, key)
    assert validated["changed_labels"] == 1
    assert validated["release_gate_eligible"] is False
    pack["rows"][0]["input"]["evidence"][0]["text"] = "Altered evidence"
    with pytest.raises(ValueError, match="differs"):
        validate_review(pack, key)


def test_partial_review_requires_a_frozen_bound_proposal_and_valid_citations() -> None:
    data = {
        "split": "external_fiveway_v21_development",
        "examples": [
            {
                "id": str(i),
                "input": {
                    "query": "",
                    "claim": "Claim",
                    "evidence": [{"id": "source", "text": "Evidence"}],
                },
                "target": {"verdict": "supported"},
            }
            for i in range(2)
        ],
    }
    pack, key = export_review(data)
    pack["rows"][0].update(
        verdict="unsupported",
        rationale="The evidence lacks the asserted fact.",
        reviewer="test",
        reviewer_kind="language_model",
        evidence_ids=["evidence-00"],
        issue="missing_evidence",
        needs_adjudication=True,
    )
    freeze = {
        "review_sha256": _sha256_json(pack),
        "cases_reviewed": 1,
        "reviewed_ids": [pack["rows"][0]["review_id"]],
    }
    report = summarize_partial_review(pack, key, freeze)
    assert report["provisionally_reviewed"] == 1
    assert report["remaining_unreviewed"] == 1
    assert report["suggested_label_changes"] == 1
    assert report["approved_label_changes"] == 0
    assert report["release_gate_eligible"] is False

    changed = copy.deepcopy(pack)
    changed["rows"][0]["verdict"] = "supported"
    with pytest.raises(ValueError, match="frozen"):
        summarize_partial_review(changed, key, freeze)
    changed["rows"][0]["evidence_ids"] = ["fabricated-evidence"]
    with pytest.raises(ValueError, match="cite"):
        summarize_partial_review(
            changed, key, {**freeze, "review_sha256": _sha256_json(changed)}
        )
    changed = copy.deepcopy(pack)
    changed["rows"][1]["input"]["claim"] = "Changed unreviewed claim"
    with pytest.raises(ValueError, match="bound"):
        summarize_partial_review(
            changed, key, {**freeze, "review_sha256": _sha256_json(changed)}
        )
