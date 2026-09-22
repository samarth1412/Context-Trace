from __future__ import annotations

from benchmarks.requirement_alignment.train import binary_metrics
from benchmarks.requirement_alignment.train import input_pair
from benchmarks.requirement_alignment.train import select_threshold
from benchmarks.requirement_alignment.train import variant_examples


def _example(task: str, construction: str, label: str) -> dict:
    return {
        "task": task,
        "split": "training",
        "input": {
            "claim": "The policy provides backups.",
            "requirement": (
                {"text": "provides backups", "start_char": 11, "end_char": 27}
                if task == "requirement_alignment"
                else None
            ),
            "evidence": [{"id": "e1", "text": "Backups are provided."}],
        },
        "target": {"label": label},
        "source": {"construction": construction},
    }


def test_fixed_variant_filters() -> None:
    rows = [
        _example("claim_group_completeness", "gold_complete_group", "complete"),
        _example("claim_group_completeness", "gold_partial_group", "incomplete"),
        _example("claim_group_completeness", "synthetic_drop_one", "incomplete"),
        _example("requirement_alignment", "gold_complete_group", "covered"),
    ]

    assert len(variant_examples(rows, "human_group")) == 2
    assert len(variant_examples(rows, "group_with_weak_negatives")) == 3
    assert len(variant_examples(rows, "multitask")) == 4


def test_input_pair_contains_no_target() -> None:
    row = _example("requirement_alignment", "gold_complete_group", "covered")

    premise, hypothesis = input_pair(row, separator="[SEP]")

    assert premise == "Backups are provided."
    assert hypothesis == (
        "Claim: The policy provides backups. Requirement: provides backups"
    )
    assert "covered" not in premise + hypothesis


def test_metrics_and_threshold_enforce_false_positive_cap() -> None:
    targets = [0, 0, 1, 1]
    probabilities = [0.05, 0.1, 0.8, 0.9]

    metrics = binary_metrics(targets, probabilities, threshold=0.5)
    policy = select_threshold(targets, probabilities)

    assert metrics["accuracy"] == 1.0
    assert policy["metrics"]["false_positive_rate"] <= 0.05
    assert policy["metrics"]["positive_recall"] == 1.0
