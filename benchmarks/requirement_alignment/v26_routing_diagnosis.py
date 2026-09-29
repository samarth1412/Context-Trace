"""Bounded saved-score routing diagnosis; no inference or release promotion."""

from __future__ import annotations

import argparse
from collections import Counter
import itertools
import json
import math
from pathlib import Path
from typing import Any

import numpy as np

from benchmarks.requirement_alignment.v14_fiveway_policy import (
    LABELS,
    _folds,
    _sha256_json,
    policy_metrics,
)

S, C, P, U, N = (
    LABELS.index(x)
    for x in (
        "supported",
        "contradicted",
        "partially_supported",
        "unverifiable",
        "unsupported",
    )
)


def validate_probabilities(values: Any) -> np.ndarray:
    p = np.asarray(values, dtype=float)
    if (
        p.ndim != 2
        or p.shape[1] != len(LABELS)
        or len(p) == 0
        or not np.isfinite(p).all()
        or (p < 0).any()
        or (p > 1).any()
        or not np.allclose(p.sum(axis=1), 1.0, atol=1e-7, rtol=0)
    ):
        raise ValueError("Expected nonempty finite five-way probability distributions.")
    return p


def route(values: Any, config: dict[str, Any]) -> np.ndarray:
    """Consume probabilities and explicit policy only; never targets or case IDs."""
    p = validate_probabilities(values)
    # Sum the remaining scores instead of subtracting from one to avoid cancellation.
    remaining = p[:, [C, P, U, N]].sum(axis=1)
    denominator = np.where(remaining > 0, remaining, 1.0)
    review = p[:, P] + p[:, U]
    if config["risk_mode"] == "absolute":
        contradiction_risk, review_risk = p[:, C], review
    elif config["risk_mode"] == "conditional_on_not_supported":
        contradiction_risk, review_risk = p[:, C] / denominator, review / denominator
    else:
        raise ValueError("Unknown risk mode.")
    for field in ("support_minimum", "contradiction_cap", "support_review_cap"):
        value = config[field]
        if (
            not isinstance(value, (int, float))
            or not math.isfinite(value)
            or not 0 <= value <= 1
        ):
            raise ValueError("Thresholds must be finite unit values.")
    accepted = (
        (p[:, S] >= config["support_minimum"])
        & (contradiction_risk <= config["contradiction_cap"])
        & (review_risk <= config["support_review_cap"])
    )
    threshold = config["review_threshold"]
    if threshold is None:
        labels = np.array([i for i in range(len(LABELS)) if i != S])
        result = labels[p[:, labels].argmax(axis=1)]
    else:
        if (
            not isinstance(threshold, (int, float))
            or not math.isfinite(threshold)
            or not 0 <= threshold <= 1
        ):
            raise ValueError("Review threshold must be a finite unit value.")
        review_labels, reject_labels = np.array([P, U]), np.array([C, N])
        result = np.where(
            review / denominator >= threshold,
            review_labels[p[:, review_labels].argmax(axis=1)],
            reject_labels[p[:, reject_labels].argmax(axis=1)],
        )
    result[accepted] = S
    return result.astype(np.int8)


def count_metrics(
    targets: np.ndarray, predictions: np.ndarray
) -> dict[str, np.ndarray]:
    """Vectorized metrics over policies; denominators stay on the original labels."""
    confusion = np.zeros((len(predictions), 5, 5), dtype=int)
    for gold, guess in itertools.product(range(5), repeat=2):
        confusion[:, gold, guess] = (predictions[:, targets == gold] == guess).sum(
            axis=1
        )
    diag = np.diagonal(confusion, axis1=1, axis2=2)
    denominator = confusion.sum(axis=1) + confusion.sum(axis=2)
    f1 = np.divide(
        2 * diag,
        denominator,
        out=np.zeros_like(diag, dtype=float),
        where=denominator != 0,
    )
    supported = targets == S
    review = np.isin(targets, [P, U])
    fs = ((predictions == S) & ~supported).sum(axis=1)
    return {
        "support_recall": (predictions[:, supported] == S).sum(axis=1)
        / max(1, int(supported.sum())),
        "false_support_rate": fs / max(1, int((~supported).sum())),
        "false_supports": fs,
        "contradiction_false_supports": (predictions[:, targets == C] == S).sum(axis=1),
        "partial_or_ambiguous_review_recall": np.isin(
            predictions[:, review], [P, U]
        ).sum(axis=1)
        / max(1, int(review.sum())),
        "review_rate": np.isin(predictions, [P, U]).sum(axis=1) / len(targets),
        "macro_f1": f1.mean(axis=1),
    }


