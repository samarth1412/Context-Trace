"""Fit and evaluate a local meta-gate over development-only Jev signals."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
from pathlib import Path
from typing import Any

from benchmarks.external_fiveway_confirmation.ambiguity_features import evaluate_rows
from benchmarks.jev_claim_verification.experiment import LABEL_CRITERIA


AMBIGUITY_FEATURES = (
    "lexical",
    "reference",
    "structure_scope",
    "pragmatic",
    "verdict_instability",
)
VERDICT_PROBABILITIES = tuple(LABEL_CRITERIA)
FEATURE_ORDER = tuple(
    ["ambiguity.%s" % name for name in AMBIGUITY_FEATURES]
    + ["verdict_probability.%s" % label for label in VERDICT_PROBABILITIES]
)
THRESHOLDS = tuple(round(value / 100, 2) for value in range(20, 91, 5))
MAX_FALSE_SUPPORT_RATE = 0.05
RANDOM_SEED = 20260922


class LearnedGateError(RuntimeError):
    """Raised when learned-gate inputs or artifacts violate the contract."""


def signal_vector(signals: dict[str, Any]) -> list[float]:
    ambiguity = signals.get("ambiguity_features")
    probabilities = signals.get("base_probabilities")
    if not isinstance(ambiguity, dict) or not isinstance(probabilities, dict):
        raise LearnedGateError("Signals omit ambiguity features or verdict probabilities.")
    if set(ambiguity) != set(AMBIGUITY_FEATURES):
        raise LearnedGateError("Ambiguity feature schema does not match the frozen order.")
    if set(probabilities) != set(VERDICT_PROBABILITIES):
        raise LearnedGateError("Verdict probability schema does not match the five-way labels.")
    vector = [float(ambiguity[name]) for name in AMBIGUITY_FEATURES]
    vector.extend(float(probabilities[label]) for label in VERDICT_PROBABILITIES)
    if any(not math.isfinite(value) for value in vector):
        raise LearnedGateError("Signal vector contains a non-finite value.")
    return vector


def ambiguity_probability(signals: dict[str, Any], model: dict[str, Any]) -> float:
    vector = signal_vector(signals)
    means = [float(value) for value in model["standard_scaler"]["mean"]]
    scales = [float(value) for value in model["standard_scaler"]["scale"]]
    coefficients = [float(value) for value in model["logistic_regression"]["coefficients"]]
    intercept = float(model["logistic_regression"]["intercept"])
    if not len(vector) == len(means) == len(scales) == len(coefficients):
        raise LearnedGateError("Serialized model dimensions do not match its feature schema.")
    if any(scale <= 0.0 for scale in scales):
        raise LearnedGateError("Serialized standard-scaler scale must be positive.")
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


def learned_verdict(signals: dict[str, Any], policy: dict[str, Any]) -> str:
    probability = ambiguity_probability(signals, policy["model"])
    if probability >= float(policy["ambiguity_threshold"]):
        return "unverifiable"
    return str(signals["base_verdict"])


def fit_policy(result: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    try:
        import numpy as np
        from sklearn.linear_model import LogisticRegression
        from sklearn.metrics import average_precision_score, roc_auc_score
        from sklearn.pipeline import make_pipeline
        from sklearn.preprocessing import StandardScaler
    except ImportError as exc:
        raise LearnedGateError("numpy and scikit-learn are required to fit the gate.") from exc

    rows = result.get("rows") or []
    calibration = [row for row in rows if row["development_partition"] == "calibration"]
    validation = [row for row in rows if row["development_partition"] == "validation"]
    if len(calibration) != 75 or len(validation) != 50:
        raise LearnedGateError("Expected the frozen 75/50 development partition.")
    training_x = np.asarray([signal_vector(row["signals"]) for row in calibration])
    training_y = np.asarray(
        [row["expected_verdict"] == "unverifiable" for row in calibration], dtype=int
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
            "ambiguity_threshold": threshold,
            "max_false_support_rate": MAX_FALSE_SUPPORT_RATE,
        }
        metrics = evaluate_with_policy(calibration, candidate)
        qualifies = bool(
            metrics["false_support_rate"] <= MAX_FALSE_SUPPORT_RATE
            and metrics["unsupported_incorrectly_supported"] == 0
        )
        candidates.append(
            {
                "ambiguity_threshold": threshold,
                "qualifies": qualifies,
                "metrics": metrics,
            }
        )
    qualified = [candidate for candidate in candidates if candidate["qualifies"]]
    if not qualified:
        raise LearnedGateError("No learned gate meets the false-support constraints.")
    selected = max(
        qualified,
        key=lambda candidate: (
            candidate["metrics"]["macro_f1"],
            candidate["metrics"]["accuracy"],
            candidate["metrics"]["per_label_recall"]["supported"],
            candidate["ambiguity_threshold"],
        ),
    )
    policy_core = {
        "model": model,
        "ambiguity_threshold": selected["ambiguity_threshold"],
        "max_false_support_rate": MAX_FALSE_SUPPORT_RATE,
    }
    policy_id = hashlib.sha256(
        json.dumps(policy_core, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    policy = {
        "schema_version": "jev-learned-ambiguity-policy-1.0",
        "policy_id": policy_id,
        "selection_split": "development.calibration",
        "validation_split": "development.validation",
        "heldout_used_for_selection": False,
        "stable_defaults_changed": False,
        "remote_provider_default_enabled": False,
        "additional_remote_requests": 0,
        "policy": policy_core,
    }
    calibration_scores = [ambiguity_probability(row["signals"], model) for row in calibration]
    validation_scores = [ambiguity_probability(row["signals"], model) for row in validation]
    calibration_targets = [
        row["expected_verdict"] == "unverifiable" for row in calibration
    ]
    validation_targets = [row["expected_verdict"] == "unverifiable" for row in validation]
    analysis = {
        "schema_version": "jev-learned-ambiguity-analysis-1.0",
        "policy_id": policy_id,
        "base_calibration": evaluate_rows(calibration, policy=None),
        "base_validation": evaluate_rows(validation, policy=None),
        "selected_calibration": selected,
        "selected_validation": evaluate_with_policy(validation, policy_core),
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
        "score_distribution": {
            partition: _score_distribution(partition_rows, model=model)
            for partition, partition_rows in (
                ("calibration", calibration),
                ("validation", validation),
            )
        },
        "candidate_count": len(candidates),
        "qualifying_candidate_count": len(qualified),
        "candidates": candidates,
    }
    return policy, analysis


def evaluate_with_policy(
    rows: list[dict[str, Any]], policy: dict[str, Any]
) -> dict[str, Any]:
    copied = json.loads(json.dumps(rows))
    for row in copied:
        row["signals"]["base_verdict"] = learned_verdict(row["signals"], policy)
    return evaluate_rows(copied, policy=None)


def apply_policy(result: dict[str, Any], policy_artifact: dict[str, Any]) -> dict[str, Any]:
    policy = policy_artifact["policy"]
    rows = json.loads(json.dumps(result.get("rows") or []))
    for row in rows:
        probability = ambiguity_probability(row["signals"], policy["model"])
        final_verdict = learned_verdict(row["signals"], policy)
        row["learned_gate"] = {
            "ambiguity_probability": round(probability, 8),
            "ambiguity_threshold": policy["ambiguity_threshold"],
            "overrode_base_verdict": final_verdict != row["signals"]["base_verdict"],
            "final_verdict": final_verdict,
        }
    metric_rows = json.loads(json.dumps(rows))
    for row in metric_rows:
        row["signals"]["base_verdict"] = row["learned_gate"]["final_verdict"]
    return {
        "schema_version": "jev-learned-ambiguity-result-1.0",
        "policy_id": policy_artifact["policy_id"],
        "source_experiment": result.get("experiment"),
        "split": result.get("split"),
        "stable_defaults_changed": False,
        "remote_provider_default_enabled": False,
        "additional_remote_requests": 0,
        "metrics": evaluate_rows(metric_rows, policy=None),
        "rows": rows,
    }


def _score_distribution(
    rows: list[dict[str, Any]], *, model: dict[str, Any]
) -> dict[str, Any]:
    output = {}
    for label in LABEL_CRITERIA:
        values = [
            ambiguity_probability(row["signals"], model)
            for row in rows
            if row["expected_verdict"] == label
        ]
        output[label] = {
            "mean": round(statistics.fmean(values), 4),
            "median": round(statistics.median(values), 4),
            "minimum": round(min(values), 4),
            "maximum": round(max(values), 4),
        }
    return output


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
            parser.error("--policy requires --applied-output and cannot be combined with fit outputs")
        policy = json.loads(Path(args.policy).read_text(encoding="utf-8"))
        applied = apply_policy(result, policy)
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
                "threshold": policy["policy"]["ambiguity_threshold"],
                "calibration": analysis["selected_calibration"]["metrics"],
                "validation": analysis["selected_validation"],
                "binary_ranking": analysis["binary_ranking"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
