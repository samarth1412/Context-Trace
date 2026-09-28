from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from benchmarks.requirement_alignment.v14_fiveway_policy import _sha256_json
from benchmarks.requirement_alignment.v20_transfer_failure_audit import (
    SPLIT,
    V20AuditError,
    _aligned_inputs,
)


ROOT = Path(__file__).resolve().parents[2]
V20 = ROOT / "benchmarks" / "requirement_alignment"


def test_v20_rejects_score_artifacts_from_another_dataset() -> None:
    dataset = {
        "split": SPLIT,
        "examples": [{"id": "case-1", "input": {"claim": "x", "evidence": []}}],
    }
    score = {
        "split": SPLIT,
        "dataset_sha256": _sha256_json(dataset),
        "remote_inference_used": False,
        "rows": [{"case_id": "case-1"}],
    }
    confirmation = {
        "status": "confirmation_failed",
        "inputs": {"dataset_sha256": _sha256_json(dataset)},
        "protocol": {"one_shot_evaluation": True},
        "rows": [{"case_id": "case-1"}],
    }
    changed = copy.deepcopy(score)
    changed["dataset_sha256"] = "0" * 64

    with pytest.raises(V20AuditError, match="do not match"):
        _aligned_inputs(dataset, changed, score, score, confirmation)


def test_committed_v20_audit_records_transfer_failure_without_tuning() -> None:
    report = json.loads(
        (V20 / "results" / "v20_transfer_failure_audit.json").read_text()
    )

    assert report["status"] == "diagnostic_complete"
    assert report["protocol"] == {
        "confirmation_claim_made": False,
        "diagnostic_categories_are_rule_based_hypotheses": True,
        "model_training_performed": False,
        "raw_claim_or_evidence_text_retained": False,
        "split": SPLIT,
        "threshold_or_policy_selected": False,
        "v19_is_consumed_diagnostic_data": True,
    }
    assert report["failure_layers"]["completeness_overconfidence"] == {
        "false_supports": 22,
        "false_supports_from_v15": 21,
        "false_supports_from_v17_rescue": 1,
        "false_supports_with_completeness_at_least_0_8": 21,
    }
    assert report["failure_layers"]["relation_transfer"] == {
        "contradiction_cases": 25,
        "contradiction_recall": 0.2,
        "contradictions_incorrectly_supported": 7,
        "correct_contradictions": 5,
        "incorrectly_supported_with_visible_relation_contradiction": 4,
    }
    assert report["failure_layers"]["verdict_head_collapse"] == {
        "maximum_v14_unverifiable_probability": 0.0897,
        "mean_v14_unverifiable_probability": 0.0043,
        "unverifiable_predictions": 0,
        "unverifiable_recall": 0.0,
    }
    guard = report["posthoc_relation_contradiction_guard"]
    assert guard["diagnostic_only_not_a_selected_policy"] is True
    assert guard["any_candidate_passes_all_gates"] is False
    assert guard["best_safe_candidate"]["support_recall"] == 0.12
    assert report["decision"] == (
        "do_not_tune_thresholds_build_domain_diverse_local_candidate"
    )
    assert report["remote_inference_used"] is False
    assert report["stable_defaults_changed"] is False
    assert report["remote_provider_default_enabled"] is False
    assert report["local_only_network_calls"] == 0


def test_committed_v20_audit_contains_no_claim_or_evidence_text() -> None:
    report = json.loads(
        (V20 / "results" / "v20_transfer_failure_audit.json").read_text()
    )

    def keys(value: object) -> set[str]:
        if isinstance(value, dict):
            return set(value) | {key for child in value.values() for key in keys(child)}
        if isinstance(value, list):
            return {key for child in value for key in keys(child)}
        return set()

    assert {"claim", "evidence", "text"}.isdisjoint(keys(report))
