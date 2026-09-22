from __future__ import annotations

from benchmarks.requirement_alignment.build_development import build_development_set


def _payload() -> dict:
    text = "The recipient may disclose information. Reverse engineering is prohibited."
    split = text.index("Reverse")
    spans = [[0, split - 1], [split, len(text)]]
    documents = []
    relations = ["Entailment", "Contradiction", "NotMentioned"]
    for index, relation in enumerate(relations, start=1):
        documents.append(
            {
                "id": index,
                "text": text,
                "spans": spans,
                "annotation_sets": [
                    {
                        "annotations": {
                            "nda-1": {
                                "choice": relation,
                                "spans": [] if relation == "NotMentioned" else [index % 2],
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


def test_builds_balanced_direct_requirement_examples() -> None:
    dataset, audit = build_development_set(_payload(), cases_per_relation=1)

    assert audit["valid"] is True
    assert audit["relation_counts"] == {
        "Contradiction": 1,
        "Entailment": 1,
        "NotMentioned": 1,
    }
    assert [row["target"]["label"] for row in dataset["examples"]].count(
        "covered"
    ) == 1
    assert all("relation" not in row["input"] for row in dataset["examples"])


def test_uses_annotated_spans_and_retrieves_only_when_no_span_exists() -> None:
    dataset, _ = build_development_set(_payload(), cases_per_relation=1)
    by_relation = {row["source"]["relation"]: row for row in dataset["examples"]}

    assert (
        by_relation["Entailment"]["source"]["evidence_selection"]
        == "upstream_annotated_spans"
    )
    assert by_relation["Entailment"]["source"]["evidence_span_indexes"] == [1]
    assert (
        by_relation["NotMentioned"]["source"]["evidence_selection"]
        == "deterministic_lexical_retrieval"
    )
    assert len(by_relation["NotMentioned"]["input"]["evidence"]) <= 3


def test_requirement_is_an_exact_claim_span() -> None:
    dataset, _ = build_development_set(_payload(), cases_per_relation=1)

    for row in dataset["examples"]:
        requirement = row["input"]["requirement"]
        assert row["input"]["claim"][
            requirement["start_char"] : requirement["end_char"]
        ] == requirement["text"]
