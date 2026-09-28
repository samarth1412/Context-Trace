"""Fuse atomic coverage with V14 using development-only out-of-fold predictions."""

from __future__ import annotations

import argparse
import json
import math
import statistics
from pathlib import Path
from typing import Any

from benchmarks.requirement_alignment.v14_fiveway_policy import (
    DEVELOPMENT_SPLIT,
    LABELS,
    SEED,
    THRESHOLDS,
    _folds,
    _sha256_json,
    feature_vector,
    policy_metrics,
)


EXPERIMENT = "contexttrace_v15_atomic_completeness"
TARGET_LABELS = {"supported", "partially_supported"}
RELATIONS = ("entailment", "contradiction", "neutral")


class V15CompletenessError(RuntimeError):
    """Raised when V15 violates its development-only completeness contract."""


def train_and_assess(
    development: dict[str, Any],
    relation_scores: dict[str, Any],
    v14_report: dict[str, Any],
    atomic_scores: dict[str, Any],
) -> dict[str, Any]:
    inputs = _aligned_inputs(development, relation_scores, v14_report, atomic_scores)
    targets = inputs["targets"]
    folds = _folds(targets)
    candidates = []
    probability_sets: dict[str, list[float]] = {}
    for feature_set_name, matrix, feature_names in _feature_sets(inputs):
        for estimator_name, estimator in _candidates():
            name = f"{feature_set_name}__{estimator_name}"
            probabilities = _out_of_fold_completeness(
                matrix, targets, folds, estimator=estimator
            )
            binary = _binary_metrics(targets, probabilities)
            policy = _select_policy(
                targets,
                inputs["v14_predictions"],
                inputs["v14_probabilities"],
                probabilities,
            )
            candidates.append(
                {
                    "candidate": name,
                    "feature_set": feature_set_name,
                    "feature_count": len(feature_names),
                    "estimator": estimator_name,
                    "binary_complete_support": binary,
                    "policy": {
                        key: value
                        for key, value in policy.items()
                        if key != "predictions"
                    },
                }
            )
            probability_sets[name] = probabilities
    selected = max(candidates, key=_candidate_key)
    selected_name = str(selected["candidate"])
    selected_policy = _select_policy(
        targets,
        inputs["v14_predictions"],
        inputs["v14_probabilities"],
        probability_sets[selected_name],
    )
    predictions = selected_policy.pop("predictions")
    metrics = selected_policy["metrics"]
    rows = [
        {
            "case_id": case_id,
            "expected_verdict": target,
            "v14_prediction": v14_prediction,
            "complete_support_probability": round(probability, 8),
            "prediction": prediction,
        }
        for case_id, target, v14_prediction, probability, prediction in zip(
            inputs["case_ids"],
            targets,
            inputs["v14_predictions"],
            probability_sets[selected_name],
            predictions,
            strict=True,
        )
    ]
    return {
        "schema_version": "contexttrace-v15-atomic-completeness-1.0",
        "experiment": EXPERIMENT,
        "status": (
            "development_candidate"
            if metrics["gates"]["all_met"]
            else "rejected_development_candidate"
        ),
        "protocol": {
            "selection_split": DEVELOPMENT_SPLIT,
            "cross_validation": "five_fold_stratified_out_of_fold",
            "binary_training_labels": sorted(TARGET_LABELS),
            "random_seed": SEED,
            "heldout_loaded": False,
            "heldout_used_for_selection": False,
            "evaluation_labels_in_model_features": False,
        },
        "inputs": {
            "development_cases": len(targets),
            "development_sha256": _sha256_json(development),
            "relation_score_rows_sha256": _sha256_json(relation_scores["rows"]),
            "v14_rows_sha256": _sha256_json(v14_report["rows"]),
            "atomic_feature_rows_sha256": _sha256_json(
                [
                    {key: value for key, value in row.items() if key != "latency_ms"}
                    for row in atomic_scores["rows"]
                ]
            ),
            "atomic_requirements": atomic_scores["requirements"],
            "model_id": atomic_scores["model"]["model_id"],
        },
        "features": {
            "sets": {
                name: {"count": len(names), "names": names}
                for name, _, names in _feature_sets(inputs)
            },
            "sources": [
                "V14 out-of-fold five-way probabilities",
                "frozen V11 full-claim relation and lexical features",
                "frozen V11 atomic-requirement relation distributions",
            ],
            "dataset_identity_included": False,
            "evaluation_labels_included": False,
        },
        "search": {
            "candidate_count": len(candidates),
            "policy_candidates_per_model": len(THRESHOLDS) ** 3,
            "candidates": candidates,
        },
        "selected": {
            **selected,
            "policy": selected_policy,
        },
        "promotion_gates": {
            "support_recall_minimum": 0.50,
            "false_support_rate_maximum": 0.05,
            "zero_contradiction_false_supports": True,
            "partial_or_ambiguous_review_recall_minimum": 0.80,
            "review_rate_maximum": 0.50,
            "all_met": bool(metrics["gates"]["all_met"]),
        },
        "decision": (
            "freeze_v15_development_candidate"
            if metrics["gates"]["all_met"]
            else "do_not_promote_v15"
        ),
        "rows": rows,
        "remote_inference_used": False,
        "stable_defaults_changed": False,
        "remote_provider_default_enabled": False,
        "local_only_network_calls": 0,
    }


