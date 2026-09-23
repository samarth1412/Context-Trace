from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from benchmarks.requirement_alignment.score_v9_auxiliary import _explode
from benchmarks.requirement_alignment.v9_router import (
    V9RouterError,
    _feature_names,
    _features,
    calibrate_router,
    candidate_route,
    score_serialized_router,
)


ROOT = Path(__file__).resolve().parents[2]
V9 = ROOT / "benchmarks" / "requirement_alignment"
RESULTS = V9 / "results"


def _load(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def test_feature_schema_does_not_read_gold_target_or_relation() -> None:
    example = {
        "id": "case",
        "input": {
            "claim": "Treatment reduced risk by 20 percent.",
            "requirement": {
                "id": "r00",
                "text": "Treatment reduced risk by 20 percent.",
            },
            "evidence": [
                {"id": "e1", "text": "The treatment reduced risk by 20 percent."}
            ],
        },
        "source": {"relation": "Entailment"},
        "target": {"label": "covered"},
    }
    local = {
        "predictions": {
            model: {
                "probabilities": {
                    "entailment": 0.9,
                    "contradiction": 0.02,
                    "neutral": 0.08,
                }
            }
            for model in ("v3", "v5")
        }
    }
    auxiliary = {
        "pinned_nli_group": {
            "entailment": 0.99,
            "contradiction": 0.005,
            "neutral": 0.005,
        },
        "per_evidence": [
            {
                "v3": local["predictions"]["v3"]["probabilities"],
                "v5": local["predictions"]["v5"]["probabilities"],
                "pinned_nli": {
                    "entailment": 0.99,
                    "contradiction": 0.005,
                    "neutral": 0.005,
                },
            }
        ],
    }
    changed = copy.deepcopy(example)
    changed["source"]["relation"] = "Contradiction"
    changed["target"]["label"] = "missing"

    assert _features(example, local, auxiliary) == _features(changed, local, auxiliary)
    assert len(_features(example, local, auxiliary)) == len(_feature_names()) == 48
    exploded = _explode([example])
    assert set(exploded[0]) == {"span_id", "claim", "requirement", "evidence"}


def test_serialized_router_and_local_only_routing() -> None:
    policy = _load(RESULTS / "v9_scifact_router_policy.json")["policy"]
    router = policy["router"]
    features = list(router["scaler_mean"])
    score = score_serialized_router(features, router)
    assert 0.0 < score < 1.0

    high_nli = {"entailment": 0.99, "contradiction": 0.005, "neutral": 0.005}
    low_nli = {"entailment": 0.50, "contradiction": 0.10, "neutral": 0.40}
    assert (
        candidate_route("route", high_nli, features, policy, local_only=True)
        == "supported"
    )
    assert (
        candidate_route("supported", high_nli, features, policy, local_only=True)
        == "supported"
    )
    assert (
        candidate_route("route", low_nli, features, policy, local_only=True)
        == "abstain"
    )
    assert (
        candidate_route("route", low_nli, features, policy, local_only=False) == "route"
    )
    with pytest.raises(V9RouterError):
        score_serialized_router(features[:-1], router)


def test_committed_v9_router_calibration_is_reproducible() -> None:
    policy, analysis = calibrate_router(
        _load(V9 / "v7_scifact_development.json"),
        _load(RESULTS / "v8_scifact_development_local_scores.json"),
        _load(RESULTS / "v9_scifact_development_auxiliary_scores.json"),
        _load(RESULTS / "v8_scifact_development_jev.json"),
        _load(RESULTS / "v8_scifact_guard_policy.json"),
    )

    assert policy == _load(RESULTS / "v9_scifact_router_policy.json")
    assert analysis == _load(RESULTS / "v9_scifact_router_calibration.json")
    selected = analysis["selected"]
    assert selected["gates"]["all_met"] is True
    assert selected["optional_jev"]["metrics"]["positive_recall"] == 0.5444
    assert selected["optional_jev"]["metrics"]["false_positive_rate"] == 0.0056
    assert selected["optional_jev"]["metrics"]["contradiction_false_support_count"] == 0
    assert selected["optional_jev"]["operations"]["remote_call_rate"] == pytest.approx(
        77 / 270
    )
    assert analysis["holdout_accessed"] is False
    assert analysis["stable_defaults_changed"] is False
    assert policy["remote_provider_default_enabled"] is False
    assert analysis["local_only_network_calls"] == 0
