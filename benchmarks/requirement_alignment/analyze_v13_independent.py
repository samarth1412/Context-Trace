"""Evaluate the frozen V11 relation policy on V13 without retuning it."""

from __future__ import annotations

import argparse
import json
import statistics
from collections import Counter
from pathlib import Path
from typing import Any

from benchmarks.requirement_alignment.build_v13_independent import _sha256_json


STATES = ("supported", "contradicted", "unresolved", "review")
EXPECTED_SPLITS = {
    "development": "external_fiveway_v13_development",
    "heldout": "external_fiveway_v13_heldout",
}


class V13AnalysisError(RuntimeError):
    """Raised when a V13 score artifact is not aligned with its frozen data."""


def analyze(
    development: dict[str, Any],
    development_scores: dict[str, Any],
    heldout: dict[str, Any],
    heldout_scores: dict[str, Any],
    v11_report: dict[str, Any],
    v13_manifest: dict[str, Any],
) -> dict[str, Any]:
    selected = v11_report["selection"]["selected"]
    thresholds = {
        "entailment_minimum": float(selected["direct_four_way"]["entailment_minimum"]),
        "contradiction_minimum": float(
            selected["direct_four_way"]["contradiction_minimum"]
        ),
    }
    results = {
        "development": _evaluate(
            development,
            development_scores,
            expected_name="development",
            thresholds=thresholds,
        ),
        "heldout": _evaluate(
            heldout, heldout_scores, expected_name="heldout", thresholds=thresholds
        ),
    }
    expected_hashes = v13_manifest.get("dataset_sha256") or {}
    for name, dataset in (("development", development), ("heldout", heldout)):
        if expected_hashes.get(name) != _sha256_json(dataset):
            raise V13AnalysisError(f"{name} dataset differs from the V13 freeze.")
    heldout_metrics = results["heldout"]["safety"]
    gates = {
        "support_recall_at_least_0_50": heldout_metrics["support_recall"] >= 0.50,
        "false_support_rate_at_most_0_05": heldout_metrics["false_support_rate"]
        <= 0.05,
        "zero_contradiction_false_supports": heldout_metrics[
            "contradiction_false_supports"
        ]
        == 0,
        "partial_or_ambiguous_review_recall_at_least_0_80": heldout_metrics[
            "partial_or_ambiguous_review_recall"
        ]
        >= 0.80,
        "review_rate_at_most_0_50": heldout_metrics["review_rate"] <= 0.50,
    }
    all_met = all(gates.values())
    return {
        "schema_version": "contexttrace-v13-independent-analysis-1.0",
        "experiment": "contexttrace_v13_independent_contradictions",
        "protocol": {
            "candidate": "frozen_v11_relation_model_and_direct_thresholds",
            "v11_selected_epoch": selected["epoch"],
            "thresholds": thresholds,
            "development_labels_used_for_retuning": False,
            "heldout_labels_used_for_selection": False,
            "evaluation_labels_sent_to_model": False,
        },
        "results": results,
        "heldout_promotion_gates": {**gates, "all_met": all_met},
        "decision": "eligible_for_v13_policy_research"
        if all_met
        else "do_not_promote_v11",
        "next_experiment": (
            "fit a development-only five-way aggregation policy, then evaluate it once on a new untouched confirmation pack"
        ),
        "remote_inference_used": False,
        "stable_defaults_changed": False,
        "remote_provider_default_enabled": False,
        "local_only_network_calls": 0,
    }


def _evaluate(
    dataset: dict[str, Any],
    scores: dict[str, Any],
    *,
    expected_name: str,
    thresholds: dict[str, float],
) -> dict[str, Any]:
    expected_split = EXPECTED_SPLITS[expected_name]
    if dataset.get("split") != expected_split or scores.get("split") != expected_split:
        raise V13AnalysisError(f"{expected_name} split mismatch.")
    if scores.get("dataset_sha256") != _sha256_json(dataset):
        raise V13AnalysisError(f"{expected_name} scores do not match the dataset.")
    if (
        scores.get("evaluation_labels_sent") is not False
        or scores.get("remote_inference_used") is not False
    ):
        raise V13AnalysisError("V13 scoring must be label-blind and local-only.")
    examples = {str(row["id"]): row for row in dataset["examples"]}
    score_rows = {str(row["case_id"]): row for row in scores["rows"]}
    if set(examples) != set(score_rows):
        raise V13AnalysisError(f"{expected_name} case IDs are misaligned.")
    rows = []
    for case_id in sorted(examples):
        example = examples[case_id]
        probability_rows = [
            row["probabilities"] for row in score_rows[case_id]["per_evidence"]
        ]
        if not probability_rows:
            raise V13AnalysisError(f"{case_id} has no relation scores.")
        entailment = max(float(row["entailment"]) for row in probability_rows)
        contradiction = max(float(row["contradiction"]) for row in probability_rows)
        neutral = max(float(row["neutral"]) for row in probability_rows)
        prediction = _prediction(entailment, contradiction, thresholds)
        gold = str(example["target"]["verdict"])
        rows.append(
            {
                "case_id": case_id,
                "dataset": example["source"]["dataset"],
                "expected_verdict": gold,
                "expected_state": _expected_state(gold),
                "prediction": prediction,
                "max_probabilities": {
                    "entailment": entailment,
                    "contradiction": contradiction,
                    "neutral": neutral,
                },
            }
        )
    targets = [row["expected_state"] for row in rows]
    predictions = [row["prediction"] for row in rows]
    return {
        "cases": len(rows),
        "evidence_spans": scores["evidence_spans"],
        "latency": scores["latency"],
        "direct_four_state": _classification_metrics(targets, predictions),
        "safety": _safety_metrics(rows),
        "signal_means_by_gold": _signal_means(rows),
        "rows": rows,
    }


