"""Diagnose the consumed V19 transfer failure without selecting a new policy."""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
from collections import Counter
from pathlib import Path
from typing import Any

from benchmarks.requirement_alignment.v14_fiveway_policy import (
    LABELS,
    _sha256_json,
    policy_metrics,
)


EXPERIMENT = "contexttrace_v20_transfer_failure_audit"
SPLIT = "external_fiveway_v19_confirmation"


class V20AuditError(RuntimeError):
    """Raised when V20 inputs do not reproduce the consumed V19 run."""


def audit(
    dataset: dict[str, Any],
    relation_scores: dict[str, Any],
    atomic_scores: dict[str, Any],
    multispan_scores: dict[str, Any],
    confirmation: dict[str, Any],
) -> dict[str, Any]:
    aligned = _aligned_inputs(
        dataset, relation_scores, atomic_scores, multispan_scores, confirmation
    )
    rows = [
        _diagnostic_row(example, relation, atomic, multispan, result)
        for example, relation, atomic, multispan, result in zip(
            aligned["examples"],
            aligned["relations"],
            aligned["atomic"],
            aligned["multispan"],
            aligned["results"],
            strict=True,
        )
    ]
    false_supports = [row for row in rows if row["flags"]["false_support"]]
    expected = [row["expected_verdict"] for row in rows]
    predicted = [row["prediction"] for row in rows]
    metrics = policy_metrics(expected, predicted)
    if metrics != confirmation["metrics"]:
        raise V20AuditError("V20 does not reproduce the committed V19 metrics.")

    summaries = {
        label: _label_summary([row for row in rows if row["expected_verdict"] == label])
        for label in LABELS
    }
    guard_frontier = _posthoc_contradiction_guard(rows)
    return {
        "schema_version": "contexttrace-v20-transfer-failure-audit-1.0",
        "experiment": EXPERIMENT,
        "status": "diagnostic_complete",
        "protocol": {
            "split": SPLIT,
            "v19_is_consumed_diagnostic_data": True,
            "model_training_performed": False,
            "threshold_or_policy_selected": False,
            "confirmation_claim_made": False,
            "diagnostic_categories_are_rule_based_hypotheses": True,
            "raw_claim_or_evidence_text_retained": False,
        },
        "inputs": {
            "cases": len(rows),
            "dataset_sha256": _sha256_json(dataset),
            "relation_rows_sha256": _rows_hash(relation_scores),
            "atomic_rows_sha256": _rows_hash(atomic_scores),
            "multispan_rows_sha256": _rows_hash(multispan_scores),
            "confirmation_rows_sha256": _sha256_json(confirmation["rows"]),
        },
        "reproduced_metrics": metrics,
        "label_summaries": summaries,
        "failure_layers": {
            "verdict_head_collapse": {
                "unverifiable_predictions": sum(
                    row["prediction"] == "unverifiable" for row in rows
                ),
                "unverifiable_recall": summaries["unverifiable"]["recall"],
                "maximum_v14_unverifiable_probability": round(
                    max(row["signals"]["v14_unverifiable_probability"] for row in rows),
                    4,
                ),
                "mean_v14_unverifiable_probability": round(
                    statistics.fmean(
                        row["signals"]["v14_unverifiable_probability"] for row in rows
                    ),
                    4,
                ),
            },
            "relation_transfer": {
                "contradiction_cases": summaries["contradicted"]["cases"],
                "correct_contradictions": summaries["contradicted"]["correct"],
                "contradiction_recall": summaries["contradicted"]["recall"],
                "contradictions_incorrectly_supported": sum(
                    row["expected_verdict"] == "contradicted"
                    and row["prediction"] == "supported"
                    for row in rows
                ),
                "incorrectly_supported_with_visible_relation_contradiction": sum(
                    row["flags"]["false_support"]
                    and row["signals"]["maximum_relation_contradiction"] >= 0.5
                    for row in rows
                ),
            },
            "completeness_overconfidence": {
                "false_supports": len(false_supports),
                "false_supports_from_v15": sum(
                    row["flags"]["false_support"]
                    and row["v15_prediction"] == "supported"
                    for row in rows
                ),
                "false_supports_with_completeness_at_least_0_8": sum(
                    row["flags"]["false_support"]
                    and row["signals"]["complete_support_probability"] >= 0.8
                    for row in rows
                ),
                "false_supports_from_v17_rescue": sum(
                    row["flags"]["false_support_from_v17_rescue"] for row in rows
                ),
            },
            "evidence_or_decomposition_risk": {
                "cases_with_empty_multispan_requirement": sum(
                    row["signals"]["empty_multispan_requirements"] > 0 for row in rows
                ),
                "errors_with_empty_multispan_requirement": sum(
                    row["prediction"] != row["expected_verdict"]
                    and row["signals"]["empty_multispan_requirements"] > 0
                    for row in rows
                ),
                "mean_selected_evidence_spans": round(
                    statistics.fmean(
                        row["signals"]["selected_evidence_spans"] for row in rows
                    ),
                    4,
                ),
            },
        },
        "false_support_analysis": {
            "count": len(false_supports),
            "by_expected_verdict": dict(
                sorted(
                    Counter(row["expected_verdict"] for row in false_supports).items()
                )
            ),
            "rows": false_supports,
        },
        "posthoc_relation_contradiction_guard": guard_frontier,
        "prior_jev_evidence": {
            "source": "ragtruth_sentence_extension_heldout_jev_and_frozen_cascade",
            "direct_cases": 72,
            "direct_accuracy": 0.75,
            "direct_observed_label_macro_f1": 0.7668,
            "direct_false_support_rate": 0.0833,
            "resolved_model": "jev-1.13.0",
            "mean_latency_ms": 237.927,
            "total_tokens": 149499,
            "cascade_five_way_accuracy": 0.7639,
            "cascade_false_support_rate": 0.0208,
            "cascade_supported_recall": 0.7917,
            "cascade_remote_call_rate": 0.9583,
            "not_directly_comparable_to_v19": True,
        },
        "decision": "do_not_tune_thresholds_build_domain_diverse_local_candidate",
        "recommended_next_work": [
            "train relation and verdict features on domain-diverse claim-evidence data",
            "add an explicit cross-span conflict feature and hard support guard",
            "learn unsupported and unverifiable behavior from evidence-insufficiency and conflict examples",
            "calibrate support probability by source domain without using dataset identity as a feature",
            "evaluate Jev only as an optional review-path signal until a fresh safety test passes",
            "freeze the next candidate before accessing a new confirmation source",
        ],
        "remote_inference_used": False,
        "stable_defaults_changed": False,
        "remote_provider_default_enabled": False,
        "local_only_network_calls": 0,
    }


