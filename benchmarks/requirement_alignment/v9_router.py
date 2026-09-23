"""Calibrate the development-only V9 local meta-router.

The router keeps the frozen V8 decisions, adds a conservative pinned-NLI
support gate, and ranks the remaining uncertain cases for optional Jev review.
SciFact document IDs define out-of-fold groups so evidence from one document
cannot appear in both a router training fold and its validation fold.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import statistics
from pathlib import Path
from typing import Any

from benchmarks.requirement_alignment.v8_guard import guarded_local_route


EXPERIMENT = "contexttrace_v9_local_meta_router"
SPLIT = "scifact_development"
SEED = 20260923
LABELS = ("entailment", "contradiction", "neutral")
LOGISTIC_CS = (0.001, 0.003, 0.01, 0.03, 0.1, 0.3, 1.0, 3.0, 10.0)
NLI_ENTAILMENT_THRESHOLD = 0.98
NLI_CONTRADICTION_MAXIMUM = 0.01
JEV_SUPPORTED_THRESHOLD = 0.50
FALSE_POSITIVE_CAP = 0.05
RECALL_TARGET = 0.50
REMOTE_CALL_RATE_TARGET = 0.30
TOKEN_PATTERN = re.compile(r"[^\W_]+", re.UNICODE)
NEGATIONS = {
    "no",
    "not",
    "never",
    "none",
    "neither",
    "without",
    "lack",
    "lacks",
    "lacked",
    "cannot",
    "cant",
    "didnt",
    "doesnt",
    "isnt",
    "wasnt",
    "wont",
}


class V9RouterError(RuntimeError):
    """Raised when V9 inputs violate the frozen experiment contract."""


def score_serialized_router(features: list[float], router: dict[str, Any]) -> float:
    """Apply the JSON-serialized local router without loading scikit-learn."""

    mean = list(router["scaler_mean"])
    scale = list(router["scaler_scale"])
    coefficients = list(router["coefficients"])
    if not (len(features) == len(mean) == len(scale) == len(coefficients)):
        raise V9RouterError("Serialized router dimensions do not match the features.")
    logit = float(router["intercept"]) + sum(
        ((float(value) - float(center)) / float(width)) * float(coefficient)
        for value, center, width, coefficient in zip(
            features, mean, scale, coefficients, strict=True
        )
    )
    if logit >= 0:
        return 1.0 / (1.0 + math.exp(-logit))
    exponential = math.exp(logit)
    return exponential / (1.0 + exponential)


def candidate_route(
    base_route: str,
    pinned_nli_probabilities: dict[str, float],
    features: list[float],
    policy: dict[str, Any],
    *,
    local_only: bool,
) -> str:
    """Return supported, missing, route, or abstain under the V9 policy."""

    if base_route in {"supported", "missing"}:
        return base_route
    if base_route != "route":
        raise V9RouterError("The base route must be supported, missing, or route.")
    if float(pinned_nli_probabilities["entailment"]) >= float(
        policy["pinned_nli_entailment_threshold"]
    ) and float(pinned_nli_probabilities["contradiction"]) <= float(
        policy["pinned_nli_contradiction_maximum"]
    ):
        return "supported"
    router = dict(policy["router"])
    if score_serialized_router(features, router) >= float(
        router["oof_score_threshold"]
    ):
        return "abstain" if local_only else "route"
    return "missing"


def calibrate_router(
    dataset: dict[str, Any],
    local_scores: dict[str, Any],
    auxiliary_scores: dict[str, Any],
    jev_result: dict[str, Any],
    v8_policy_manifest: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    examples = _map_rows(dataset, "examples", "id")
    local = _map_rows(local_scores, "rows", "case_id")
    auxiliary = _map_rows(auxiliary_scores, "rows", "case_id")
    jev = {
        str(row["case_id"]): dict(row["prediction"])
        for row in jev_result.get("rows") or []
    }
    case_ids = sorted(examples)
    _validate_inputs(
        case_ids,
        dataset,
        local_scores,
        auxiliary_scores,
        jev_result,
        local,
        auxiliary,
        jev,
    )
    v8_policy = dict(v8_policy_manifest["policy"])
    features = [
        _features(examples[cid], local[cid], auxiliary[cid]) for cid in case_ids
    ]
    feature_names = _feature_names()
    if any(len(row) != len(feature_names) for row in features):
        raise V9RouterError("Feature rows do not match the frozen feature schema.")

    relations = [str(examples[cid]["source"]["relation"]) for cid in case_ids]
    targets = [relation == "Entailment" for relation in relations]
    document_groups = [str(examples[cid]["source"]["document_id"]) for cid in case_ids]
    base_routes = [
        guarded_local_route(local[cid]["predictions"], v8_policy) for cid in case_ids
    ]
    route_indexes = [
        index for index, route in enumerate(base_routes) if route == "route"
    ]
    teacher = [
        bool(
            jev[cid]["verdict"] == "supported"
            and float(jev[cid]["probabilities"]["supported"]) >= JEV_SUPPORTED_THRESHOLD
        )
        for cid in case_ids
    ]
    nli_support = [
        bool(
            base_routes[index] == "route"
            and float(auxiliary[cid]["pinned_nli_group"]["entailment"])
            >= NLI_ENTAILMENT_THRESHOLD
            and float(auxiliary[cid]["pinned_nli_group"]["contradiction"])
            <= NLI_CONTRADICTION_MAXIMUM
        )
        for index, cid in enumerate(case_ids)
    ]
    eligible_indexes = [index for index in route_indexes if not nli_support[index]]
    max_remote = math.floor(len(case_ids) * REMOTE_CALL_RATE_TARGET)

    searches: list[dict[str, Any]] = []
    score_sets: dict[float, tuple[list[float], list[int]]] = {}
    for regularization in LOGISTIC_CS:
        scores, folds = _oof_scores(
            features,
            teacher,
            document_groups,
            route_indexes,
            regularization=regularization,
        )
        score_sets[regularization] = (scores, folds)
        ranked = sorted(
            eligible_indexes, key=lambda index: (-scores[index], case_ids[index])
        )
        for remote_calls in range(max_remote + 1):
            remote = set(ranked[:remote_calls])
            evaluated = _evaluate(
                case_ids, relations, targets, base_routes, nli_support, remote, jev
            )
            searches.append(
                {
                    "regularization_c": regularization,
                    "remote_calls": remote_calls,
                    "remote_call_rate": _ratio(remote_calls, len(case_ids)),
                    "metrics": evaluated["optional_jev"]["metrics"],
                    "local_only": evaluated["local_only"],
                    "gates": _gates(evaluated),
                }
            )
    eligible = [row for row in searches if row["gates"]["all_met"]]
    if not eligible:
        raise V9RouterError("No grouped out-of-fold router candidate meets the gates.")
    selected_search = max(eligible, key=_selection_key)
    selected_c = float(selected_search["regularization_c"])
    selected_count = int(selected_search["remote_calls"])
    oof_scores, fold_ids = score_sets[selected_c]
    ranked = sorted(
        eligible_indexes, key=lambda index: (-oof_scores[index], case_ids[index])
    )
    selected_remote = set(ranked[:selected_count])
    selected_threshold = float(oof_scores[ranked[selected_count - 1]])
    evaluated = _evaluate(
        case_ids, relations, targets, base_routes, nli_support, selected_remote, jev
    )
    model = _fit_full_model(features, teacher, route_indexes, regularization=selected_c)
    model.update(
        {
            "feature_names": feature_names,
            "oof_score_threshold": selected_threshold,
            "oof_threshold_comparison": ">=",
            "training_cases": len(route_indexes),
            "training_positive_cases": sum(teacher[index] for index in route_indexes),
        }
    )
    full_fit_remote = [
        index
        for index in eligible_indexes
        if score_serialized_router(features[index], model) >= selected_threshold
    ]
    policy_core = {
        "base_policy_id": str(v8_policy_manifest["policy_id"]),
        "pinned_nli_entailment_threshold": NLI_ENTAILMENT_THRESHOLD,
        "pinned_nli_contradiction_maximum": NLI_CONTRADICTION_MAXIMUM,
        "jev_supported_probability": JEV_SUPPORTED_THRESHOLD,
        "router": model,
    }
    policy = {
        "schema_version": "contexttrace-v9-router-policy-1.0",
        "experiment": EXPERIMENT,
        "policy_id": _sha256_json(policy_core),
        "selection_split": SPLIT,
        "evaluation_split_accessed": False,
        "policy": policy_core,
        "decision_order": [
            "Apply the frozen V8 local supported and missing gates.",
            "For V8 uncertainty, accept pinned local NLI support only at the frozen high-confidence gate.",
            "Score remaining uncertainty with the serialized local logistic router.",
            "Call optional Jev only when the router score meets the frozen threshold; local_only abstains.",
        ],
        "stable_defaults_changed": False,
        "remote_provider_default_enabled": False,
    }
    analysis = {
        "schema_version": "contexttrace-v9-router-calibration-1.0",
        "experiment": EXPERIMENT,
        "selection_split": SPLIT,
        "evaluation_split_accessed": False,
        "cross_validation": {
            "method": "StratifiedGroupKFold",
            "folds": 5,
            "seed": SEED,
            "group": "SciFact document_id",
            "unique_documents": len(set(document_groups)),
            "route_documents": len({document_groups[index] for index in route_indexes}),
            "fold_case_counts": [fold_ids.count(index) for index in range(5)],
        },
        "search": {
            "target": "Jev accepted-support outcome without evaluation labels in features",
            "regularization_c": list(LOGISTIC_CS),
            "remote_call_counts": [0, max_remote],
            "candidate_count": len(searches),
            "gate_passing_candidate_count": len(eligible),
            "selection_rule": [
                "meet every safety, recall, and remote-call gate",
                "maximize positive recall",
                "maximize macro F1",
                "minimize remote calls",
                "prefer stronger regularization",
            ],
        },
        "selected": {
            "regularization_c": selected_c,
            "remote_calls": selected_count,
            "oof_score_threshold": selected_threshold,
            "gates": _gates(evaluated),
            **evaluated,
        },
        "pinned_nli_gate": {
            "automatic_supported_cases": sum(nli_support),
            "true_supported_cases": sum(
                target and support
                for target, support in zip(targets, nli_support, strict=True)
            ),
            "false_supported_cases": sum(
                not target and support
                for target, support in zip(targets, nli_support, strict=True)
            ),
            "contradiction_false_supported_cases": sum(
                relation == "Contradiction" and support
                for relation, support in zip(relations, nli_support, strict=True)
            ),
        },
        "full_fit_development_diagnostic": {
            "in_sample": True,
            "eligible_cases_at_or_above_oof_threshold": len(full_fit_remote),
            "rate_over_all_development_cases": _ratio(
                len(full_fit_remote), len(case_ids)
            ),
            "used_for_reported_oof_metrics": False,
        },
        "router_rows": [
            {
                "case_id": cid,
                "fold": fold_ids[index] if index in route_indexes else None,
                "oof_score": oof_scores[index] if index in route_indexes else None,
                "v8_route": base_routes[index],
                "pinned_nli_supported": nli_support[index],
                "remote_selected": index in selected_remote,
            }
            for index, cid in enumerate(case_ids)
        ],
        "stable_defaults_changed": False,
        "remote_provider_default_enabled": False,
        "local_only_network_calls": 0,
        "holdout_accessed": False,
    }
    return policy, analysis


def _features(
    example: dict[str, Any], local: dict[str, Any], auxiliary: dict[str, Any]
) -> list[float]:
    values: list[float] = []
    per_evidence = list(auxiliary["per_evidence"])
    for model in ("v3", "v5"):
        values.extend(
            float(local["predictions"][model]["probabilities"][label])
            for label in LABELS
        )
        for aggregation in (max, min, statistics.fmean):
            values.extend(
                float(aggregation(float(row[model][label]) for row in per_evidence))
                for label in LABELS
            )
    values.extend(_lexical_features(example))
    values.extend(float(auxiliary["pinned_nli_group"][label]) for label in LABELS)
    for aggregation in (max, min, statistics.fmean):
        values.extend(
            float(aggregation(float(row["pinned_nli"][label]) for row in per_evidence))
            for label in LABELS
        )
    return values


def _feature_names() -> list[str]:
    names: list[str] = []
    for model in ("v3", "v5"):
        names.extend(f"{model}.group.{label}" for label in LABELS)
        for aggregation in ("max", "min", "mean"):
            names.extend(f"{model}.span.{aggregation}.{label}" for label in LABELS)
    names.extend(
        [
            "lexical.claim_coverage",
            "lexical.jaccard",
            "lexical.best_span_coverage",
            "lexical.best_span_jaccard",
            "lexical.bigram_coverage",
            "lexical.claim_negation",
            "lexical.evidence_negation",
            "lexical.negation_mismatch",
            "lexical.number_coverage",
            "lexical.missing_number",
            "lexical.log_claim_tokens",
            "lexical.log_evidence_tokens",
        ]
    )
    names.extend(f"pinned_nli.group.{label}" for label in LABELS)
    for aggregation in ("max", "min", "mean"):
        names.extend(f"pinned_nli.span.{aggregation}.{label}" for label in LABELS)
    return names


def _lexical_features(example: dict[str, Any]) -> list[float]:
    claim = _tokens(str(example["input"]["claim"]))
    evidence = [_tokens(str(row["text"])) for row in example["input"]["evidence"]]
    all_evidence = [token for row in evidence for token in row]
    claim_set, evidence_set = set(claim), set(all_evidence)
    claim_bigrams = set(zip(claim, claim[1:]))
    evidence_bigrams = set(zip(all_evidence, all_evidence[1:]))
    claim_numbers = {token for token in claim if any(char.isdigit() for char in token)}
    evidence_numbers = {
        token for token in all_evidence if any(char.isdigit() for char in token)
    }
    claim_negation = bool(claim_set & NEGATIONS)
    evidence_negation = bool(evidence_set & NEGATIONS)
    return [
        _coverage(claim_set, evidence_set),
        _jaccard(claim_set, evidence_set),
        max(_coverage(claim_set, set(row)) for row in evidence),
        max(_jaccard(claim_set, set(row)) for row in evidence),
        _coverage(claim_bigrams, evidence_bigrams),
        float(claim_negation),
        float(evidence_negation),
        float(claim_negation != evidence_negation),
        _coverage(claim_numbers, evidence_numbers) if claim_numbers else 1.0,
        float(bool(claim_numbers - evidence_numbers)),
        math.log1p(len(claim)),
        math.log1p(len(all_evidence)),
    ]


def _oof_scores(
    features: list[list[float]],
    teacher: list[bool],
    groups: list[str],
    route_indexes: list[int],
    *,
    regularization: float,
) -> tuple[list[float], list[int]]:
    import numpy as np
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import StratifiedGroupKFold
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    matrix = np.asarray(features, dtype=float)
    labels = np.asarray(teacher, dtype=int)
    route = np.asarray(route_indexes, dtype=int)
    scores = np.zeros(len(features), dtype=float)
    fold_ids = np.full(len(features), -1, dtype=int)
    splitter = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=SEED)
    route_groups = np.asarray(groups)[route]
    for fold, (train_positions, valid_positions) in enumerate(
        splitter.split(matrix[route], labels[route], groups=route_groups)
    ):
        train = route[train_positions]
        valid = route[valid_positions]
        estimator = make_pipeline(
            StandardScaler(),
            LogisticRegression(
                C=regularization,
                class_weight="balanced",
                max_iter=3000,
                random_state=SEED,
                solver="lbfgs",
            ),
        )
        estimator.fit(matrix[train], labels[train])
        positive = list(estimator.classes_).index(1)
        scores[valid] = estimator.predict_proba(matrix[valid])[:, positive]
        fold_ids[valid] = fold
    return scores.tolist(), fold_ids.tolist()


def _fit_full_model(
    features: list[list[float]],
    teacher: list[bool],
    route_indexes: list[int],
    *,
    regularization: float,
) -> dict[str, Any]:
    import numpy as np
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler

    matrix = np.asarray(features, dtype=float)[route_indexes]
    labels = np.asarray(teacher, dtype=int)[route_indexes]
    scaler = StandardScaler().fit(matrix)
    transformed = scaler.transform(matrix)
    model = LogisticRegression(
        C=regularization,
        class_weight="balanced",
        max_iter=3000,
        random_state=SEED,
        solver="lbfgs",
    ).fit(transformed, labels)
    return {
        "kind": "standardized_logistic_regression",
        "regularization_c": regularization,
        "class_weight": "balanced",
        "positive_class": "jev_accepted_support",
        "scaler_mean": [float(value) for value in scaler.mean_],
        "scaler_scale": [float(value) for value in scaler.scale_],
        "coefficients": [float(value) for value in model.coef_[0]],
        "intercept": float(model.intercept_[0]),
    }


def _evaluate(
    case_ids: list[str],
    relations: list[str],
    targets: list[bool],
    base_routes: list[str],
    nli_support: list[bool],
    remote: set[int],
    jev: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    predictions: list[bool] = []
    local_predictions: list[bool | None] = []
    for index, cid in enumerate(case_ids):
        if base_routes[index] == "supported" or nli_support[index]:
            prediction = True
            local_prediction: bool | None = True
        elif base_routes[index] == "missing" or index not in remote:
            prediction = False
            local_prediction = False
        else:
            prediction = bool(
                jev[cid]["verdict"] == "supported"
                and float(jev[cid]["probabilities"]["supported"])
                >= JEV_SUPPORTED_THRESHOLD
            )
            local_prediction = None
        predictions.append(prediction)
        local_predictions.append(local_prediction)
    metrics = _binary_metrics(targets, predictions)
    false_support = [
        cid
        for cid, target, prediction in zip(case_ids, targets, predictions, strict=True)
        if not target and prediction
    ]
    contradiction_false_support = [
        cid
        for cid, relation, prediction in zip(
            case_ids, relations, predictions, strict=True
        )
        if relation == "Contradiction" and prediction
    ]
    decided = [
        index for index, value in enumerate(local_predictions) if value is not None
    ]
    local_targets = [targets[index] for index in decided]
    local_guesses = [bool(local_predictions[index]) for index in decided]
    local_metrics = _binary_metrics(local_targets, local_guesses)
    local_contradiction_false_support = [
        case_ids[index]
        for index, prediction in zip(decided, local_guesses, strict=True)
        if relations[index] == "Contradiction" and prediction
    ]
    remote_rows = [jev[case_ids[index]] for index in sorted(remote)]
    return {
        "local_only": {
            "network_calls": 0,
            "privacy_behavior": "router-selected remote cases abstain",
            "automatic_cases": len(decided),
            "automatic_coverage": _ratio(len(decided), len(case_ids)),
            "metrics": local_metrics,
            "contradiction_false_support_count": len(local_contradiction_false_support),
            "abstentions": len(remote),
        },
        "optional_jev": {
            "metrics": {
                **metrics,
                "false_support_case_ids": false_support,
                "contradiction_false_support_count": len(contradiction_false_support),
                "contradiction_false_support_case_ids": contradiction_false_support,
            },
            "operations": {
                "remote_calls": len(remote),
                "remote_call_rate": _ratio(len(remote), len(case_ids)),
                "routed_case_ids": [case_ids[index] for index in sorted(remote)],
                "tokens": {
                    "input": sum(
                        int(row["usage"]["input_tokens"]) for row in remote_rows
                    ),
                    "output": sum(
                        int(row["usage"]["output_tokens"]) for row in remote_rows
                    ),
                    "total": sum(
                        int(row["usage"]["total_tokens"]) for row in remote_rows
                    ),
                },
                "latency_ms": {
                    "total": round(
                        sum(float(row["latency_ms"]) for row in remote_rows), 3
                    ),
                    "mean": round(
                        statistics.fmean(
                            float(row["latency_ms"]) for row in remote_rows
                        ),
                        3,
                    )
                    if remote_rows
                    else 0.0,
                },
            },
        },
    }


def _binary_metrics(targets: list[bool], predictions: list[bool]) -> dict[str, Any]:
    tp = sum(
        target and prediction
        for target, prediction in zip(targets, predictions, strict=True)
    )
    tn = sum(
        not target and not prediction
        for target, prediction in zip(targets, predictions, strict=True)
    )
    fp = sum(
        not target and prediction
        for target, prediction in zip(targets, predictions, strict=True)
    )
    fn = sum(
        target and not prediction
        for target, prediction in zip(targets, predictions, strict=True)
    )
    positive_recall = _ratio(tp, tp + fn)
    negative_recall = _ratio(tn, tn + fp)
    positive_precision = _ratio(tp, tp + fp)
    negative_precision = _ratio(tn, tn + fn)
    positive_f1 = _ratio(
        2 * positive_precision * positive_recall, positive_precision + positive_recall
    )
    negative_f1 = _ratio(
        2 * negative_precision * negative_recall, negative_precision + negative_recall
    )
    return {
        "cases": len(targets),
        "accuracy": round(_ratio(tp + tn, len(targets)), 4),
        "macro_f1": round(statistics.fmean((positive_f1, negative_f1)), 4),
        "positive_recall": round(positive_recall, 4),
        "false_positive_rate": round(_ratio(fp, fp + tn), 4),
        "confusion": {
            "missing": {"missing": tn, "supported": fp},
            "supported": {"missing": fn, "supported": tp},
        },
    }


def _gates(evaluated: dict[str, Any]) -> dict[str, bool]:
    metrics = evaluated["optional_jev"]["metrics"]
    local = evaluated["local_only"]["metrics"]
    gates = {
        "positive_recall": metrics["positive_recall"] >= RECALL_TARGET,
        "false_positive_rate": metrics["false_positive_rate"] <= FALSE_POSITIVE_CAP,
        "local_false_positive_rate": local["false_positive_rate"] <= FALSE_POSITIVE_CAP,
        "zero_contradiction_false_support": metrics["contradiction_false_support_count"]
        == 0,
        "remote_call_rate": evaluated["optional_jev"]["operations"]["remote_call_rate"]
        <= REMOTE_CALL_RATE_TARGET,
    }
    return {**gates, "all_met": all(gates.values())}


def _selection_key(row: dict[str, Any]) -> tuple[Any, ...]:
    metrics = row["metrics"]
    return (
        float(metrics["positive_recall"]),
        float(metrics["macro_f1"]),
        -int(row["remote_calls"]),
        -float(row["regularization_c"]),
    )


def _validate_inputs(
    case_ids: list[str],
    dataset: dict[str, Any],
    local_scores: dict[str, Any],
    auxiliary_scores: dict[str, Any],
    jev_result: dict[str, Any],
    local: dict[str, Any],
    auxiliary: dict[str, Any],
    jev: dict[str, Any],
) -> None:
    if dataset.get("split") != SPLIT or any(
        payload.get("split") != SPLIT
        for payload in (local_scores, auxiliary_scores, jev_result)
    ):
        raise V9RouterError("V9 calibration accepts only SciFact development inputs.")
    expected = set(case_ids)
    if set(local) != expected or set(auxiliary) != expected or set(jev) != expected:
        raise V9RouterError("V9 inputs must cover identical case IDs.")
    if auxiliary_scores.get("remote_inference_used") is not False:
        raise V9RouterError("Auxiliary features must be produced locally.")
    if auxiliary_scores.get("evaluation_labels_sent") is not False:
        raise V9RouterError("Evaluation labels must not be sent to feature models.")


def _map_rows(
    payload: dict[str, Any], field: str, key: str
) -> dict[str, dict[str, Any]]:
    rows = payload.get(field) or []
    result = {str(row[key]): row for row in rows}
    if not result or len(result) != len(rows):
        raise V9RouterError(f"{field} must contain unique non-empty rows.")
    return result


def _tokens(value: str) -> list[str]:
    return [token.lower() for token in TOKEN_PATTERN.findall(value)]


def _coverage(left: set[Any], right: set[Any]) -> float:
    return _ratio(len(left & right), len(left))


def _jaccard(left: set[Any], right: set[Any]) -> float:
    return _ratio(len(left & right), len(left | right))


def _ratio(numerator: float, denominator: float) -> float:
    return float(numerator / denominator) if denominator else 0.0


def _sha256_json(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"))
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
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--local-scores", required=True)
    parser.add_argument("--auxiliary-scores", required=True)
    parser.add_argument("--jev-result", required=True)
    parser.add_argument("--v8-policy", required=True)
    parser.add_argument("--policy-output", required=True)
    parser.add_argument("--analysis-output", required=True)
    args = parser.parse_args(argv)
    policy, analysis = calibrate_router(
        _load(args.dataset),
        _load(args.local_scores),
        _load(args.auxiliary_scores),
        _load(args.jev_result),
        _load(args.v8_policy),
    )
    _write(args.policy_output, policy)
    _write(args.analysis_output, analysis)
    print(
        json.dumps(
            {"policy_id": policy["policy_id"], "selected": analysis["selected"]},
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
