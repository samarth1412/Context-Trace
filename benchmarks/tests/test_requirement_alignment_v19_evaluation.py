from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from benchmarks.requirement_alignment.evaluate_v19_confirmation import (
    SPLIT,
    V19EvaluationError,
    _preflight,
)
from benchmarks.requirement_alignment.score_v13_relations import SPLITS
from benchmarks.requirement_alignment.score_v15_atomic import (
    ALLOWED_SPLITS as V15_SPLITS,
)
from benchmarks.requirement_alignment.score_v17_multispan import (
    ALLOWED_SPLITS as V17_SPLITS,
)
from benchmarks.requirement_alignment.v14_fiveway_policy import _sha256_json


ROOT = Path(__file__).resolve().parents[2]
V19 = ROOT / "benchmarks" / "requirement_alignment"


def test_v19_scorers_explicitly_accept_the_frozen_confirmation_split() -> None:
    assert SPLIT in SPLITS
    assert SPLIT in V15_SPLITS
    assert SPLIT in V17_SPLITS


def test_v19_preflight_rejects_a_dataset_changed_after_freeze() -> None:
    dataset = {
        "split": SPLIT,
        "examples": [{"id": "case-1", "input": {"claim": "x", "evidence": []}}],
    }
    manifest = {
        "status": "frozen_before_v18_candidate_scoring",
        "dataset_sha256": _sha256_json(dataset),
        "v18_artifact_sha256": "artifact-hash",
        "candidate_or_policy_changed_after_v18": False,
        "confirmation_predictions_generated": False,
        "confirmation_predictions_inspected": False,
        "confirmation_labels_used_for_selection": False,
        "retraining_allowed": False,
    }
    candidate = {
        "status": "frozen_before_new_confirmation_data_access",
        "artifact": {"sha256": "artifact-hash"},
    }
    score = {
        "split": SPLIT,
        "dataset_sha256": _sha256_json(dataset),
        "remote_inference_used": False,
        "evaluation_labels_sent": False,
        "input_contract": {"evaluation_labels_sent": False},
    }
    changed = copy.deepcopy(dataset)
    changed["examples"][0]["input"]["claim"] = "changed"

    with pytest.raises(V19EvaluationError, match="freeze manifest"):
        _preflight(changed, manifest, candidate, score, score, score)


def test_committed_v19_result_records_failed_untouched_confirmation() -> None:
    report = json.loads((V19 / "results" / "v19_confirmation_result.json").read_text())
    metrics = report["metrics"]

    assert report["status"] == "confirmation_failed"
    assert report["decision"] == "confirmation_failed_do_not_package_or_release"
    assert report["protocol"] == {
        "candidate_frozen_before_dataset": True,
        "case_removal_after_prediction": False,
        "dataset_frozen_before_scoring": True,
        "evaluation_labels_in_model_inputs": False,
        "evaluation_split": SPLIT,
        "model_outputs_used_for_case_selection": False,
        "one_shot_evaluation": True,
        "retraining_performed": False,
        "threshold_or_policy_changes": False,
    }
    assert report["inputs"]["cases"] == 125
    assert metrics["accuracy"] == 0.232
    assert metrics["macro_f1"] == 0.2003
    assert metrics["support_recall"] == 0.36
    assert metrics["false_support_rate"] == 0.22
    assert metrics["contradiction_false_supports"] == 7
    assert metrics["partial_or_ambiguous_review_recall"] == 0.38
    assert metrics["review_rate"] == 0.336
    assert metrics["gates"] == {
        "all_met": False,
        "false_support_rate": False,
        "partial_or_ambiguous_review_recall": False,
        "review_rate": True,
        "support_recall": False,
        "zero_contradiction_false_supports": False,
    }
    assert sum(row["prediction"] == "unverifiable" for row in report["rows"]) == 0
    assert report["rescue"] == {
        "correct_promotions": 2,
        "promoted_case_ids": [
            "averitec_dev_0037",
            "averitec_dev_0215",
            "averitec_dev_0391",
        ],
        "promotion_precision": 0.6667,
        "promotions": 3,
    }
    assert report["confidence_intervals_95"]["samples"] == 10_000
    assert report["confidence_intervals_95"]["seed"] == 20260927
    assert report["remote_inference_used"] is False
    assert report["stable_defaults_changed"] is False
    assert report["remote_provider_default_enabled"] is False
    assert report["local_only_network_calls"] == 0


def test_committed_v19_result_contains_no_claim_or_evidence_text() -> None:
    report = json.loads((V19 / "results" / "v19_confirmation_result.json").read_text())

    def keys(value: object) -> set[str]:
        if isinstance(value, dict):
            return set(value) | {key for child in value.values() for key in keys(child)}
        if isinstance(value, list):
            return {key for child in value for key in keys(child)}
        return set()

    assert {"claim", "evidence", "text"}.isdisjoint(keys(report))
