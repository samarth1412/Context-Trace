from __future__ import annotations

import hashlib
import json
from pathlib import Path

from benchmarks.requirement_alignment import build_v10_climate_development
from benchmarks.requirement_alignment.build_v10_climate_development import build


ROOT = Path(__file__).resolve().parents[2]
V10 = ROOT / "benchmarks" / "requirement_alignment"
LABELS = ("SUPPORTS", "REFUTES", "NOT_ENOUGH_INFO", "DISPUTED")


def _canonical(value: object) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _evidence(label: str, claim_id: str) -> list[dict[str, object]]:
    rows = []
    for index in range(5):
        evidence_label = label if index == 0 else "NOT_ENOUGH_INFO"
        if label == "DISPUTED":
            evidence_label = (
                "SUPPORTS"
                if index == 0
                else "REFUTES"
                if index == 1
                else "NOT_ENOUGH_INFO"
            )
        rows.append(
            {
                "evidence_id": f"{claim_id}:{index}",
                "evidence_label": evidence_label,
                "article": f"Article {claim_id} {index}",
                "evidence": f"Evidence {claim_id} {index}.",
                "entropy": 0.0,
                "votes": [evidence_label, evidence_label],
            }
        )
    return rows


def _source_rows() -> list[dict[str, object]]:
    rows = []
    for label_index, label in enumerate(LABELS):
        for index in range(4):
            claim_id = str(label_index * 10 + index)
            rows.append(
                {
                    "claim_id": claim_id,
                    "claim": f"Claim {claim_id}.",
                    "claim_label": label,
                    "evidences": _evidence(label, claim_id),
                }
            )
    return rows


def test_builder_excludes_consumed_ids_and_separates_exact_evidence(
    tmp_path, monkeypatch
) -> None:
    source = tmp_path / "climate-fever.jsonl"
    rows = _source_rows()
    source.write_text("".join(json.dumps(row) + "\n" for row in rows))
    monkeypatch.setattr(
        build_v10_climate_development,
        "DATASET_SHA256",
        hashlib.sha256(source.read_bytes()).hexdigest(),
    )
    selected = {label: [str(index * 10)] for index, label in enumerate(LABELS)}
    consumed = {
        "selected_claim_ids": selected,
        "selected_claim_ids_sha256": _canonical(selected),
    }
    consumed_path = tmp_path / "consumed.json"
    consumed_path.write_text(json.dumps(consumed))

    training, development, selection, audit, manifest = build(
        source,
        consumed_path,
        training_per_label=1,
        development_per_label=1,
    )

    assert len(training["examples"]) == 4
    assert len(development["examples"]) == 4
    assert audit["checks"]["all_consumed_v9_claim_ids_excluded"] is True
    assert audit["checks"]["training_development_claim_ids_disjoint"] is True
    assert audit["checks"]["training_development_exact_evidence_disjoint"] is True
    assert audit["checks"]["development_uses_one_claim_per_evidence_component"] is True
    assert selection["model_outputs_used"] is False
    assert selection["source_text_included"] is False
    assert manifest["status"] == "development_data_frozen_before_model_training"
    assert manifest["v9_holdout_reused"] is False
    for example in training["examples"] + development["examples"]:
        assert not ({"label", "target", "relation"} & set(example["input"]))


def test_committed_v10_receipts_are_self_consistent_and_text_free() -> None:
    selection = json.loads((V10 / "v10_climate_selection.json").read_text())
    audit = json.loads((V10 / "v10_climate_audit.json").read_text())
    manifest = json.loads((V10 / "v10_climate_manifest.json").read_text())
    v9 = json.loads((V10 / "v9_climate_fever_selection.json").read_text())

    training_ids = {
        claim_id
        for values in selection["training_claim_ids"].values()
        for claim_id in values
    }
    development_ids = {
        claim_id
        for values in selection["development_claim_ids"].values()
        for claim_id in values
    }
    consumed_ids = {
        claim_id for values in v9["selected_claim_ids"].values() for claim_id in values
    }
    assert {
        label: len(values) for label, values in selection["training_claim_ids"].items()
    } == {label: 75 for label in LABELS}
    assert {
        label: len(values)
        for label, values in selection["development_claim_ids"].items()
    } == {label: 15 for label in LABELS}
    assert not (training_ids & development_ids)
    assert not ((training_ids | development_ids) & consumed_ids)
    assert audit["checks"]["training_development_exact_evidence_disjoint"] is True
    assert (
        audit["holdout_boundary"]["future_confirmation_must_use_a_different_dataset"]
        is True
    )
    assert manifest["selection_sha256"] == _canonical(selection)
    assert manifest["audit_sha256"] == _canonical(audit)
    assert manifest["model_outputs_accessed"] is False
    assert selection["source_text_included"] is False
    assert not (V10 / "v10_climate_training.json").exists()
    assert not (V10 / "v10_climate_development.json").exists()
