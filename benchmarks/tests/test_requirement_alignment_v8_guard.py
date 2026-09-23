from __future__ import annotations

import json
from pathlib import Path

from benchmarks.requirement_alignment.v8_guard import calibrate_guard
from benchmarks.requirement_alignment.v8_guard import evaluate_guarded_rows
from benchmarks.requirement_alignment.v8_guard import guarded_local_route
from benchmarks.requirement_alignment.v8_guard import validate_policy


ROOT = Path(__file__).resolve().parents[2]
V8 = ROOT / "benchmarks" / "requirement_alignment"
RESULTS = V8 / "results"


def _predictions(
    v3_entailment: float,
    v5_entailment: float,
    *,
    v3_contradiction: float = 0.01,
    v5_contradiction: float = 0.01,
) -> dict[str, dict[str, object]]:
    return {
        "v3": {
            "entailment_probability": v3_entailment,
            "probabilities": {
                "entailment": v3_entailment,
                "contradiction": v3_contradiction,
                "neutral": 1.0 - v3_entailment - v3_contradiction,
            },
        },
        "v5": {
            "entailment_probability": v5_entailment,
            "probabilities": {
                "entailment": v5_entailment,
                "contradiction": v5_contradiction,
                "neutral": 1.0 - v5_entailment - v5_contradiction,
            },
        },
    }


def _jev(verdict: str, supported: float) -> dict[str, object]:
    return {
        "verdict": verdict,
        "probabilities": {
            "supported": supported,
            "partially_supported": 0.1,
            "unsupported": 0.1,
            "contradicted": 0.1,
            "unverifiable": 0.1,
        },
        "confidence": 0.9,
        "latency_ms": 10.0,
        "usage": {"input_tokens": 10, "output_tokens": 2, "total_tokens": 12},
    }


def test_guard_vetoes_local_support_when_either_model_detects_contradiction() -> None:
    policy = {
        "local_missing_threshold": 0.7,
        "local_supported_threshold": 0.875,
        "local_contradiction_veto_threshold": 0.04,
    }

    assert guarded_local_route(_predictions(0.91, 0.90), policy) == "supported"
    assert (
        guarded_local_route(_predictions(0.91, 0.90, v3_contradiction=0.041), policy)
        == "route"
    )
    assert guarded_local_route(_predictions(0.50, 0.60), policy) == "missing"


def test_guarded_evaluation_uses_jev_only_for_routed_cases() -> None:
    policy = {
        "local_missing_threshold": 0.7,
        "local_supported_threshold": 0.875,
        "local_contradiction_veto_threshold": 0.04,
        "jev_supported_probability": 0.5,
        "review_confidence": 0.8,
        "always_review_supported": True,
    }
    examples = {
        "local-supported": {
            "target": {"label": "covered"},
            "source": {"relation": "Entailment"},
        },
        "routed-contradiction": {
            "target": {"label": "missing"},
            "source": {"relation": "Contradiction"},
        },
        "local-missing": {
            "target": {"label": "missing"},
            "source": {"relation": "NotMentioned"},
        },
    }
    local = {
        "local-supported": {"predictions": _predictions(0.91, 0.90)},
        "routed-contradiction": {
            "predictions": _predictions(0.91, 0.90, v3_contradiction=0.08)
        },
        "local-missing": {"predictions": _predictions(0.50, 0.60)},
    }
    jev = {"routed-contradiction": {"prediction": _jev("contradicted", supported=0.01)}}

    result = evaluate_guarded_rows(
        examples, local, jev, policy=policy, require_all_jev=False
    )

    assert result["optional_jev"]["metrics"]["accuracy"] == 1.0
    assert result["optional_jev"]["operations"]["remote_calls"] == 1
    assert result["local_only"]["network_calls"] == 0
    assert result["local_only"]["metrics"]["abstentions"] == 1


def test_committed_v8_calibration_is_reproducible() -> None:
    dataset = json.loads((V8 / "v7_scifact_development.json").read_text())
    local = json.loads(
        (RESULTS / "v8_scifact_development_local_scores.json").read_text()
    )
    jev = json.loads((RESULTS / "v8_scifact_development_jev.json").read_text())
    committed_policy = json.loads(
        (RESULTS / "v8_scifact_guard_policy.json").read_text()
    )
    committed_analysis = json.loads(
        (RESULTS / "v8_scifact_guard_calibration.json").read_text()
    )

    policy, analysis = calibrate_guard(dataset, local, jev)

    assert policy == committed_policy
    assert analysis == committed_analysis
    assert analysis["selected"]["gates"]["quality_gates_met"] is True
    assert analysis["selected"]["gates"]["all_release_gates_met"] is False
    assert analysis["release_ready_candidate_count"] == 0


def test_committed_v8_remote_rows_preserve_minimized_state_and_audit_fields() -> None:
    development = json.loads((RESULTS / "v8_scifact_development_jev.json").read_text())
    evaluation = json.loads((RESULTS / "v8_scifact_evaluation_jev.json").read_text())
    for result, expected in ((development, 270), (evaluation, 95)):
        assert result["complete"] is True
        assert result["completed"] == expected
        assert len(result["rows"]) == expected
        for row in result["rows"]:
            prediction = row["prediction"]
            assert prediction["resolved_model"] == "jev-1.13.0"
            assert set(prediction["probabilities"]) == {
                "supported",
                "partially_supported",
                "unsupported",
                "contradicted",
                "unverifiable",
            }
            assert prediction["reason"] is None
            assert prediction["matched_facts"] == []
            assert prediction["missing_facts"] == []
            assert prediction["conflicting_facts"] == []
            audit = prediction["input_audit"]
            assert audit["sent_fields"] == ["claim", "selected_evidence"]
            assert audit["evaluation_label_sent"] is False
            assert audit["query_sent"] is False
            assert audit["context_metadata_sent"] is False
            assert prediction["usage"]["total_tokens"] == (
                prediction["usage"]["input_tokens"]
                + prediction["usage"]["output_tokens"]
            )


def test_posthoc_result_is_diagnostic_and_keeps_defaults_unchanged() -> None:
    policy = json.loads((RESULTS / "v8_scifact_guard_policy.json").read_text())
    result = json.loads((RESULTS / "v8_scifact_posthoc_evaluation.json").read_text())

    validate_policy(policy)
    assert result["evaluation_used_for_selection"] is False
    assert result["evaluation_previously_consumed_by_v7"] is True
    assert result["eligible_as_fresh_release_evidence"] is False
    assert result["stable_defaults_changed"] is False
    assert result["remote_provider_default_enabled"] is False
    assert result["local_only_network_calls"] == 0
    assert result["optional_jev"]["metrics"]["false_positive_rate"] == 0.0083
    assert result["optional_jev"]["metrics"]["positive_recall"] == 0.35
    assert result["comparison_to_v7"]["introduced_false_support_case_ids"] == []
    assert len(result["comparison_to_v7"]["eliminated_false_support_case_ids"]) == 4
