from __future__ import annotations

from benchmarks.requirement_alignment.evaluate_v4_aggregation import (
    aggregate_probabilities,
)
from benchmarks.requirement_alignment.evaluate_v4_aggregation import explode_evidence


def _row() -> dict:
    return {
        "id": "case",
        "input": {
            "claim": "A claim.",
            "requirement": {
                "id": "r00",
                "text": "A claim.",
                "start_char": 0,
                "end_char": 8,
            },
            "evidence": [
                {"id": "e1", "text": "First."},
                {"id": "e2", "text": "Second."},
            ],
        },
        "target": {"label": "covered"},
        "source": {},
    }


def test_explode_evidence_preserves_one_source_span_per_example() -> None:
    exploded, owners = explode_evidence([_row()])

    assert owners == [0, 0]
    assert [row["input"]["evidence"][0]["id"] for row in exploded] == ["e1", "e2"]
    assert all(len(row["input"]["evidence"]) == 1 for row in exploded)


def test_max_entailment_uses_best_span() -> None:
    scores, audit = aggregate_probabilities(
        policy="max_entailment",
        concatenated=[[0.1, 0.2, 0.7]],
        per_span=[[0.1, 0.8, 0.1], [0.2, 0.6, 0.2]],
        owners=[0, 0],
    )

    assert scores == [0.8]
    assert audit["vetoed_examples"] == 0


def test_contradiction_veto_blocks_high_entailment_span_group() -> None:
    scores, audit = aggregate_probabilities(
        policy="contradiction_veto",
        concatenated=[[0.1, 0.2, 0.7]],
        per_span=[[0.1, 0.9, 0.0], [0.7, 0.2, 0.1]],
        owners=[0, 0],
    )

    assert scores == [0.0]
    assert audit["vetoed_examples"] == 1
