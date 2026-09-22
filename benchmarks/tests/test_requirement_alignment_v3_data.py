from __future__ import annotations

from benchmarks.requirement_alignment.build_v3_training import build_v3_training_data


def _contract_payload() -> dict:
    text = "Disclosure is permitted. Reverse engineering is prohibited."
    split = text.index("Reverse")
    documents = []
    for index, relation in enumerate(
        ["Entailment", "Contradiction", "NotMentioned"], start=1
    ):
        documents.append(
            {
                "id": index,
                "text": text,
                "spans": [[0, split - 1], [split, len(text)]],
                "annotation_sets": [
                    {
                        "annotations": {
                            "nda-1": {
                                "choice": relation,
                                "spans": [] if relation == "NotMentioned" else [1],
                            }
                        }
                    }
                ],
            }
        )
    return {
        "labels": {
            "nda-1": {
                "hypothesis": "Reverse engineering is prohibited.",
                "short_description": "No reverse engineering",
            }
        },
        "documents": documents,
    }


def _wice_payload() -> dict:
    def row(identifier: str, label: str) -> dict:
        return {
            "id": identifier,
            "split": "training",
            "task": "requirement_alignment",
            "input": {
                "claim": "The policy applies.",
                "requirement": {
                    "id": "r00",
                    "text": "The policy applies.",
                    "start_char": 0,
                    "end_char": 19,
                },
                "evidence": [{"id": "e1", "text": "The policy applies."}],
            },
            "target": {"label": label},
            "source": {"dataset": "WiCE", "source_split": "train"},
        }

    return {"examples": [row("positive", "covered"), row("negative", "missing")]}


def test_v3_builder_preserves_three_relations_and_maps_wice() -> None:
    dataset, audit = build_v3_training_data(
        _contract_payload(), _wice_payload(), cases_per_relation=1
    )

    assert audit["valid"] is True
    assert audit["source_counts"] == {"ContractNLI": 3, "WiCE": 2}
    assert audit["relation_counts"] == {
        "contradiction": 1,
        "entailment": 2,
        "neutral": 2,
    }
    assert all(row["split"] == "training" for row in dataset["examples"])


def test_v3_builder_uses_no_contract_development_or_test_cases() -> None:
    dataset, audit = build_v3_training_data(
        _contract_payload(), _wice_payload(), cases_per_relation=1
    )

    contract_rows = [
        row for row in dataset["examples"] if row["source"]["dataset"] == "ContractNLI"
    ]
    assert {row["source"]["source_split"] for row in contract_rows} == {"train"}
    assert audit["integrity"]["contract_development_or_test_used"] is False
    assert all("target" not in row["input"] for row in dataset["examples"])
