"""Screen a local four-way verifier on the frozen V10 development split."""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
from pathlib import Path
from typing import Any

from benchmarks.requirement_alignment.v9_router import _feature_names, _features


EXPERIMENT = "contexttrace_v10_fourway_feature_screen"
TRAINING_SPLIT = "climate_fever_v10_training"
DEVELOPMENT_SPLIT = "climate_fever_v10_development"
SEED = 20260927
LABELS = ("DISPUTED", "NOT_ENOUGH_INFO", "REFUTES", "SUPPORTS")
LOGISTIC_CS = (0.001, 0.003, 0.01, 0.03, 0.1, 0.3, 1.0, 3.0, 10.0)
SUPPORT_RECALL_TARGET = 0.50
FALSE_SUPPORT_CAP = 0.05
DISPUTED_REVIEW_TARGET = 0.90
REVIEW_RATE_CAP = 0.30


class V10FourwayError(RuntimeError):
    """Raised when a V10 verifier input violates the frozen experiment contract."""


def screen_fourway(
    training: dict[str, Any],
    training_local: dict[str, Any],
    training_auxiliary: dict[str, Any],
    development: dict[str, Any],
    development_local: dict[str, Any],
    development_auxiliary: dict[str, Any],
) -> dict[str, Any]:
    """Fit frozen-feature candidates and assess them only on V10 development."""

    train_features, train_labels, _ = _matrix(
        training, training_local, training_auxiliary, expected_split=TRAINING_SPLIT
    )
    dev_features, dev_labels, dev_ids = _matrix(
        development,
        development_local,
        development_auxiliary,
        expected_split=DEVELOPMENT_SPLIT,
    )
    candidates = []
    fitted: dict[float, tuple[Any, list[list[float]]]] = {}
    for regularization in LOGISTIC_CS:
        model = _fit(train_features, train_labels, regularization=regularization)
        probabilities = model.predict_proba(dev_features).tolist()
        predictions = model.predict(dev_features).tolist()
        metrics = four_way_metrics(dev_labels, predictions)
        candidates.append(
            {
                "regularization_c": regularization,
                "development": metrics,
            }
        )
        fitted[regularization] = (model, probabilities)
    selected = max(
        candidates,
        key=lambda row: (
            float(row["development"]["macro_f1"]),
            float(row["development"]["accuracy"]),
            -float(row["regularization_c"]),
        ),
    )
    selected_c = float(selected["regularization_c"])
    model, probabilities = fitted[selected_c]
    class_order = [str(value) for value in model.classes_]
    policy = _search_policy(dev_ids, dev_labels, probabilities, class_order)
    gates = dict(policy["selected_diagnostic"]["gates"])
    report = {
        "schema_version": "contexttrace-v10-fourway-screen-1.0",
        "experiment": EXPERIMENT,
        "status": "rejected_development_candidate",
        "inputs": {
            "training_split": TRAINING_SPLIT,
            "training_cases": len(train_labels),
            "training_sha256": _sha256_json(training),
            "development_split": DEVELOPMENT_SPLIT,
            "development_cases": len(dev_labels),
            "development_sha256": _sha256_json(development),
            "local_prediction_rows_sha256": {
                "training": _sha256_json(training_local["rows"]),
                "development": _sha256_json(development_local["rows"]),
            },
            "auxiliary_prediction_rows_sha256": {
                "training": _sha256_json(training_auxiliary["rows"]),
                "development": _sha256_json(development_auxiliary["rows"]),
            },
        },
        "features": {
            "count": len(_feature_names()),
            "names": _feature_names(),
            "sources": [
                "frozen v3 group and evidence-span probabilities",
                "frozen v5 group and evidence-span probabilities",
                "pinned local NLI group and evidence-span probabilities",
                "deterministic lexical overlap and negation signals",
            ],
            "evaluation_labels_in_model_inputs": False,
        },
        "search": {
            "family": "standardized_multinomial_logistic_regression",
            "regularization_c": list(LOGISTIC_CS),
            "class_weight": "balanced",
            "random_seed": SEED,
            "selection_split": DEVELOPMENT_SPLIT,
            "candidates": candidates,
        },
        "selected": {
            "regularization_c": selected_c,
            "class_order": class_order,
            "development": selected["development"],
            "policy_diagnostic": policy,
        },
        "promotion_gates": {
            "support_recall_minimum": SUPPORT_RECALL_TARGET,
            "false_support_rate_maximum": FALSE_SUPPORT_CAP,
            "zero_refutation_false_supports": True,
            "disputed_review_coverage_minimum": DISPUTED_REVIEW_TARGET,
            "review_rate_maximum": REVIEW_RATE_CAP,
            "all_met": bool(gates["all_met"]),
        },
        "decision": {
            "promote": False,
            "reason": "No development policy met all safety, support-recall, disputed-review, and review-budget gates.",
            "next_experiment": "improve evidence-level relation supervision and conflict aggregation before freezing a candidate on a new dataset",
        },
        "v9_holdout_reused": False,
        "future_confirmation_required": True,
        "stable_defaults_changed": False,
        "remote_inference_used": False,
        "remote_provider_default_enabled": False,
        "local_only_network_calls": 0,
    }
    return report


