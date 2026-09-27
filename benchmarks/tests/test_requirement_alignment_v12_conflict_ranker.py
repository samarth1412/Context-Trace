from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest

from benchmarks.requirement_alignment import build_v12_conflict_training
from benchmarks.requirement_alignment.build_v12_conflict_training import build
from benchmarks.requirement_alignment.v12_conflict_ranker import (
    _ranking_metrics,
    conflict_features,
)


ROOT = Path(__file__).resolve().parents[2]
V12 = ROOT / "benchmarks" / "requirement_alignment"
LABELS = ("SUPPORTS", "REFUTES", "NOT_ENOUGH_INFO", "DISPUTED")


def _evidence(claim_id: str, claim_label: str) -> list[dict[str, object]]:
    rows = []
    for index in range(5):
        if claim_label == "DISPUTED":
            label = (
                "SUPPORTS"
                if index == 0
                else "REFUTES"
                if index == 1
                else "NOT_ENOUGH_INFO"
            )
        else:
            label = claim_label if index == 0 else "NOT_ENOUGH_INFO"
        rows.append(
            {
                "evidence_id": f"article-{claim_id}:{index}",
                "evidence_label": label,
                "article": f"Article {claim_id} {index}",
                "evidence": f"Evidence {claim_id} {index}.",
                "entropy": 0.0,
                "votes": [label, label],
            }
        )
    return rows


def _source_rows() -> list[dict[str, object]]:
    rows = []
    for label_index, label in enumerate(LABELS):
        for offset in range(3):
            claim_id = str(label_index * 10 + offset)
            rows.append(
                {
                    "claim_id": claim_id,
                    "claim": f"Claim {claim_id}.",
                    "claim_label": label,
                    "evidences": _evidence(claim_id, label),
                }
            )
    return rows


def test_v12_builder_keeps_all_eligible_claim_groups(tmp_path, monkeypatch) -> None:
    source = tmp_path / "climate-fever.jsonl"
    source.write_text("".join(json.dumps(row) + "\n" for row in _source_rows()))
    monkeypatch.setattr(
        build_v12_conflict_training,
        "DATASET_SHA256",
        hashlib.sha256(source.read_bytes()).hexdigest(),
    )
    v9_ids = {label: [str(index * 10)] for index, label in enumerate(LABELS)}
    v10_ids = {label: [str(index * 10 + 1)] for index, label in enumerate(LABELS)}
    v9 = tmp_path / "v9.json"
    v10 = tmp_path / "v10.json"
    v9.write_text(json.dumps({"selected_claim_ids": v9_ids}))
    v10.write_text(json.dumps({"development_claim_ids": v10_ids}))

    training, selection, audit, manifest = build(source, v9, v10)

    assert len(training["examples"]) == 4
    assert audit["counts"]["claims"] == 4
    assert audit["counts"]["evidence_spans"] == 20
    assert audit["checks"]["all_v9_claim_ids_excluded"] is True
    assert audit["checks"]["all_v10_development_components_excluded"] is True
    assert audit["checks"]["exact_evidence_disjoint_from_v10_development"] is True
    assert selection["model_outputs_used"] is False
    assert selection["source_text_included"] is False
    assert manifest["status"] == "conflict_training_data_frozen_before_v12_scoring"


def test_conflict_features_ignore_targets_and_have_frozen_shape() -> None:
    example = {
        "input": {
            "claim": "The treatment reduced risk by 20 percent.",
            "evidence": [
                {"id": f"e{index}", "text": f"Evidence sentence {index}."}
                for index in range(5)
            ],
        },
        "source": {"claim_label": "DISPUTED"},
        "target": {"label": "review"},
    }
    score_row = {
        "per_evidence": [
            {
                "probabilities": {
                    "entailment": 0.7 - index * 0.05,
                    "contradiction": 0.1 + index * 0.05,
                    "neutral": 0.2,
                }
            }
            for index in range(5)
        ]
    }
    changed = copy.deepcopy(example)
    changed["source"]["claim_label"] = "SUPPORTS"
    changed["target"]["label"] = "covered"

    names, values = conflict_features(example, score_row)
    changed_names, changed_values = conflict_features(changed, score_row)

    assert names == changed_names
    assert values == changed_values
    assert len(names) == len(values) == 143
    assert len(set(names)) == len(names)


def test_ranking_metric_uses_fixed_eighteen_case_budget() -> None:
    targets = [True] * 15 + [False] * 45
    scores = [float(60 - index) for index in range(60)]
    metrics = _ranking_metrics(
        targets, [f"case-{index:02d}" for index in range(60)], scores
    )

    assert metrics["disputed_hits_at_18"] == 15
    assert metrics["disputed_recall_at_18"] == 1.0
    assert metrics["review_budget"] == 18


def test_committed_v12_result_is_local_and_rejected() -> None:
    selection = json.loads((V12 / "v12_conflict_selection.json").read_text())
    audit = json.loads((V12 / "v12_conflict_audit.json").read_text())
    manifest = json.loads((V12 / "v12_conflict_manifest.json").read_text())
    report = json.loads((V12 / "results" / "v12_conflict_ranker.json").read_text())

    assert audit["counts"]["claims"] == 1210
    assert audit["counts"]["claim_labels"]["DISPUTED"] == 78
    assert audit["counts"]["evidence_spans"] == 6050
    assert selection["model_outputs_used"] is False
    assert manifest["training_sha256"] == report["inputs"]["training_sha256"]
    assert report["features"]["count"] == 143
    assert report["selected"]["disputed_recall_at_18"] == pytest.approx(0.6)
    assert report["selected"]["disputed_hits_at_18"] == 9
    assert report["selected"]["policy"]["gates"]["all_met"] is False
    assert report["pairwise_cross_encoder_diagnostic"]["promote"] is False
    assert report["decision"] == "retain_v11_as_best_local_research_candidate"
    assert report["remote_inference_used"] is False
    assert report["stable_defaults_changed"] is False
    assert not (V12 / "v12_conflict_training.json").exists()
