from __future__ import annotations

import json
from pathlib import Path

from benchmarks.requirement_alignment.build_v21_development import (
    AVERITEC_TRAIN_SHA256,
    SPLIT,
    _averitec_train_candidates,
)
from benchmarks.requirement_alignment.score_v13_relations import SPLITS
from benchmarks.requirement_alignment.score_v15_atomic import (
    ALLOWED_SPLITS as V15_SPLITS,
)
from benchmarks.requirement_alignment.score_v17_multispan import (
    ALLOWED_SPLITS as V17_SPLITS,
)


ROOT = Path(__file__).resolve().parents[2]
V21 = ROOT / "benchmarks" / "requirement_alignment"


def test_v21_averitec_adapter_uses_qa_content_without_justification(
    tmp_path: Path,
) -> None:
    source = tmp_path / "train.json"
    source.write_text(
        json.dumps(
            [
                {
                    "claim": "The program began in 2021.",
                    "label": "Supported",
                    "justification": "Label-bearing rationale must stay out.",
                    "questions": [
                        {
                            "question": "When did it begin?",
                            "answers": [
                                {
                                    "answer": "It began in 2021.",
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

    rows = _averitec_train_candidates(source)

    assert rows[0]["id"] == "averitec_train_0000"
    assert rows[0]["source_split"] == "train"
    assert rows[0]["expected_verdict"] == "supported"
    assert rows[0]["contexts"] == [
        {
            "id": "averitec_train_0000_q000_a000",
            "text": "Question: When did it begin?\nAnswer: It began in 2021.",
        }
    ]
    assert "justification" not in json.dumps(rows)


def test_v21_scorers_accept_the_development_split() -> None:
    assert SPLIT in SPLITS
    assert SPLIT in V15_SPLITS
    assert SPLIT in V17_SPLITS


def test_committed_v21_development_set_is_balanced_and_disjoint() -> None:
    audit = json.loads((V21 / "v21_development_audit.json").read_text())
    manifest = json.loads((V21 / "v21_development_manifest.json").read_text())

    assert audit["valid"] is True
    assert audit["sources"]["averitec"]["sha256"] == AVERITEC_TRAIN_SHA256
    assert audit["counts"] == {
        "cases": 500,
        "datasets": {"AVeriTeC": 400, "WiCE": 100},
        "labels": {
            "contradicted": 100,
            "partially_supported": 100,
            "supported": 100,
            "unsupported": 100,
            "unverifiable": 100,
        },
        "selected_evidence_spans": 2624,
    }
    assert all(
        value
        for key, value in audit["checks"].items()
        if key
        not in {"model_outputs_used_for_selection", "future_confirmation_data_accessed"}
    )
    assert audit["checks"]["model_outputs_used_for_selection"] is False
    assert audit["checks"]["future_confirmation_data_accessed"] is False
    assert manifest["status"] == "development_only_not_confirmation"
    assert manifest["dataset_sha256"] == (
        "b9422ebb87ee69c13e1e52a2244210177fa7affafa73f63db3a0a68bb3b2ea70"
    )
    assert manifest["labels_may_be_used_for_training"] is True
    assert manifest["future_confirmation_data_accessed"] is False
    assert manifest["stable_defaults_changed"] is False
