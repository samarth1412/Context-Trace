from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from benchmarks.requirement_alignment.v15_atomic_completeness import (
    V15CompletenessError,
    _aligned_inputs,
    atomic_feature_vector,
)


ROOT = Path(__file__).resolve().parents[2]
V15 = ROOT / "benchmarks" / "requirement_alignment"


def _atomic_row() -> dict[str, object]:
    return {
        "case_id": "case-1",
        "requirements": [
            {
                "status": "covered",
                "nli_scores": {
                    "entailment": 0.8,
                    "contradiction": 0.1,
                    "neutral": 0.1,
                },
            },
            {
                "status": "missing",
                "nli_scores": {
                    "entailment": 0.3,
                    "contradiction": 0.1,
                    "neutral": 0.6,
                },
            },
        ],
    }


def test_v15_atomic_features_have_frozen_label_blind_schema() -> None:
    row = _atomic_row()
    changed = copy.deepcopy(row)
    changed["expected_verdict"] = "supported"
    changed["dataset"] = "fixture"

    names, values = atomic_feature_vector(row)
    changed_names, changed_values = atomic_feature_vector(changed)

    assert names == changed_names
    assert values == changed_values
    assert len(names) == len(values) == 34
    assert len(set(names)) == len(names)


def test_v15_rejects_heldout_artifacts_before_reading_features() -> None:
    heldout = {"split": "external_fiveway_v13_heldout"}
    with pytest.raises(V15CompletenessError, match="only V13 development"):
        _aligned_inputs(
            heldout,
            heldout,
            {
                "protocol": {
                    "selection_split": "external_fiveway_v13_development",
                    "heldout_loaded": False,
                    "heldout_used_for_selection": False,
                }
            },
            heldout,
        )


def test_committed_v15_result_improves_v14_but_remains_rejected() -> None:
    report = json.loads((V15 / "results" / "v15_atomic_completeness.json").read_text())
    metrics = report["selected"]["policy"]["metrics"]

    assert report["protocol"]["heldout_loaded"] is False
    assert report["protocol"]["heldout_used_for_selection"] is False
    assert report["inputs"]["atomic_requirements"] == 153
    assert report["search"]["candidate_count"] == 60
    assert metrics["macro_f1"] == pytest.approx(0.7005)
    assert metrics["support_recall"] == 0.4
    assert metrics["false_support_rate"] == 0.04
    assert metrics["contradiction_false_supports"] == 0
    assert metrics["partial_or_ambiguous_review_recall"] == 0.8
    assert metrics["review_rate"] == 0.48
    assert (
        sum(value for key, value in metrics["gates"].items() if key != "all_met") == 4
    )
    assert report["promotion_gates"]["all_met"] is False
    assert report["decision"] == "do_not_promote_v15"
    assert report["remote_inference_used"] is False
    assert report["stable_defaults_changed"] is False