def _prediction(
    entailment: float, contradiction: float, thresholds: dict[str, float]
) -> str:
    support = entailment >= thresholds["entailment_minimum"]
    refute = contradiction >= thresholds["contradiction_minimum"]
    if support and refute:
        return "review"
    if support:
        return "supported"
    if refute:
        return "contradicted"
    return "unresolved"


def _expected_state(label: str) -> str:
    return {
        "supported": "supported",
        "contradicted": "contradicted",
        "unsupported": "unresolved",
        "partially_supported": "review",
        "unverifiable": "review",
    }[label]


def _safety_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    support_total = sum(row["expected_verdict"] == "supported" for row in rows)
    negatives = len(rows) - support_total
    predicted_support = [row for row in rows if row["prediction"] == "supported"]
    true_support = sum(
        row["expected_verdict"] == "supported" for row in predicted_support
    )
    false_by_gold = Counter(
        row["expected_verdict"]
        for row in predicted_support
        if row["expected_verdict"] != "supported"
    )
    review_targets = [
        row
        for row in rows
        if row["expected_verdict"] in {"partially_supported", "unverifiable"}
    ]
    reviewed_targets = sum(row["prediction"] == "review" for row in review_targets)
    return {
        "support_recall": round(_ratio(true_support, support_total), 4),
        "support_precision": round(_ratio(true_support, len(predicted_support)), 4),
        "false_support_rate": round(_ratio(sum(false_by_gold.values()), negatives), 4),
        "false_supports": sum(false_by_gold.values()),
        "false_supports_by_gold": dict(sorted(false_by_gold.items())),
        "unsupported_incorrectly_supported": false_by_gold["unsupported"],
        "contradiction_false_supports": false_by_gold["contradicted"],
        "contradiction_recall": round(
            _ratio(
                sum(
                    row["expected_verdict"] == "contradicted"
                    and row["prediction"] == "contradicted"
                    for row in rows
                ),
                sum(row["expected_verdict"] == "contradicted" for row in rows),
            ),
            4,
        ),
        "partial_or_ambiguous_review_recall": round(
            _ratio(reviewed_targets, len(review_targets)), 4
        ),
        "review_rate": round(
            _ratio(sum(row["prediction"] == "review" for row in rows), len(rows)), 4
        ),
    }


def _classification_metrics(
    targets: list[str], predictions: list[str]
) -> dict[str, Any]:
    confusion = {gold: {guess: 0 for guess in STATES} for gold in STATES}
    for gold, guess in zip(targets, predictions, strict=True):
        confusion[gold][guess] += 1
    f1s = []
    per_state = {}
    for state in STATES:
        tp = confusion[state][state]
        fp = sum(confusion[gold][state] for gold in STATES if gold != state)
        fn = sum(confusion[state][guess] for guess in STATES if guess != state)
        precision = _ratio(tp, tp + fp)
        recall = _ratio(tp, tp + fn)
        f1 = _ratio(2 * precision * recall, precision + recall)
        f1s.append(f1)
        per_state[state] = {
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
            "support": sum(confusion[state].values()),
        }
    return {
        "accuracy": round(
            _ratio(sum(confusion[state][state] for state in STATES), len(targets)), 4
        ),
        "macro_f1": round(statistics.fmean(f1s), 4),
        "per_state": per_state,
        "confusion": confusion,
    }


def _signal_means(rows: list[dict[str, Any]]) -> dict[str, Any]:
    labels = sorted({row["expected_verdict"] for row in rows})
    return {
        label: {
            relation: round(
                statistics.fmean(
                    row["max_probabilities"][relation]
                    for row in rows
                    if row["expected_verdict"] == label
                ),
                4,
            )
            for relation in ("entailment", "contradiction", "neutral")
        }
        for label in labels
    }


def _ratio(numerator: float, denominator: float) -> float:
    return numerator / denominator if denominator else 0.0


def _load(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--development", required=True)
    parser.add_argument("--development-scores", required=True)
    parser.add_argument("--heldout", required=True)
    parser.add_argument("--heldout-scores", required=True)
    parser.add_argument("--v11-report", required=True)
    parser.add_argument("--v13-manifest", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    report = analyze(
        _load(args.development),
        _load(args.development_scores),
        _load(args.heldout),
        _load(args.heldout_scores),
        _load(args.v11_report),
        _load(args.v13_manifest),
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "decision": report["decision"],
                "results": {
                    name: value["safety"] for name, value in report["results"].items()
                },
                "gates": report["heldout_promotion_gates"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