def atomic_feature_vector(row: dict[str, Any]) -> tuple[list[str], list[float]]:
    requirements = list(row.get("requirements") or [])
    if not requirements:
        raise V15CompletenessError("Atomic score row has no requirements.")
    names = ["atomic.log_requirement_count"]
    values = [math.log1p(len(requirements))]
    statuses = ("covered", "missing", "contradicted")
    for status in statuses:
        names.append(f"atomic.status_fraction.{status}")
        values.append(
            sum(requirement["status"] == status for requirement in requirements)
            / len(requirements)
        )
    for relation in RELATIONS:
        items = [
            float(requirement["nli_scores"][relation]) for requirement in requirements
        ]
        ordered = sorted(items)
        names.extend(
            f"atomic.{relation}.{statistic}"
            for statistic in ("minimum", "maximum", "mean", "std", "median")
        )
        values.extend(
            (
                ordered[0],
                ordered[-1],
                statistics.fmean(items),
                statistics.pstdev(items),
                statistics.median(items),
            )
        )
        for threshold in (0.2, 0.4, 0.6, 0.8):
            names.append(f"atomic.{relation}.fraction_ge_{threshold:.1f}")
            values.append(sum(value >= threshold for value in items) / len(items))
    names.extend(
        (
            "atomic.minimum_entailment_minus_maximum_contradiction",
            "atomic.minimum_entailment_minus_maximum_neutral",
            "atomic.all_requirements_entailment_product",
        )
    )
    entailment = [float(row["nli_scores"]["entailment"]) for row in requirements]
    contradiction = [float(row["nli_scores"]["contradiction"]) for row in requirements]
    neutral = [float(row["nli_scores"]["neutral"]) for row in requirements]
    values.extend(
        (
            min(entailment) - max(contradiction),
            min(entailment) - max(neutral),
            math.prod(entailment),
        )
    )
    return names, [float(value) for value in values]


def _aligned_inputs(
    development: dict[str, Any],
    relation_scores: dict[str, Any],
    v14_report: dict[str, Any],
    atomic_scores: dict[str, Any],
) -> dict[str, Any]:
    if any(
        artifact.get("split") != DEVELOPMENT_SPLIT
        for artifact in (development, relation_scores, atomic_scores)
    ):
        raise V15CompletenessError("V15 accepts only V13 development artifacts.")
    if v14_report.get("protocol", {}).get("selection_split") != DEVELOPMENT_SPLIT:
        raise V15CompletenessError(
            "V14 input does not use the expected development split."
        )
    if (
        v14_report["protocol"].get("heldout_loaded") is not False
        or v14_report["protocol"].get("heldout_used_for_selection") is not False
    ):
        raise V15CompletenessError("V14 input does not attest held-out isolation.")
    if relation_scores.get("dataset_sha256") != _sha256_json(
        development
    ) or atomic_scores.get("dataset_sha256") != _sha256_json(development):
        raise V15CompletenessError("V15 score artifacts do not match development data.")
    if (
        relation_scores.get("remote_inference_used") is not False
        or relation_scores.get("evaluation_labels_sent") is not False
        or atomic_scores.get("remote_inference_used") is not False
        or atomic_scores.get("input_contract", {}).get("evaluation_labels_sent")
        is not False
    ):
        raise V15CompletenessError("V15 inputs must be local and label-blind.")
    examples = {str(row["id"]): row for row in development.get("examples") or []}
    relations = {str(row["case_id"]): row for row in relation_scores.get("rows") or []}
    v14_rows = {str(row["case_id"]): row for row in v14_report.get("rows") or []}
    atomic = {str(row["case_id"]): row for row in atomic_scores.get("rows") or []}
    if not examples or not set(examples) == set(relations) == set(v14_rows) == set(
        atomic
    ):
        raise V15CompletenessError("V15 case IDs are empty or misaligned.")
    case_ids = sorted(examples)
    return {
        "case_ids": case_ids,
        "examples": [examples[case_id] for case_id in case_ids],
        "relations": [relations[case_id] for case_id in case_ids],
        "atomic": [atomic[case_id] for case_id in case_ids],
        "targets": [examples[case_id]["target"]["verdict"] for case_id in case_ids],
        "v14_predictions": [v14_rows[case_id]["prediction"] for case_id in case_ids],
        "v14_probabilities": [
            [float(v14_rows[case_id]["probabilities"][label]) for label in LABELS]
            for case_id in case_ids
        ],
    }


