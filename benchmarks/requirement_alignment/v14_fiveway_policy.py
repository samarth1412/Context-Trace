"""Cross-validate a local five-way policy on V13 development only."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
from pathlib import Path
from typing import Any

from benchmarks.requirement_alignment.v9_router import _lexical_features


EXPERIMENT = "contexttrace_v14_fiveway_policy"
DEVELOPMENT_SPLIT = "external_fiveway_v13_development"
LABELS = (
    "contradicted",
    "partially_supported",
    "supported",
    "unsupported",
    "unverifiable",
)
RELATIONS = ("entailment", "contradiction", "neutral")
SEED = 20260927
SUPPORT_RECALL_MINIMUM = 0.50
FALSE_SUPPORT_RATE_MAXIMUM = 0.05
REVIEW_RECALL_MINIMUM = 0.80
REVIEW_RATE_MAXIMUM = 0.50
THRESHOLDS = tuple(round(value / 100, 2) for value in range(20, 96, 5))


class V14PolicyError(RuntimeError):
    """Raised when V14 violates its development-only policy contract."""


def train_and_cross_validate(
    development: dict[str, Any],
    scores: dict[str, Any],
) -> dict[str, Any]:
    matrix, targets, case_ids, feature_names = _matrix(development, scores)
    folds = _folds(targets)
    candidates = []
    probability_sets: dict[str, list[list[float]]] = {}
    for name, estimator in _candidates():
        probabilities = _out_of_fold_probabilities(
            matrix, targets, folds, estimator=estimator
        )
        direct_predictions = [LABELS[_argmax(row)] for row in probabilities]
        direct = classification_metrics(targets, direct_predictions)
        policy = _select_policy(targets, probabilities)
        candidates.append(
            {
                "candidate": name,
                "direct": direct,
                "policy": {
                    key: value for key, value in policy.items() if key != "predictions"
                },
            }
        )
        probability_sets[name] = probabilities
    selected = max(candidates, key=_selection_key)
    selected_name = str(selected["candidate"])
    selected_probabilities = probability_sets[selected_name]
    selected_policy = _select_policy(targets, selected_probabilities)
    predictions = selected_policy.pop("predictions")
    fold_metrics = []
    for fold_index, (_, validation_indexes) in enumerate(folds):
        fold_targets = [targets[index] for index in validation_indexes]
        fold_predictions = [predictions[index] for index in validation_indexes]
        fold_metrics.append(
            {
                "fold": fold_index,
                "cases": len(validation_indexes),
                "metrics": policy_metrics(fold_targets, fold_predictions),
            }
        )
    rows = [
        {
            "case_id": case_id,
            "expected_verdict": target,
            "prediction": prediction,
            "probabilities": {
                label: round(float(probability), 8)
                for label, probability in zip(LABELS, probabilities, strict=True)
            },
        }
        for case_id, target, prediction, probabilities in zip(
            case_ids, targets, predictions, selected_probabilities, strict=True
        )
    ]
    gates = selected_policy["metrics"]["gates"]
    return {
        "schema_version": "contexttrace-v14-fiveway-policy-1.0",
        "experiment": EXPERIMENT,
        "status": "development_candidate"
        if gates["all_met"]
        else "rejected_development_candidate",
        "protocol": {
            "selection_split": DEVELOPMENT_SPLIT,
            "cross_validation": "five_fold_stratified_out_of_fold",
            "random_seed": SEED,
            "heldout_loaded": False,
            "heldout_used_for_selection": False,
            "evaluation_labels_in_model_features": False,
        },
        "inputs": {
            "development_cases": len(targets),
            "development_sha256": _sha256_json(development),
            "score_rows_sha256": _sha256_json(scores["rows"]),
            "model_id": scores["model"]["model_id"],
        },
        "features": {
            "count": len(feature_names),
            "names": feature_names,
            "sources": [
                "frozen V11 per-evidence relation probabilities",
                "cross-span relation interactions",
                "deterministic lexical overlap, negation, number, and length signals",
            ],
            "dataset_identity_included": False,
            "evaluation_labels_included": False,
        },
        "search": {
            "candidate_count": len(candidates),
            "support_thresholds": list(THRESHOLDS),
            "contradiction_caps": list(THRESHOLDS),
            "review_risk_caps": list(THRESHOLDS),
            "candidates": candidates,
        },
        "selected": {
            "candidate": selected_name,
            "direct": selected["direct"],
            "policy": selected_policy,
            "fold_metrics": fold_metrics,
        },
        "promotion_gates": {
            "support_recall_minimum": SUPPORT_RECALL_MINIMUM,
            "false_support_rate_maximum": FALSE_SUPPORT_RATE_MAXIMUM,
            "zero_contradiction_false_supports": True,
            "partial_or_ambiguous_review_recall_minimum": REVIEW_RECALL_MINIMUM,
            "review_rate_maximum": REVIEW_RATE_MAXIMUM,
            "all_met": bool(gates["all_met"]),
        },
        "decision": (
            "freeze_development_candidate_and_build_new_confirmation"
            if gates["all_met"]
            else "do_not_promote_v14"
        ),
        "rows": rows,
        "remote_inference_used": False,
        "stable_defaults_changed": False,
        "remote_provider_default_enabled": False,
        "local_only_network_calls": 0,
    }


def feature_vector(
    example: dict[str, Any], score_row: dict[str, Any]
) -> tuple[list[str], list[float]]:
    evidence = list(example["input"]["evidence"])
    probabilities = [dict(row["probabilities"]) for row in score_row["per_evidence"]]
    if not evidence or len(evidence) != len(probabilities):
        raise V14PolicyError(
            "Evidence and relation probabilities must be nonempty and aligned."
        )
    names: list[str] = []
    values: list[float] = []
    names.append("evidence.log_count")
    values.append(math.log1p(len(evidence)))
    relation_values: dict[str, list[float]] = {}
    for relation in RELATIONS:
        items = [float(row[relation]) for row in probabilities]
        if any(not math.isfinite(value) or not 0.0 <= value <= 1.0 for value in items):
            raise V14PolicyError("Relation probabilities must be finite unit values.")
        relation_values[relation] = items
        ordered = sorted(items, reverse=True)
        names.extend(
            f"relation.{relation}.{statistic}"
            for statistic in (
                "maximum",
                "second",
                "minimum",
                "mean",
                "std",
                "median",
                "range",
            )
        )
        values.extend(
            (
                ordered[0],
                ordered[1] if len(ordered) > 1 else ordered[0],
                ordered[-1],
                statistics.fmean(items),
                statistics.pstdev(items),
                statistics.median(items),
                ordered[0] - ordered[-1],
            )
        )
        for threshold in (0.2, 0.4, 0.6, 0.8):
            names.append(f"relation.{relation}.fraction_ge_{threshold:.1f}")
            values.append(sum(value >= threshold for value in items) / len(items))
    entailment = relation_values["entailment"]
    contradiction = relation_values["contradiction"]
    max_entailment = max(entailment)
    max_contradiction = max(contradiction)
    same_products = [
        left * right for left, right in zip(entailment, contradiction, strict=True)
    ]
    cross_products = [
        entailment[left] * contradiction[right]
        for left in range(len(evidence))
        for right in range(len(evidence))
        if left != right
    ]
    names.extend(
        (
            "interaction.maximum_entailment_times_contradiction",
            "interaction.minimum_relation_maximum",
            "interaction.absolute_maximum_difference",
            "interaction.same_span_product_maximum",
            "interaction.same_span_product_mean",
            "interaction.cross_span_product_maximum",
            "interaction.cross_span_product_mean",
            "interaction.argmax_spans_differ",
        )
    )
    values.extend(
        (
            max_entailment * max_contradiction,
            min(max_entailment, max_contradiction),
            abs(max_entailment - max_contradiction),
            max(same_products),
            statistics.fmean(same_products),
            max(cross_products) if cross_products else same_products[0],
            statistics.fmean(cross_products) if cross_products else same_products[0],
            float(
                entailment.index(max_entailment)
                != contradiction.index(max_contradiction)
            ),
        )
    )
    lexical_names = (
        "claim_coverage",
        "jaccard",
        "best_span_coverage",
        "best_span_jaccard",
        "bigram_coverage",
        "claim_negation",
        "evidence_negation",
        "negation_mismatch",
        "number_coverage",
        "missing_number",
        "log_claim_tokens",
        "log_evidence_tokens",
    )
    names.extend(f"lexical.{name}" for name in lexical_names)
    values.extend(_lexical_features(example))
    return names, [float(value) for value in values]


def _matrix(
    development: dict[str, Any], scores: dict[str, Any]
) -> tuple[list[list[float]], list[str], list[str], list[str]]:
    if (
        development.get("split") != DEVELOPMENT_SPLIT
        or scores.get("split") != DEVELOPMENT_SPLIT
    ):
        raise V14PolicyError("V14 accepts only the V13 development split.")
    if scores.get("dataset_sha256") != _sha256_json(development):
        raise V14PolicyError("Relation scores do not match the development dataset.")
    if (
        scores.get("remote_inference_used") is not False
        or scores.get("evaluation_labels_sent") is not False
    ):
        raise V14PolicyError("V14 requires local, label-blind relation scores.")
    examples = {str(row["id"]): row for row in development.get("examples") or []}
    score_rows = {str(row["case_id"]): row for row in scores.get("rows") or []}
    if (
        not examples
        or len(examples) != len(development["examples"])
        or set(examples) != set(score_rows)
    ):
        raise V14PolicyError(
            "Development examples and score rows must be unique and aligned."
        )
    case_ids = sorted(examples)
    matrix = []
    feature_names: list[str] | None = None
    for case_id in case_ids:
        names, values = feature_vector(examples[case_id], score_rows[case_id])
        if feature_names is None:
            feature_names = names
        elif names != feature_names:
            raise V14PolicyError("V14 feature schemas are inconsistent.")
        matrix.append(values)
    targets = [str(examples[case_id]["target"]["verdict"]) for case_id in case_ids]
    if set(targets) != set(LABELS):
        raise V14PolicyError("V14 development labels do not cover the five-way schema.")
    return matrix, targets, case_ids, list(feature_names or [])


def _folds(targets: list[str]) -> list[tuple[list[int], list[int]]]:
    import numpy as np
    from sklearn.model_selection import StratifiedKFold

    indexes = np.arange(len(targets))
    splitter = StratifiedKFold(n_splits=5, shuffle=True, random_state=SEED)
    return [
        (train.tolist(), validation.tolist())
        for train, validation in splitter.split(indexes, targets)
    ]


def _out_of_fold_probabilities(
    matrix: list[list[float]],
    targets: list[str],
    folds: list[tuple[list[int], list[int]]],
    *,
    estimator: Any,
) -> list[list[float]]:
    import numpy as np
    from sklearn.base import clone

    features = np.asarray(matrix, dtype=float)
    labels = np.asarray(targets)
    output: list[list[float] | None] = [None] * len(targets)
    for train_indexes, validation_indexes in folds:
        model = clone(estimator)
        model.fit(features[train_indexes], labels[train_indexes])
        fold_probabilities = model.predict_proba(features[validation_indexes])
        class_indexes = {
            str(label): index for index, label in enumerate(model.classes_)
        }
        for row_index, probabilities in zip(
            validation_indexes, fold_probabilities, strict=True
        ):
            output[row_index] = [
                float(probabilities[class_indexes[label]]) for label in LABELS
            ]
    if any(row is None for row in output):
        raise V14PolicyError("Out-of-fold prediction coverage is incomplete.")
    return [list(row) for row in output if row is not None]


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
    for depth in (2, 3, 4, None):
        for leaf in (2, 4, 8, 16):
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
    for leaves in (3, 7, 15):
        for minimum_leaf in (5, 10, 20):
            rows.append(
                (
                    f"hist_leaves_{leaves}_minimum_{minimum_leaf}",
                    HistGradientBoostingClassifier(
                        max_iter=200,
                        max_leaf_nodes=leaves,
                        min_samples_leaf=minimum_leaf,
                        l2_regularization=1.0,
                        class_weight="balanced",
                        random_state=SEED,
                    ),
                )
            )
    return rows


def _select_policy(
    targets: list[str], probabilities: list[list[float]]
) -> dict[str, Any]:
    indexes = {label: LABELS.index(label) for label in LABELS}
    rows = []
    for support_minimum in THRESHOLDS:
        for contradiction_maximum in THRESHOLDS:
            for review_risk_maximum in THRESHOLDS:
                predictions = []
                for values in probabilities:
                    contradiction = values[indexes["contradicted"]]
                    review_risk = (
                        values[indexes["partially_supported"]]
                        + values[indexes["unverifiable"]]
                    )
                    if (
                        values[indexes["supported"]] >= support_minimum
                        and contradiction <= contradiction_maximum
                        and review_risk <= review_risk_maximum
                    ):
                        predictions.append("supported")
                    else:
                        predictions.append(
                            max(
                                (label for label in LABELS if label != "supported"),
                                key=lambda label: values[indexes[label]],
                            )
                        )
                metrics = policy_metrics(targets, predictions)
                rows.append(
                    {
                        "support_probability_minimum": support_minimum,
                        "contradiction_probability_maximum": contradiction_maximum,
                        "partial_or_ambiguous_probability_maximum": review_risk_maximum,
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
    selected = max(passing or eligible or rows, key=_policy_selection_key)
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


def policy_metrics(targets: list[str], predictions: list[str]) -> dict[str, Any]:
    classification = classification_metrics(targets, predictions)
    support_total = sum(value == "supported" for value in targets)
    negative_total = len(targets) - support_total
    true_supports = sum(
        target == prediction == "supported"
        for target, prediction in zip(targets, predictions, strict=True)
    )
    false_supports = sum(
        target != "supported" and prediction == "supported"
        for target, prediction in zip(targets, predictions, strict=True)
    )
    contradiction_false_supports = sum(
        target == "contradicted" and prediction == "supported"
        for target, prediction in zip(targets, predictions, strict=True)
    )
    review_total = sum(
        target in {"partially_supported", "unverifiable"} for target in targets
    )
    reviewed = sum(
        target in {"partially_supported", "unverifiable"}
        and prediction in {"partially_supported", "unverifiable"}
        for target, prediction in zip(targets, predictions, strict=True)
    )
    review_predictions = sum(
        prediction in {"partially_supported", "unverifiable"}
        for prediction in predictions
    )
    support_recall = _ratio(true_supports, support_total)
    false_support_rate = _ratio(false_supports, negative_total)
    review_recall = _ratio(reviewed, review_total)
    review_rate = _ratio(review_predictions, len(targets))
    gates = {
        "support_recall": support_recall >= SUPPORT_RECALL_MINIMUM,
        "false_support_rate": false_support_rate <= FALSE_SUPPORT_RATE_MAXIMUM,
        "zero_contradiction_false_supports": contradiction_false_supports == 0,
        "partial_or_ambiguous_review_recall": review_recall >= REVIEW_RECALL_MINIMUM,
        "review_rate": review_rate <= REVIEW_RATE_MAXIMUM,
    }
    return {
        **classification,
        "support_recall": round(support_recall, 4),
        "false_support_rate": round(false_support_rate, 4),
        "false_supports": false_supports,
        "contradiction_false_supports": contradiction_false_supports,
        "partial_or_ambiguous_review_recall": round(review_recall, 4),
        "review_rate": round(review_rate, 4),
        "gates": {**gates, "all_met": all(gates.values())},
    }


def classification_metrics(
    targets: list[str], predictions: list[str]
) -> dict[str, Any]:
    confusion = {gold: {guess: 0 for guess in LABELS} for gold in LABELS}
    for gold, guess in zip(targets, predictions, strict=True):
        if gold not in LABELS or guess not in LABELS:
            raise V14PolicyError("Unknown five-way label.")
        confusion[gold][guess] += 1
    f1s = []
    per_label = {}
    for label in LABELS:
        true_positive = confusion[label][label]
        false_positive = sum(confusion[gold][label] for gold in LABELS if gold != label)
        false_negative = sum(
            confusion[label][guess] for guess in LABELS if guess != label
        )
        precision = _ratio(true_positive, true_positive + false_positive)
        recall = _ratio(true_positive, true_positive + false_negative)
        f1 = _ratio(2 * precision * recall, precision + recall)
        f1s.append(f1)
        per_label[label] = {
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
            "support": sum(confusion[label].values()),
        }
    return {
        "accuracy": round(
            _ratio(sum(confusion[label][label] for label in LABELS), len(targets)), 4
        ),
        "macro_f1": round(statistics.fmean(f1s), 4),
        "per_label": per_label,
        "confusion": confusion,
    }


def _selection_key(row: dict[str, Any]) -> tuple[Any, ...]:
    policy = row["policy"]
    metrics = policy["metrics"]
    return (
        bool(metrics["gates"]["all_met"]),
        sum(bool(value) for key, value in metrics["gates"].items() if key != "all_met"),
        float(metrics["macro_f1"]),
        float(metrics["support_recall"]),
        -float(metrics["false_support_rate"]),
        float(metrics["partial_or_ambiguous_review_recall"]),
        float(row["direct"]["macro_f1"]),
        str(row["candidate"]),
    )


def _policy_selection_key(row: dict[str, Any]) -> tuple[Any, ...]:
    metrics = row["metrics"]
    return (
        float(metrics["macro_f1"]),
        float(metrics["support_recall"]),
        float(metrics["partial_or_ambiguous_review_recall"]),
        -float(metrics["false_support_rate"]),
        -float(metrics["review_rate"]),
        float(row["support_probability_minimum"]),
    )


def _argmax(values: list[float]) -> int:
    return max(range(len(values)), key=values.__getitem__)


def _ratio(numerator: float, denominator: float) -> float:
    return numerator / denominator if denominator else 0.0


def _sha256_json(value: object) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--development", required=True)
    parser.add_argument("--scores", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    development = json.loads(Path(args.development).read_text(encoding="utf-8"))
    scores = json.loads(Path(args.scores).read_text(encoding="utf-8"))
    report = train_and_cross_validate(development, scores)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    selected = report["selected"]
    print(
        json.dumps(
            {
                "status": report["status"],
                "candidate": selected["candidate"],
                "direct": selected["direct"],
                "policy": selected["policy"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
