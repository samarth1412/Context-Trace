from __future__ import annotations

import copy
import json
from pathlib import Path

import numpy as np
import pytest

from benchmarks.requirement_alignment.v14_fiveway_policy import _sha256_json
from benchmarks.requirement_alignment.v27_preserved_nli_signal import (
    feature_variants,
    validate_inputs,
)


def fixture():
    state = {
        "query": "",
        "claim": "A claim",
        "evidence": [{"id": "e", "text": "Some selected evidence"}],
    }
    dataset = {
        "split": "external_fiveway_v21_development",
        "examples": [{"id": "a", "input": state, "target": {"verdict": "supported"}}],
    }
    source = {
        "future_confirmation_loaded": False,
        "variants": {
            "restored_selected_qa": {
                "rows": [
                    {
                        "case_id": "a",
                        "input_sha256": _sha256_json(state),
                        "expected_verdict": "supported",
                    }
                ]
            }
        },
    }
    protocol = {
        "dataset_sha256": _sha256_json(dataset),
        "v25_source_sha256": _sha256_json(source),
        "release_gate_eligible": False,
        "input_policy": {"indicator_regex": r"claim is true", "indicator_flags": []},
    }
    return dataset, source, protocol


def test_model_pairs_exclude_labels_and_preserve_only_selected_text():
    dataset, source, protocol = fixture()
    assert validate_inputs(dataset, source, protocol) == [
        ("Some selected evidence", "A claim")
    ]
    changed = copy.deepcopy(dataset)
    changed["examples"][0]["target"]["verdict"] = "unverifiable"
    with pytest.raises(ValueError, match="frozen"):
        validate_inputs(changed, source, protocol)


def test_source_assessment_flags_must_match_frozen_audit():
    dataset, source, protocol = fixture()
    protocol["input_policy"]["indicator_flags"] = [
        {"case_id": "a", "input_sha256": "invented"}
    ]
    with pytest.raises(ValueError, match="assessment"):
        validate_inputs(dataset, source, protocol)


def test_rebound_dataset_still_requires_exact_case_alignment():
    dataset, source, protocol = fixture()
    dataset["examples"][0]["input"]["evidence"][0]["text"] = "Different evidence"
    protocol["dataset_sha256"] = _sha256_json(dataset)
    with pytest.raises(ValueError, match="binding"):
        validate_inputs(dataset, source, protocol)


def test_feature_ablation_preserves_control_and_adds_only_frozen_logits():
    cls = np.arange(8).reshape(2, 4)
    logits = np.array([[1.0, 2.0, 3.0], [-1.0, 0.0, 1.0]])
    variants = feature_variants(cls, logits)
    np.testing.assert_array_equal(variants["cls_control"], cls)
    np.testing.assert_array_equal(
        variants["cls_plus_pretrained_nli_logits"][:, :4], cls
    )
    np.testing.assert_array_equal(
        variants["cls_plus_pretrained_nli_logits"][:, 4:], logits
    )
    with pytest.raises(ValueError, match="aligned"):
        feature_variants(cls, logits[:1])
    with pytest.raises(ValueError, match="finite"):
        feature_variants(cls, np.full((2, 3), float("nan")))


def test_recorded_ablation_reproduces_control_and_keeps_inputs_bound():
    root = Path(__file__).resolve().parents[1] / "requirement_alignment/results"
    source = json.loads((root / "v25_joint_representation.json").read_text())
    result = json.loads((root / "v27_preserved_nli_signal.json").read_text())
    baseline = source["variants"]["restored_selected_qa"]
    control = result["variants"]["cls_control"]
    assert result["control_probability_max_absolute_difference"] <= 1e-6
    assert control["policy"]["metrics"] == baseline["policy"]["metrics"]
    for variant in result["variants"].values():
        for old, new in zip(baseline["rows"], variant["rows"], strict=True):
            assert (old["case_id"], old["input_sha256"], old["expected_verdict"]) == (
                new["case_id"],
                new["input_sha256"],
                new["expected_verdict"],
            )
            assert set(new["pretrained_nli_logits"]) == {
                "entailment",
                "neutral",
                "contradiction",
            }
    assert result["release_gate_eligible"] is False
    assert result["source_assessments_may_reveal_labels"] is True
    assert result["remote_inference_used"] is False
