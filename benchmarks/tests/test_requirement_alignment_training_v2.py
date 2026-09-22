from __future__ import annotations

import json
from pathlib import Path

import pytest
import torch

from benchmarks.requirement_alignment.train_v2 import AlignmentV2TrainingError
from benchmarks.requirement_alignment.train_v2 import directory_manifest
from benchmarks.requirement_alignment.train_v2 import focal_loss
from benchmarks.requirement_alignment.train_v2 import hard_positive_margin_loss
from benchmarks.requirement_alignment.train_v2 import prepare_variant_examples
from benchmarks.requirement_alignment.train_v2 import select_safe_recall_threshold
from benchmarks.requirement_alignment.train_v2 import verify_source_model


def _row(label: str, construction: str) -> dict:
    return {
        "task": "claim_group_completeness",
        "target": {"label": label},
        "source": {"construction": construction},
    }


def test_confidence_filter_removes_only_high_scoring_weak_negatives() -> None:
    rows = [
        _row("complete", "gold_complete_group"),
        _row("incomplete", "gold_partial_group"),
        _row("incomplete", "same_document_hard_negative"),
        _row("incomplete", "synthetic_drop_one"),
    ]

    selected, audit = prepare_variant_examples(
        rows, [0.9, 0.95, 0.7, 0.69], "confidence_filtered"
    )

    assert len(selected) == 3
    assert rows[1] in selected
    assert rows[2] not in selected
    assert audit["removed_weak_negatives"] == 1


def test_hard_positive_variant_duplicates_only_missed_positives() -> None:
    hard = _row("complete", "gold_complete_group")
    easy = _row("complete", "gold_complete_group")
    negative = _row("incomplete", "gold_partial_group")

    selected, audit = prepare_variant_examples(
        [hard, easy, negative], [0.49, 0.5, 0.9], "hard_positive_margin"
    )

    assert selected == [hard, easy, negative, hard]
    assert audit["hard_positives_duplicated_once"] == 1


def test_safe_recall_threshold_obeys_fpr_cap_and_prioritizes_recall() -> None:
    policy = select_safe_recall_threshold(
        [0, 0, 0, 0, 1, 1], [0.1, 0.2, 0.3, 0.85, 0.65, 0.95]
    )

    assert policy["threshold"] == 0.95
    assert policy["metrics"]["positive_recall"] == 0.5
    assert policy["metrics"]["false_positive_rate"] == 0.0


def test_safe_recall_threshold_can_fall_back_to_full_abstention() -> None:
    policy = select_safe_recall_threshold([0, 1], [0.99, 0.99])

    assert policy["threshold"] == 1.0
    assert policy["metrics"]["positive_recall"] == 0.0
    assert policy["metrics"]["false_positive_rate"] == 0.0


def test_source_model_verification_rejects_changed_file(tmp_path: Path) -> None:
    model = tmp_path / "model"
    model.mkdir()
    (model / "config.json").write_text("original", encoding="utf-8")
    files = directory_manifest(model)
    model_id = __import__("hashlib").sha256(
        json.dumps(files, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps({"files": files, "model_id": model_id}), encoding="utf-8"
    )
    verify_source_model(model, manifest)

    (model / "config.json").write_text("changed", encoding="utf-8")
    with pytest.raises(AlignmentV2TrainingError, match="does not match"):
        verify_source_model(model, manifest)


def test_focal_loss_emphasizes_misclassified_examples() -> None:
    easy = focal_loss(torch.tensor([[-3.0, 3.0]]), torch.tensor([1]), torch=torch)
    hard = focal_loss(torch.tensor([[1.0, -1.0]]), torch.tensor([1]), torch=torch)

    assert hard > easy


def test_margin_loss_rewards_positive_negative_separation() -> None:
    labels = torch.tensor([1, 0])
    weights = torch.ones(2)
    poorly_separated = hard_positive_margin_loss(
        torch.tensor([[0.0, 0.0], [0.0, 1.0]]),
        labels,
        class_weights=weights,
        torch=torch,
    )
    well_separated = hard_positive_margin_loss(
        torch.tensor([[0.0, 2.0], [2.0, 0.0]]),
        labels,
        class_weights=weights,
        torch=torch,
    )

    assert well_separated < poorly_separated
