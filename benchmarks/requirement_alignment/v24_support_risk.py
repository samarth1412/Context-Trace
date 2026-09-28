"""Cross-validate explicit support, contradiction, and review risk heads."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Callable

from benchmarks.requirement_alignment.v14_fiveway_policy import (
    LABELS,
    THRESHOLDS,
    _folds,
    _sha256_json,
    policy_metrics,
)
from benchmarks.requirement_alignment.v22_domain_candidate import (
    SPLIT,
    _aligned_inputs,
    _candidates,
    _rows_hash,
)


EXPERIMENT = "contexttrace_v24_support_risk"
ROUTING_EXPERIMENT = "contexttrace_v23_stronger_nli_atomic_screen"


class V24SupportRiskError(RuntimeError):
    """Raised when V24 inputs violate the development-only contract."""


def train_and_cross_validate(
    development: dict[str, Any],
    relation_scores: dict[str, Any],
    atomic_scores: dict[str, Any],
    multispan_scores: dict[str, Any],
    routing_result: dict[str, Any],
) -> dict[str, Any]:
    inputs = _aligned_inputs(
        development, relation_scores, atomic_scores, multispan_scores
    )
    routing_probabilities = _routing_probabilities(
        development, inputs["case_ids"], routing_result
    )
    folds = _folds(inputs["targets"])
    candidates = []
    probability_sets: dict[str, dict[str, list[float]]] = {}
    for name, estimator in _candidates():
        probabilities = {
            "support": _binary_out_of_fold_probabilities(
                inputs["matrix"],
                inputs["targets"],
                folds,
                estimator,
                lambda label: label == "supported",
            ),
            "contradiction_risk": _binary_out_of_fold_probabilities(
                inputs["matrix"],
                inputs["targets"],
                folds,
                estimator,
                lambda label: label == "contradicted",
            ),
            "review_risk": _binary_out_of_fold_probabilities(
                inputs["matrix"],
                inputs["targets"],
                folds,
                estimator,
                lambda label: label in {"partially_supported", "unverifiable"},
            ),
        }
        policy = _select_policy(
            inputs["targets"], probabilities, routing_probabilities
        )
        candidates.append(
            {
                "candidate": name,
                "policy": {
                    key: value for key, value in policy.items() if key != "predictions"
                },
            }
        )
        probability_sets[name] = probabilities
    selected = max(candidates, key=_candidate_key)
    selected_name = str(selected["candidate"])
    selected_policy = _select_policy(
        inputs["targets"],
        probability_sets[selected_name],
        routing_probabilities,
    )
    predictions = selected_policy.pop("predictions")
    metrics = selected_policy["metrics"]
    probabilities = probability_sets[selected_name]
    rows = []
    for index, (case_id, target, prediction) in enumerate(
        zip(
            inputs["case_ids"], inputs["targets"], predictions, strict=True
        )
    ):
        rows.append(
            {
                "case_id": case_id,
                "expected_verdict": target,
                "prediction": prediction,
                "risk_probabilities": {
                    key: round(values[index], 8)
                    for key, values in probabilities.items()
                },
                "routing_probabilities": {
                    label: round(value, 8)
                    for label, value in zip(
                        LABELS, routing_probabilities[index], strict=True
                    )
                },
            }
        )
    return {
        "schema_version": "contexttrace-v24-support-risk-1.0",
        "experiment": EXPERIMENT,
        "status": (
            "development_candidate"
            if metrics["gates"]["all_met"]
            else "rejected_development_candidate"
        ),
        "protocol": {
            "selection_split": SPLIT,
            "cross_validation": "five_fold_stratified_out_of_fold",
            "development_only": True,
            "future_confirmation_loaded": False,
            "future_confirmation_used_for_selection": False,
            "evaluation_labels_in_model_features": False,
            "dataset_identity_in_model_features": False,
            "risk_heads": ["support", "contradiction_risk", "review_risk"],
        },
        "inputs": {
            "development_cases": len(inputs["case_ids"]),
            "development_sha256": _sha256_json(development),
            "relation_rows_sha256": _rows_hash(relation_scores),
            "atomic_rows_sha256": _rows_hash(atomic_scores),
            "multispan_rows_sha256": _rows_hash(multispan_scores),
            "routing_result_sha256": _sha256_json(routing_result),
            "relation_model_id": relation_scores["model"]["model_id"],
            "atomic_model_id": atomic_scores["model"]["model_id"],
            "multispan_model_id": multispan_scores["model"]["model_id"],
        },
        "features": {
            "count": len(inputs["feature_names"]),
            "names": inputs["feature_names"],
            "evaluation_labels_included": False,
            "dataset_identity_included": False,
        },
        "search": {
            "candidate_count": len(candidates),
            "thresholds_per_risk_head": list(THRESHOLDS),
            "policy_candidates_per_estimator": len(THRESHOLDS) ** 3,
            "candidates": candidates,
        },
        "selected": {**selected, "policy": selected_policy},
        "promotion_gates": {
            "support_recall_minimum": 0.50,
            "false_support_rate_maximum": 0.05,
            "zero_contradiction_false_supports": True,
            "partial_or_ambiguous_review_recall_minimum": 0.80,
            "review_rate_maximum": 0.50,
            "all_met": bool(metrics["gates"]["all_met"]),
        },
        "decision": (
            "freeze_v24_development_candidate"
            if metrics["gates"]["all_met"]
            else "do_not_promote_v24"
        ),
        "rows": rows,
        "remote_inference_used": False,
        "stable_defaults_changed": False,
        "remote_provider_default_enabled": False,
        "local_only_network_calls": 0,
    }


def _binary_out_of_fold_probabilities(
    matrix: list[list[float]],
    targets: list[str],
    folds: list[tuple[list[int], list[int]]],
    estimator: Any,
    positive: Callable[[str], bool],
) -> list[float]:
    import numpy as np
    from sklearn.base import clone

    features = np.asarray(matrix, dtype=float)
    labels = np.asarray([positive(target) for target in targets])
    output: list[float | None] = [None] * len(targets)
    for train_indexes, validation_indexes in folds:
        model = clone(estimator)
        model.fit(features[train_indexes], labels[train_indexes])
        positive_index = list(model.classes_).index(True)
        fold_probabilities = model.predict_proba(features[validation_indexes])
        for row_index, values in zip(
            validation_indexes, fold_probabilities, strict=True
        ):
            output[row_index] = float(values[positive_index])
    if any(value is None for value in output):
        raise V24SupportRiskError("Out-of-fold risk coverage is incomplete.")
    return [float(value) for value in output if value is not None]


def _select_policy(
    targets: list[str],
    probabilities: dict[str, list[float]],
    routing_probabilities: list[list[float]],
) -> dict[str, Any]:
    label_indexes = {label: LABELS.index(label) for label in LABELS}
    rows = []
    for support_minimum in THRESHOLDS:
        for contradiction_maximum in THRESHOLDS:
            for review_maximum in THRESHOLDS:
                predictions = []
                for support, contradiction, review, routing in zip(
                    probabilities["support"],
                    probabilities["contradiction_risk"],
                    probabilities["review_risk"],
                    routing_probabilities,
                    strict=True,
                ):
                    if (
                        support >= support_minimum
                        and contradiction <= contradiction_maximum
                        and review <= review_maximum
                    ):
                        predictions.append("supported")
                    else:
                        predictions.append(
                            max(
                                (label for label in LABELS if label != "supported"),
                                key=lambda label: routing[label_indexes[label]],
                            )
                        )
                metrics = policy_metrics(targets, predictions)
                rows.append(
                    {
                        "support_probability_minimum": support_minimum,
                        "contradiction_risk_maximum": contradiction_maximum,
                        "review_risk_maximum": review_maximum,
                        "metrics": metrics,
                        "predictions": predictions,
                    }
                )
    passing = [row for row in rows if row["metrics"]["gates"]["all_met"]]
    eligible = [
        row
        for row in rows
        if row["metrics"]["gates"]["false_support_rate"]
        and row["metrics"]["gates"]["zero_contradiction_false_supports"]
    ]
    selected = max(passing or eligible or rows, key=_policy_key)
    return {
        **selected,
        "candidate_count": len(rows),
        "all_gate_candidate_count": len(passing),
        "selection_kind": (
            "all_gates"
            if passing
            else "safety_eligible"
            if eligible
            else "best_available_diagnostic"
        ),
    }


def _routing_probabilities(
    development: dict[str, Any],
    case_ids: list[str],
    routing_result: dict[str, Any],
) -> list[list[float]]:
    if routing_result.get("experiment") != ROUTING_EXPERIMENT:
        raise V24SupportRiskError("V24 requires the V23 atomic routing result.")
    if routing_result.get("inputs", {}).get("development_sha256") != _sha256_json(
        development
    ):
        raise V24SupportRiskError("V24 routing probabilities do not match V21.")
    if (
        routing_result.get("remote_inference_used") is not False
        or routing_result.get("stable_defaults_changed") is not False
    ):
        raise V24SupportRiskError("V24 requires the local unchanged V23 result.")
    rows = {str(row["case_id"]): row for row in routing_result.get("rows") or []}
    if set(rows) != set(case_ids):
        raise V24SupportRiskError("V24 routing case IDs are misaligned.")
    return [
        [float(rows[case_id]["probabilities"][label]) for label in LABELS]
        for case_id in case_ids
    ]


def _candidate_key(row: dict[str, Any]) -> tuple[Any, ...]:
    metrics = row["policy"]["metrics"]
    return (
        bool(metrics["gates"]["all_met"]),
        sum(
            bool(value)
            for key, value in metrics["gates"].items()
            if key != "all_met"
        ),
        float(metrics["macro_f1"]),
        float(metrics["support_recall"]),
        -float(metrics["false_support_rate"]),
        float(metrics["partial_or_ambiguous_review_recall"]),
        -float(metrics["review_rate"]),
        str(row["candidate"]),
    )


def _policy_key(row: dict[str, Any]) -> tuple[Any, ...]:
    metrics = row["metrics"]
    return (
        float(metrics["macro_f1"]),
        float(metrics["support_recall"]),
        float(metrics["partial_or_ambiguous_review_recall"]),
        -float(metrics["false_support_rate"]),
        -float(metrics["review_rate"]),
        float(row["support_probability_minimum"]),
    )


def _load(path: str) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--development", required=True)
    parser.add_argument("--relation-scores", required=True)
    parser.add_argument("--atomic-scores", required=True)
    parser.add_argument("--multispan-scores", required=True)
    parser.add_argument("--routing-result", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    result = train_and_cross_validate(
        _load(args.development),
        _load(args.relation_scores),
        _load(args.atomic_scores),
        _load(args.multispan_scores),
        _load(args.routing_result),
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "status": result["status"],
                "candidate": result["selected"]["candidate"],
                "policy": result["selected"]["policy"],
                "decision": result["decision"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
