from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from types import SimpleNamespace

from benchmarks.external_fiveway_confirmation.adapter import LABELS
from benchmarks.external_fiveway_confirmation.ambiguity_features import (
    FEATURES,
    ambiguity_score,
    feature_verdict,
    run_features,
)
from benchmarks.external_fiveway_confirmation.ambiguity_gate import gated_verdict, run_signals
from benchmarks.external_fiveway_confirmation.audit import audit_case_pack
from benchmarks.external_fiveway_confirmation.freeze import verify_manifest
from benchmarks.external_fiveway_confirmation.learned_ambiguity_gate import (
    apply_policy,
    ambiguity_probability,
    learned_verdict,
)


ROOT = Path(__file__).resolve().parents[2]
BENCHMARK = ROOT / "benchmarks" / "external_fiveway_confirmation"


def test_frozen_confirmation_pack_is_balanced_and_uses_lossless_mappings() -> None:
    payload = json.loads((BENCHMARK / "confirmation_cases.json").read_text(encoding="utf-8"))
    cases = payload["cases"]

    assert len(cases) == 125
    assert Counter(row["expected_verdict"] for row in cases) == Counter(
        {label: 25 for label in LABELS}
    )
    assert payload["predictions_used_for_selection"] is False
    assert payload["evidence_regime"]["oracle_evidence_used_as_model_input"] is False
    assert all("predictions" not in row for row in cases)


def test_frozen_confirmation_inputs_are_label_isolated_and_disjoint() -> None:
    result = audit_case_pack(
        BENCHMARK / "confirmation_cases.json",
        prior_case_packs=[
            ROOT / "benchmarks" / "jev_claim_verification" / "development_cases.json",
            ROOT / "benchmarks" / "jev_claim_verification" / "heldout_cases.json",
            ROOT
            / "benchmarks"
            / "jev_v2_verification"
            / "ragtruth_sentence_extension_development.json",
            ROOT
            / "benchmarks"
            / "jev_v2_verification"
            / "ragtruth_sentence_extension_heldout.json",
        ],
    )

    assert result["valid"] is True
    assert result["label_isolation"]["evaluation_labels_sent"] is False
    assert result["prior_overlap"] == {
        "case_ids": [],
        "normalized_claims": [],
        "normalized_inputs": [],
    }
    assert result["selection"]["nonempty_for_every_case"] is True


def test_confirmation_freeze_manifest_hashes_still_match() -> None:
    result = verify_manifest(BENCHMARK / "freeze_manifest.json")
    assert result["valid"] is True


def test_development_pack_is_balanced_partitioned_and_disjoint() -> None:
    payload = json.loads((BENCHMARK / "development_cases.json").read_text(encoding="utf-8"))
    cases = payload["cases"]

    assert Counter(row["development_partition"] for row in cases) == {
        "calibration": 75,
        "validation": 50,
    }
    assert Counter(
        (row["development_partition"], row["expected_verdict"]) for row in cases
    ) == Counter(
        {
            (partition, label): count
            for partition, count in (("calibration", 15), ("validation", 10))
            for label in LABELS
        }
    )
    assert payload["heldout_confirmation_cases_excluded"] is True


def test_ambiguity_gate_sends_only_claim_and_selected_evidence(tmp_path) -> None:
    class FakeClient:
        def __init__(self) -> None:
            self.state = None

        def system_one(self, *, state, questions, model):
            self.state = state
            assert set(questions) == {"verdict", "linguistic_ambiguity", "complete_support"}
            assert model == "jev-test"
            return SimpleNamespace(
                answers={
                    "verdict": SimpleNamespace(
                        choice="supported",
                        probabilities={
                            "supported": 0.8,
                            "partially_supported": 0.1,
                            "unsupported": 0.04,
                            "contradicted": 0.03,
                            "unverifiable": 0.03,
                        },
                        confidence=0.75,
                    ),
                    "linguistic_ambiguity": SimpleNamespace(noul=0.91),
                    "complete_support": SimpleNamespace(noul=0.82),
                },
                usage=SimpleNamespace(input_tokens=40, output_tokens=8),
                model="jev-test-resolved",
            )

    client = FakeClient()
    case = {
        "id": "case",
        "dataset": "fixture",
        "query": "private query metadata",
        "claim": "The policy is clear.",
        "contexts": [{"id": "policy", "text": "The policy is clear."}],
        "expected_verdict": "unverifiable",
        "development_partition": "calibration",
    }
    result = run_signals(
        [case],
        client=client,
        choice_factory=lambda **kwargs: kwargs,
        noul_factory=lambda **kwargs: kwargs,
        noul_criteria_factory=lambda **kwargs: kwargs,
        model="jev-test",
        checkpoint=tmp_path / "checkpoint.json",
    )

    assert set(client.state) == {"claim", "selected_evidence"}
    assert "private query metadata" not in json.dumps(client.state)
    assert "expected_verdict" not in json.dumps(client.state)
    assert result["rows"][0]["input_audit"]["evaluation_label_sent"] is False
    assert gated_verdict(
        result["rows"][0]["signals"],
        policy={"ambiguity_threshold": 0.8, "complete_support_threshold": 0.7},
    ) == "unverifiable"


