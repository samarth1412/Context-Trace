from __future__ import annotations

import pytest

from benchmarks.requirement_alignment.build_v6_cascade_cases import build_v6_cases
from benchmarks.requirement_alignment.v6_cascade import V6CascadeError
from benchmarks.requirement_alignment.v6_cascade import build_jev_state
from benchmarks.requirement_alignment.v6_cascade import calibrate_policy
from benchmarks.requirement_alignment.v6_cascade import cascade_decision
from benchmarks.requirement_alignment.v6_cascade import enforce_remote_policy
from benchmarks.requirement_alignment.v6_cascade import evaluate_frozen_policy
from benchmarks.requirement_alignment.v6_cascade import local_route


def _payload(documents: int = 9) -> dict:
    labels = {
        "nda-1": {
            "hypothesis": "Reverse engineering is prohibited.",
            "short_description": "No reverse engineering",
        }
    }
    relations = ["Entailment", "Contradiction", "NotMentioned"]
    rows = []
    for index in range(documents):
        text = "Reverse engineering is prohibited. Disclosure may be allowed."
        split = text.index("Disclosure")
        relation = relations[index % len(relations)]
        rows.append(
            {
                "id": str(index),
                "text": text,
                "spans": [[0, split - 1], [split, len(text)]],
                "annotation_sets": [
                    {
                        "annotations": {
                            "nda-1": {
                                "choice": relation,
                                "spans": [] if relation == "NotMentioned" else [0],
                            }
                        }
                    }
                ],
            }
        )
    return {"labels": labels, "documents": rows}


def test_v6_cases_exclude_training_and_separate_policy_evaluation() -> None:
    training = {
        "examples": [
            {
                "id": "contractnli_train_0_nda-1",
                "source": {"dataset": "ContractNLI", "document_id": "0"},
            },
            {
                "id": "contractnli_train_1_nda-1",
                "source": {"dataset": "ContractNLI", "document_id": "1"},
            },
            {
                "id": "contractnli_train_2_nda-1",
                "source": {"dataset": "ContractNLI", "document_id": "2"},
            },
        ]
    }

    datasets, audit = build_v6_cases(
        _payload(), training, cases_per_relation_per_split=1
    )

    calibration = datasets["cascade_calibration"]["examples"]
    evaluation = datasets["cascade_evaluation"]["examples"]
    calibration_ids = {row["id"] for row in calibration}
    evaluation_ids = {row["id"] for row in evaluation}
    assert len(calibration) == len(evaluation) == 3
    assert calibration_ids.isdisjoint(evaluation_ids)
    assert not (calibration_ids | evaluation_ids) & {
        "contractnli_train_0_nda-1",
        "contractnli_train_1_nda-1",
        "contractnli_train_2_nda-1",
    }
    assert audit["integrity"]["targets_absent_from_model_inputs"] is True
    assert all("target" not in row["input"] for row in calibration + evaluation)


def test_jev_state_contains_only_claim_and_selected_evidence() -> None:
    example = {
        "input": {
            "claim": "Reverse engineering is prohibited.",
            "evidence": [{"id": "span-1", "text": "No reverse engineering."}],
        },
        "target": {"label": "covered"},
        "source": {"relation": "Entailment"},
    }

    state = build_jev_state(example)

    assert state == {
        "claim": "Reverse engineering is prohibited.",
        "selected_evidence": [{"id": "span-1", "text": "No reverse engineering."}],
    }
    assert "target" not in str(state)
    assert "relation" not in str(state)


def test_local_route_requires_agreement_and_abstains_on_uncertainty() -> None:
    policy = {
        "local_missing_threshold": 0.2,
        "local_supported_threshold": 0.9,
        "jev_supported_probability": 0.8,
        "review_confidence": 0.8,
    }

    assert local_route(_predictions(0.95, 0.91), policy) == "supported"
    assert local_route(_predictions(0.05, 0.20), policy) == "missing"
    assert local_route(_predictions(0.95, 0.30), policy) == "route"
    local_only = cascade_decision(
        _predictions(0.95, 0.30), policy=policy, jev=None
    )
    assert local_only["verdict"] == "abstain"
    assert local_only["remote_called"] is False