def _feature_sets(
    inputs: dict[str, Any],
) -> list[tuple[str, list[list[float]], list[str]]]:
    atomic_matrix = []
    relation_matrix = []
    atomic_names: list[str] | None = None
    relation_names: list[str] | None = None
    for example, relation, atomic in zip(
        inputs["examples"], inputs["relations"], inputs["atomic"], strict=True
    ):
        current_atomic_names, current_atomic = atomic_feature_vector(atomic)
        current_relation_names, current_relation = feature_vector(example, relation)
        if atomic_names is None:
            atomic_names = current_atomic_names
            relation_names = current_relation_names
        elif (
            atomic_names != current_atomic_names
            or relation_names != current_relation_names
        ):
            raise V15CompletenessError("V15 feature schemas are inconsistent.")
        atomic_matrix.append(current_atomic)
        relation_matrix.append(current_relation)
    probability_names = [f"v14.probability.{label}" for label in LABELS]
    atomic_names = list(atomic_names or [])
    relation_names = list(relation_names or [])
    probabilities = inputs["v14_probabilities"]
    return [
        ("atomic", atomic_matrix, atomic_names),
        (
            "atomic_v14",
            [
                left + right
                for left, right in zip(atomic_matrix, probabilities, strict=True)
            ],
            atomic_names + probability_names,
        ),
        (
            "atomic_v14_relation",
            [
                atomic + probability + relation
                for atomic, probability, relation in zip(
                    atomic_matrix, probabilities, relation_matrix, strict=True
                )
            ],
            atomic_names + probability_names + relation_names,
        ),
    ]


def _out_of_fold_completeness(
    matrix: list[list[float]],
    targets: list[str],
    folds: list[tuple[list[int], list[int]]],
    *,
    estimator: Any,
) -> list[float]:
    import numpy as np
    from sklearn.base import clone

    features = np.asarray(matrix, dtype=float)
    output: list[float | None] = [None] * len(targets)
    for training_indexes, validation_indexes in folds:
        binary_training = [
            index for index in training_indexes if targets[index] in TARGET_LABELS
        ]
        labels = np.asarray(
            [targets[index] == "supported" for index in binary_training]
        )
        model = clone(estimator)
        model.fit(features[binary_training], labels)
        class_index = list(model.classes_).index(True)
        probabilities = model.predict_proba(features[validation_indexes])[
            :, class_index
        ]
        for index, value in zip(validation_indexes, probabilities, strict=True):
            output[index] = float(value)
    if any(value is None for value in output):
        raise V15CompletenessError("V15 out-of-fold coverage is incomplete.")
    return [float(value) for value in output if value is not None]


def _candidates() -> list[tuple[str, Any]]:
    from sklearn.ensemble import ExtraTreesClassifier, HistGradientBoostingClassifier
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    rows: list[tuple[str, Any]] = []
    for regularization in (0.003, 0.01, 0.03, 0.1, 0.3, 1.0, 3.0, 10.0):
        rows.append(
            (
                f"logistic_c_{regularization}",
                make_pipeline(
                    StandardScaler(),
                    LogisticRegression(
                        C=regularization,
                        class_weight="balanced",
                        max_iter=5000,
                        random_state=SEED,
                    ),
                ),
            )
        )
    for depth in (2, 3, None):
        for leaf in (2, 4, 8):
            rows.append(
                (
                    f"extra_depth_{depth}_leaf_{leaf}",
                    ExtraTreesClassifier(
                        n_estimators=400,
                        max_depth=depth,
                        min_samples_leaf=leaf,
                        max_features=0.75,
                        class_weight="balanced",
                        random_state=SEED,
                        n_jobs=1,
                    ),
                )
            )
    for minimum_leaf in (5, 10, 20):
        rows.append(
            (
                f"hist_minimum_{minimum_leaf}",
                HistGradientBoostingClassifier(
                    max_iter=200,
                    max_leaf_nodes=3,
                    min_samples_leaf=minimum_leaf,
                    l2_regularization=1.0,
                    class_weight="balanced",
                    random_state=SEED,
                ),
            )
        )
    return rows


