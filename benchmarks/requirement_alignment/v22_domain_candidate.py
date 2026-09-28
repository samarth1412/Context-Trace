"""Cross-validate a domain-diverse five-way candidate on V21 development data."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from benchmarks.requirement_alignment.v14_fiveway_policy import (
    LABELS,
    SEED,
    _folds,
    _out_of_fold_probabilities,
    _select_policy,
    _selection_key,
    _sha256_json,
    classification_metrics,
    feature_vector,
)
from benchmarks.requirement_alignment.v15_atomic_completeness import (
    atomic_feature_vector,
)
from benchmarks.requirement_alignment.v17_multispan_completeness import (
    multispan_feature_vector,
)


EXPERIMENT = "contexttrace_v22_domain_diverse_candidate"
SPLIT = "external_fiveway_v21_development"


class V22CandidateError(RuntimeError):
    """Raised when V22 inputs violate the development-only contract."""


def train_and_cross_validate(
    development: dict[str, Any],
    relation_scores: dict[str, Any],
    atomic_scores: dict[str, Any],
    multispan_scores: dict[str, Any],
    *,
    experiment: str = EXPERIMENT,
) -> dict[str, Any]:
    inputs = _aligned_inputs(
        development, relation_scores, atomic_scores, multispan_scores
    )
    folds = _folds(inputs["targets"])
    candidates = []
    probability_sets: dict[str, list[list[float]]] = {}
    for name, estimator in _candidates():
        probabilities = _out_of_fold_probabilities(
            inputs["matrix"], inputs["targets"], folds, estimator=estimator
        )
        direct_predictions = [
            LABELS[max(range(len(values)), key=values.__getitem__)]
            for values in probabilities
        ]
        direct = classification_metrics(inputs["targets"], direct_predictions)
        policy = _select_policy(inputs["targets"], probabilities)
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
    selected_policy = _select_policy(inputs["targets"], probability_sets[selected_name])
    predictions = selected_policy.pop("predictions")
    metrics = selected_policy["metrics"]
    candidate_version = "v23" if "_v23_" in experiment else "v22"
    rows = [
        {
            "case_id": case_id,
            "expected_verdict": target,
            "prediction": prediction,
            "probabilities": {
                label: round(float(probability), 8)
                for label, probability in zip(LABELS, values, strict=True)
            },
            "maximum_relation_contradiction": round(signal, 4),
        }
        for case_id, target, prediction, values, signal in zip(
            inputs["case_ids"],
            inputs["targets"],
            predictions,
            probability_sets[selected_name],
            inputs["maximum_relation_contradiction"],
            strict=True,
        )
    ]
    return {
        "schema_version": "contexttrace-v22-domain-candidate-1.0",
        "experiment": experiment,
        "status": (
            "development_candidate"
            if metrics["gates"]["all_met"]
            else "rejected_development_candidate"
        ),
        "protocol": {
            "selection_split": SPLIT,
            "cross_validation": "five_fold_stratified_out_of_fold",
            "random_seed": SEED,
            "development_only": True,
            "future_confirmation_loaded": False,
            "future_confirmation_used_for_selection": False,
            "evaluation_labels_in_model_features": False,
            "dataset_identity_in_model_features": False,
        },
        "inputs": {
            "development_cases": len(inputs["case_ids"]),
            "development_sha256": _sha256_json(development),
            "relation_rows_sha256": _rows_hash(relation_scores),
            "atomic_rows_sha256": _rows_hash(atomic_scores),
            "multispan_rows_sha256": _rows_hash(multispan_scores),
            "relation_evidence_spans": relation_scores["evidence_spans"],
            "atomic_requirements": atomic_scores["requirements"],
            "multispan_requirements": multispan_scores["requirements"],
            "evidence_combinations": multispan_scores["combinations"],
            "local_model_id": relation_scores["model"]["model_id"],
            "atomic_model_id": atomic_scores["model"]["model_id"],
            "multispan_model_id": multispan_scores["model"]["model_id"],
        },
        "features": {
            "count": len(inputs["feature_names"]),
            "names": inputs["feature_names"],
            "sources": [
                "hash-verified local per-evidence relation probabilities",
                "deterministic lexical overlap, negation, number, and length signals",
                "local atomic-requirement relation distributions",
                "local multi-span decomposition and evidence-combination distributions",
                "explicit relation and multi-span conflict interactions",
            ],
            "dataset_identity_included": False,
            "evaluation_labels_included": False,
        },
        "search": {
            "candidate_count": len(candidates),
            "policy_selection_uses_development_only": True,
            "candidates": candidates,
        },
        "selected": {
            **selected,
            "policy": selected_policy,
        },
        "promotion_gates": {
            "support_recall_minimum": 0.50,
            "false_support_rate_maximum": 0.05,
            "zero_contradiction_false_supports": True,
            "partial_or_ambiguous_review_recall_minimum": 0.80,
            "review_rate_maximum": 0.50,
            "all_met": bool(metrics["gates"]["all_met"]),
        },
        "error_counts": {
            "false_supports_with_relation_contradiction_at_least_0_5": sum(
                target != "supported" and prediction == "supported" and signal >= 0.5
                for target, prediction, signal in zip(
                    inputs["targets"],
                    predictions,
                    inputs["maximum_relation_contradiction"],
                    strict=True,
                )
            ),
            "unverifiable_predictions": sum(
                prediction == "unverifiable" for prediction in predictions
            ),
        },
        "decision": (
            f"freeze_{candidate_version}_development_candidate"
            if metrics["gates"]["all_met"]
            else f"do_not_promote_{candidate_version}"
        ),
        "rows": rows,
        "remote_inference_used": False,
        "stable_defaults_changed": False,
        "remote_provider_default_enabled": False,
        "local_only_network_calls": 0,
    }


def combined_feature_vector(
    example: dict[str, Any],
    relation: dict[str, Any],
    atomic: dict[str, Any],
    multispan: dict[str, Any],
) -> tuple[list[str], list[float]]:
    relation_names, relation_values = feature_vector(example, relation)
    atomic_names, atomic_values = atomic_feature_vector(atomic)
    multispan_names, multispan_values = multispan_feature_vector(multispan)
    probabilities = [row["probabilities"] for row in relation["per_evidence"]]
    maximum_entailment = max(float(row["entailment"]) for row in probabilities)
    maximum_contradiction = max(float(row["contradiction"]) for row in probabilities)
    maximum_neutral = max(float(row["neutral"]) for row in probabilities)
    summaries = [row["summary"] for row in multispan["requirements"]]
    maximum_multispan_contradiction = max(
        float(row["best_contradiction"]) for row in summaries
    )
    maximum_multispan_entailment = max(
        float(row["best_entailment"]) for row in summaries
    )
    minimum_multispan_entailment = min(
        float(row["best_entailment"]) for row in summaries
    )
    conflict_names = [
        "v22.conflict.minimum_relation_maxima",
        "v22.conflict.relation_maxima_product",
        "v22.conflict.relation_both_ge_0_5",
        "v22.conflict.multispan_minimum_maxima",
        "v22.conflict.multispan_maxima_product",
        "v22.completeness.minimum_multispan_entailment",
        "v22.completeness.relation_entailment_minus_neutral",
        "v22.completeness.multispan_entailment_minus_contradiction",
        "v22.evidence.empty_requirement_fraction",
    ]
    conflict_values = [
        min(maximum_entailment, maximum_contradiction),
        maximum_entailment * maximum_contradiction,
        float(maximum_entailment >= 0.5 and maximum_contradiction >= 0.5),
        min(maximum_multispan_entailment, maximum_multispan_contradiction),
        maximum_multispan_entailment * maximum_multispan_contradiction,
        minimum_multispan_entailment,
        maximum_entailment - maximum_neutral,
        maximum_multispan_entailment - maximum_multispan_contradiction,
        sum(row["selected_span_count"] == 0 for row in multispan["requirements"])
        / len(multispan["requirements"]),
    ]
    return (
        relation_names + atomic_names + multispan_names + conflict_names,
        relation_values + atomic_values + multispan_values + conflict_values,
    )


def _candidates() -> list[tuple[str, Any]]:
    from sklearn.ensemble import ExtraTreesClassifier, HistGradientBoostingClassifier
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    candidates: list[tuple[str, Any]] = []
    for regularization in (0.03, 0.1, 0.3, 1.0):
        candidates.append(
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
    for depth, leaf in ((4, 4), (6, 4), (8, 8), (None, 8)):
        candidates.append(
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
    for leaves, minimum_leaf in ((7, 10), (7, 20), (15, 10), (15, 20)):
        candidates.append(
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
    return candidates


def _aligned_inputs(
    development: dict[str, Any],
    relation_scores: dict[str, Any],
    atomic_scores: dict[str, Any],
    multispan_scores: dict[str, Any],
) -> dict[str, Any]:
    artifacts = (development, relation_scores, atomic_scores, multispan_scores)
    if any(artifact.get("split") != SPLIT for artifact in artifacts):
        raise V22CandidateError("V22 accepts only V21 development artifacts.")
    expected_hash = _sha256_json(development)
    if any(
        artifact.get("dataset_sha256") != expected_hash
        for artifact in (relation_scores, atomic_scores, multispan_scores)
    ):
        raise V22CandidateError("V22 score artifacts do not match V21 development.")
    if (
        relation_scores.get("remote_inference_used") is not False
        or relation_scores.get("evaluation_labels_sent") is not False
        or atomic_scores.get("remote_inference_used") is not False
        or atomic_scores.get("input_contract", {}).get("evaluation_labels_sent")
        is not False
        or multispan_scores.get("remote_inference_used") is not False
        or multispan_scores.get("input_contract", {}).get("evaluation_labels_sent")
        is not False
        or multispan_scores.get("local_only_network_calls") != 0
    ):
        raise V22CandidateError("V22 inputs must be local and label-blind.")
    mappings = [
        {str(row.get("case_id", row.get("id"))): row for row in values}
        for values in (
            development["examples"],
            relation_scores["rows"],
            atomic_scores["rows"],
            multispan_scores["rows"],
        )
    ]
    case_ids = set(mappings[0])
    if not case_ids or any(set(mapping) != case_ids for mapping in mappings[1:]):
        raise V22CandidateError("V22 inputs contain misaligned case IDs.")
    ordered = sorted(case_ids)
    matrix = []
    feature_names: list[str] | None = None
    maximum_relation_contradiction = []
    for case_id in ordered:
        example, relation, atomic, multispan = (
            mapping[case_id] for mapping in mappings
        )
        names, values = combined_feature_vector(example, relation, atomic, multispan)
        if feature_names is None:
            feature_names = names
        elif names != feature_names:
            raise V22CandidateError("V22 feature schemas are inconsistent.")
        matrix.append(values)
        maximum_relation_contradiction.append(
            max(
                float(row["probabilities"]["contradiction"])
                for row in relation["per_evidence"]
            )
        )
    targets = [str(mappings[0][case_id]["target"]["verdict"]) for case_id in ordered]
    if set(targets) != set(LABELS):
        raise V22CandidateError("V22 development does not cover all verdicts.")
    return {
        "case_ids": ordered,
        "targets": targets,
        "matrix": matrix,
        "feature_names": list(feature_names or []),
        "maximum_relation_contradiction": maximum_relation_contradiction,
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
    parser.add_argument("--development", required=True)
    parser.add_argument("--relation-scores", required=True)
    parser.add_argument("--atomic-scores", required=True)
    parser.add_argument("--multispan-scores", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--experiment", default=EXPERIMENT)
    args = parser.parse_args(argv)
    result = train_and_cross_validate(
        _load(args.development),
        _load(args.relation_scores),
        _load(args.atomic_scores),
        _load(args.multispan_scores),
        experiment=args.experiment,
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
                "direct": result["selected"]["direct"],
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
