"""Evaluate development-only V17 decomposition and multi-span completeness."""

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
from benchmarks.requirement_alignment.v15_atomic_completeness import (
    _binary_metrics,
    _candidate_key,
    _candidates,
    _out_of_fold_completeness,
    _select_policy,
    atomic_feature_vector,
)


EXPERIMENT = "contexttrace_v17_multispan_completeness"
SUMMARY_SIGNALS = (
    "best_entailment",
    "best_contradiction",
    "best_neutral",
    "best_single_entailment",
    "best_pair_entailment",
    "best_triple_entailment",
    "multispan_entailment_gain",
    "mean_entailment",
)
DECOMPOSITION_SOURCES = (
    "semantic_core_v2_1",
    "local_quality",
    "atomic_coverage_v2",
    "whole_claim_fallback",
)
FROZEN_SINGLE_SPAN_ENTAILMENT_MINIMUM = 0.70


class V17CompletenessError(RuntimeError):
    """Raised when V17 violates its development-only evaluation contract."""


def train_and_assess(
    development: dict[str, Any],
    relation_scores: dict[str, Any],
    v14_report: dict[str, Any],
    v15_atomic_scores: dict[str, Any],
    v15_report: dict[str, Any],
    v17_scores: dict[str, Any],
) -> dict[str, Any]:
    inputs = _aligned_inputs(
        development,
        relation_scores,
        v14_report,
        v15_atomic_scores,
        v15_report,
        v17_scores,
    )
    targets = inputs["targets"]
    folds = _folds(targets)
    candidates = []
    probability_sets: dict[str, list[float]] = {}
    feature_sets = _feature_sets(inputs)
    for feature_set_name, matrix, feature_names in feature_sets:
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
    selected_classifier = max(candidates, key=_candidate_key)
    selected_classifier_name = str(selected_classifier["candidate"])
    selected_classifier_policy = _select_policy(
        targets,
        inputs["v14_predictions"],
        inputs["v14_probabilities"],
        probability_sets[selected_classifier_name],
    )
    selected_classifier_policy.pop("predictions")
    rescue = _frozen_rescue_policy(inputs)
    predictions = rescue.pop("predictions")
    metrics = rescue["metrics"]
    rows = [
        {
            "case_id": case_id,
            "expected_verdict": target,
            "v14_prediction": v14_prediction,
            "v15_prediction": v15_prediction,
            "minimum_single_span_entailment": round(single_entailment, 4),
            "prediction": prediction,
        }
        for case_id, target, v14_prediction, v15_prediction, single_entailment, prediction in zip(
            inputs["case_ids"],
            targets,
            inputs["v14_predictions"],
            inputs["v15_predictions"],
            inputs["minimum_single_span_entailments"],
            predictions,
            strict=True,
        )
    ]
    return {
        "schema_version": "contexttrace-v17-multispan-completeness-1.0",
        "experiment": EXPERIMENT,
        "status": (
            "development_candidate"
            if metrics["gates"]["all_met"]
            else "rejected_development_candidate"
        ),
        "protocol": {
            "selection_split": DEVELOPMENT_SPLIT,
            "cross_validation": "five_fold_stratified_out_of_fold",
            "random_seed": SEED,
            "heldout_loaded": False,
            "heldout_used_for_selection": False,
            "evaluation_labels_in_model_features": False,
            "existing_contradiction_and_ambiguity_guards_preserved": True,
            "rescue_threshold_selected_without_evaluation_labels": True,
            "fresh_confirmation_required": True,
        },
        "inputs": {
            "development_cases": len(targets),
            "development_sha256": _sha256_json(development),
            "relation_rows_sha256": _sha256_json(relation_scores["rows"]),
            "v14_rows_sha256": _sha256_json(v14_report["rows"]),
            "v15_atomic_rows_sha256": _sha256_json(
                [
                    {key: value for key, value in row.items() if key != "latency_ms"}
                    for row in v15_atomic_scores["rows"]
                ]
            ),
            "v15_rows_sha256": _sha256_json(v15_report["rows"]),
            "v17_rows_sha256": _sha256_json(
                [
                    {key: value for key, value in row.items() if key != "latency_ms"}
                    for row in v17_scores["rows"]
                ]
            ),
            "v17_requirements": v17_scores["requirements"],
            "v17_evidence_combinations": v17_scores["combinations"],
            "model_id": v17_scores["model"]["model_id"],
        },
        "features": {
            "sets": {
                name: {"count": len(names), "names": names}
                for name, _, names in feature_sets
            },
            "sources": [
                "V17 deterministic decomposition selection",
                "V17 frozen local NLI evidence-combination distributions",
                "V15 frozen atomic requirement distributions",
                "V14 out-of-fold five-way probabilities",
                "V11 full-claim relation and lexical features",
            ],
            "dataset_identity_included": False,
            "evaluation_labels_included": False,
        },
        "search": {
            "candidate_count": len(candidates),
            "policy_candidates_per_model": len(THRESHOLDS) ** 3,
            "candidates": candidates,
        },
        "classifier_screen": {
            "selected": {
                **selected_classifier,
                "policy": selected_classifier_policy,
            },
            "all_gate_candidate_count": sum(
                row["policy"]["all_gate_candidate_count"] for row in candidates
            ),
        },
        "selected": {
            "candidate": "v15_v14_supported_route_v17_single_entailment_rescue",
            "baseline": "v15_selected_policy",
            "route_requirement": "v14_prediction_supported",
            "minimum_single_span_entailment": FROZEN_SINGLE_SPAN_ENTAILMENT_MINIMUM,
            "threshold_source": "frozen_atomic_coverage_entailment_threshold",
            **rescue,
        },
        "v15_baseline_metrics": v15_report["selected"]["policy"]["metrics"],
        "promotion_gates": {
            "support_recall_minimum": 0.50,
            "false_support_rate_maximum": 0.05,
            "zero_contradiction_false_supports": True,
            "partial_or_ambiguous_review_recall_minimum": 0.80,
            "review_rate_maximum": 0.50,
            "all_met": bool(metrics["gates"]["all_met"]),
        },
        "decision": (
            "freeze_v17_development_candidate"
            if metrics["gates"]["all_met"]
            else "do_not_promote_v17"
        ),
        "rows": rows,
        "remote_inference_used": False,
        "stable_defaults_changed": False,
        "remote_provider_default_enabled": False,
        "local_only_network_calls": 0,
    }


