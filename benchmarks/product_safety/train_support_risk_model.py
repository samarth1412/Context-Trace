"""Train and evaluate the tiny local ContextTrace support-risk model."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

from build_checker_development_corpus import DEFAULT_OUTPUT, build_corpus
from contexttrace.verify.schema import TraceContext
from contexttrace.verify.semantic_core_v2 import build_pinned_nli, verify_nli_artifact
from contexttrace.verify.semantic_core_v2_1.risk_model import (
    RISK_FEATURE_NAMES,
    RISK_FEATURE_VERSION,
    extract_risk_features,
)

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
DEFAULT_ARTIFACT = (
    REPO_ROOT
    / "packages"
    / "contexttrace"
    / "contexttrace"
    / "verify"
    / "semantic_core_v2_1"
    / "artifacts"
    / "support-risk-v1.json"
)
DEFAULT_REPORT = HERE / "support-risk-training-report-v1.json"
MODEL_VERSION = "contexttrace-support-risk-v1.1.0"
EPOCHS = 3000
LEARNING_RATE = 0.08
L2 = 0.01


def train(model_path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    stored = json.loads(DEFAULT_OUTPUT.read_text(encoding="utf-8"))
    if stored != build_corpus():
        raise ValueError("Checker development corpus is stale; rebuild it first.")
    lock = verify_nli_artifact(model_path)
    judge = build_pinned_nli(model_path)
    rows: list[dict[str, Any]] = []
    for case in stored["cases"]:
        verdict = judge.verify_claim(
            query=str(case["query"]),
            claim=str(case["claim"]),
            contexts=[
                TraceContext(
                    id=str(case["id"]),
                    text=str(case["premise"]),
                )
            ],
        )
        features = extract_risk_features(
            str(case["claim"]),
            str(case["premise"]),
            verdict,
        )
        rows.append(
            {
                "id": case["id"],
                "split": case["split"],
                "source_family": case["source_family"],
                "label": int(case["label"]),
                "base_probability": float(
                    (verdict.raw.get("nli_scores") or {}).get(
                        "entailment",
                        verdict.confidence if verdict.verdict == "supported" else 0.0,
                    )
                ),
                "features": [features[name] for name in RISK_FEATURE_NAMES],
            }
        )

    train_rows = [row for row in rows if row["split"] == "train"]
    validation_rows = [row for row in rows if row["split"] == "validation"]
    test_rows = [row for row in rows if row["split"] == "test"]
    means, scales = _normalization(train_rows)
    weights, intercept = _fit(train_rows, means, scales)
    for row in rows:
        row["learned_probability"] = _predict(
            row["features"],
            means,
            scales,
            weights,
            intercept,
        )
    support_threshold = _select_support_threshold(validation_rows)
    reject_threshold = min(0.5, support_threshold - 0.05)
    artifact: dict[str, Any] = {
        "schema_version": "1.0",
        "model_version": MODEL_VERSION,
        "feature_version": RISK_FEATURE_VERSION,
        "feature_names": list(RISK_FEATURE_NAMES),
        "means": [round(value, 9) for value in means],
        "scales": [round(value, 9) for value in scales],
        "weights": [round(value, 9) for value in weights],
        "intercept": round(intercept, 9),
        "support_threshold": support_threshold,
        "reject_threshold": round(reject_threshold, 6),
        "training": {
            "corpus_payload_sha256": stored["payload_sha256"],
            "train_cases": len(train_rows),
            "validation_cases": len(validation_rows),
            "optimizer": "deterministic_full_batch_logistic_gradient_descent",
            "epochs": EPOCHS,
            "learning_rate": LEARNING_RATE,
            "l2": L2,
        },
    }
    artifact["payload_sha256"] = _canonical_sha256(artifact)
    report = {
        "schema_version": "1.0",
        "evidence_class": "synthetic_development_only_not_research_evidence",
        "model_version": MODEL_VERSION,
        "artifact_sha256": artifact["payload_sha256"],
        "model_lock": {
            "model_id": lock["model_id"],
            "model_revision": lock["model_revision"],
            "artifact_manifest_sha256": lock["artifact_manifest_sha256"],
        },
        "corpus_payload_sha256": stored["payload_sha256"],
        "support_threshold": support_threshold,
        "reject_threshold": reject_threshold,
        "validation": {
            "base": _metrics(validation_rows, "base_probability", 0.8, 0.8),
            "learned": _metrics(
                validation_rows,
                "learned_probability",
                support_threshold,
                reject_threshold,
            ),
        },
        "test": {
            "base": _metrics(test_rows, "base_probability", 0.8, 0.8),
            "learned": _metrics(
                test_rows,
                "learned_probability",
                support_threshold,
                reject_threshold,
            ),
        },
        "limitations": [
            "All cases are synthetic development examples.",
            "Test means held-out development families, not an untouched research test.",
            "External evaluation is required before any SOTA claim.",
        ],
    }
    return artifact, report


def _normalization(rows: list[dict[str, Any]]) -> tuple[list[float], list[float]]:
    width = len(RISK_FEATURE_NAMES)
    means = [sum(row["features"][i] for row in rows) / len(rows) for i in range(width)]
    scales = []
    for index, mean in enumerate(means):
        variance = sum((row["features"][index] - mean) ** 2 for row in rows) / len(rows)
        scales.append(max(math.sqrt(variance), 1e-6))
    return means, scales


def _fit(
    rows: list[dict[str, Any]],
    means: list[float],
    scales: list[float],
) -> tuple[list[float], float]:
    weights = [0.0] * len(RISK_FEATURE_NAMES)
    intercept = 0.0
    normalized = [
        [
            (value - mean) / scale
            for value, mean, scale in zip(
                row["features"],
                means,
                scales,
                strict=True,
            )
        ]
        for row in rows
    ]
    for _ in range(EPOCHS):
        gradient = [0.0] * len(weights)
        intercept_gradient = 0.0
        for row, features in zip(rows, normalized, strict=True):
            probability = _sigmoid(
                intercept
                + sum(
                    weight * value
                    for weight, value in zip(weights, features, strict=True)
                )
            )
            error = probability - row["label"]
            intercept_gradient += error
            for index, value in enumerate(features):
                gradient[index] += error * value
        count = len(rows)
        intercept -= LEARNING_RATE * intercept_gradient / count
        for index in range(len(weights)):
            regularized = gradient[index] / count + L2 * weights[index]
            weights[index] -= LEARNING_RATE * regularized
    return weights, intercept


def _predict(
    features: list[float],
    means: list[float],
    scales: list[float],
    weights: list[float],
    intercept: float,
) -> float:
    normalized = [
        (value - mean) / scale
        for value, mean, scale in zip(features, means, scales, strict=True)
    ]
    return _sigmoid(
        intercept
        + sum(weight * value for weight, value in zip(weights, normalized, strict=True))
    )


def _select_support_threshold(rows: list[dict[str, Any]]) -> float:
    candidates = [value / 100 for value in range(50, 100)]
    scored = []
    for threshold in candidates:
        metrics = _metrics(rows, "learned_probability", threshold, threshold)
        if metrics["false_entailment_rate"] <= 0.02:
            scored.append(
                (
                    metrics["accuracy"],
                    metrics["positive_recall"],
                    -threshold,
                    threshold,
                )
            )
    if not scored:
        return 0.99
    return round(max(scored)[3], 6)


def _metrics(
    rows: list[dict[str, Any]],
    probability_key: str,
    threshold: float,
    reject_threshold: float,
) -> dict[str, Any]:
    labels = [int(row["label"]) for row in rows]
    probabilities = [float(row[probability_key]) for row in rows]
    predictions = [int(probability >= threshold) for probability in probabilities]
    positives = sum(labels)
    negatives = len(labels) - positives
    false_positives = sum(
        prediction == 1 and label == 0
        for prediction, label in zip(predictions, labels, strict=True)
    )
    covered = [
        index
        for index, probability in enumerate(probabilities)
        if probability >= threshold or probability <= reject_threshold
    ]
    covered_errors = sum(predictions[index] != labels[index] for index in covered)
    return {
        "cases": len(rows),
        "accuracy": _ratio(
            sum(
                prediction == label
                for prediction, label in zip(predictions, labels, strict=True)
            ),
            len(rows),
        ),
        "positive_recall": _ratio(
            sum(
                prediction == 1 and label == 1
                for prediction, label in zip(predictions, labels, strict=True)
            ),
            positives,
        ),
        "false_entailment_rate": _ratio(false_positives, negatives),
        "selective_coverage": _ratio(len(covered), len(rows)),
        "selective_risk": _ratio(covered_errors, len(covered)),
        "ece_10_bin": _ece(probabilities, labels),
        "aurc": _aurc(probabilities, labels, threshold),
    }


def _ece(probabilities: list[float], labels: list[int]) -> float:
    total = len(labels)
    value = 0.0
    for index in range(10):
        low = index / 10
        high = (index + 1) / 10
        members = [
            item
            for item, probability in enumerate(probabilities)
            if low <= probability < high or (index == 9 and probability == 1.0)
        ]
        if not members:
            continue
        confidence = sum(probabilities[item] for item in members) / len(members)
        accuracy = sum(labels[item] for item in members) / len(members)
        value += len(members) / total * abs(accuracy - confidence)
    return round(value, 6)


def _aurc(
    probabilities: list[float],
    labels: list[int],
    threshold: float,
) -> float:
    rows = sorted(
        (
            (
                max(probability, 1.0 - probability),
                int(probability >= threshold) != label,
            )
            for probability, label in zip(probabilities, labels, strict=True)
        ),
        reverse=True,
    )
    cumulative_errors = 0
    risks: list[float] = []
    for covered, (_, error) in enumerate(rows, start=1):
        cumulative_errors += int(error)
        risks.append(cumulative_errors / covered)
    return round(sum(risks) / len(risks), 6) if risks else 0.0


def _sigmoid(value: float) -> float:
    if value >= 0:
        exp = math.exp(-value)
        return 1.0 / (1.0 + exp)
    exp = math.exp(value)
    return exp / (1.0 + exp)


def _ratio(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 6) if denominator else 0.0


def _canonical_sha256(payload: dict[str, Any]) -> str:
    unsigned = dict(payload)
    unsigned.pop("payload_sha256", None)
    raw = json.dumps(
        unsigned,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-path", type=Path, required=True)
    parser.add_argument("--artifact", type=Path, default=DEFAULT_ARTIFACT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args(argv)
    artifact, report = train(args.model_path)
    args.artifact.write_text(
        json.dumps(artifact, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    args.report.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
