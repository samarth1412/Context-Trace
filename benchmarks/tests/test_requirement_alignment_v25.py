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