def test_decomposed_ambiguity_features_are_private_and_deterministic(tmp_path) -> None:
    class FakeClient:
        def __init__(self) -> None:
            self.state = None

        def system_one(self, *, state, questions, model):
            self.state = state
            assert set(questions) == {"verdict", *("ambiguity_" + name for name in FEATURES)}
            assert model == "jev-test"
            answers = {
                "verdict": SimpleNamespace(
                    choice="supported",
                    probabilities={
                        "supported": 0.8,
                        "partially_supported": 0.1,
                        "unsupported": 0.04,
                        "contradicted": 0.03,
                        "unverifiable": 0.03,
                    },
                    confidence=0.75,
                )
            }
            feature_values = {
                "lexical": 0.2,
                "reference": 0.9,
                "structure_scope": 0.6,
                "pragmatic": 0.3,
                "verdict_instability": 0.8,
            }
            answers.update(
                {
                    "ambiguity_" + name: SimpleNamespace(noul=value)
                    for name, value in feature_values.items()
                }
            )
            return SimpleNamespace(
                answers=answers,
                usage=SimpleNamespace(input_tokens=50, output_tokens=12),
                model="jev-test-resolved",
            )

    client = FakeClient()
    case = {
        "id": "case",
        "dataset": "fixture",
        "query": "private query metadata",
        "claim": "The bank is nearby.",
        "contexts": [{"id": "context", "text": "The bank is nearby."}],
        "expected_verdict": "unverifiable",
    }
    result = run_features(
        [case],
        client=client,
        choice_factory=lambda **kwargs: kwargs,
        noul_factory=lambda **kwargs: kwargs,
        noul_criteria_factory=lambda **kwargs: kwargs,
        model="jev-test",
        checkpoint=tmp_path / "checkpoint.json",
    )

    assert set(client.state) == {"claim", "selected_evidence"}
    assert "private query metadata" not in json.dumps(client.state)
    row = result["rows"][0]
    assert row["development_partition"] is None
    assert row["input_audit"]["evaluation_label_sent"] is False
    assert ambiguity_score(row["signals"]["ambiguity_features"], "maximum") == 0.9
    assert round(
        ambiguity_score(row["signals"]["ambiguity_features"], "top_two_mean"), 2
    ) == 0.85
    assert feature_verdict(
        row["signals"],
        policy={"ambiguity_aggregation": "top_two_mean", "ambiguity_threshold": 0.8},
    ) == "unverifiable"


def test_serialized_learned_gate_scores_without_sklearn_runtime() -> None:
    signals = {
        "base_verdict": "supported",
        "ambiguity_features": {name: 0.5 for name in FEATURES},
        "base_probabilities": {
            "supported": 0.8,
            "partially_supported": 0.1,
            "unsupported": 0.04,
            "contradicted": 0.03,
            "unverifiable": 0.03,
        },
    }
    model = {
        "standard_scaler": {"mean": [0.0] * 10, "scale": [1.0] * 10},
        "logistic_regression": {"coefficients": [0.0] * 10, "intercept": 0.0},
    }
    policy = {"model": model, "ambiguity_threshold": 0.5}

    assert ambiguity_probability(signals, model) == 0.5
    assert learned_verdict(signals, policy) == "unverifiable"
    applied = apply_policy(
        {
            "experiment": "fixture",
            "split": {"name": "fixture"},
            "rows": [
                {
                    "expected_verdict": "unverifiable",
                    "signals": signals,
                }
            ],
        },
        {"policy_id": "fixture-policy", "policy": policy},
    )
    assert applied["metrics"]["accuracy"] == 1.0
    assert applied["rows"][0]["learned_gate"]["overrode_base_verdict"] is True


def test_second_confirmation_pack_is_balanced_and_disjoint() -> None:
    first = json.loads((BENCHMARK / "confirmation_cases.json").read_text(encoding="utf-8"))
    second = json.loads((BENCHMARK / "confirmation_v2_cases.json").read_text(encoding="utf-8"))
    first_ids = {row["id"] for row in first["cases"]}
    first_claims = {" ".join(row["claim"].casefold().split()) for row in first["cases"]}

    assert Counter(row["expected_verdict"] for row in second["cases"]) == Counter(
        {label: 7 for label in LABELS}
    )
    assert not first_ids.intersection(row["id"] for row in second["cases"])
    assert not first_claims.intersection(
        " ".join(row["claim"].casefold().split()) for row in second["cases"]
    )
    assert second["predictions_used_for_selection"] is False
