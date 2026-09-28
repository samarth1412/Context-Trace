"""Run the frozen V18 candidate once on the frozen V19 confirmation set."""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path
from typing import Any

from benchmarks.requirement_alignment.v14_fiveway_policy import (
    LABELS,
    _sha256_json,
    policy_metrics,
)
from benchmarks.requirement_alignment.v18_candidate import (
    load_frozen_candidate,
    predict_candidate,
)


EXPERIMENT = "contexttrace_v19_untouched_confirmation"
SPLIT = "external_fiveway_v19_confirmation"
BOOTSTRAP_SEED = 20260927
BOOTSTRAP_SAMPLES = 10_000


class V19EvaluationError(RuntimeError):
    """Raised when the one-shot V19 confirmation contract is violated."""


def evaluate(
    dataset: dict[str, Any],
    freeze_manifest: dict[str, Any],
    candidate_manifest: dict[str, Any],
    relation_scores: dict[str, Any],
    atomic_scores: dict[str, Any],
    multispan_scores: dict[str, Any],
    bundle: dict[str, Any],
) -> dict[str, Any]:
    _preflight(
        dataset,
        freeze_manifest,
        candidate_manifest,
        relation_scores,
        atomic_scores,
        multispan_scores,
    )
    prediction_rows = predict_candidate(
        bundle, dataset, relation_scores, atomic_scores, multispan_scores
    )
    examples = {str(row["id"]): row for row in dataset["examples"]}
    targets = [
        str(examples[row["case_id"]]["target"]["verdict"]) for row in prediction_rows
    ]
    v15_predictions = [str(row["v15_prediction"]) for row in prediction_rows]
    predictions = [str(row["prediction"]) for row in prediction_rows]
    v15_metrics = policy_metrics(targets, v15_predictions)
    metrics = policy_metrics(targets, predictions)
    promoted = [
        (row, target)
        for row, target in zip(prediction_rows, targets, strict=True)
        if row["prediction"] == "supported" and row["v15_prediction"] != "supported"
    ]
    correct_promotions = sum(target == "supported" for _, target in promoted)
    rows = [
        {
            **row,
            "expected_verdict": target,
            "dataset": str(examples[row["case_id"]]["source"]["dataset"]),
        }
        for row, target in zip(prediction_rows, targets, strict=True)
    ]
    return {
        "schema_version": "contexttrace-v19-confirmation-result-1.0",
        "experiment": EXPERIMENT,
        "status": "confirmation_passed"
        if metrics["gates"]["all_met"]
        else "confirmation_failed",
        "protocol": {
            "evaluation_split": SPLIT,
            "candidate_frozen_before_dataset": True,
            "dataset_frozen_before_scoring": True,
            "one_shot_evaluation": True,
            "retraining_performed": False,
            "threshold_or_policy_changes": False,
            "case_removal_after_prediction": False,
            "evaluation_labels_in_model_inputs": False,
            "model_outputs_used_for_case_selection": False,
        },
        "inputs": {
            "cases": len(rows),
            "dataset_sha256": _sha256_json(dataset),
            "freeze_manifest_sha256": _sha256_json(freeze_manifest),
            "candidate_manifest_sha256": _sha256_json(candidate_manifest),
            "candidate_artifact_sha256": candidate_manifest["artifact"]["sha256"],
            "relation_rows_sha256": _rows_hash(relation_scores),
            "atomic_rows_sha256": _rows_hash(atomic_scores),
            "multispan_rows_sha256": _rows_hash(multispan_scores),
            "model_id": relation_scores["model"]["model_id"],
            "relation_evidence_spans": relation_scores["evidence_spans"],
            "atomic_requirements": atomic_scores["requirements"],
            "multispan_requirements": multispan_scores["requirements"],
            "evidence_combinations": multispan_scores["combinations"],
        },
        "frozen_policy": candidate_manifest["candidate"],
        "v15_baseline_metrics": v15_metrics,
        "metrics": metrics,
        "confidence_intervals_95": _stratified_bootstrap(rows),
        "rescue": {
            "promotions": len(promoted),
            "correct_promotions": correct_promotions,
            "promotion_precision": round(correct_promotions / len(promoted), 4)
            if promoted
            else 0.0,
            "promoted_case_ids": [row["case_id"] for row, _ in promoted],
        },
        "decision": (
            "confirmation_passed_candidate_eligible_for_packaging_review"
            if metrics["gates"]["all_met"]
            else "confirmation_failed_do_not_package_or_release"
        ),
        "rows": rows,
        "remote_inference_used": False,
        "stable_defaults_changed": False,
        "remote_provider_default_enabled": False,
        "local_only_network_calls": 0,
    }


