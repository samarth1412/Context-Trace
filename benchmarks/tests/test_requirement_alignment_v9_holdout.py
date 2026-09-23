from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

from benchmarks.requirement_alignment import v9_holdout
from benchmarks.requirement_alignment.v9_holdout import evaluate_holdout, route_holdout


ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "benchmarks" / "requirement_alignment" / "results"


def _dataset() -> dict[str, object]:
    examples = []
    specifications = (
        ("Entailment", "covered"),
        ("Contradiction", "missing"),
        ("NotMentioned", "missing"),
        ("Disputed", "review"),
    )
    for relation, target in specifications:
        for index in range(60):
            claim = f"Claim {relation} {index}."
            examples.append(
                {
                    "id": f"case_{relation}_{index}",
                    "split": v9_holdout.SPLIT,
                    "input": {
                        "claim": claim,
                        "requirement": {"id": "r00", "text": claim},
                        "evidence": [{"id": "e1", "text": claim}],
                    },
                    "target": {"label": target},
                    "source": {"relation": relation},
                }
            )
    return {"split": v9_holdout.SPLIT, "examples": examples}


def _probabilities(entailment: float) -> dict[str, float]:
    return {
        "entailment": entailment,
        "contradiction": 0.01,
        "neutral": 0.99 - entailment,
    }


def _scores(dataset: dict[str, object]) -> tuple[dict[str, object], dict[str, object]]:
    local_rows = []
    auxiliary_rows = []
    for example in dataset["examples"]:
        relation = example["source"]["relation"]
        entailment = 0.90 if relation == "Entailment" else 0.40
        probabilities = _probabilities(entailment)
        local_rows.append(
            {
                "case_id": example["id"],
                "predictions": {
                    "v3": {"probabilities": probabilities},
                    "v5": {"probabilities": probabilities},
                },
            }
        )
        auxiliary_rows.append(
            {
                "case_id": example["id"],
                "input_sha256": "input",
                "pinned_nli_group": _probabilities(0.40),
                "per_evidence": [
                    {
                        "v3": probabilities,
                        "v5": probabilities,
                        "pinned_nli": _probabilities(0.40),
                    }
                ],
            }
        )
    common = {"split": v9_holdout.SPLIT, "remote_inference_used": False}
    return (
        {**common, "rows": local_rows},
        {**common, "evaluation_labels_sent": False, "rows": auxiliary_rows},
    )


def _canonical(value: object) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def test_routing_does_not_use_evaluation_labels(monkeypatch) -> None:
    dataset = _dataset()
    local, auxiliary = _scores(dataset)
    v8 = json.loads((RESULTS / "v8_scifact_guard_policy.json").read_text())
    v9 = json.loads((RESULTS / "v9_scifact_router_policy.json").read_text())
    monkeypatch.setattr(v9_holdout, "EXPECTED_DATASET_SHA256", _canonical(dataset))
    original = route_holdout(dataset, local, auxiliary, v8, v9)

    changed = copy.deepcopy(dataset)
    for example in changed["examples"]:
        example["target"]["label"] = "covered"
        example["source"]["relation"] = "Entailment"
    monkeypatch.setattr(v9_holdout, "EXPECTED_DATASET_SHA256", _canonical(changed))
    relabeled = route_holdout(changed, local, auxiliary, v8, v9)

    assert [row["route"] for row in original["rows"]] == [
        row["route"] for row in relabeled["rows"]
    ]
    assert original["evaluation_labels_used_for_routing"] is False
    assert original["local_only_network_calls"] == 0


def test_disputed_gate_blocks_release_when_review_coverage_is_low(monkeypatch) -> None:
    dataset = _dataset()
    monkeypatch.setattr(v9_holdout, "EXPECTED_DATASET_SHA256", _canonical(dataset))
    routes = {
        "split": v9_holdout.SPLIT,
        "dataset_sha256": _canonical(dataset),
        "policy_id": v9_holdout.EXPECTED_POLICY_ID,
        "evaluation_labels_used_for_routing": False,
        "routed_case_ids": [],
        "rows": [
            {
                "case_id": example["id"],
                "base_route": (
                    "supported"
                    if example["source"]["relation"] == "Entailment"
                    else "missing"
                ),
                "route": (
                    "supported"
                    if example["source"]["relation"] == "Entailment"
                    else "missing"
                ),
            }
            for example in dataset["examples"]
        ],
    }
    jev = {"complete": True, "rows": []}

    result = evaluate_holdout(dataset, routes, jev)

    assert result["primary_binary"]["gates"]["all_met"] is True
    assert result["disputed_challenge"]["review_or_abstain_coverage"] == 0.0
    assert result["disputed_challenge"]["gates"]["all_met"] is False
    assert result["release_gates_met"] is False
    assert result["stable_defaults_changed"] is False


def test_committed_holdout_result_records_failed_fresh_confirmation() -> None:
    result = json.loads((RESULTS / "v9_climate_fever_holdout.json").read_text())
    manifest = json.loads(
        (RESULTS / "v9_climate_fever_result_manifest.json").read_text()
    )

    assert result["dataset_sha256"] == v9_holdout.EXPECTED_DATASET_SHA256
    assert result["policy_id"] == v9_holdout.EXPECTED_POLICY_ID
    assert result["evaluation_used_for_selection"] is False
    assert result["eligible_as_fresh_release_evidence"] is True
    assert result["primary_binary"]["metrics"]["positive_recall"] == 0.1
    assert result["primary_binary"]["metrics"]["false_positive_rate"] == 0.0
    assert result["primary_binary"]["metrics"]["contradiction_false_support_count"] == 0
    assert result["primary_binary"]["operations"]["remote_calls"] == 12
    assert result["disputed_challenge"]["review_or_abstain_coverage"] == 0.0833
    assert result["release_gates_met"] is False
    assert result["stable_defaults_changed"] is False
    assert result["local_only_network_calls"] == 0
    assert result["all_cases_operations"]["resolved_models"] == {"jev-1.13.0": 17}
    assert manifest["status"] == "evaluated_once_release_gates_failed"
    assert manifest["holdout_consumed"] is True
    assert manifest["aggregate_result"]["sha256"] == _canonical(result)
    assert manifest["source_text_committed"] is False
