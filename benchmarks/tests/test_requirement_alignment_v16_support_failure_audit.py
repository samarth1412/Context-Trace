from __future__ import annotations

import json
from pathlib import Path

import pytest

from benchmarks.requirement_alignment.v16_support_failure_audit import (
    V16AuditError,
    _aligned,
)


ROOT = Path(__file__).resolve().parents[2]
V16 = ROOT / "benchmarks" / "requirement_alignment"


def test_v16_rejects_heldout_before_diagnostic_alignment() -> None:
    heldout = {"split": "external_fiveway_v13_heldout"}

    with pytest.raises(V16AuditError, match="only V13 development"):
        _aligned(heldout, heldout, heldout, {}, {})


def test_committed_v16_result_fixes_the_required_promotion_boundary() -> None:
    report = json.loads(
        (V16 / "results" / "v16_support_failure_audit.json").read_text()
    )
    boundary = report["support_boundary"]

    assert boundary == {
        "additional_true_supports_needed": 3,
        "correctly_supported": 10,
        "false_support_budget": 5,
        "false_supports": 4,
        "minimum_precision_for_next_promotions": 0.75,
        "missed_supported": 15,
        "remaining_false_support_budget": 1,
        "supported_cases": 25,
    }
    assert report["protocol"]["split"] == "external_fiveway_v13_development"
    assert report["protocol"]["heldout_loaded"] is False
    assert report["protocol"]["heldout_used"] is False
    assert report["remote_inference_used"] is False
    assert report["stable_defaults_changed"] is False
    assert report["remote_provider_default_enabled"] is False
    assert report["local_only_network_calls"] == 0


def test_committed_v16_frontier_rules_out_threshold_only_recovery() -> None:
    report = json.loads(
        (V16 / "results" / "v16_support_failure_audit.json").read_text()
    )
    diagnostics = report["missed_support_diagnostics"]
    frontier = report["exact_threshold_frontier"]
    safe = frontier["best_policy_preserving_other_four_gates"]["metrics"]
    target = frontier["lowest_false_support_policy_reaching_support_target"]["metrics"]

    assert diagnostics["primary_counts"] == {
        "atomic_under_decomposition_candidate": 3,
        "completeness_ranker_false_negative": 2,
        "relation_scoring_false_negative_candidate": 2,
        "selected_evidence_coverage_risk": 4,
        "v14_non_target_route": 4,
    }
    assert diagnostics["flag_counts"]["selected_evidence_low_best_span_coverage"] == 11
    assert diagnostics["flag_counts"]["atomic_entailment_below_0_70"] == 11
    assert diagnostics["flag_counts"]["v15_completeness_below_threshold"] == 14
    assert frontier["candidate_count"] == 140_608
    assert frontier["all_gate_candidate_count"] == 0
    assert safe["support_recall"] == 0.4
    assert safe["false_support_rate"] == 0.03
    assert all(
        safe["gates"][name]
        for name in (
            "false_support_rate",
            "zero_contradiction_false_supports",
            "partial_or_ambiguous_review_recall",
            "review_rate",
        )
    )
    assert target["support_recall"] == 0.52
    assert target["false_support_rate"] == 0.09
    assert target["contradiction_false_supports"] == 1
    assert target["partial_or_ambiguous_review_recall"] == 0.74
    assert report["decision"].endswith("before_v17_classifier")