def _preflight(
    dataset: dict[str, Any],
    freeze_manifest: dict[str, Any],
    candidate_manifest: dict[str, Any],
    relation_scores: dict[str, Any],
    atomic_scores: dict[str, Any],
    multispan_scores: dict[str, Any],
) -> None:
    if dataset.get("split") != SPLIT or not dataset.get("examples"):
        raise V19EvaluationError("V19 confirmation dataset is empty or invalid.")
    if freeze_manifest.get("status") != "frozen_before_v18_candidate_scoring":
        raise V19EvaluationError("V19 dataset was not frozen before scoring.")
    if freeze_manifest.get("dataset_sha256") != _sha256_json(dataset):
        raise V19EvaluationError("V19 dataset does not match its freeze manifest.")
    if freeze_manifest.get("v18_artifact_sha256") != candidate_manifest.get(
        "artifact", {}
    ).get("sha256"):
        raise V19EvaluationError("V19 is not bound to this candidate artifact.")
    if candidate_manifest.get("status") != "frozen_before_new_confirmation_data_access":
        raise V19EvaluationError("V18 candidate manifest has an invalid freeze status.")
    if any(
        freeze_manifest.get(name) is not expected
        for name, expected in (
            ("candidate_or_policy_changed_after_v18", False),
            ("confirmation_predictions_generated", False),
            ("confirmation_predictions_inspected", False),
            ("confirmation_labels_used_for_selection", False),
            ("retraining_allowed", False),
        )
    ):
        raise V19EvaluationError("V19 freeze manifest permits post-freeze adaptation.")
    dataset_hash = _sha256_json(dataset)
    for artifact in (relation_scores, atomic_scores, multispan_scores):
        if (
            artifact.get("split") != SPLIT
            or artifact.get("dataset_sha256") != dataset_hash
            or artifact.get("remote_inference_used") is not False
        ):
            raise V19EvaluationError(
                "V19 score artifacts violate the frozen input contract."
            )
    if relation_scores.get("evaluation_labels_sent") is not False or any(
        artifact.get("input_contract", {}).get("evaluation_labels_sent") is not False
        for artifact in (atomic_scores, multispan_scores)
    ):
        raise V19EvaluationError("V19 score artifacts do not attest label isolation.")


def _stratified_bootstrap(rows: list[dict[str, Any]]) -> dict[str, Any]:
    grouped = {
        label: [row for row in rows if row["expected_verdict"] == label]
        for label in LABELS
    }
    if any(not values for values in grouped.values()):
        raise V19EvaluationError("Bootstrap requires every five-way verdict.")
    rng = random.Random(BOOTSTRAP_SEED)
    values: dict[str, list[float]] = {
        name: []
        for name in (
            "accuracy",
            "macro_f1",
            "support_recall",
            "false_support_rate",
            "partial_or_ambiguous_review_recall",
            "review_rate",
        )
    }
    for _ in range(BOOTSTRAP_SAMPLES):
        sample = [
            rng.choice(grouped[label])
            for label in LABELS
            for _ in range(len(grouped[label]))
        ]
        metrics = policy_metrics(
            [row["expected_verdict"] for row in sample],
            [row["prediction"] for row in sample],
        )
        for name in values:
            values[name].append(float(metrics[name]))
    return {
        "method": "label_stratified_percentile_bootstrap",
        "samples": BOOTSTRAP_SAMPLES,
        "seed": BOOTSTRAP_SEED,
        "intervals": {
            name: {
                "lower": round(_percentile(items, 0.025), 4),
                "upper": round(_percentile(items, 0.975), 4),
            }
            for name, items in values.items()
        },
    }


def _percentile(values: list[float], probability: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def _rows_hash(artifact: dict[str, Any]) -> str:
    return _sha256_json(
        [
            {key: value for key, value in row.items() if key != "latency_ms"}
            for row in artifact["rows"]
        ]
    )


def _load(path: str) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--freeze-manifest", required=True)
    parser.add_argument("--candidate-artifact", required=True)
    parser.add_argument("--candidate-manifest", required=True)
    parser.add_argument("--relation-scores", required=True)
    parser.add_argument("--atomic-scores", required=True)
    parser.add_argument("--multispan-scores", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    dataset = _load(args.dataset)
    freeze_manifest = _load(args.freeze_manifest)
    candidate_manifest = _load(args.candidate_manifest)
    bundle = load_frozen_candidate(args.candidate_artifact, args.candidate_manifest)
    report = evaluate(
        dataset,
        freeze_manifest,
        candidate_manifest,
        _load(args.relation_scores),
        _load(args.atomic_scores),
        _load(args.multispan_scores),
        bundle,
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "status": report["status"],
                "metrics": report["metrics"],
                "rescue": report["rescue"],
                "decision": report["decision"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
