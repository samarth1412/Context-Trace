from __future__ import annotations

from types import SimpleNamespace

import pytest

from benchmarks.requirement_alignment.diagnose_v5_threshold import (
    fine_threshold_diagnostic,
)
from benchmarks.requirement_alignment.train_v5 import V5TrainingError
from benchmarks.requirement_alignment.train_v5 import resolve_relation_ids
from benchmarks.requirement_alignment.train_v5 import select_dual_threshold


def test_relation_ids_follow_checkpoint_semantics_instead_of_position() -> None:
    config = SimpleNamespace(
        label2id={"entailment": 0, "neutral": 1, "contradiction": 2}
    )

    assert resolve_relation_ids(config) == {
        "contradiction": 2,
        "entailment": 0,
        "neutral": 1,
    }


def test_relation_ids_reject_incomplete_checkpoint_mapping() -> None:
    config = SimpleNamespace(label2id={"LABEL_0": 0, "LABEL_1": 1, "LABEL_2": 2})

    with pytest.raises(V5TrainingError, match="entailment, neutral, and contradiction"):
        resolve_relation_ids(config)


def test_v5_threshold_keeps_both_safety_caps() -> None:
    targets = [0] * 20 + [1] * 4
    contract_probabilities = [0.4] * 19 + [0.86] + [0.86] * 3 + [0.2]
    wice_probabilities = [0.4] * 20 + [0.86] * 2 + [0.2] * 2

    selected = select_dual_threshold(
        targets, contract_probabilities, targets, wice_probabilities
    )["selected"]

    assert selected["threshold"] == 0.85
    assert selected["contract_development"]["false_positive_rate"] == 0.05
    assert selected["wice_internal"]["false_positive_rate"] == 0.0
    assert selected["promotion_gates_met"] is True


def test_fine_diagnostic_cannot_relabel_the_fixed_promotion_result() -> None:
    def row(identifier: str, label: str) -> dict:
        return {
            "id": identifier,
            "target": {"label": label},
            "source": {
                "relation": "Entailment" if label == "covered" else "NotMentioned",
                "hypothesis_id": "nda-1",
                "evidence_span_indexes": [1],
            },
        }

    contract = [row("n", "missing"), row("p", "covered")]
    wice = [row("wn", "missing"), row("wp", "covered")]
    report = fine_threshold_diagnostic(contract, [0.1, 0.91], wice, [0.1, 0.91])

    assert report["best_eligible"]["contract_development"]["positive_recall"] == 1.0
    assert report["contract_recall_target_met"] is True
    assert "cannot satisfy" in report["warning"]
