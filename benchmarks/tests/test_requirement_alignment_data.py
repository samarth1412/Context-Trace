from __future__ import annotations

import hashlib

from benchmarks.requirement_alignment.build import build_dataset
from benchmarks.requirement_alignment.build import requirement_spans


def _row(case_id: str, label: str, claim: str, groups: list[list[int]]) -> dict:
    return {
        "label": label,
        "claim": claim,
        "supporting_sentences": groups,
        "evidence": [
            "The system provides daily backups.",
            "It supports encryption at rest.",
            "The unrelated service has a dashboard.",
        ],
        "meta": {"id": case_id},
    }


def test_requirement_spans_are_exact_claim_slices() -> None:
    claim = "The system provides backups and supports encryption."

    rows = requirement_spans(claim)

    assert [row["text"] for row in rows] == [
        "The system provides backups",
        "supports encryption.",
    ]
    assert all(claim[row["start_char"] : row["end_char"]] == row["text"] for row in rows)


def test_builder_separates_targets_from_inputs_and_creates_hard_negatives() -> None:
    rows = [
        _row(
            "train-supported",
            "supported",
            "The system provides backups and supports encryption.",
            [[0, 1]],
        ),
        _row(
            "train-partial",
            "partially_supported",
            "The system provides backups and has worldwide offices.",
            [[0]],
        ),
    ]

    dataset, audit = build_dataset(rows, validation_fraction=0.2)

    constructions = {row["source"]["construction"] for row in dataset["examples"]}
    assert {
        "gold_complete_group",
        "gold_partial_group",
        "same_document_hard_negative",
        "synthetic_drop_one",
    } <= constructions
    assert audit["valid"] is True
    assert audit["integrity"]["training_targets_absent_from_model_inputs"] is True
    assert all("label" not in row["input"] for row in dataset["examples"])


def test_builder_excludes_evaluation_claims_before_splitting() -> None:
    rows = [
        _row("train-a", "supported", "A system provides daily backups.", [[0]]),
        _row("train-b", "partially_supported", "A system has worldwide offices.", [[0]]),
    ]
    excluded = hashlib.sha256(
        "a system provides daily backups.".encode("utf-8")
    ).hexdigest()
    excluded_dataset, excluded_audit = build_dataset(
        rows,
        excluded_claims={excluded},
        validation_fraction=0.2,
    )

    assert excluded_dataset["examples"]
    assert excluded_audit["exclusions"]["evaluation_claim_overlap"] == 1
    assert excluded_audit["integrity"]["evaluation_claim_overlap"] == []