def select(
    metrics: dict[str, np.ndarray],
    baseline: dict[str, Any],
    *,
    same_false_supports: bool = False,
) -> int | None:
    eligible = (
        (metrics["false_support_rate"] <= 0.05)
        & (metrics["contradiction_false_supports"] == 0)
        & (metrics["review_rate"] <= 0.50)
        & (metrics["support_recall"] >= baseline["support_recall"])
        & (
            metrics["partial_or_ambiguous_review_recall"]
            >= baseline["partial_or_ambiguous_review_recall"]
        )
    )
    if same_false_supports:
        eligible &= metrics["false_supports"] <= baseline["false_supports"]
    indexes = np.flatnonzero(eligible)
    if len(indexes) == 0:
        return None
    return int(
        max(
            indexes,
            key=lambda i: (
                metrics["support_recall"][i],
                metrics["partial_or_ambiguous_review_recall"][i],
                -metrics["false_supports"][i],
                metrics["macro_f1"][i],
                -int(i),
            ),
        )
    )


def diagnose(rows: list[dict[str, Any]], baseline: dict[str, Any]) -> dict[str, Any]:
    support = [r for r in rows if r["expected_verdict"] == "supported"]
    review = [
        r
        for r in rows
        if r["expected_verdict"] in {"partially_supported", "unverifiable"}
    ]
    missed = [
        r
        for r in review
        if r["prediction"] not in {"partially_supported", "unverifiable"}
    ]
    direct_true = [r for r in support if r["direct_prediction"] == "supported"]
    return {
        "supported_targets": len(support),
        "direct_true_supports": len(direct_true),
        "direct_true_supports_rejected_by_policy": sum(
            r["prediction"] != "supported" for r in direct_true
        ),
        "supported_targets_missed_by_direct_classifier": len(support)
        - len(direct_true),
        "supported_target_truncations": sum(
            r["input_tokens_before_truncation"] > 512 for r in support
        ),
        "review_targets": len(review),
        "missed_review_targets": len(missed),
        "missed_reviews_by_target": dict(
            Counter(r["expected_verdict"] for r in missed)
        ),
        "missed_reviews_by_prediction": dict(Counter(r["prediction"] for r in missed)),
        "extra_correct_reviews_needed": math.ceil(0.8 * len(review))
        - (len(review) - len(missed)),
        "remaining_review_slots": math.floor(0.5 * len(rows))
        - sum(r["prediction"] in {"partially_supported", "unverifiable"} for r in rows),
        "high_support_scored_contradictions": [
            {"case_id": r["case_id"], "probabilities": r["probabilities"]}
            for r in rows
            if r["expected_verdict"] == "contradicted"
            and r["probabilities"]["supported"] >= 0.9
        ],
        "baseline": baseline,
        "label_validity": "Inherited labels unresolved; no model-assisted proposals adopted or used for selection.",
    }