def _binary_metrics(targets: list[str], probabilities: list[float]) -> dict[str, Any]:
    from sklearn.metrics import average_precision_score, roc_auc_score

    indexes = [index for index, target in enumerate(targets) if target in TARGET_LABELS]
    labels = [targets[index] == "supported" for index in indexes]
    scores = [probabilities[index] for index in indexes]
    return {
        "cases": len(indexes),
        "roc_auc": round(float(roc_auc_score(labels, scores)), 4),
        "average_precision": round(float(average_precision_score(labels, scores)), 4),
    }


def _select_policy(
    targets: list[str],
    v14_predictions: list[str],
    v14_probabilities: list[list[float]],
    completeness: list[float],
) -> dict[str, Any]:
    indexes = {label: LABELS.index(label) for label in LABELS}
    candidates = []
    for completeness_minimum in THRESHOLDS:
        for contradiction_maximum in THRESHOLDS:
            for ambiguity_maximum in THRESHOLDS:
                predictions = []
                for base, base_probabilities, complete_probability in zip(
                    v14_predictions, v14_probabilities, completeness, strict=True
                ):
                    if base not in TARGET_LABELS:
                        predictions.append(base)
                    elif (
                        complete_probability >= completeness_minimum
                        and base_probabilities[indexes["contradicted"]]
                        <= contradiction_maximum
                        and base_probabilities[indexes["unverifiable"]]
                        <= ambiguity_maximum
                    ):
                        predictions.append("supported")
                    else:
                        predictions.append("partially_supported")
                metrics = policy_metrics(targets, predictions)
                candidates.append(
                    {
                        "complete_support_probability_minimum": completeness_minimum,
                        "contradiction_probability_maximum": contradiction_maximum,
                        "unverifiable_probability_maximum": ambiguity_maximum,
                        "metrics": metrics,
                        "predictions": predictions,
                    }
                )
    passing = [row for row in candidates if row["metrics"]["gates"]["all_met"]]
    safety = [
        row
        for row in candidates
        if row["metrics"]["gates"]["false_support_rate"]
        and row["metrics"]["gates"]["zero_contradiction_false_supports"]
    ]
    selected = max(passing or safety or candidates, key=_policy_key)
    return {
        **selected,
        "candidate_count": len(candidates),
        "all_gate_candidate_count": len(passing),
        "selection_kind": (
            "all_gates"
            if passing
            else "safety_eligible"
            if safety
            else "best_available_diagnostic"
        ),
    }


def _candidate_key(row: dict[str, Any]) -> tuple[Any, ...]:
    metrics = row["policy"]["metrics"]
    return (
        bool(metrics["gates"]["all_met"]),
        sum(bool(value) for key, value in metrics["gates"].items() if key != "all_met"),
        float(metrics["macro_f1"]),
        float(metrics["support_recall"]),
        -float(metrics["false_support_rate"]),
        float(row["binary_complete_support"]["roc_auc"]),
        str(row["candidate"]),
    )


def _policy_key(row: dict[str, Any]) -> tuple[Any, ...]:
    metrics = row["metrics"]
    return (
        float(metrics["macro_f1"]),
        float(metrics["support_recall"]),
        -float(metrics["false_support_rate"]),
        float(metrics["partial_or_ambiguous_review_recall"]),
        -float(metrics["review_rate"]),
        float(row["complete_support_probability_minimum"]),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--development", required=True)
    parser.add_argument("--relation-scores", required=True)
    parser.add_argument("--v14-report", required=True)
    parser.add_argument("--atomic-scores", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)

    def load(path: str) -> dict[str, Any]:
        return json.loads(Path(path).read_text(encoding="utf-8"))

    report = train_and_assess(
        load(args.development),
        load(args.relation_scores),
        load(args.v14_report),
        load(args.atomic_scores),
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
                "candidate": report["selected"]["candidate"],
                "binary": report["selected"]["binary_complete_support"],
                "policy": report["selected"]["policy"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
