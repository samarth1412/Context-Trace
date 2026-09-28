from __future__ import annotations

import json
from pathlib import Path

import pytest

from benchmarks.requirement_alignment.v24_support_risk import (
    V24SupportRiskError,
    _routing_probabilities,
)


ROOT = Path(__file__).resolve().parents[2]
BENCHMARK = ROOT / "benchmarks" / "requirement_alignment"


def test_v24_rejects_an_unrelated_routing_result() -> None:
    development = {"split": "external_fiveway_v21_development", "examples": []}
    routing = {
        "experiment": "wrong_experiment",
        "inputs": {},
        "rows": [],
        "remote_inference_used": False,
        "stable_defaults_changed": False,
    }

    with pytest.raises(V24SupportRiskError, match="V23 atomic"):
        _routing_probabilities(development, [], routing)


def test_committed_v24_result_records_the_support_risk_limit() -> None:
    result = json.loads(
        (BENCHMARK / "results" / "v24_support_risk.json").read_text()
    )
    policy = result["selected"]["policy"]
    metrics = policy["metrics"]

    assert result["status"] == "rejected_development_candidate"
    assert result["decision"] == "do_not_promote_v24"
    assert result["selected"]["candidate"] == "logistic_c_0.03"
    assert policy["all_gate_candidate_count"] == 0
    assert metrics["accuracy"] == 0.426
    assert metrics["macro_f1"] == 0.3894
    assert metrics["support_recall"] == 0.07
    assert metrics["false_support_rate"] == 0.0025
    assert metrics["false_supports"] == 1
    assert metrics["contradiction_false_supports"] == 0
    assert metrics["partial_or_ambiguous_review_recall"] == 0.775
    assert metrics["review_rate"] == 0.496
    assert metrics["gates"]["all_met"] is False


def test_committed_v24_result_preserves_privacy_and_defaults() -> None:
    result = json.loads(
        (BENCHMARK / "results" / "v24_support_risk.json").read_text()
    )

    assert result["protocol"]["evaluation_labels_in_model_features"] is False
    assert result["protocol"]["dataset_identity_in_model_features"] is False
    assert result["remote_inference_used"] is False
    assert result["local_only_network_calls"] == 0
    assert result["remote_provider_default_enabled"] is False
    assert result["stable_defaults_changed"] is False
    assert all(
        "claim" not in row and "evidence" not in row for row in result["rows"]
    )
