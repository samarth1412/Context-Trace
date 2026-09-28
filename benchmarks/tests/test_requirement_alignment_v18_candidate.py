from __future__ import annotations

import json
from pathlib import Path

import pytest

from benchmarks.requirement_alignment.v18_candidate import (
    V18CandidateError,
    _aligned_rows,
    _v14_route,
    _v15_route,
    _v17_rescue,
    load_frozen_candidate,
)


ROOT = Path(__file__).resolve().parents[2]
V18 = ROOT / "benchmarks" / "requirement_alignment"


def test_v18_v14_route_preserves_contradiction_and_review_guards() -> None:
    policy = {
        "support_probability_minimum": 0.9,
        "contradiction_probability_maximum": 0.2,
        "partial_or_ambiguous_probability_maximum": 0.2,
    }

    assert _v14_route([0.02, 0.03, 0.91, 0.02, 0.02], policy) == "supported"
    assert _v14_route([0.21, 0.03, 0.91, 0.02, 0.02], policy) != "supported"
    assert _v14_route([0.02, 0.12, 0.91, 0.02, 0.09], policy) != "supported"


def test_v18_v15_and_v17_routes_use_only_frozen_boundaries() -> None:
    v15_policy = {
        "complete_support_probability_minimum": 0.8,
        "contradiction_probability_maximum": 0.2,
        "unverifiable_probability_maximum": 0.4,
    }
    v17_policy = {"minimum_single_span_entailment": 0.7}
    safe_v14 = [0.05, 0.2, 0.7, 0.03, 0.02]

    assert _v15_route("supported", safe_v14, 0.8, v15_policy) == "supported"
    assert (
        _v15_route("partially_supported", safe_v14, 0.79, v15_policy)
        == "partially_supported"
    )
    assert _v15_route("contradicted", safe_v14, 0.99, v15_policy) == "contradicted"
    assert (
        _v17_rescue("partially_supported", "supported", 0.7, v17_policy) == "supported"
    )
    assert (
        _v17_rescue("partially_supported", "partially_supported", 0.99, v17_policy)
        == "partially_supported"
    )


def test_v18_rejects_labels_inside_model_inputs() -> None:
    dataset = {
        "split": "confirmation",
        "examples": [
            {
                "id": "case-1",
                "input": {"claim": "x", "target": "supported", "evidence": []},
            }
        ],
    }
    dataset_hash = _json_hash(dataset)
    artifact = {
        "split": "confirmation",
        "dataset_sha256": dataset_hash,
        "remote_inference_used": False,
        "evaluation_labels_sent": False,
        "input_contract": {"evaluation_labels_sent": False},
        "rows": [{"case_id": "case-1"}],
    }

    with pytest.raises(V18CandidateError, match="labels or metadata"):
        _aligned_rows(dataset, artifact, artifact, artifact)


def test_v18_loader_checks_hash_before_deserialization(tmp_path: Path) -> None:
    artifact = tmp_path / "candidate.joblib"
    artifact.write_bytes(b"not a trusted artifact")
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps({"artifact": {"sha256": "0" * 64}}), encoding="utf-8"
    )

    with pytest.raises(V18CandidateError, match="does not match"):
        load_frozen_candidate(artifact, manifest)


def test_committed_v18_manifest_freezes_before_confirmation() -> None:
    manifest = json.loads(
        (V18 / "results" / "v18_frozen_candidate_manifest.json").read_text()
    )

    assert manifest["status"] == "frozen_before_new_confirmation_data_access"
    assert manifest["artifact"] == {
        "bytes": 139768,
        "format": "joblib",
        "path": "v18_frozen_candidate.joblib",
        "sha256": "bcc5f0d2e66edbb5a400c5c54bb59a31a39ac1a6ce02ff38602b5f0af6288009",
        "trusted_local_artifact_only": True,
    }
    assert manifest["candidate"]["v14"]["estimator"] == "hist_leaves_3_minimum_10"
    assert manifest["candidate"]["v15"]["estimator"] == "hist_minimum_5"
    assert manifest["candidate"]["v17"]["minimum_single_span_entailment"] == 0.7
    assert manifest["protocol"] == {
        "configuration_changed_after_v17": False,
        "confirmation_data_loaded": False,
        "confirmation_labels_loaded": False,
        "confirmation_predictions_inspected": False,
        "development_fitted_once": True,
        "evaluation_labels_in_model_features": False,
        "future_confirmation_retraining_allowed": False,
    }
    assert manifest["remote_inference_used"] is False
    assert manifest["stable_defaults_changed"] is False
    assert manifest["remote_provider_default_enabled"] is False
    assert manifest["local_only_network_calls"] == 0


def _json_hash(value: object) -> str:
    import hashlib

    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()
