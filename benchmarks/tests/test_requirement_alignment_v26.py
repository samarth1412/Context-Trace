from __future__ import annotations

import copy
import json
from pathlib import Path

import numpy as np
import pytest

from benchmarks.requirement_alignment.v14_fiveway_policy import LABELS, policy_metrics
from benchmarks.requirement_alignment.v26_routing_diagnosis import (
    count_metrics,
    route,
    run,
    select,
    validate_probabilities,
)


def config(**changes):
    return {
        "risk_mode": "absolute",
        "support_minimum": 0.95,
        "contradiction_cap": 0.2,
        "support_review_cap": 0.2,
        "review_threshold": None,
        **changes,
    }


def values(**scores):
    return [scores.get(label, 0.0) for label in LABELS]


def test_explicit_review_combines_partial_and_ambiguous_probability():
    # Neither review class wins individually; their joint mass is a majority.
    row = values(
        contradicted=0.30,
        partially_supported=0.26,
        supported=0.05,
        unsupported=0.13,
        unverifiable=0.26,
    )
    assert LABELS[route([row], config())[0]] == "contradicted"
    assert (
        LABELS[route([row], config(review_threshold=0.5))[0]] == "partially_supported"
    )


def test_support_gate_and_low_contradiction_cap_take_precedence():
    row = values(
        contradicted=0.01,
        partially_supported=0.01,
        supported=0.96,
        unsupported=0.01,
        unverifiable=0.01,
    )
    assert LABELS[route([row], config(review_threshold=0))[0]] == "supported"
    assert (
        LABELS[route([row], config(contradiction_cap=0.005, review_threshold=0))[0]]
        != "supported"
    )
    certain = values(supported=1.0)
    assert (
        LABELS[route([certain], config(risk_mode="conditional_on_not_supported"))[0]]
        == "supported"
    )
    # Conditional rejection risk can be large even when absolute risk is small.
    assert (
        LABELS[route([row], config(risk_mode="conditional_on_not_supported"))[0]]
        != "supported"
    )


@pytest.mark.parametrize(
    "bad", [[[]], [[0.2] * 4], [[0.3] * 5], [[float("nan")] * 5], [[-1, 1, 1, 0, 0]]]
)
def test_invalid_probabilities_are_rejected(bad):
    with pytest.raises(ValueError, match="probability"):
        validate_probabilities(bad)


def test_vectorized_metrics_match_existing_metric_contract():
    y = np.arange(5)
    predictions = np.array([np.arange(5), np.zeros(5, dtype=int), [2, 4, 1, 3, 2]])
    metrics = count_metrics(y, predictions)
    for i, prediction in enumerate(predictions):
        expected = policy_metrics(list(LABELS), [LABELS[j] for j in prediction])
        for name, numbers in metrics.items():
            assert round(float(numbers[i]), 4) == expected[name]


def test_selector_rejects_recall_gain_from_unsafe_supports_or_excess_reviews():
    metrics = {
        "support_recall": np.array([0.11, 0.5, 0.4, 0.3, 0.2]),
        "false_support_rate": np.array([0.0025, 0.01, 0.01, 0.01, 0.005]),
        "false_supports": np.array([1, 4, 4, 4, 2]),
        "contradiction_false_supports": np.array([0, 1, 0, 0, 0]),
        "partial_or_ambiguous_review_recall": np.array([0.78, 0.9, 0.9, 0.77, 0.8]),
        "review_rate": np.array([0.494, 0.49, 0.51, 0.49, 0.49]),
        "macro_f1": np.array([0.5, 0.8, 0.8, 0.8, 0.6]),
    }
    baseline = {
        "support_recall": 0.11,
        "partial_or_ambiguous_review_recall": 0.78,
        "false_supports": 1,
    }
    assert select(metrics, baseline) == 4
    assert select(metrics, baseline, same_false_supports=True) == 0


def test_frozen_source_rejects_changed_scores_before_search():
    root = Path(__file__).resolve().parents[1] / "requirement_alignment/results"
    source = json.loads((root / "v25_joint_representation.json").read_text())
    protocol = json.loads((root / "v26_protocol.json").read_text())
    changed = copy.deepcopy(source)
    changed["variants"]["restored_selected_qa"]["rows"][0]["expected_verdict"] = (
        "contradicted"
    )
    with pytest.raises(ValueError, match="frozen"):
        run(changed, protocol)


def test_recorded_predictions_preserve_scores_and_reproduce_metrics():
    root = Path(__file__).resolve().parents[1] / "requirement_alignment/results"
    source = json.loads((root / "v25_joint_representation.json").read_text())
    result = json.loads((root / "v26_routing_diagnosis.json").read_text())
    rows = result["rows"]
    for old, new in zip(
        source["variants"]["restored_selected_qa"]["rows"], rows, strict=True
    ):
        assert (
            old["case_id"],
            old["input_sha256"],
            old["probabilities"],
            old["expected_verdict"],
        ) == (
            new["case_id"],
            new["input_sha256"],
            new["probabilities"],
            new["expected_verdict"],
        )
    assert result["selected"]["metrics"] == policy_metrics(
        [r["expected_verdict"] for r in rows], [r["prediction"] for r in rows]
    )
    assert result["release_gate_eligible"] is False
    assert result["new_inference_calls"] == 0
    assert result["cross_fold_selection_sensitivity"]["independent_validation"] is False
