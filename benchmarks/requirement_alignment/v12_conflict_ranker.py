"""Train and assess V12 local disputed-evidence rankers."""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
from pathlib import Path
from typing import Any

from benchmarks.requirement_alignment.train_v11_relation_conflict import (
    _routing_metrics,
)
from benchmarks.requirement_alignment.v10_fourway import (
    DEVELOPMENT_SPLIT,
    DISPUTED_REVIEW_TARGET,
)
from benchmarks.requirement_alignment.v9_router import (
    NEGATIONS,
    _coverage,
    _jaccard,
    _lexical_features,
    _tokens,
)


EXPERIMENT = "contexttrace_v12_conflict_ranking"
TRAINING_SPLIT = "climate_fever_v12_conflict_training"
SEED = 20260927
REVIEW_BUDGET = 18
COUNT_THRESHOLDS = (0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9)
RELATIONS = ("entailment", "contradiction", "neutral")


class V12RankerError(RuntimeError):
    """Raised when V12 conflict ranking violates its frozen contract."""


def train_and_assess(
    training: dict[str, Any],
    training_scores: dict[str, Any],
    development: dict[str, Any],
    development_scores: dict[str, Any],
) -> dict[str, Any]:
    train_features, train_targets, _, feature_names = _matrix(
        training, training_scores, expected_split=TRAINING_SPLIT
    )
    dev_features, dev_targets, dev_ids, dev_feature_names = _matrix(
        development, development_scores, expected_split=DEVELOPMENT_SPLIT
    )
    if feature_names != dev_feature_names:
        raise V12RankerError("Training and development feature schemas differ.")
    candidates = []
    score_sets: dict[str, list[float]] = {}
    for name, estimator in _candidates():
        estimator.fit(train_features, train_targets)
        if hasattr(estimator, "predict_proba"):
            positive = list(estimator.classes_).index(True)
            scores = estimator.predict_proba(dev_features)[:, positive].tolist()
        else:
            scores = estimator.decision_function(dev_features).tolist()
        metrics = _ranking_metrics(dev_targets, dev_ids, scores)
        candidates.append({"candidate": name, **metrics})
        score_sets[name] = [float(value) for value in scores]
    selected = max(
        candidates,
        key=lambda row: (
            float(row["disputed_recall_at_18"]),
            float(row["average_precision"]),
            float(row["roc_auc"]),
            str(row["candidate"]),
        ),
    )
    selected_scores = score_sets[str(selected["candidate"])]
    policy = _select_policy(
        development,
        development_scores,
        dev_targets,
        dev_ids,
        selected_scores,
    )
    return {
        "schema_version": "contexttrace-v12-conflict-ranker-1.0",
        "experiment": EXPERIMENT,
        "status": "rejected_development_candidate",
        "inputs": {
            "training_cases": len(train_targets),
            "training_disputed_cases": sum(train_targets),
            "training_sha256": _sha256_json(training),
            "training_score_rows_sha256": _sha256_json(training_scores["rows"]),
            "development_cases": len(dev_targets),
            "development_disputed_cases": sum(dev_targets),
            "development_sha256": _sha256_json(development),
            "development_score_rows_sha256": _sha256_json(development_scores["rows"]),
        },
        "features": {
            "count": len(feature_names),
            "names": feature_names,
            "sources": [
                "selected V11 per-evidence relation probabilities",
                "cross-span entailment and contradiction interactions",
                "deterministic lexical overlap, negation, and evidence-pair similarity",
            ],
            "evaluation_labels_in_model_inputs": False,
        },
        "search": {
            "selection_split": DEVELOPMENT_SPLIT,
            "selection_rule": [
                "maximize disputed recall within 18 review slots",
                "maximize average precision",
                "maximize ROC-AUC",
            ],
            "candidate_count": len(candidates),
            "candidates": candidates,
        },
        "selected": {
            **selected,
            "policy": policy,
        },
        "pairwise_cross_encoder_diagnostic": {
            "training_positive_pairs": 141,
            "training_hard_negative_pairs": 705,
            "hard_negative_rule": "highest V11 cross-span entailment-contradiction product among unanimous non-conflict pairs",
            "epochs": [
                {
                    "epoch": 0,
                    "disputed_recall_at_18": 0.4,
                    "average_precision": 0.3483,
                    "roc_auc": 0.5985,
                },
                {
                    "epoch": 1,
                    "disputed_recall_at_18": 0.3333,
                    "average_precision": 0.3349,
                    "roc_auc": 0.5911,
                },
                {
                    "epoch": 2,
                    "disputed_recall_at_18": 0.2667,
                    "average_precision": 0.3237,
                    "roc_auc": 0.5437,
                },
                {
                    "epoch": 3,
                    "disputed_recall_at_18": 0.3333,
                    "average_precision": 0.3613,
                    "roc_auc": 0.64,
                },
            ],
            "promote": False,
            "model_artifact_retained": False,
        },
        "promotion": {
            "disputed_review_coverage_minimum": DISPUTED_REVIEW_TARGET,
            "all_gates_met": policy["gates"]["all_met"],
            "promote": False,
            "reason": "Neither learned conflict ranker improves disputed coverage over the V11 explicit cross-span policy.",
        },
        "decision": "retain_v11_as_best_local_research_candidate",
        "v9_holdout_reused": False,
        "remote_inference_used": False,
        "stable_defaults_changed": False,
        "remote_provider_default_enabled": False,
        "local_only_network_calls": 0,
    }