def four_way_metrics(targets: list[str], predictions: list[str]) -> dict[str, Any]:
    if len(targets) != len(predictions) or not targets:
        raise V10FourwayError("Targets and predictions must be non-empty and aligned.")
    confusion = {gold: {guess: 0 for guess in LABELS} for gold in LABELS}
    for gold, guess in zip(targets, predictions, strict=True):
        if gold not in LABELS or guess not in LABELS:
            raise V10FourwayError("Unknown four-way label.")
        confusion[gold][guess] += 1
    per_class = {}
    f1s = []
    for label in LABELS:
        tp = confusion[label][label]
        fp = sum(confusion[gold][label] for gold in LABELS if gold != label)
        fn = sum(confusion[label][guess] for guess in LABELS if guess != label)
        precision = _ratio(tp, tp + fp)
        recall = _ratio(tp, tp + fn)
        f1 = _ratio(2 * precision * recall, precision + recall)
        f1s.append(f1)
        per_class[label] = {
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
            "support": sum(confusion[label].values()),
        }
    correct = sum(confusion[label][label] for label in LABELS)
    return {
        "accuracy": round(_ratio(correct, len(targets)), 4),
        "macro_f1": round(statistics.fmean(f1s), 4),
        "per_class": per_class,
        "confusion": confusion,
    }


def _search_policy(
    case_ids: list[str],
    targets: list[str],
    probabilities: list[list[float]],
    class_order: list[str],
) -> dict[str, Any]:
    indexes = {label: class_order.index(label) for label in LABELS}
    dispute_scores = [row[indexes["DISPUTED"]] for row in probabilities]
    support_scores = [row[indexes["SUPPORTS"]] for row in probabilities]
    refute_scores = [row[indexes["REFUTES"]] for row in probabilities]
    ranked = sorted(
        range(len(case_ids)),
        key=lambda index: (-dispute_scores[index], case_ids[index]),
    )
    max_review = int(len(case_ids) * REVIEW_RATE_CAP)
    support_thresholds = sorted({0.0, 1.0, *support_scores})
    refute_maximums = sorted({0.0, 1.0, *refute_scores})
    rows = []
    for review_count in range(max_review + 1):
        review = set(ranked[:review_count])
        for support_threshold in support_thresholds:
            for refute_maximum in refute_maximums:
                supported = {
                    index
                    for index in range(len(case_ids))
                    if index not in review
                    and support_scores[index] >= support_threshold
                    and refute_scores[index] <= refute_maximum
                }
                row = _policy_metrics(targets, supported, review)
                row.update(
                    {
                        "review_cases": review_count,
                        "review_rate": _ratio(review_count, len(case_ids)),
                        "support_probability_minimum": support_threshold,
                        "refutation_probability_maximum": refute_maximum,
                    }
                )
                rows.append(row)
    passing = [row for row in rows if row["gates"]["all_met"]]
    safe = [
        row
        for row in rows
        if row["gates"]["false_support_rate"]
        and row["gates"]["zero_refutation_false_supports"]
        and row["gates"]["review_rate"]
    ]
    selected = max(
        passing or safe,
        key=lambda row: (
            float(row["support_recall"]),
            float(row["disputed_review_coverage"]),
            -float(row["false_support_rate"]),
            -int(row["review_cases"]),
        ),
    )
    return {
        "candidate_count": len(rows),
        "all_gate_candidate_count": len(passing),
        "selected_kind": "all_gates" if passing else "best_safety_eligible_diagnostic",
        "selected_diagnostic": selected,
    }