def _diagnostic_row(
    example: dict[str, Any],
    relation: dict[str, Any],
    atomic: dict[str, Any],
    multispan: dict[str, Any],
    result: dict[str, Any],
) -> dict[str, Any]:
    relation_probabilities = [row["probabilities"] for row in relation["per_evidence"]]
    requirements = list(multispan["requirements"])
    expected = str(result["expected_verdict"])
    prediction = str(result["prediction"])
    claim = str(example["input"]["claim"])
    false_support = prediction == "supported" and expected != "supported"
    return {
        "case_id": str(example["id"]),
        "claim_sha256": hashlib.sha256(claim.encode("utf-8")).hexdigest(),
        "dataset": str(example["source"]["dataset"]),
        "expected_verdict": expected,
        "prediction": prediction,
        "v14_prediction": str(result["v14_prediction"]),
        "v15_prediction": str(result["v15_prediction"]),
        "signals": {
            "selected_evidence_spans": len(example["input"]["evidence"]),
            "maximum_relation_entailment": round(
                max(float(row["entailment"]) for row in relation_probabilities), 4
            ),
            "maximum_relation_contradiction": round(
                max(float(row["contradiction"]) for row in relation_probabilities), 4
            ),
            "maximum_relation_neutral": round(
                max(float(row["neutral"]) for row in relation_probabilities), 4
            ),
            "v14_supported_probability": float(
                result["v14_probabilities"]["supported"]
            ),
            "v14_unverifiable_probability": float(
                result["v14_probabilities"]["unverifiable"]
            ),
            "complete_support_probability": float(
                result["complete_support_probability"]
            ),
            "atomic_verdict": str(atomic["atomic_verdict"]),
            "atomic_requirements": len(atomic["requirements"]),
            "multispan_requirements": len(requirements),
            "empty_multispan_requirements": sum(
                row["selected_span_count"] == 0 for row in requirements
            ),
            "minimum_single_span_entailment": float(
                result["minimum_single_span_entailment"]
            ),
            "maximum_multispan_contradiction": round(
                max(
                    float(row["summary"]["best_contradiction"]) for row in requirements
                ),
                4,
            ),
        },
        "flags": {
            "incorrect": prediction != expected,
            "false_support": false_support,
            "false_support_from_v17_rescue": bool(
                false_support and result["v15_prediction"] != "supported"
            ),
            "visible_relation_contradiction": max(
                float(row["contradiction"]) for row in relation_probabilities
            )
            >= 0.5,
            "cross_span_conflict_signal": bool(
                max(float(row["entailment"]) for row in relation_probabilities) >= 0.5
                and max(float(row["contradiction"]) for row in relation_probabilities)
                >= 0.5
            ),
        },
    }