def _frozen_rescue_policy(inputs: dict[str, Any]) -> dict[str, Any]:
    predictions = []
    promoted_case_ids = []
    correct_promotions = 0
    for case_id, target, v14_prediction, v15_prediction, score in zip(
        inputs["case_ids"],
        inputs["targets"],
        inputs["v14_predictions"],
        inputs["v15_predictions"],
        inputs["minimum_single_span_entailments"],
        strict=True,
    ):
        promote = bool(
            v15_prediction != "supported"
            and v14_prediction == "supported"
            and score >= FROZEN_SINGLE_SPAN_ENTAILMENT_MINIMUM
        )
        prediction = "supported" if promote else str(v15_prediction)
        predictions.append(prediction)
        if promote:
            promoted_case_ids.append(str(case_id))
            correct_promotions += int(target == "supported")
    return {
        "promoted_case_ids": promoted_case_ids,
        "promotions": len(promoted_case_ids),
        "correct_promotions": correct_promotions,
        "promotion_precision": round(correct_promotions / len(promoted_case_ids), 4)
        if promoted_case_ids
        else 0.0,
        "metrics": policy_metrics(inputs["targets"], predictions),
        "predictions": predictions,
    }


def multispan_feature_vector(row: dict[str, Any]) -> tuple[list[str], list[float]]:
    requirements = list(row.get("requirements") or [])
    if not requirements:
        raise V17CompletenessError("V17 score row has no requirements.")
    names = ["v17.log_requirement_count"]
    values = [math.log1p(len(requirements))]
    source = str(row.get("decomposition_source") or "")
    for candidate in DECOMPOSITION_SOURCES:
        names.append(f"v17.decomposition.{candidate}")
        values.append(float(source == candidate))
    selected_counts = [float(value["selected_span_count"]) for value in requirements]
    names.extend(
        (
            "v17.selected_spans.minimum",
            "v17.selected_spans.maximum",
            "v17.selected_spans.mean",
        )
    )
    values.extend(
        (
            min(selected_counts),
            max(selected_counts),
            statistics.fmean(selected_counts),
        )
    )
    for signal in SUMMARY_SIGNALS:
        items = [float(value["summary"][signal]) for value in requirements]
        names.extend(
            f"v17.{signal}.{statistic}"
            for statistic in ("minimum", "maximum", "mean", "std", "median")
        )
        values.extend(
            (
                min(items),
                max(items),
                statistics.fmean(items),
                statistics.pstdev(items),
                statistics.median(items),
            )
        )
    best_entailments = [
        float(value["summary"]["best_entailment"]) for value in requirements
    ]
    for threshold in (0.4, 0.6, 0.7, 0.8, 0.9):
        names.append(f"v17.best_entailment.fraction_ge_{threshold:.1f}")
        values.append(
            sum(value >= threshold for value in best_entailments) / len(requirements)
        )
    names.extend(
        (
            "v17.best_combination.fraction_multispan",
            "v17.multispan_gain.fraction_ge_0.10",
        )
    )
    values.extend(
        (
            sum(
                int(value["summary"]["best_entailment_combination_size"]) > 1
                for value in requirements
            )
            / len(requirements),
            sum(
                float(value["summary"]["multispan_entailment_gain"]) >= 0.10
                for value in requirements
            )
            / len(requirements),
        )
    )
    return names, [float(value) for value in values]


