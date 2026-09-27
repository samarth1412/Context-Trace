from __future__ import annotations

import json
from pathlib import Path

import pytest

from benchmarks.requirement_alignment.v10_fourway import (
    _policy_metrics,
    four_way_metrics,
)


ROOT = Path(__file__).resolve().parents[2]
V10 = ROOT / "benchmarks" / "requirement_alignment"


def test_four_way_metrics_preserve_all_labels() -> None:
    labels = ["DISPUTED", "NOT_ENOUGH_INFO", "REFUTES", "SUPPORTS"]
    metrics = four_way_metrics(labels, labels)

    assert metrics["accuracy"] == 1.0
    assert metrics["macro_f1"] == 1.0
    assert set(metrics["confusion"]) == set(labels)
    assert all(metrics["per_class"][label]["recall"] == 1.0 for label in labels)


def test_policy_metrics_require_safety_recall_and_disputed_review() -> None:
    targets = [
        *(["SUPPORTS"] * 10),
        *(["REFUTES"] * 10),
        *(["NOT_ENOUGH_INFO"] * 10),
        *(["DISPUTED"] * 10),
    ]
    passing = _policy_metrics(targets, set(range(5)), set(range(30, 40)))
    unsafe = _policy_metrics(targets, {0, 10}, set(range(30, 40)))

    assert passing["gates"]["all_met"] is True
    assert passing["support_recall"] == 0.5
    assert passing["disputed_review_coverage"] == 1.0
    assert unsafe["gates"]["zero_refutation_false_supports"] is False
    assert unsafe["gates"]["all_met"] is False


def test_committed_v10_feature_screen_is_a_local_negative_result() -> None:
    report = json.loads(
        (V10 / "results" / "v10_fourway_feature_screen.json").read_text()
    )

    assert report["status"] == "rejected_development_candidate"
    assert report["selected"]["regularization_c"] == pytest.approx(0.01)
    assert report["selected"]["development"]["macro_f1"] == pytest.approx(0.3931)
    diagnostic = report["selected"]["policy_diagnostic"]
    assert diagnostic["all_gate_candidate_count"] == 0
    assert diagnostic["selected_diagnostic"]["refutation_false_supports"] == 0
    assert report["promotion_gates"]["all_met"] is False
    assert report["v9_holdout_reused"] is False
    assert report["stable_defaults_changed"] is False
    assert report["remote_inference_used"] is False
    assert report["local_only_network_calls"] == 0
