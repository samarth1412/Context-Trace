from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from benchmarks.requirement_alignment.score_v17_multispan import (
    _combination_summary,
    decompose_v17_requirements,
)
from benchmarks.requirement_alignment.v17_multispan_completeness import (
    V17CompletenessError,
    _aligned_inputs,
    multispan_feature_vector,
)


ROOT = Path(__file__).resolve().parents[2]
V17 = ROOT / "benchmarks" / "requirement_alignment"


def test_v17_decomposition_rejects_relative_fragments_and_splits_full_clauses() -> None:
    source, relative = decompose_v17_requirements(
        "It was opened by Brian Wilkins, who had used the beach since 1938."
    )
    assert source == "semantic_core_v2_1"
    assert relative == [
        "It was opened by Brian Wilkins, who had used the beach since 1938."
    ]

    _, coordinated = decompose_v17_requirements(
        "John was declared bankrupt and the brewery was leased to his nephews."
    )
    assert coordinated == [
        "John was declared bankrupt.",
        "the brewery was leased to his nephews.",
    ]


def test_v17_multispan_summary_records_gain_over_single_span() -> None:
    summary = _combination_summary(
        [
            {
                "size": 1,
                "nli_scores": {
                    "entailment": 0.4,
                    "contradiction": 0.1,
                    "neutral": 0.5,
                },
            },
            {
                "size": 2,
                "nli_scores": {
                    "entailment": 0.8,
                    "contradiction": 0.05,
                    "neutral": 0.15,
                },
            },
        ]
    )

    assert summary["best_entailment"] == 0.8
    assert summary["best_entailment_combination_size"] == 2
    assert summary["multispan_entailment_gain"] == 0.4


def test_v17_features_are_label_blind() -> None:
    row = {
        "decomposition_source": "semantic_core_v2_1",
        "requirements": [
            {
                "selected_span_count": 2,
                "summary": {
                    "best_entailment": 0.8,
                    "best_contradiction": 0.1,
                    "best_neutral": 0.4,
                    "best_single_entailment": 0.6,
                    "best_pair_entailment": 0.8,
                    "best_triple_entailment": 0.0,
                    "best_entailment_combination_size": 2,
                    "multispan_entailment_gain": 0.2,
                    "mean_entailment": 0.55,
                },
            }
        ],
    }
    changed = copy.deepcopy(row)
    changed["expected_verdict"] = "supported"
    changed["dataset"] = "fixture"

    assert multispan_feature_vector(row) == multispan_feature_vector(changed)


def test_v17_rejects_heldout_artifacts_before_alignment() -> None:
    heldout = {"split": "external_fiveway_v13_heldout"}

    with pytest.raises(V17CompletenessError, match="only V13 development"):
        _aligned_inputs(heldout, heldout, {}, heldout, {}, heldout)


def test_committed_v17_candidate_passes_all_development_gates() -> None:
    report = json.loads(
        (V17 / "results" / "v17_multispan_completeness.json").read_text()
    )
    selected = report["selected"]
    metrics = selected["metrics"]

    assert report["status"] == "development_candidate"
    assert report["protocol"]["heldout_loaded"] is False
    assert report["protocol"]["heldout_used_for_selection"] is False
    assert report["protocol"]["fresh_confirmation_required"] is True
    assert report["inputs"]["v17_requirements"] == 145
    assert report["inputs"]["v17_evidence_combinations"] == 1217
    assert report["search"]["candidate_count"] == 80
    assert report["classifier_screen"]["all_gate_candidate_count"] == 0
    assert selected["minimum_single_span_entailment"] == 0.7
    assert selected["threshold_source"] == "frozen_atomic_coverage_entailment_threshold"
    assert selected["promotions"] == selected["correct_promotions"] == 3
    assert selected["promotion_precision"] == 1.0
    assert metrics["accuracy"] == 0.728
    assert metrics["macro_f1"] == 0.7276
    assert metrics["support_recall"] == 0.52
    assert metrics["false_support_rate"] == 0.04
    assert metrics["contradiction_false_supports"] == 0
    assert metrics["partial_or_ambiguous_review_recall"] == 0.8
    assert metrics["review_rate"] == 0.456
    assert metrics["gates"]["all_met"] is True
    assert report["decision"] == "freeze_v17_development_candidate"
    assert report["remote_inference_used"] is False
    assert report["stable_defaults_changed"] is False
    assert report["remote_provider_default_enabled"] is False
    assert report["local_only_network_calls"] == 0