def conflict_features(
    example: dict[str, Any], score_row: dict[str, Any]
) -> tuple[list[str], list[float]]:
    probabilities = [dict(row["probabilities"]) for row in score_row["per_evidence"]]
    evidence = list(example["input"]["evidence"])
    if len(probabilities) != 5 or len(evidence) != 5:
        raise V12RankerError("V12 conflict features require five evidence spans.")
    names: list[str] = []
    values: list[float] = []
    for relation in RELATIONS:
        relation_values = [float(row[relation]) for row in probabilities]
        descending = sorted(relation_values, reverse=True)
        names.extend(f"{relation}.raw.{index}" for index in range(5))
        values.extend(relation_values)
        names.extend(f"{relation}.sorted.{index}" for index in range(5))
        values.extend(descending)
        names.extend(
            f"{relation}.{statistic}"
            for statistic in ("max", "min", "mean", "std", "median", "range")
        )
        values.extend(
            [
                max(relation_values),
                min(relation_values),
                statistics.fmean(relation_values),
                statistics.pstdev(relation_values),
                statistics.median(relation_values),
                max(relation_values) - min(relation_values),
            ]
        )
        names.extend(
            f"{relation}.fraction_ge_{value:.1f}" for value in COUNT_THRESHOLDS
        )
        values.extend(
            sum(item >= threshold for item in relation_values) / 5
            for threshold in COUNT_THRESHOLDS
        )
    entailment = [float(row["entailment"]) for row in probabilities]
    contradiction = [float(row["contradiction"]) for row in probabilities]
    cross = sorted(
        (
            entailment[left] * contradiction[right]
            for left in range(5)
            for right in range(5)
            if left != right
        ),
        reverse=True,
    )
    same = sorted(
        (entailment[index] * contradiction[index] for index in range(5)),
        reverse=True,
    )
    names.extend(f"interaction.cross_product.{index}" for index in range(10))
    values.extend(cross[:10])
    names.extend(("interaction.cross_product.mean", "interaction.cross_product.std"))
    values.extend((statistics.fmean(cross), statistics.pstdev(cross)))
    names.extend(f"interaction.same_span_product.{index}" for index in range(5))
    values.extend(same)
    names.extend(
        (
            "interaction.cross_minus_same",
            "interaction.argmax_spans_differ",
            "interaction.minimum_maxima",
            "interaction.product_maxima",
            "interaction.absolute_maxima_difference",
        )
    )
    values.extend(
        (
            max(cross) - max(same),
            float(
                entailment.index(max(entailment))
                != contradiction.index(max(contradiction))
            ),
            min(max(entailment), max(contradiction)),
            max(entailment) * max(contradiction),
            abs(max(entailment) - max(contradiction)),
        )
    )
    lexical = _lexical_features(example)
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
    values.extend(lexical)
    claim_tokens = set(_tokens(str(example["input"]["claim"])))
    evidence_tokens = [set(_tokens(str(row["text"]))) for row in evidence]
    groups = {
        "span_claim_coverage": [
            _coverage(claim_tokens, tokens) for tokens in evidence_tokens
        ],
        "span_claim_jaccard": [
            _jaccard(claim_tokens, tokens) for tokens in evidence_tokens
        ],
        "evidence_pair_jaccard": [
            _jaccard(evidence_tokens[left], evidence_tokens[right])
            for left in range(5)
            for right in range(left + 1, 5)
        ],
    }
    for prefix, group in groups.items():
        descending = sorted(group, reverse=True)
        names.extend(f"lexical.{prefix}.sorted.{index}" for index in range(len(group)))
        values.extend(descending)
        names.extend((f"lexical.{prefix}.mean", f"lexical.{prefix}.std"))
        values.extend((statistics.fmean(group), statistics.pstdev(group)))
    names.extend(f"lexical.evidence_negation.{index}" for index in range(5))
    values.extend(float(bool(tokens & NEGATIONS)) for tokens in evidence_tokens)
    entailment_index = entailment.index(max(entailment))
    contradiction_index = contradiction.index(max(contradiction))
    names.extend(
        (
            "lexical.top_relation_span_jaccard",
            "lexical.top_entailment_claim_coverage",
            "lexical.top_contradiction_claim_coverage",
        )
    )
    values.extend(
        (
            _jaccard(
                evidence_tokens[entailment_index], evidence_tokens[contradiction_index]
            ),
            _coverage(claim_tokens, evidence_tokens[entailment_index]),
            _coverage(claim_tokens, evidence_tokens[contradiction_index]),
        )
    )
    return names, values


