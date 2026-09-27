from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from benchmarks.requirement_alignment.v14_fiveway_policy import (
    DEVELOPMENT_SPLIT,
    V14PolicyError,
    _matrix,
    feature_vector,
    policy_metrics,
)


ROOT = Path(__file__).resolve().parents[2]
V14 = ROOT / "benchmarks" / "requirement_alignment"


def _example() -> dict[str, object]:
    return {
        "id": "case-1",
        "input": {
            "query": "",
            "claim": "The treatment reduced risk by 20 percent.",
            "evidence": [
                {"id": "e1", "text": "The treatment reduced risk by 20 percent."},
                {"id": "e2", "text": "A second study found no reduction."},
            ],
        },
        "source": {"dataset": "fixture"},
        "target": {"verdict": "supported"},
    }


def _score_row() -> dict[str, object]:
    return {
        "case_id": "case-1",
        "per_evidence": [
            {
                "probabilities": {
                    "entailment": 0.8,
                    "contradiction": 0.1,
                    "neutral": 0.1,
                }
            },
            {
                "probabilities": {
                    "entailment": 0.1,
                    "contradiction": 0.7,
                    "neutral": 0.2,
                }
            },
        ],
    }


def test_v14_features_ignore_target_and_dataset_identity() -> None:
    example = _example()
    changed = copy.deepcopy(example)
    changed["source"]["dataset"] = "different"  # type: ignore[index]
    changed["target"]["verdict"] = "contradicted"  # type: ignore[index]

    names, values = feature_vector(example, _score_row())
    changed_names, changed_values = feature_vector(changed, _score_row())

    assert names == changed_names
    assert values == changed_values
    assert len(names) == len(values) == 54
    assert len(set(names)) == len(names)


def test_v14_matrix_rejects_consumed_heldout_split() -> None:
    development = {
        "split": "external_fiveway_v13_heldout",
        "examples": [_example()],
    }
    scores = {
        "split": "external_fiveway_v13_heldout",
        "rows": [_score_row()],
        "remote_inference_used": False,
        "evaluation_labels_sent": False,
    }

    with pytest.raises(V14PolicyError, match="only the V13 development"):
        _matrix(development, scores)


def test_v14_policy_metrics_enforce_false_support_and_review_gates() -> None:
    targets = [
        "supported",
        "contradicted",
        "partially_supported",
        "unsupported",
        "unverifiable",
    ]
    safe_predictions = [
        "supported",
        "contradicted",
        "partially_supported",
        "unsupported",
        "unverifiable",
    ]
    unsafe_predictions = ["supported"] * 5

    assert policy_metrics(targets, safe_predictions)["gates"]["all_met"] is True
    unsafe = policy_metrics(targets, unsafe_predictions)
    assert unsafe["false_support_rate"] == 1.0
    assert unsafe["contradiction_false_supports"] == 1
    assert unsafe["gates"]["all_met"] is False


def test_committed_v14_result_is_development_only_and_rejected() -> None:
    report = json.loads((V14 / "results" / "v14_fiveway_policy.json").read_text())

    assert report["protocol"]["selection_split"] == DEVELOPMENT_SPLIT
    assert report["protocol"]["heldout_loaded"] is False
    assert report["protocol"]["heldout_used_for_selection"] is False
    assert report["features"]["count"] == 54
    assert report["search"]["candidate_count"] == 33
    assert report["selected"]["policy"]["metrics"]["macro_f1"] == pytest.approx(0.6549)
    assert report["selected"]["policy"]["metrics"]["false_support_rate"] == 0.02
    assert report["selected"]["policy"]["metrics"]["contradiction_false_supports"] == 0
    assert report["selected"]["policy"]["metrics"]["support_recall"] == 0.2
    assert report["promotion_gates"]["all_met"] is False
    assert report["decision"] == "do_not_promote_v14"
    assert report["remote_inference_used"] is False
    assert report["stable_defaults_changed"] is False