def _aligned_inputs(
    development: dict[str, Any],
    relation_scores: dict[str, Any],
    v14_report: dict[str, Any],
    v15_atomic_scores: dict[str, Any],
    v15_report: dict[str, Any],
    v17_scores: dict[str, Any],
) -> dict[str, Any]:
    artifacts = (development, relation_scores, v15_atomic_scores, v17_scores)
    if any(artifact.get("split") != DEVELOPMENT_SPLIT for artifact in artifacts):
        raise V17CompletenessError("V17 accepts only V13 development artifacts.")
    for report in (v14_report, v15_report):
        protocol = report.get("protocol") or {}
        if (
            protocol.get("selection_split") != DEVELOPMENT_SPLIT
            or protocol.get("heldout_loaded") is not False
            or protocol.get("heldout_used_for_selection") is not False
        ):
            raise V17CompletenessError(
                "V17 report input does not attest development-only selection."
            )
    expected_hash = _sha256_json(development)
    if any(
        artifact.get("dataset_sha256") != expected_hash
        for artifact in (relation_scores, v15_atomic_scores, v17_scores)
    ):
        raise V17CompletenessError("V17 score artifacts do not match development data.")
    if (
        relation_scores.get("remote_inference_used") is not False
        or relation_scores.get("evaluation_labels_sent") is not False
        or v15_atomic_scores.get("remote_inference_used") is not False
        or v15_atomic_scores.get("input_contract", {}).get("evaluation_labels_sent")
        is not False
        or v17_scores.get("remote_inference_used") is not False
        or v17_scores.get("input_contract", {}).get("evaluation_labels_sent")
        is not False
        or v17_scores.get("local_only_network_calls") != 0
    ):
        raise V17CompletenessError("V17 inputs must be local and label-blind.")
    examples = {str(row["id"]): row for row in development.get("examples") or []}
    relations = {str(row["case_id"]): row for row in relation_scores.get("rows") or []}
    v14 = {str(row["case_id"]): row for row in v14_report.get("rows") or []}
    atomic = {str(row["case_id"]): row for row in v15_atomic_scores.get("rows") or []}
    v15 = {str(row["case_id"]): row for row in v15_report.get("rows") or []}
    v17 = {str(row["case_id"]): row for row in v17_scores.get("rows") or []}
    if not examples or not set(examples) == set(relations) == set(v14) == set(
        atomic
    ) == set(v15) == set(v17):
        raise V17CompletenessError("V17 case IDs are empty or misaligned.")
    case_ids = sorted(examples)
    return {
        "case_ids": case_ids,
        "examples": [examples[case_id] for case_id in case_ids],
        "relations": [relations[case_id] for case_id in case_ids],
        "v14_probabilities": [
            [float(v14[case_id]["probabilities"][label]) for label in LABELS]
            for case_id in case_ids
        ],
        "v14_predictions": [v14[case_id]["prediction"] for case_id in case_ids],
        "v15_atomic": [atomic[case_id] for case_id in case_ids],
        "v15_predictions": [v15[case_id]["prediction"] for case_id in case_ids],
        "v17": [v17[case_id] for case_id in case_ids],
        "minimum_single_span_entailments": [
            min(
                float(requirement["summary"]["best_single_entailment"])
                for requirement in v17[case_id]["requirements"]
            )
            for case_id in case_ids
        ],
        "targets": [examples[case_id]["target"]["verdict"] for case_id in case_ids],
    }


