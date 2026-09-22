from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from types import SimpleNamespace

from benchmarks.external_fiveway_confirmation.completeness_gate import (
    gated_verdict,
    metrics,
    support_probability,
)
from benchmarks.external_fiveway_confirmation.completeness_signals import (
    FEATURES,
    run_signals,
)


ROOT = Path(__file__).resolve().parents[2]
BENCHMARK = ROOT / "benchmarks" / "external_fiveway_confirmation"


def test_completeness_runner_sends_only_claim_and_selected_evidence(tmp_path) -> None:
    class FakeClient:
        def __init__(self) -> None:
            self.state = None

        def system_one(self, *, state, questions, model):
            self.state = state
            assert set(questions) == {
                "verdict",
                "support_extent",
                *("completeness_" + name for name in FEATURES),
            }
            assert model == "jev-test"
            answers = {
                "verdict": SimpleNamespace(
                    choice="partially_supported",
                    probabilities={
                        "supported": 0.35,
                        "partially_supported": 0.55,
                        "unsupported": 0.04,
                        "contradicted": 0.03,
                        "unverifiable": 0.03,
                    },
                    confidence=0.7,
                )
            }
            answers["support_extent"] = SimpleNamespace(
                choice="complete_support",
                probabilities={"complete_support": 0.8, "partial_support": 0.2},
                confidence=0.75,
            )
            answers.update(
                {
                    "completeness_" + name: SimpleNamespace(noul=0.8)
                    for name in FEATURES
                }
            )
            return SimpleNamespace(
                answers=answers,
                usage=SimpleNamespace(input_tokens=60, output_tokens=15),
                model="jev-test-resolved",
            )

    client = FakeClient()
    result = run_signals(
        [
            {
                "id": "case",
                "dataset": "fixture",
                "query": "private query",
                "claim": "Every requirement is covered.",
                "contexts": [{"id": "evidence", "text": "Every requirement is covered."}],
                "expected_verdict": "supported",
                "development_partition": "calibration",
            }
        ],
        client=client,
        choice_factory=lambda **kwargs: kwargs,
        noul_factory=lambda **kwargs: kwargs,
        noul_criteria_factory=lambda **kwargs: kwargs,
        model="jev-test",
        checkpoint=tmp_path / "checkpoint.json",
    )

    assert set(client.state) == {"claim", "selected_evidence"}
    assert "private query" not in json.dumps(client.state)
    row = result["rows"][0]
    assert row["input_audit"]["evaluation_label_sent"] is False
    assert set(row["signals"]["completeness_features"]) == set(FEATURES)


def test_completeness_gate_scores_locally_and_preserves_other_verdicts() -> None:
    signals = {
        "base_verdict": "partially_supported",
        "completeness_features": {name: 0.5 for name in FEATURES},
        "base_probabilities": {
            "supported": 0.35,
            "partially_supported": 0.55,
            "unsupported": 0.04,
            "contradicted": 0.03,
            "unverifiable": 0.03,
        },
        "support_extent_probabilities": {
            "complete_support": 0.5,
            "partial_support": 0.5,
        },
        "local_support_probability": 0.5,
    }
    model = {
        "standard_scaler": {"mean": [0.0] * 15, "scale": [1.0] * 15},
        "logistic_regression": {"coefficients": [0.0] * 15, "intercept": 0.0},
    }
    policy = {"model": model, "support_threshold": 0.5}

    assert support_probability(signals, model) == 0.5
    assert gated_verdict(signals, policy) == "supported"
    signals["base_verdict"] = "contradicted"
    assert gated_verdict(signals, policy) == "contradicted"


def test_completeness_metrics_count_partial_false_support() -> None:
    rows = [
        {
            "expected_verdict": "supported",
            "signals": {"base_verdict": "supported"},
        },
        {
            "expected_verdict": "partially_supported",
            "signals": {"base_verdict": "supported"},
        },
    ]

    result = metrics(rows)
    assert result["accuracy"] == 0.5
    assert result["partial_incorrectly_supported_count"] == 1
    assert result["partial_incorrectly_supported_rate"] == 1.0


def test_completeness_extension_is_fresh_balanced_development_data() -> None:
    initial = json.loads(
        (BENCHMARK / "completeness_development_cases.json").read_text(encoding="utf-8")
    )
    extension = json.loads(
        (BENCHMARK / "completeness_development_extension_cases.json").read_text(
            encoding="utf-8"
        )
    )
    initial_ids = {row["id"] for row in initial["cases"]}
    initial_claims = {" ".join(row["claim"].casefold().split()) for row in initial["cases"]}

    assert Counter(row["expected_verdict"] for row in initial["cases"]) == {
        "supported": 60,
        "partially_supported": 60,
    }
    assert Counter(row["expected_verdict"] for row in extension["cases"]) == {
        "supported": 30,
        "partially_supported": 30,
    }
    assert {row["development_partition"] for row in extension["cases"]} == {"validation"}
    assert not initial_ids.intersection(row["id"] for row in extension["cases"])
    assert not initial_claims.intersection(
        " ".join(row["claim"].casefold().split()) for row in extension["cases"]
    )
    assert not (BENCHMARK / "completeness_confirmation_cases.json").exists()
