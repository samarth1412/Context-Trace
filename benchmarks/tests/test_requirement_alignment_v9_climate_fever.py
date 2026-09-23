from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from benchmarks.requirement_alignment import build_v9_climate_fever
from benchmarks.requirement_alignment.build_v9_climate_fever import V9BuildError
from benchmarks.requirement_alignment.build_v9_climate_fever import build


ROOT = Path(__file__).resolve().parents[2]
V9 = ROOT / "benchmarks" / "requirement_alignment"


def _evidence(label: str, prefix: str) -> list[dict[str, object]]:
    rows = []
    for index in range(5):
        evidence_label = label if index == 0 else "NOT_ENOUGH_INFO"
        rows.append(
            {
                "evidence_id": "%s:%d" % (prefix, index),
                "evidence_label": evidence_label,
                "article": "%s article" % prefix,
                "evidence": "%s evidence %d." % (prefix, index),
                "entropy": 0.0,
                "votes": [evidence_label, evidence_label],
            }
        )
    return rows


def _source_rows() -> list[dict[str, object]]:
    disputed = _evidence("SUPPORTS", "disputed")
    disputed[1]["evidence_label"] = "REFUTES"
    disputed[1]["votes"] = ["REFUTES", "REFUTES"]
    return [
        {
            "claim_id": "1",
            "claim": "The observation supports the claim.",
            "claim_label": "SUPPORTS",
            "evidences": _evidence("SUPPORTS", "support"),
        },
        {
            "claim_id": "2",
            "claim": "The observation contradicts the claim.",
            "claim_label": "REFUTES",
            "evidences": _evidence("REFUTES", "refute"),
        },
        {
            "claim_id": "3",
            "claim": "The observation is unrelated.",
            "claim_label": "NOT_ENOUGH_INFO",
            "evidences": _evidence("NOT_ENOUGH_INFO", "missing"),
        },
        {
            "claim_id": "4",
            "claim": "The evidence conflicts.",
            "claim_label": "DISPUTED",
            "evidences": disputed,
        },
    ]


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def _canonical_sha256(value: object) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def test_builder_freezes_balanced_four_way_holdout(tmp_path, monkeypatch) -> None:
    source = tmp_path / "climate-fever.jsonl"
    _write_jsonl(source, _source_rows())
    monkeypatch.setattr(
        build_v9_climate_fever,
        "DATASET_SHA256",
        hashlib.sha256(source.read_bytes()).hexdigest(),
    )

    evaluation, selection, audit, manifest = build(source, per_label=1)

    assert len(evaluation["examples"]) == 4
    assert audit["evaluation"]["claim_labels"] == {
        "DISPUTED": 1,
        "NOT_ENOUGH_INFO": 1,
        "REFUTES": 1,
        "SUPPORTS": 1,
    }
    assert audit["evaluation"]["targets"] == {
        "covered": 1,
        "missing": 2,
        "review": 1,
    }
    assert audit["checks"]["labels_absent_from_inputs"] is True
    assert audit["checks"]["model_outputs_used_for_selection"] is False
    assert audit["redistribution"]["source_text_committed"] is False
    assert selection["source_text_included"] is False
    assert manifest["status"] == "frozen_before_model_scoring"
    assert manifest["model_outputs_accessed"] is False
    for row in evaluation["examples"]:
        assert len(row["input"]["evidence"]) == 5
        assert not ({"label", "target", "relation"} & set(row["input"]))


def test_builder_rejects_inconsistent_macro_label(tmp_path, monkeypatch) -> None:
    rows = _source_rows()
    rows[0]["claim_label"] = "REFUTES"
    source = tmp_path / "climate-fever.jsonl"
    _write_jsonl(source, rows)
    monkeypatch.setattr(
        build_v9_climate_fever,
        "DATASET_SHA256",
        hashlib.sha256(source.read_bytes()).hexdigest(),
    )

    with pytest.raises(V9BuildError, match="inconsistent"):
        build(source, per_label=1)


def test_committed_holdout_protocol_is_frozen_without_source_text() -> None:
    selection = json.loads((V9 / "v9_climate_fever_selection.json").read_text())
    audit = json.loads((V9 / "v9_climate_fever_audit.json").read_text())
    manifest = json.loads((V9 / "v9_climate_fever_manifest.json").read_text())

    selected = selection["selected_claim_ids"]
    assert {key: len(value) for key, value in selected.items()} == {
        "DISPUTED": 60,
        "NOT_ENOUGH_INFO": 60,
        "REFUTES": 60,
        "SUPPORTS": 60,
    }
    assert len({value for values in selected.values() for value in values}) == 240
    assert selection["model_outputs_used"] is False
    assert selection["source_text_included"] is False
    assert audit["source_counts"]["claims"] == 1535
    assert audit["evaluation"]["cases"] == 240
    assert audit["evaluation"]["evidence_sentences"] == 1200
    assert audit["checks"]["v8_policy_frozen_before_evaluation"] is True
    assert audit["redistribution"]["source_text_committed"] is False
    assert manifest["status"] == "frozen_before_model_scoring"
    assert manifest["model_outputs_accessed"] is False
    assert manifest["evaluation_used_for_policy_selection"] is False
    assert manifest["stable_defaults_changed"] is False
    assert manifest["selection_sha256"] == _canonical_sha256(selection)
    assert manifest["audit_sha256"] == _canonical_sha256(audit)
    assert not (V9 / "v9_climate_fever_evaluation.json").exists()