def run(source: dict[str, Any], protocol: dict[str, Any]) -> dict[str, Any]:
    if (
        source.get("experiment") != "contexttrace_v25_joint_representation"
        or _sha256_json(source) != protocol["source_sha256"]
    ):
        raise ValueError("Source differs from frozen V25 scores.")
    if (
        protocol.get("release_gate_eligible") is not False
        or source.get("future_confirmation_loaded") is not False
    ):
        raise ValueError("Only development diagnostics are allowed.")
    variant = source["variants"][protocol["variant"]]
    rows = variant["rows"]
    ids = [r["case_id"] for r in rows]
    if not rows or len(set(ids)) != len(ids):
        raise ValueError("Case IDs must be unique and nonempty.")
    targets = [r["expected_verdict"] for r in rows]
    if set(targets) != set(LABELS):
        raise ValueError("All five target classes are required.")
    y = np.array([LABELS.index(t) for t in targets])
    p = validate_probabilities(
        [[r["probabilities"][label] for label in LABELS] for r in rows]
    )
    old = variant["policy"]
    original_config = {
        "risk_mode": "absolute",
        "support_minimum": old["support_probability_minimum"],
        "contradiction_cap": old["contradiction_probability_maximum"],
        "support_review_cap": old["partial_or_ambiguous_probability_maximum"],
        "review_threshold": None,
    }
    original = route(p, original_config)
    if [LABELS[i] for i in original] != [r["prediction"] for r in rows]:
        raise ValueError("Legacy policy does not reproduce recorded predictions.")
    baseline = policy_metrics(targets, [LABELS[i] for i in original])
    if baseline != old["metrics"]:
        raise ValueError("Legacy metrics differ from saved report.")
    configs = [original_config]
    predictions = [original]
    for mode, s, c, r, threshold in itertools.product(
        protocol["risk_modes"],
        protocol["support_thresholds"],
        protocol["contradiction_caps"],
        protocol["support_review_caps"],
        protocol["review_thresholds"],
    ):
        config = {
            "risk_mode": mode,
            "support_minimum": s,
            "contradiction_cap": c,
            "support_review_cap": r,
            "review_threshold": threshold,
        }
        configs.append(config)
        predictions.append(route(p, config))
    all_predictions = np.array(predictions)
    metrics = count_metrics(y, all_predictions)

    def describe(index: int | None) -> dict[str, Any] | None:
        if index is None:
            return None
        return {
            "config": configs[index],
            "metrics": policy_metrics(
                targets, [LABELS[i] for i in all_predictions[index]]
            ),
        }

    chosen = select(metrics, baseline)
    same_safety = select(metrics, baseline, same_false_supports=True)
    assert chosen is not None and same_safety is not None  # The original is eligible.
    ablations = []
    for mode in protocol["risk_modes"]:
        for explicit in (False, True):
            indices = [
                i
                for i, c in enumerate(configs)
                if c["risk_mode"] == mode
                and (c["review_threshold"] is not None) == explicit
            ]
            subset = {k: v[indices] for k, v in metrics.items()}
            best = select(subset, baseline)
            ablations.append(
                {
                    "risk_mode": mode,
                    "explicit_review": explicit,
                    "policy_count": len(indices),
                    "best_nonregressing": describe(indices[best])
                    if best is not None
                    else None,
                }
            )
    # Diagnostic selection sensitivity only: existing OOF fits share training labels.
    fold_reports, cross_predictions = [], np.empty(len(y), dtype=np.int8)
    for fold, (train, test) in enumerate(_folds(targets)):
        train_targets = [targets[i] for i in train]
        train_baseline = policy_metrics(
            train_targets, [LABELS[i] for i in original[train]]
        )
        train_metrics = count_metrics(y[train], all_predictions[:, train])
        index = select(train_metrics, train_baseline)
        index = 0 if index is None else index
        cross_predictions[test] = all_predictions[index, test]
        fold_reports.append(
            {
                "fold": fold,
                "config": configs[index],
                "metrics": policy_metrics(
                    [targets[i] for i in test],
                    [LABELS[i] for i in all_predictions[index, test]],
                ),
            }
        )
    all_gates = (
        (metrics["support_recall"] >= 0.5)
        & (metrics["false_support_rate"] <= 0.05)
        & (metrics["contradiction_false_supports"] == 0)
        & (metrics["partial_or_ambiguous_review_recall"] >= 0.8)
        & (metrics["review_rate"] <= 0.5)
    )
    selected_predictions = all_predictions[chosen]
    return {
        "experiment": protocol["experiment"],
        "protocol_sha256": _sha256_json(protocol),
        "source_sha256": _sha256_json(source),
        "dataset_sha256": variant["dataset_sha256"],
        "resolved_model_revision": source["resolved_model_revision"],
        "status": "development_diagnostic_only",
        "diagnosis": diagnose(rows, baseline),
        "policies_evaluated_including_baseline": len(configs),
        "all_gate_policies": int(all_gates.sum()),
        "selected": describe(chosen),
        "selected_without_increasing_false_support_count": describe(same_safety),
        "ablations": ablations,
        "cross_fold_selection_sensitivity": {
            "independent_validation": False,
            "limitation": "Scores are reused from overlapping OOF model fits; this diagnoses threshold instability, not nested-CV or held-out performance.",
            "metrics": policy_metrics(targets, [LABELS[i] for i in cross_predictions]),
            "folds": fold_reports,
        },
        "rows": [
            {
                "case_id": r["case_id"],
                "input_sha256": r["input_sha256"],
                "expected_verdict": targets[i],
                "probabilities": r["probabilities"],
                "baseline_prediction": r["prediction"],
                "prediction": LABELS[selected_predictions[i]],
                "same_false_support_count_prediction": LABELS[
                    all_predictions[same_safety, i]
                ],
                "selection_sensitivity_prediction": LABELS[cross_predictions[i]],
            }
            for i, r in enumerate(rows)
        ],
        "stable_defaults_changed": False,
        "labels_changed": False,
        "evidence_changed": False,
        "model_retrained": False,
        "new_inference_calls": 0,
        "local_only_network_calls": 0,
        "future_confirmation_loaded": False,
        "release_gate_eligible": False,
        "limitations": [
            "Selection-biased development results against unresolved inherited labels.",
            "Original source prose may contain assessments; no new text is sent to any model.",
            "Conditional scores are routing ratios, not newly calibrated probabilities.",
            "No stable runtime integration or release promotion.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for field in ("source", "protocol", "output"):
        parser.add_argument(f"--{field}", required=True)
    args = parser.parse_args()
    result = run(
        json.loads(Path(args.source).read_text()),
        json.loads(Path(args.protocol).read_text()),
    )
    Path(args.output).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(
        json.dumps(
            {
                k: result[k]
                for k in (
                    "policies_evaluated_including_baseline",
                    "all_gate_policies",
                    "selected",
                    "selected_without_increasing_false_support_count",
                )
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