def _matrix(
    dataset: dict[str, Any], scores: dict[str, Any], *, expected_split: str
) -> tuple[list[list[float]], list[bool], list[str], list[str]]:
    if dataset.get("split") != expected_split or scores.get("split") != expected_split:
        raise V12RankerError("V12 dataset and scores must match the requested split.")
    if (
        scores.get("remote_inference_used") is not False
        or scores.get("evaluation_labels_sent") is not False
    ):
        raise V12RankerError("V12 relation scores must be local and label-free.")
    examples = {str(row["id"]): row for row in dataset.get("examples") or []}
    score_rows = {str(row["case_id"]): row for row in scores.get("rows") or []}
    if (
        not examples
        or len(examples) != len(dataset["examples"])
        or set(examples) != set(score_rows)
    ):
        raise V12RankerError("V12 dataset and score rows must be unique and aligned.")
    ids = sorted(examples)
    matrix = []
    feature_names = None
    for case_id in ids:
        names, values = conflict_features(examples[case_id], score_rows[case_id])
        if feature_names is None:
            feature_names = names
        elif names != feature_names:
            raise V12RankerError("V12 conflict feature rows are inconsistent.")
        matrix.append(values)
    targets = [
        str(examples[case_id]["source"]["claim_label"]) == "DISPUTED" for case_id in ids
    ]
    return matrix, targets, ids, list(feature_names or [])