def _policy_metrics(
    targets: list[str], supported: set[int], review: set[int]
) -> dict[str, Any]:
    support_total = sum(value == "SUPPORTS" for value in targets)
    negatives = len(targets) - support_total
    true_support = sum(targets[index] == "SUPPORTS" for index in supported)
    false_support = sum(targets[index] != "SUPPORTS" for index in supported)
    refute_false_support = sum(targets[index] == "REFUTES" for index in supported)
    disputed_total = sum(value == "DISPUTED" for value in targets)
    disputed_reviewed = sum(targets[index] == "DISPUTED" for index in review)
    recall = _ratio(true_support, support_total)
    false_rate = _ratio(false_support, negatives)
    dispute_coverage = _ratio(disputed_reviewed, disputed_total)
    review_rate = _ratio(len(review), len(targets))
    gates = {
        "support_recall": recall >= SUPPORT_RECALL_TARGET,
        "false_support_rate": false_rate <= FALSE_SUPPORT_CAP,
        "zero_refutation_false_supports": refute_false_support == 0,
        "disputed_review_coverage": dispute_coverage >= DISPUTED_REVIEW_TARGET,
        "review_rate": review_rate <= REVIEW_RATE_CAP,
    }
    return {
        "support_recall": round(recall, 4),
        "false_support_rate": round(false_rate, 4),
        "refutation_false_supports": refute_false_support,
        "disputed_review_coverage": round(dispute_coverage, 4),
        "true_supports": true_support,
        "false_supports": false_support,
        "gates": {**gates, "all_met": all(gates.values())},
    }


def _matrix(
    dataset: dict[str, Any],
    local_scores: dict[str, Any],
    auxiliary_scores: dict[str, Any],
    *,
    expected_split: str,
) -> tuple[list[list[float]], list[str], list[str]]:
    if dataset.get("split") != expected_split:
        raise V10FourwayError("Dataset split does not match the requested V10 split.")
    if (
        local_scores.get("split") != expected_split
        or auxiliary_scores.get("split") != expected_split
    ):
        raise V10FourwayError("Score artifacts do not match the requested V10 split.")
    if (
        local_scores.get("remote_inference_used") is not False
        or auxiliary_scores.get("remote_inference_used") is not False
    ):
        raise V10FourwayError("V10 feature scoring must be local-only.")
    if auxiliary_scores.get("evaluation_labels_sent") is not False:
        raise V10FourwayError("Evaluation labels must not be sent to feature models.")
    examples = _map_rows(dataset, "examples", "id")
    local = _map_rows(local_scores, "rows", "case_id")
    auxiliary = _map_rows(auxiliary_scores, "rows", "case_id")
    if set(examples) != set(local) or set(examples) != set(auxiliary):
        raise V10FourwayError("Dataset and score artifacts must cover identical cases.")
    if any(
        row.get("input_audit", {}).get("evaluation_label_sent") is not False
        for row in local.values()
    ):
        raise V10FourwayError("Evaluation labels must not be sent to local models.")
    case_ids = sorted(examples)
    features = [
        _features(examples[cid], local[cid], auxiliary[cid]) for cid in case_ids
    ]
    if any(len(row) != len(_feature_names()) for row in features):
        raise V10FourwayError("Feature rows do not match the frozen schema.")
    labels = [str(examples[cid]["source"]["claim_label"]) for cid in case_ids]
    if any(label not in LABELS for label in labels):
        raise V10FourwayError("Dataset contains an unknown four-way label.")
    if any(
        {"label", "target", "relation"} & set(examples[cid]["input"])
        for cid in case_ids
    ):
        raise V10FourwayError("Evaluation labels must not appear in model inputs.")
    return features, labels, case_ids


def _fit(
    features: list[list[float]], labels: list[str], *, regularization: float
) -> Any:
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    model = make_pipeline(
        StandardScaler(),
        LogisticRegression(
            C=regularization,
            class_weight="balanced",
            max_iter=5000,
            random_state=SEED,
            solver="lbfgs",
        ),
    )
    model.fit(features, labels)
    return model


def _map_rows(
    payload: dict[str, Any], field: str, key: str
) -> dict[str, dict[str, Any]]:
    rows = payload.get(field) or []
    result = {str(row[key]): row for row in rows}
    if not result or len(result) != len(rows):
        raise V10FourwayError(f"{field} must contain unique non-empty rows.")
    return result


def _ratio(numerator: float, denominator: float) -> float:
    return float(numerator / denominator) if denominator else 0.0


def _sha256_json(value: object) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _load(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _write(path: str | Path, value: dict[str, Any]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--training-dataset", required=True)
    parser.add_argument("--training-local-scores", required=True)
    parser.add_argument("--training-auxiliary-scores", required=True)
    parser.add_argument("--development-dataset", required=True)
    parser.add_argument("--development-local-scores", required=True)
    parser.add_argument("--development-auxiliary-scores", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    report = screen_fourway(
        _load(args.training_dataset),
        _load(args.training_local_scores),
        _load(args.training_auxiliary_scores),
        _load(args.development_dataset),
        _load(args.development_local_scores),
        _load(args.development_auxiliary_scores),
    )
    _write(args.output, report)
    print(
        json.dumps(
            {"status": report["status"], "selected": report["selected"]}, indent=2
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
