from __future__ import annotations

from benchmarks.requirement_alignment.analyze_development import compare_predictions
from benchmarks.requirement_alignment.analyze_development import prediction_records
from benchmarks.requirement_alignment.analyze_development import relation_metrics


def _example(identifier: str, relation: str, label: str) -> dict:
    return {
        "id": identifier,
        "target": {"label": label},
        "source": {
            "relation": relation,
            "hypothesis_id": "nda-1",
        },
    }


def test_relation_metrics_separate_false_support_from_missed_support() -> None:
    examples = [
        _example("e", "Entailment", "covered"),
        _example("c", "Contradiction", "missing"),
        _example("n", "NotMentioned", "missing"),
    ]

    result = relation_metrics(examples, [0.95, 0.91, 0.1], threshold=0.9)

    assert result["Entailment"]["accuracy"] == 1.0
    assert result["Contradiction"]["predicted_covered_rate"] == 1.0
    assert result["Contradiction"]["accuracy"] == 0.0
    assert result["NotMentioned"]["accuracy"] == 1.0


def test_comparison_records_corrected_and_introduced_errors() -> None:
    examples = [
        _example("positive", "Entailment", "covered"),
        _example("negative", "Contradiction", "missing"),
    ]

    result = compare_predictions(
        examples,
        [0.1, 0.1],
        [0.95, 0.95],
        first_threshold=0.9,
        second_threshold=0.9,
    )

    assert result["transition_counts"] == {
        "v1_only_correct": 1,
        "v2_only_correct": 1,
    }
    assert len(result["prediction_disagreements"]) == 2


def test_prediction_records_keep_probabilities_without_explanations() -> None:
    rows = prediction_records(
        [_example("e", "Entailment", "covered")], [0.91234567], threshold=0.9
    )

    assert rows == [
        {
            "id": "e",
            "relation": "Entailment",
            "hypothesis_id": "nda-1",
            "target": "covered",
            "prediction": "covered",
            "covered_probability": 0.912346,
        }
    ]