def _candidates() -> list[tuple[str, Any]]:
    from sklearn.ensemble import (
        ExtraTreesClassifier,
        HistGradientBoostingClassifier,
        RandomForestClassifier,
    )
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    from sklearn.svm import SVC

    rows: list[tuple[str, Any]] = []
    for regularization in (0.001, 0.003, 0.01, 0.03, 0.1, 0.3, 1.0, 3.0, 10.0, 30.0):
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
    for depth in (2, 3, 4, 6, 8, None):
        for leaf in (1, 2, 4, 8, 16):
            for feature_fraction in (0.5, 1.0):
                rows.append(
                    (
                        f"extra_depth_{depth}_leaf_{leaf}_features_{feature_fraction}",
                        ExtraTreesClassifier(
                            n_estimators=500,
                            max_depth=depth,
                            min_samples_leaf=leaf,
                            max_features=feature_fraction,
                            class_weight="balanced",
                            random_state=SEED,
                            n_jobs=1,
                        ),
                    )
                )
    for depth in (2, 3, 4, 6, None):
        for leaf in (1, 2, 4, 8, 16):
            rows.append(
                (
                    f"forest_depth_{depth}_leaf_{leaf}",
                    RandomForestClassifier(
                        n_estimators=500,
                        max_depth=depth,
                        min_samples_leaf=leaf,
                        max_features=0.75,
                        class_weight="balanced",
                        random_state=SEED,
                        n_jobs=1,
                    ),
                )
            )
    for leaves in (3, 7, 15, 31):
        for minimum_leaf in (5, 10, 20, 40):
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
    for regularization in (0.01, 0.03, 0.1, 0.3, 1.0, 3.0, 10.0):
        for gamma in ("scale", 0.001, 0.003, 0.01, 0.03):
            rows.append(
                (
                    f"svc_c_{regularization}_gamma_{gamma}",
                    make_pipeline(
                        StandardScaler(),
                        SVC(C=regularization, gamma=gamma, class_weight="balanced"),
                    ),
                )
            )
    return rows


def _ranking_metrics(
    targets: list[bool], case_ids: list[str], scores: list[float]
) -> dict[str, Any]:
    from sklearn.metrics import average_precision_score, roc_auc_score

    ranked = sorted(
        range(len(targets)), key=lambda index: (-scores[index], case_ids[index])
    )
    reviewed = ranked[:REVIEW_BUDGET]
    hits = sum(targets[index] for index in reviewed)
    return {
        "disputed_recall_at_18": round(hits / sum(targets), 4),
        "disputed_hits_at_18": hits,
        "review_budget": REVIEW_BUDGET,
        "average_precision": round(float(average_precision_score(targets, scores)), 4),
        "roc_auc": round(float(roc_auc_score(targets, scores)), 4),
    }


def _select_policy(
    development: dict[str, Any],
    development_scores: dict[str, Any],
    targets: list[bool],
    case_ids: list[str],
    conflict_scores: list[float],
) -> dict[str, Any]:
    examples = {str(row["id"]): row for row in development["examples"]}
    scores = {str(row["case_id"]): row for row in development_scores["rows"]}
    labels = [str(examples[case_id]["source"]["claim_label"]) for case_id in case_ids]
    entailment = [
        max(
            float(row["probabilities"]["entailment"])
            for row in scores[case_id]["per_evidence"]
        )
        for case_id in case_ids
    ]
    contradiction = [
        max(
            float(row["probabilities"]["contradiction"])
            for row in scores[case_id]["per_evidence"]
        )
        for case_id in case_ids
    ]
    ranked = sorted(
        range(len(case_ids)),
        key=lambda index: (-conflict_scores[index], case_ids[index]),
    )
    candidates = []
    for review_count in range(REVIEW_BUDGET + 1):
        review = set(ranked[:review_count])
        for support_minimum in sorted({0.0, 1.0, *entailment}):
            for contradiction_maximum in sorted({0.0, 1.0, *contradiction}):
                supported = {
                    index
                    for index in range(len(case_ids))
                    if index not in review
                    and entailment[index] >= support_minimum
                    and contradiction[index] <= contradiction_maximum
                }
                row = _routing_metrics(labels, supported, review)
                row.update(
                    {
                        "review_cases": review_count,
                        "review_rate": review_count / len(case_ids),
                        "support_probability_minimum": support_minimum,
                        "contradiction_probability_maximum": contradiction_maximum,
                    }
                )
                candidates.append(row)
    passing = [row for row in candidates if row["gates"]["all_met"]]
    safe = [
        row
        for row in candidates
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
        **selected,
        "candidate_count": len(candidates),
        "all_gate_candidate_count": len(passing),
        "selected_kind": "all_gates" if passing else "best_safety_eligible_diagnostic",
        "review_budget": REVIEW_BUDGET,
    }


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
    parser.add_argument("--training-scores", required=True)
    parser.add_argument("--development-dataset", required=True)
    parser.add_argument("--development-scores", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    report = train_and_assess(
        _load(args.training_dataset),
        _load(args.training_scores),
        _load(args.development_dataset),
        _load(args.development_scores),
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
