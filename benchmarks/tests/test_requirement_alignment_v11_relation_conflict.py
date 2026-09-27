from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from benchmarks.requirement_alignment import build_v11_span_training
from benchmarks.requirement_alignment.build_v11_span_training import build
from benchmarks.requirement_alignment.train_v11_relation_conflict import (
    _classification_metrics,
    _four_way_label,
    _routing_metrics,
)


ROOT = Path(__file__).resolve().parents[2]
V11 = ROOT / "benchmarks" / "requirement_alignment"
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
        entropy = 0.0 if index < 2 else 0.6931471805599453
        rows.append(
            {
                "evidence_id": f"article-{claim_id}:{index}",
                "evidence_label": label,
                "article": f"Article {claim_id} {index}",
                "evidence": f"Evidence {claim_id} {index}.",
                "entropy": entropy,
                "votes": [label, label] if entropy == 0.0 else [label, None],
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


def test_v11_builder_excludes_prior_claims_and_development_components(
    tmp_path, monkeypatch
) -> None:
    source = tmp_path / "climate-fever.jsonl"
    source.write_text("".join(json.dumps(row) + "\n" for row in _source_rows()))
    monkeypatch.setattr(
        build_v11_span_training,
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

    assert audit["counts"]["eligible_claims"] == 4
    assert audit["counts"]["selected_spans"] == 8
    assert audit["checks"]["all_v9_claim_ids_excluded"] is True
    assert audit["checks"]["all_v10_development_components_excluded"] is True
    assert audit["checks"]["exact_evidence_disjoint_from_v10_development"] is True
    assert audit["checks"]["all_selected_annotations_unanimous"] is True
    assert selection["model_outputs_used"] is False
    assert selection["source_text_included"] is False
    assert manifest["status"] == "training_data_frozen_before_v11_model_training"
    for row in training["examples"]:
        assert not ({"label", "target", "relation"} & set(row["input"]))


def test_relation_and_routing_helpers_keep_policy_explicit() -> None:
    labels = ("NOT_ENOUGH_INFO", "REFUTES", "SUPPORTS")
    metrics = _classification_metrics(list(labels), list(labels), labels)
    targets = [
        *(["SUPPORTS"] * 10),
        *(["REFUTES"] * 10),
        *(["NOT_ENOUGH_INFO"] * 10),
        *(["DISPUTED"] * 10),
    ]
    policy = _routing_metrics(targets, set(range(5)), set(range(30, 40)))

    assert metrics["macro_f1"] == 1.0
    assert [_four_way_label(True, True), _four_way_label(False, False)] == [
        "DISPUTED",
        "NOT_ENOUGH_INFO",
    ]
    assert policy["gates"]["all_met"] is True


def test_committed_v11_receipts_and_result_are_local_and_rejected() -> None:
    selection = json.loads((V11 / "v11_span_selection.json").read_text())
    audit = json.loads((V11 / "v11_span_audit.json").read_text())
    data_manifest = json.loads((V11 / "v11_span_manifest.json").read_text())
    report = json.loads(
        (V11 / "results" / "v11_relation_conflict_training.json").read_text()
    )
    model_manifest = json.loads(
        (V11 / "results" / "v11_relation_model_manifest.json").read_text()
    )

    assert audit["counts"]["selected_spans"] == 3039
    assert audit["counts"]["selected_relations"] == {
        "contradiction": 388,
        "entailment": 1345,
        "neutral": 1306,
    }
    assert all(
        value
        for key, value in audit["checks"].items()
        if key != "model_outputs_used_for_selection"
    )
    assert audit["checks"]["model_outputs_used_for_selection"] is False
    assert selection["model_outputs_used"] is False
    assert data_manifest["training_sha256"] == report["datasets"]["training"]["sha256"]
    assert report["selection"]["selected_epoch"] == 2
    selected = report["selection"]["selected"]
    assert selected["direct_four_way"]["metrics"]["macro_f1"] == pytest.approx(0.596)
    assert selected["policy"]["gates"]["all_met"] is False
    assert selected["policy"]["refutation_false_supports"] == 0
    assert report["decision"] == "do_not_promote"
    assert report["v9_holdout_reused"] is False
    assert report["remote_inference_used"] is False
    assert report["stable_defaults_changed"] is False
    assert model_manifest["promotion_gates_met"] is False
    assert model_manifest["runtime_network_required"] is False
    assert not (V11 / "v11_span_training.json").exists()