def _feature_sets(
    inputs: dict[str, Any],
) -> list[tuple[str, list[list[float]], list[str]]]:
    v17_matrix = []
    atomic_matrix = []
    relation_matrix = []
    v17_names: list[str] | None = None
    atomic_names: list[str] | None = None
    relation_names: list[str] | None = None
    for example, relation, atomic, multispan in zip(
        inputs["examples"],
        inputs["relations"],
        inputs["v15_atomic"],
        inputs["v17"],
        strict=True,
    ):
        current_v17_names, current_v17 = multispan_feature_vector(multispan)
        current_atomic_names, current_atomic = atomic_feature_vector(atomic)
        current_relation_names, current_relation = feature_vector(example, relation)
        if v17_names is None:
            v17_names = current_v17_names
            atomic_names = current_atomic_names
            relation_names = current_relation_names
        elif (
            v17_names != current_v17_names
            or atomic_names != current_atomic_names
            or relation_names != current_relation_names
        ):
            raise V17CompletenessError("V17 feature schemas are inconsistent.")
        v17_matrix.append(current_v17)
        atomic_matrix.append(current_atomic)
        relation_matrix.append(current_relation)
    probabilities = inputs["v14_probabilities"]
    probability_names = [f"v14.probability.{label}" for label in LABELS]
    v17_names = list(v17_names or [])
    atomic_names = list(atomic_names or [])
    relation_names = list(relation_names or [])
    return [
        ("v17_multispan", v17_matrix, v17_names),
        (
            "v17_multispan_v14",
            [
                left + right
                for left, right in zip(v17_matrix, probabilities, strict=True)
            ],
            v17_names + probability_names,
        ),
        (
            "v17_multispan_v14_relation",
            [
                multi + probability + relation
                for multi, probability, relation in zip(
                    v17_matrix, probabilities, relation_matrix, strict=True
                )
            ],
            v17_names + probability_names + relation_names,
        ),
        (
            "v17_multispan_v15_atomic_v14_relation",
            [
                multi + atomic + probability + relation
                for multi, atomic, probability, relation in zip(
                    v17_matrix,
                    atomic_matrix,
                    probabilities,
                    relation_matrix,
                    strict=True,
                )
            ],
            v17_names + atomic_names + probability_names + relation_names,
        ),
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--development", required=True)
    parser.add_argument("--relation-scores", required=True)
    parser.add_argument("--v14-report", required=True)
    parser.add_argument("--v15-atomic-scores", required=True)
    parser.add_argument("--v15-report", required=True)
    parser.add_argument("--v17-scores", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)

    def load(path: str) -> dict[str, Any]:
        return json.loads(Path(path).read_text(encoding="utf-8"))

    report = train_and_assess(
        load(args.development),
        load(args.relation_scores),
        load(args.v14_report),
        load(args.v15_atomic_scores),
        load(args.v15_report),
        load(args.v17_scores),
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "selected": report["selected"],
                "promotion_gates": report["promotion_gates"],
                "decision": report["decision"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
