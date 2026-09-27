from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from benchmarks.requirement_alignment import build_v13_independent
from benchmarks.requirement_alignment.analyze_v13_independent import analyze
from benchmarks.requirement_alignment.build_v13_independent import LABELS, build


ROOT = Path(__file__).resolve().parents[2]
V13 = ROOT / "benchmarks" / "requirement_alignment"


def _pack(split: str, suffix: str) -> dict[str, object]:
    cases = []
    for label in LABELS:
        for index in range(25):
            cases.append(
                {
                    "id": f"{suffix}-{label}-{index}",
                    "dataset": "fixture",
                    "label_scope": "fixture",
                    "source_split": split,
                    "query": "",
                    "claim": f"{suffix} {label} claim {index}",
                    "contexts": [
                        {
                            "id": f"{suffix}-{label}-{index}-evidence",
                            "text": f"{suffix} {label} evidence {index}.",
                        }
                    ],
                    "expected_verdict": label,
                }
            )
    return {
        "split": split,
        "predictions_used_for_selection": False,
        "cases": cases,
    }


def test_v13_builder_freezes_disjoint_label_blind_splits(tmp_path, monkeypatch) -> None:
    development_path = tmp_path / "development.json"
    heldout_path = tmp_path / "heldout.json"
    development_path.write_text(json.dumps(_pack("development", "dev")))
    heldout_path.write_text(json.dumps(_pack("heldout", "held")))
    monkeypatch.setitem(
        build_v13_independent.SOURCE_HASHES,
        "development",
        hashlib.sha256(development_path.read_bytes()).hexdigest(),
    )
    monkeypatch.setitem(
        build_v13_independent.SOURCE_HASHES,
        "heldout",
        hashlib.sha256(heldout_path.read_bytes()).hexdigest(),
    )

    development, heldout, audit, manifest = build(development_path, heldout_path)

    assert len(development["examples"]) == len(heldout["examples"]) == 125
    assert audit["checks"]["normalized_selected_inputs_disjoint"] is True
    assert audit["checks"]["labels_absent_from_model_inputs"] is True
    assert audit["checks"]["heldout_predictions_used_for_selection"] is False
    assert manifest["status"] == "heldout_frozen_before_v13_relation_scoring"
    assert all("verdict" not in row["input"] for row in heldout["examples"])


def test_v13_analysis_counts_unsafe_false_supports() -> None:
    examples = []
    score_rows = []
    for index, label in enumerate(LABELS):
        case_id = f"case-{index}"
        examples.append(
            {
                "id": case_id,
                "input": {
                    "query": "",
                    "claim": case_id,
                    "evidence": [{"id": "e", "text": "evidence"}],
                },
                "target": {"verdict": label},
                "source": {"dataset": "fixture"},
            }
        )
        score_rows.append(
            {
                "case_id": case_id,
                "per_evidence": [
                    {
                        "probabilities": {
                            "entailment": 0.9,
                            "contradiction": 0.05,
                            "neutral": 0.05,
                        }
                    }
                ],
            }
        )

    def dataset(split: str) -> dict[str, object]:
        return {"split": split, "examples": examples}

    def scores(split: str, data: dict[str, object]) -> dict[str, object]:
        from benchmarks.requirement_alignment.build_v13_independent import _sha256_json

        return {
            "split": split,
            "dataset_sha256": _sha256_json(data),
            "evaluation_labels_sent": False,
            "remote_inference_used": False,
            "evidence_spans": 5,
            "latency": {},
            "rows": score_rows,
        }

    dev = dataset("external_fiveway_v13_development")
    held = dataset("external_fiveway_v13_heldout")
    from benchmarks.requirement_alignment.build_v13_independent import _sha256_json

    report = analyze(
        dev,
        scores("external_fiveway_v13_development", dev),
        held,
        scores("external_fiveway_v13_heldout", held),
        {
            "selection": {
                "selected": {
                    "epoch": 2,
                    "direct_four_way": {
                        "entailment_minimum": 0.5,
                        "contradiction_minimum": 0.5,
                    },
                }
            }
        },
        {
            "dataset_sha256": {
                "development": _sha256_json(dev),
                "heldout": _sha256_json(held),
            }
        },
    )

    safety = report["results"]["heldout"]["safety"]
    assert safety["support_recall"] == 1.0
    assert safety["false_supports"] == 4
    assert safety["unsupported_incorrectly_supported"] == 1
    assert safety["contradiction_false_supports"] == 1
    assert report["heldout_promotion_gates"]["all_met"] is False


def test_committed_v13_transfer_result_rejects_v11() -> None:
    audit = json.loads((V13 / "v13_independent_audit.json").read_text())
    manifest = json.loads((V13 / "v13_independent_manifest.json").read_text())
    report = json.loads((V13 / "results" / "v13_independent_transfer.json").read_text())

    assert audit["counts"]["development"]["cases"] == 125
    assert audit["counts"]["heldout"]["cases"] == 125
    assert audit["checks"]["labels_absent_from_model_inputs"] is True
    assert manifest["heldout_labels_used_for_policy_selection"] is False
    assert report["results"]["heldout"]["safety"][
        "false_support_rate"
    ] == pytest.approx(0.45)
    assert report["results"]["heldout"]["safety"]["contradiction_false_supports"] == 11
    assert (
        report["results"]["heldout"]["safety"]["unsupported_incorrectly_supported"] == 5
    )
    assert report["heldout_promotion_gates"]["all_met"] is False
    assert report["decision"] == "do_not_promote_v11"
    assert report["remote_inference_used"] is False
    assert report["stable_defaults_changed"] is False