def test_local_only_blocks_jev_even_with_remote_flag() -> None:
    with pytest.raises(V6CascadeError, match="local_only"):
        enforce_remote_policy(local_only=True, allow_remote=True)

    with pytest.raises(V6CascadeError, match="explicit --allow-remote"):
        enforce_remote_policy(local_only=False, allow_remote=False)


def test_calibration_freezes_policy_before_disjoint_evaluation() -> None:
    calibration, calibration_local, calibration_jev = _experiment_payloads(
        "cascade_calibration", all_jev=True
    )
    policy, analysis = calibrate_policy(
        calibration, calibration_local, calibration_jev
    )

    assert policy["selection_split"] == "cascade_calibration"
    assert policy["evaluation_used_for_selection"] is False
    assert analysis["selected"]["promotion_gates_met"] is True

    evaluation, evaluation_local, evaluation_jev_all = _experiment_payloads(
        "cascade_evaluation", all_jev=True
    )
    routed = {
        row["case_id"]
        for row in evaluation_local["rows"]
        if local_route(row["predictions"], policy["policy"]) == "route"
    }
    evaluation_jev = {
        **evaluation_jev_all,
        "rows": [
            row for row in evaluation_jev_all["rows"] if row["case_id"] in routed
        ],
        "routed_case_ids": sorted(routed),
        "all_cases_requested": len(routed),
        "completed": len(routed),
    }
    result = evaluate_frozen_policy(
        evaluation, evaluation_local, evaluation_jev, policy
    )

    assert result["evaluation_gates_met"] is True
    assert result["local_only"]["network_calls"] == 0
    assert result["optional_jev"]["metrics"]["false_positive_rate"] == 0.0


def _predictions(v3: float, v5: float) -> dict:
    return {
        "v3": {"entailment_probability": v3},
        "v5": {"entailment_probability": v5},
    }


def _experiment_payloads(split: str, *, all_jev: bool) -> tuple[dict, dict, dict]:
    examples = []
    local_rows = []
    jev_rows = []
    values = [
        ("p1", "covered", "Entailment", 0.6, 0.6, "supported", 0.95),
        ("p2", "covered", "Entailment", 0.7, 0.7, "supported", 0.96),
        ("n1", "missing", "Contradiction", 0.1, 0.1, "contradicted", 0.02),
        ("n2", "missing", "Contradiction", 0.1, 0.1, "contradicted", 0.02),
        ("n3", "missing", "NotMentioned", 0.1, 0.1, "unsupported", 0.03),
        ("n4", "missing", "NotMentioned", 0.1, 0.1, "unsupported", 0.03),
    ]
    for case_id, target, relation, v3, v5, verdict, supported_probability in values:
        examples.append(
            {
                "id": "%s-%s" % (split, case_id),
                "split": split,
                "input": {"claim": case_id, "evidence": [{"id": case_id, "text": case_id}]},
                "target": {"label": target},
                "source": {"relation": relation},
            }
        )
        local_rows.append(
            {
                "case_id": "%s-%s" % (split, case_id),
                "predictions": _predictions(v3, v5),
            }
        )
        jev_rows.append(
            {
                "case_id": "%s-%s" % (split, case_id),
                "prediction": {
                    "verdict": verdict,
                    "probabilities": {
                        "supported": supported_probability,
                        "partially_supported": 0.01,
                        "unsupported": 0.01,
                        "contradicted": 0.01,
                        "unverifiable": 0.01,
                    },
                    "confidence": 0.95,
                    "latency_ms": 10.0,
                    "usage": {"input_tokens": 10, "output_tokens": 2, "total_tokens": 12},
                },
            }
        )
    dataset = {"examples": examples}
    local = {"split": split, "rows": local_rows}
    jev = {
        "split": split,
        "complete": True,
        "rows": jev_rows if all_jev else [],
    }
    return dataset, local, jev
