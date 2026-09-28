from __future__ import annotations

import json
from pathlib import Path

from benchmarks.requirement_alignment.build_v19_confirmation import (
    AVERITEC_SHA256,
    V18_ARTIFACT_SHA256,
    WICE_SHA256,
    _averitec_candidates,
    _prior_examples,
)


ROOT = Path(__file__).resolve().parents[2]
V19 = ROOT / "benchmarks" / "requirement_alignment"


def test_v19_averitec_adapter_uses_qa_evidence_without_justification(
    tmp_path: Path,
) -> None:
    source = tmp_path / "averitec.json"
    source.write_text(
        json.dumps(
            [
                {
                    "claim": "The policy started in 2020.",
                    "label": "Supported",
                    "justification": "This label-bearing rationale must stay out.",
                    "questions": [
                        {
                            "question": "When did the policy start?",
                            "answers": [
                                {
                                    "answer": "It started in 2020.",
                                    "boolean_explanation": "",
                                }
                            ],
                        }
                    ],
                }
            ]
        ),
        encoding="utf-8",
    )

    rows = _averitec_candidates(source)

    assert len(rows) == 1
    assert rows[0]["expected_verdict"] == "supported"
    assert rows[0]["contexts"] == [
        {
            "id": "averitec_dev_0000_q000_a000",
            "text": "Question: When did the policy start?\nAnswer: It started in 2020.",
        }
    ]
    assert "justification" not in json.dumps(rows)


def test_v19_prior_scan_collects_ids_and_normalized_claims(tmp_path: Path) -> None:
    benchmark = tmp_path / "benchmarks" / "prior"
    benchmark.mkdir(parents=True)
    (benchmark / "cases.json").write_text(
        json.dumps(
            {
                "cases": [
                    {"id": "prior-1", "claim": "  A Prior   Claim. "},
                ]
            }
        ),
        encoding="utf-8",
    )

    ids, claims, sources = _prior_examples(tmp_path, [])

    assert ids == {"prior-1"}
    assert claims == {"a prior claim."}
    assert sources[0]["claims"] == 1


def test_committed_v19_pack_is_frozen_balanced_and_disjoint() -> None:
    audit = json.loads((V19 / "v19_confirmation_audit.json").read_text())
    manifest = json.loads((V19 / "v19_confirmation_manifest.json").read_text())

    assert audit["valid"] is True
    assert audit["sources"]["averitec"]["sha256"] == AVERITEC_SHA256
    assert audit["sources"]["wice"]["sha256"] == WICE_SHA256
    assert audit["counts"]["cases"] == 125
    assert audit["counts"]["labels"] == {
        "contradicted": 25,
        "partially_supported": 25,
        "supported": 25,
        "unsupported": 25,
        "unverifiable": 25,
    }
    assert audit["counts"]["datasets"] == {"AVeriTeC": 100, "WiCE": 25}
    assert all(
        value
        for key, value in audit["checks"].items()
        if key != "predictions_used_for_selection"
    )
    assert audit["checks"]["predictions_used_for_selection"] is False
    assert manifest["status"] == "frozen_before_v18_candidate_scoring"
    assert (
        manifest["dataset_sha256"]
        == "2fa52ad909c62cee9b610191aea89d5ab74523446a411070c0a96c387f36050c"
    )
    assert manifest["v18_artifact_sha256"] == V18_ARTIFACT_SHA256
    assert manifest["candidate_or_policy_changed_after_v18"] is False
    assert manifest["confirmation_predictions_generated"] is False
    assert manifest["confirmation_predictions_inspected"] is False
    assert manifest["confirmation_labels_used_for_selection"] is False
    assert manifest["retraining_allowed"] is False