def _label_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    label = rows[0]["expected_verdict"]
    return {
        "cases": len(rows),
        "correct": sum(row["prediction"] == label for row in rows),
        "recall": round(sum(row["prediction"] == label for row in rows) / len(rows), 4),
        "prediction_counts": dict(
            sorted(Counter(row["prediction"] for row in rows).items())
        ),
        "signal_means": {
            name: round(
                statistics.fmean(float(row["signals"][name]) for row in rows), 4
            )
            for name in (
                "maximum_relation_entailment",
                "maximum_relation_contradiction",
                "maximum_relation_neutral",
                "v14_supported_probability",
                "v14_unverifiable_probability",
                "complete_support_probability",
                "minimum_single_span_entailment",
            )
        },
    }


def _posthoc_contradiction_guard(rows: list[dict[str, Any]]) -> dict[str, Any]:
    thresholds = sorted(
        {
            0.0,
            1.0,
            *(
                float(row["signals"]["maximum_relation_contradiction"])
                for row in rows
                if row["prediction"] == "supported"
            ),
        }
    )
    candidates = []
    targets = [row["expected_verdict"] for row in rows]
    for threshold in thresholds:
        predictions = [
            "partially_supported"
            if row["prediction"] == "supported"
            and row["signals"]["maximum_relation_contradiction"] > threshold
            else row["prediction"]
            for row in rows
        ]
        metrics = policy_metrics(targets, predictions)
        candidates.append(
            {
                "maximum_relation_contradiction": threshold,
                "support_recall": metrics["support_recall"],
                "false_support_rate": metrics["false_support_rate"],
                "contradiction_false_supports": metrics["contradiction_false_supports"],
                "review_rate": metrics["review_rate"],
                "all_gates_met": metrics["gates"]["all_met"],
            }
        )
    safe = [
        row
        for row in candidates
        if row["false_support_rate"] <= 0.05
        and row["contradiction_false_supports"] == 0
    ]
    best_safe = max(safe, key=lambda row: row["support_recall"])
    return {
        "diagnostic_only_not_a_selected_policy": True,
        "candidate_count": len(candidates),
        "any_candidate_passes_all_gates": any(
            row["all_gates_met"] for row in candidates
        ),
        "best_safe_candidate": best_safe,
        "conclusion": "a_relation_contradiction_cap_cannot_recover_safe_support_recall",
    }


def _aligned_inputs(
    dataset: dict[str, Any],
    relation_scores: dict[str, Any],
    atomic_scores: dict[str, Any],
    multispan_scores: dict[str, Any],
    confirmation: dict[str, Any],
) -> dict[str, list[dict[str, Any]]]:
    if dataset.get("split") != SPLIT or not dataset.get("examples"):
        raise V20AuditError("V20 requires the nonempty consumed V19 dataset.")
    dataset_hash = _sha256_json(dataset)
    for artifact in (relation_scores, atomic_scores, multispan_scores):
        if (
            artifact.get("split") != SPLIT
            or artifact.get("dataset_sha256") != dataset_hash
            or artifact.get("remote_inference_used") is not False
        ):
            raise V20AuditError("V20 score artifacts do not match frozen V19.")
    if (
        confirmation.get("status") != "confirmation_failed"
        or confirmation.get("inputs", {}).get("dataset_sha256") != dataset_hash
        or confirmation.get("protocol", {}).get("one_shot_evaluation") is not True
    ):
        raise V20AuditError("V20 requires the committed failed V19 confirmation.")
    mappings = [
        {str(row.get("case_id", row.get("id"))): row for row in values}
        for values in (
            dataset["examples"],
            relation_scores["rows"],
            atomic_scores["rows"],
            multispan_scores["rows"],
            confirmation["rows"],
        )
    ]
    case_ids = set(mappings[0])
    if not case_ids or any(set(mapping) != case_ids for mapping in mappings[1:]):
        raise V20AuditError("V20 inputs contain misaligned case IDs.")
    ordered = sorted(case_ids)
    return {
        name: [mapping[case_id] for case_id in ordered]
        for name, mapping in zip(
            ("examples", "relations", "atomic", "multispan", "results"),
            mappings,
            strict=True,
        )
    }


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
    parser.add_argument("--relation-scores", required=True)
    parser.add_argument("--atomic-scores", required=True)
    parser.add_argument("--multispan-scores", required=True)
    parser.add_argument("--confirmation-result", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    result = audit(
        _load(args.dataset),
        _load(args.relation_scores),
        _load(args.atomic_scores),
        _load(args.multispan_scores),
        _load(args.confirmation_result),
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
                "failure_layers": result["failure_layers"],
                "decision": result["decision"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
