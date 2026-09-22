"""Fit and apply a local complete-support gate over typed Jev signals."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
from collections import Counter
from pathlib import Path
from typing import Any

from benchmarks.external_fiveway_confirmation.completeness_data import LABELS
from benchmarks.external_fiveway_confirmation.completeness_signals import FEATURES
from benchmarks.external_fiveway_confirmation.completeness_signals import (
    SUPPORT_EXTENT_CRITERIA,
)
from benchmarks.jev_claim_verification.experiment import LABEL_CRITERIA


FEATURE_NAMES = tuple(FEATURES)
PROBABILITY_NAMES = tuple(LABEL_CRITERIA)
EXTENT_PROBABILITY_NAMES = tuple(SUPPORT_EXTENT_CRITERIA)
FEATURE_ORDER = tuple(
    ["completeness.%s" % name for name in FEATURE_NAMES]
    + ["verdict_probability.%s" % name for name in PROBABILITY_NAMES]
    + ["support_extent_probability.%s" % name for name in EXTENT_PROBABILITY_NAMES]
    + ["local_support_probability"]
)
THRESHOLDS = tuple(round(value / 100, 2) for value in range(5, 96, 5))
MAX_PARTIAL_TO_SUPPORTED_RATE = 0.05
MIN_SUPPORTED_RECALL = 0.50
MIN_PARTIAL_RECALL = 0.70
RANDOM_SEED = 20260923


class CompletenessGateError(RuntimeError):
    """Raised when completeness fitting or scoring violates the contract."""


def signal_vector(signals: dict[str, Any]) -> list[float]:
    features = signals.get("completeness_features")
    probabilities = signals.get("base_probabilities")
    extent_probabilities = signals.get("support_extent_probabilities")
    if not isinstance(features, dict) or set(features) != set(FEATURE_NAMES):
        raise CompletenessGateError("Completeness feature schema does not match.")
    if not isinstance(probabilities, dict) or set(probabilities) != set(PROBABILITY_NAMES):
        raise CompletenessGateError("Verdict probability schema does not match.")
    if not isinstance(extent_probabilities, dict) or set(extent_probabilities) != set(
        EXTENT_PROBABILITY_NAMES
    ):
        raise CompletenessGateError("Support-extent probability schema does not match.")
    vector = [float(features[name]) for name in FEATURE_NAMES]
    vector.extend(float(probabilities[name]) for name in PROBABILITY_NAMES)
    vector.extend(float(extent_probabilities[name]) for name in EXTENT_PROBABILITY_NAMES)
    local_probability = float(signals.get("local_support_probability", float("nan")))
    vector.append(local_probability)
    if any(not math.isfinite(value) for value in vector):
        raise CompletenessGateError("Completeness signal vector contains a non-finite value.")
    return vector


def support_probability(signals: dict[str, Any], model: dict[str, Any]) -> float:
    vector = signal_vector(signals)
    means = [float(value) for value in model["standard_scaler"]["mean"]]
    scales = [float(value) for value in model["standard_scaler"]["scale"]]
    coefficients = [float(value) for value in model["logistic_regression"]["coefficients"]]
    intercept = float(model["logistic_regression"]["intercept"])
    if not len(vector) == len(means) == len(scales) == len(coefficients):
        raise CompletenessGateError("Serialized completeness model dimensions do not match.")
    if any(scale <= 0.0 for scale in scales):
        raise CompletenessGateError("Serialized scaler values must be positive.")
    logit = intercept + sum(
        coefficient * ((value - mean) / scale)
        for value, mean, scale, coefficient in zip(
            vector, means, scales, coefficients, strict=True
        )
    )
    if logit >= 0:
        return 1.0 / (1.0 + math.exp(-logit))
    exponential = math.exp(logit)
    return exponential / (1.0 + exponential)


def gated_verdict(signals: dict[str, Any], policy: dict[str, Any]) -> str:
    base = str(signals["base_verdict"])
    if base not in LABELS:
        return base
    probability = support_probability(signals, policy["model"])
    return "supported" if probability >= float(policy["support_threshold"]) else "partially_supported"


def metrics(rows: list[dict[str, Any]], policy: dict[str, Any] | None = None) -> dict[str, Any]:
    gold = [str(row["expected_verdict"]) for row in rows]
    predicted = [
        str(row["signals"]["base_verdict"])
        if policy is None
        else gated_verdict(row["signals"], policy)
        for row in rows
    ]
    correct = sum(g == p for g, p in zip(gold, predicted, strict=True))
    recalls = {}
    f1s = []
    for label in LABELS:
        tp = sum(g == p == label for g, p in zip(gold, predicted, strict=True))
        fp = sum(g != label and p == label for g, p in zip(gold, predicted, strict=True))
        fn = sum(g == label and p != label for g, p in zip(gold, predicted, strict=True))
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        recalls[label] = round(recall, 4)
        f1s.append(2 * precision * recall / (precision + recall) if precision + recall else 0.0)
    partial_total = sum(g == "partially_supported" for g in gold)
    partial_to_supported = sum(
        g == "partially_supported" and p == "supported"
        for g, p in zip(gold, predicted, strict=True)
    )
    return {
        "cases": len(rows),
        "accuracy": round(correct / len(rows), 4),
        "macro_f1": round(statistics.fmean(f1s), 4),
        "per_label_recall": recalls,
        "partial_incorrectly_supported_count": partial_to_supported,
        "partial_incorrectly_supported_rate": round(
            partial_to_supported / partial_total, 4
        ),
        "other_verdict_count": sum(p not in LABELS for p in predicted),
        "confusion": {
            label: dict(
                sorted(Counter(p for g, p in zip(gold, predicted, strict=True) if g == label).items())
            )
            for label in LABELS
        },
    }


def fit_policy(result: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    try:
        import numpy as np
        from sklearn.linear_model import LogisticRegression
        from sklearn.metrics import average_precision_score, roc_auc_score
        from sklearn.pipeline import make_pipeline
        from sklearn.preprocessing import StandardScaler
    except ImportError as exc:
        raise CompletenessGateError("numpy and scikit-learn are required to fit the gate.") from exc
    rows = result.get("rows") or []
    calibration = [row for row in rows if row["development_partition"] == "calibration"]
    validation = [row for row in rows if row["development_partition"] == "validation"]
    if not calibration or not validation:
        raise CompletenessGateError("Both development partitions are required.")
    training_x = np.asarray([signal_vector(row["signals"]) for row in calibration])
    training_y = np.asarray(
        [row["expected_verdict"] == "supported" for row in calibration], dtype=int
    )
    estimator = make_pipeline(
        StandardScaler(),
        LogisticRegression(
            C=1.0,
            class_weight="balanced",
            max_iter=500,
            random_state=RANDOM_SEED,
            solver="lbfgs",
        ),
    )
    estimator.fit(training_x, training_y)
    scaler = estimator.named_steps["standardscaler"]
    logistic = estimator.named_steps["logisticregression"]
    model = {
        "feature_order": list(FEATURE_ORDER),
        "standard_scaler": {
            "mean": [float(value) for value in scaler.mean_],
            "scale": [float(value) for value in scaler.scale_],
        },
        "logistic_regression": {
            "solver": "lbfgs",
            "C": 1.0,
            "class_weight": "balanced",
            "random_seed": RANDOM_SEED,
            "coefficients": [float(value) for value in logistic.coef_[0]],
            "intercept": float(logistic.intercept_[0]),
        },
    }
    candidates = []
    for threshold in THRESHOLDS:
        candidate = {
            "model": model,
            "support_threshold": threshold,
            "max_partial_to_supported_rate": MAX_PARTIAL_TO_SUPPORTED_RATE,
        }
        candidate_metrics = metrics(calibration, candidate)
        qualifies = bool(
            candidate_metrics["partial_incorrectly_supported_rate"]
            <= MAX_PARTIAL_TO_SUPPORTED_RATE
        )
        meets_recall_targets = bool(
            candidate_metrics["per_label_recall"]["supported"] >= MIN_SUPPORTED_RECALL
            and candidate_metrics["per_label_recall"]["partially_supported"]
            >= MIN_PARTIAL_RECALL
        )
        candidates.append(
            {
                "support_threshold": threshold,
                "qualifies_safety": qualifies,
                "meets_recall_targets": meets_recall_targets,
                "metrics": candidate_metrics,
            }
        )
    qualified = [candidate for candidate in candidates if candidate["qualifies_safety"]]
    if not qualified:
        raise CompletenessGateError("No completeness threshold meets calibration error constraint.")
    selected = max(
        qualified,
        key=lambda candidate: (
            candidate["metrics"]["macro_f1"],
            candidate["metrics"]["accuracy"],
            candidate["metrics"]["per_label_recall"]["supported"],
            candidate["support_threshold"],
        ),
    )
    policy_core = {
        "model": model,
        "support_threshold": selected["support_threshold"],
        "max_partial_to_supported_rate": MAX_PARTIAL_TO_SUPPORTED_RATE,
    }
    policy_id = hashlib.sha256(
        json.dumps(policy_core, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    policy = {
        "schema_version": "jev-completeness-policy-1.0",
        "policy_id": policy_id,
        "selection_split": "development.calibration",
        "validation_split": "development.validation",
        "heldout_used_for_selection": False,
        "stable_defaults_changed": False,
        "remote_provider_default_enabled": False,
        "additional_remote_requests": 0,
        "policy": policy_core,
    }
    calibration_scores = [support_probability(row["signals"], model) for row in calibration]
    validation_scores = [support_probability(row["signals"], model) for row in validation]
    calibration_targets = [row["expected_verdict"] == "supported" for row in calibration]
    validation_targets = [row["expected_verdict"] == "supported" for row in validation]
    base_validation = metrics(validation)
    selected_validation = metrics(validation, policy_core)
    analysis = {
        "schema_version": "jev-completeness-analysis-1.0",
        "policy_id": policy_id,
        "base_calibration": metrics(calibration),
        "base_validation": base_validation,
        "selected_calibration": selected,
        "selected_validation": selected_validation,
        "prespecified_success_criteria": {
            "supported_recall_at_least": MIN_SUPPORTED_RECALL,
            "partial_recall_at_least": MIN_PARTIAL_RECALL,
            "partial_to_supported_rate_at_most": MAX_PARTIAL_TO_SUPPORTED_RATE,
            "macro_f1_must_improve": True,
        },
        "meets_prespecified_success": bool(
            selected_validation["per_label_recall"]["supported"] >= MIN_SUPPORTED_RECALL
            and selected_validation["per_label_recall"]["partially_supported"]
            >= MIN_PARTIAL_RECALL
            and selected_validation["partial_incorrectly_supported_rate"]
            <= MAX_PARTIAL_TO_SUPPORTED_RATE
            and selected_validation["macro_f1"] > base_validation["macro_f1"]
        ),
        "binary_ranking": {
            "calibration_roc_auc": round(
                float(roc_auc_score(calibration_targets, calibration_scores)), 4
            ),
            "calibration_average_precision": round(
                float(average_precision_score(calibration_targets, calibration_scores)), 4
            ),
            "validation_roc_auc": round(
                float(roc_auc_score(validation_targets, validation_scores)), 4
            ),
            "validation_average_precision": round(
                float(average_precision_score(validation_targets, validation_scores)), 4
            ),
        },
        "candidate_count": len(candidates),
        "qualifying_candidate_count": len(qualified),
        "candidates": candidates,
    }
    return policy, analysis


def apply_policy(result: dict[str, Any], artifact: dict[str, Any]) -> dict[str, Any]:
    policy = artifact["policy"]
    rows = json.loads(json.dumps(result.get("rows") or []))
    for row in rows:
        probability = support_probability(row["signals"], policy["model"])
        final_verdict = gated_verdict(row["signals"], policy)
        row["completeness_gate"] = {
            "support_probability": round(probability, 8),
            "support_threshold": policy["support_threshold"],
            "overrode_base_verdict": final_verdict != row["signals"]["base_verdict"],
            "final_verdict": final_verdict,
        }
    metric_rows = json.loads(json.dumps(rows))
    for row in metric_rows:
        row["signals"]["base_verdict"] = row["completeness_gate"]["final_verdict"]
    return {
        "schema_version": "jev-completeness-result-1.0",
        "policy_id": artifact["policy_id"],
        "split": result.get("split"),
        "stable_defaults_changed": False,
        "remote_provider_default_enabled": False,
        "additional_remote_requests": 0,
        "metrics": metrics(metric_rows),
        "rows": rows,
    }


def _write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--result", required=True)
    parser.add_argument("--policy-output")
    parser.add_argument("--analysis-output")
    parser.add_argument("--policy")
    parser.add_argument("--applied-output")
    args = parser.parse_args(argv)
    result = json.loads(Path(args.result).read_text(encoding="utf-8"))
    if args.policy:
        if not args.applied_output or args.policy_output or args.analysis_output:
            parser.error("--policy requires --applied-output and no fit outputs")
        artifact = json.loads(Path(args.policy).read_text(encoding="utf-8"))
        applied = apply_policy(result, artifact)
        _write(Path(args.applied_output), applied)
        print(json.dumps({"policy_id": applied["policy_id"], **applied["metrics"]}, indent=2))
        return 0
    if not args.policy_output or not args.analysis_output or args.applied_output:
        parser.error("fitting requires --policy-output and --analysis-output")
    policy, analysis = fit_policy(result)
    _write(Path(args.policy_output), policy)
    _write(Path(args.analysis_output), analysis)
    print(
        json.dumps(
            {
                "policy_id": policy["policy_id"],
                "threshold": policy["policy"]["support_threshold"],
                "calibration": analysis["selected_calibration"]["metrics"],
                "validation": analysis["selected_validation"],
                "meets_prespecified_success": analysis["meets_prespecified_success"],
                "binary_ranking": analysis["binary_ranking"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
