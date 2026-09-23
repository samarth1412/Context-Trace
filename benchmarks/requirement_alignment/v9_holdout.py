"""Run the frozen V9 router once on the external Climate-FEVER holdout."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import statistics
from collections import Counter
from pathlib import Path
from typing import Any

from benchmarks.requirement_alignment.score_v6_cascade import score_local_models
from benchmarks.requirement_alignment.score_v9_auxiliary import score_auxiliary
from benchmarks.requirement_alignment.v6_cascade import (
    V6JevJudge,
    _load_env_file,
    _percentile,
    build_jev_state,
    enforce_remote_policy,
)
from benchmarks.requirement_alignment.v8_guard import guarded_local_route
from benchmarks.requirement_alignment.v9_router import (
    _binary_metrics,
    _features,
    candidate_route,
)
from contexttrace.config import load_config


EXPERIMENT = "contexttrace_v9_climate_fever_confirmation"
SPLIT = "climate_fever_evaluation"
EXPECTED_DATASET_SHA256 = (
    "d582c53e6a87d800e3bf293c3d597e7e11ee0fb5dff0a79f31be5e2395e26858"
)
EXPECTED_POLICY_ID = "718b3e848ea6998387400b88f6851bb751e4dba638010a4b19724c8fe0f475c6"
FALSE_POSITIVE_CAP = 0.05
RECALL_TARGET = 0.50
REMOTE_CALL_RATE_TARGET = 0.30
DISPUTED_REVIEW_TARGET = 0.90
REVIEW_CONFIDENCE = 0.80


class V9HoldoutError(RuntimeError):
    """Raised when the one-shot holdout contract is violated."""


def score_local_holdout(
    dataset_path: str | Path,
    *,
    v3_model_path: str | Path,
    v3_manifest_path: str | Path,
    v5_model_path: str | Path,
    v5_manifest_path: str | Path,
    pinned_nli_path: str | Path,
    batch_size: int = 16,
) -> tuple[dict[str, Any], dict[str, Any]]:
    dataset = _load(Path(dataset_path))
    _validate_dataset(dataset)
    local = score_local_models(
        dataset_path,
        expected_split=SPLIT,
        v3_model_path=v3_model_path,
        v3_manifest_path=v3_manifest_path,
        v5_model_path=v5_model_path,
        v5_manifest_path=v5_manifest_path,
        batch_size=batch_size,
    )
    local.update(
        {
            "schema_version": "contexttrace-v9-climate-fever-local-scores-1.0",
            "experiment": EXPERIMENT,
            "source_dataset": "Climate-FEVER",
            "evaluation_split_accessed": True,
            "evaluation_labels_sent": False,
        }
    )
    auxiliary = score_auxiliary(
        dataset_path,
        expected_split=SPLIT,
        v3_model_path=v3_model_path,
        v3_manifest_path=v3_manifest_path,
        v5_model_path=v5_model_path,
        v5_manifest_path=v5_manifest_path,
        pinned_nli_path=pinned_nli_path,
        batch_size=batch_size,
    )
    auxiliary.update(
        {
            "schema_version": "contexttrace-v9-climate-fever-auxiliary-scores-1.0",
            "experiment": EXPERIMENT,
            "source_dataset": "Climate-FEVER",
            "evaluation_split_accessed": True,
        }
    )
    return local, auxiliary


def route_holdout(
    dataset: dict[str, Any],
    local_scores: dict[str, Any],
    auxiliary_scores: dict[str, Any],
    v8_policy_manifest: dict[str, Any],
    v9_policy_manifest: dict[str, Any],
) -> dict[str, Any]:
    examples, local, auxiliary = _validated_maps(
        dataset, local_scores, auxiliary_scores
    )
    _validate_policies(v8_policy_manifest, v9_policy_manifest)
    v8_policy = dict(v8_policy_manifest["policy"])
    v9_policy = dict(v9_policy_manifest["policy"])
    rows = []
    for case_id in sorted(examples):
        example = examples[case_id]
        feature_values = _features(example, local[case_id], auxiliary[case_id])
        base_route = guarded_local_route(local[case_id]["predictions"], v8_policy)
        route = candidate_route(
            base_route,
            auxiliary[case_id]["pinned_nli_group"],
            feature_values,
            v9_policy,
            local_only=False,
        )
        local_only_route = "abstain" if route == "route" else route
        rows.append(
            {
                "case_id": case_id,
                "input_sha256": auxiliary[case_id]["input_sha256"],
                "base_route": base_route,
                "route": route,
                "local_only_route": local_only_route,
            }
        )
    route_ids = [row["case_id"] for row in rows if row["route"] == "route"]
    return {
        "schema_version": "contexttrace-v9-climate-fever-routes-1.0",
        "experiment": EXPERIMENT,
        "split": SPLIT,
        "dataset_sha256": _sha256_json(dataset),
        "local_scores_sha256": _sha256_json(local_scores),
        "auxiliary_scores_sha256": _sha256_json(auxiliary_scores),
        "policy_id": v9_policy_manifest["policy_id"],
        "cases": len(rows),
        "routed_case_ids": route_ids,
        "remote_calls": len(route_ids),
        "remote_call_rate": round(len(route_ids) / len(rows), 4),
        "evaluation_labels_used_for_routing": False,
        "stable_defaults_changed": False,
        "remote_provider_default_enabled": False,
        "local_only_network_calls": 0,
        "rows": rows,
    }


def run_jev_holdout(
    dataset_path: str | Path,
    route_path: str | Path,
    *,
    output_path: str | Path,
    model: str,
    allow_remote: bool,
    env_file: str | Path | None,
) -> dict[str, Any]:
    if env_file:
        _load_env_file(env_file)
    enforce_remote_policy(
        local_only=load_config().local_only, allow_remote=allow_remote
    )
    api_key = os.environ.get("TYPESAFE_API_KEY", "").strip()
    if not api_key:
        raise V9HoldoutError("TYPESAFE_API_KEY is not set.")
    dataset_file = Path(dataset_path)
    route_file = Path(route_path)
    dataset = _load(dataset_file)
    routes = _load(route_file)
    examples = _example_map(dataset)
    _validate_dataset(dataset)
    _validate_routes(routes, dataset)
    route_ids = set(str(value) for value in routes["routed_case_ids"])
    if not route_ids <= set(examples):
        raise V9HoldoutError("Route manifest contains unknown case IDs.")

    completed: dict[str, dict[str, Any]] = {}
    output_file = Path(output_path)
    if output_file.is_file():
        checkpoint = _load(output_file)
        if (
            checkpoint.get("dataset_sha256") != _sha256_json(dataset)
            or checkpoint.get("routes_sha256") != _sha256_json(routes)
            or checkpoint.get("policy_id") != EXPECTED_POLICY_ID
            or checkpoint.get("requested_model") != model
            or set(checkpoint.get("routed_case_ids") or []) != route_ids
        ):
            raise V9HoldoutError("Existing Jev checkpoint does not match this run.")
        completed = {str(row["case_id"]): row for row in checkpoint.get("rows") or []}
        for case_id, row in completed.items():
            _validate_jev_row(case_id, row["prediction"], examples[case_id], model)

    from typesafe_sdk import Choice, TypeSafeClient

    client = TypeSafeClient(
        api_key=api_key,
        base_url=(
            os.environ.get("TYPESAFE_BASE_URL")
            or os.environ.get("TYPESAFE_ENDPOINT")
            or None
        ),
    )
    judge = V6JevJudge(client=client, choice_factory=Choice, model=model)
    try:
        missing = sorted(route_ids - set(completed))
        for index, case_id in enumerate(missing, 1):
            prediction = judge.verify(examples[case_id])
            _validate_jev_row(case_id, prediction, examples[case_id], model)
            completed[case_id] = {"case_id": case_id, "prediction": prediction}
            _write(
                output_file,
                _jev_payload(dataset, routes, model, route_ids, completed),
            )
            print(f"jev {index}/{len(missing)} {case_id}", flush=True)
    finally:
        close = getattr(client, "close", None)
        if callable(close):
            close()
    return _jev_payload(dataset, routes, model, route_ids, completed)


def evaluate_holdout(
    dataset: dict[str, Any],
    routes: dict[str, Any],
    jev_result: dict[str, Any],
) -> dict[str, Any]:
    _validate_dataset(dataset)
    _validate_routes(routes, dataset)
    examples = _example_map(dataset)
    route_rows = {str(row["case_id"]): row for row in routes.get("rows") or []}
    jev_rows = {
        str(row["case_id"]): row["prediction"] for row in jev_result.get("rows") or []
    }
    expected_remote = set(str(value) for value in routes["routed_case_ids"])
    if jev_result.get("complete") is not True or set(jev_rows) != expected_remote:
        raise V9HoldoutError("Jev rows must exactly cover the frozen route set.")
    decisions = {}
    for case_id in sorted(examples):
        route = str(route_rows[case_id]["route"])
        if route == "route":
            prediction = jev_rows[case_id]
            supported = bool(
                prediction["verdict"] == "supported"
                and float(prediction["probabilities"]["supported"]) >= 0.50
            )
            verdict = "supported" if supported else "missing"
            review = bool(
                supported or float(prediction["confidence"]) < REVIEW_CONFIDENCE
            )
            source = "jev"
        else:
            verdict = route
            review = route == "supported"
            source = "local"
        decisions[case_id] = {
            "verdict": verdict,
            "review_required": review,
            "source": source,
        }

    primary_ids = [
        case_id
        for case_id in sorted(examples)
        if examples[case_id]["source"]["relation"] != "Disputed"
    ]
    disputed_ids = [
        case_id
        for case_id in sorted(examples)
        if examples[case_id]["source"]["relation"] == "Disputed"
    ]
    targets = [
        examples[case_id]["target"]["label"] == "covered" for case_id in primary_ids
    ]
    predictions = [
        decisions[case_id]["verdict"] == "supported" for case_id in primary_ids
    ]
    metrics = _binary_metrics(targets, predictions)
    false_support = [
        case_id
        for case_id, target, prediction in zip(
            primary_ids, targets, predictions, strict=True
        )
        if not target and prediction
    ]
    contradiction_false_support = [
        case_id
        for case_id in primary_ids
        if examples[case_id]["source"]["relation"] == "Contradiction"
        and decisions[case_id]["verdict"] == "supported"
    ]
    primary_remote = [
        case_id for case_id in primary_ids if route_rows[case_id]["route"] == "route"
    ]
    local_decided = [
        case_id for case_id in primary_ids if route_rows[case_id]["route"] != "route"
    ]
    local_targets = [
        examples[case_id]["target"]["label"] == "covered" for case_id in local_decided
    ]
    local_predictions = [
        decisions[case_id]["verdict"] == "supported" for case_id in local_decided
    ]
    local_metrics = _binary_metrics(local_targets, local_predictions)
    metrics.update(
        {
            "false_support_case_ids": false_support,
            "contradiction_false_support_count": len(contradiction_false_support),
            "contradiction_false_support_case_ids": contradiction_false_support,
            "relation_breakdown": _relation_breakdown(primary_ids, examples, decisions),
        }
    )
    binary_gates = {
        "positive_recall": metrics["positive_recall"] >= RECALL_TARGET,
        "false_positive_rate": metrics["false_positive_rate"] <= FALSE_POSITIVE_CAP,
        "local_false_positive_rate": local_metrics["false_positive_rate"]
        <= FALSE_POSITIVE_CAP,
        "zero_contradiction_false_support": len(contradiction_false_support) == 0,
        "remote_call_rate": len(primary_remote) / len(primary_ids)
        <= REMOTE_CALL_RATE_TARGET,
    }
    automatic_supported = [
        case_id
        for case_id in disputed_ids
        if decisions[case_id]["verdict"] == "supported"
        and not decisions[case_id]["review_required"]
    ]
    reviewed_or_abstained = [
        case_id
        for case_id in disputed_ids
        if decisions[case_id]["review_required"]
        or decisions[case_id]["verdict"] == "abstain"
    ]
    disputed_remote = [
        case_id for case_id in disputed_ids if route_rows[case_id]["route"] == "route"
    ]
    disputed = {
        "cases": len(disputed_ids),
        "verdict_counts": dict(
            sorted(Counter(decisions[cid]["verdict"] for cid in disputed_ids).items())
        ),
        "review_required": len(reviewed_or_abstained),
        "review_or_abstain_coverage": round(
            len(reviewed_or_abstained) / len(disputed_ids), 4
        ),
        "automatic_supported_count": len(automatic_supported),
        "automatic_supported_case_ids": automatic_supported,
        "remote_calls": len(disputed_remote),
        "remote_call_rate": round(len(disputed_remote) / len(disputed_ids), 4),
    }
    disputed_gates = {
        "zero_automatic_supported": disputed["automatic_supported_count"] == 0,
        "review_or_abstain_coverage": disputed["review_or_abstain_coverage"]
        >= DISPUTED_REVIEW_TARGET,
    }
    remote_predictions = [jev_rows[case_id] for case_id in sorted(expected_remote)]
    routing_by_relation = {}
    jev_by_relation = {}
    for relation in ("Entailment", "Contradiction", "NotMentioned", "Disputed"):
        relation_ids = [
            case_id
            for case_id in sorted(examples)
            if examples[case_id]["source"]["relation"] == relation
        ]
        relation_remote = [case_id for case_id in relation_ids if case_id in jev_rows]
        routing_by_relation[relation] = {
            "cases": len(relation_ids),
            "v8_base_routes": dict(
                sorted(
                    Counter(
                        route_rows[case_id]["base_route"] for case_id in relation_ids
                    ).items()
                )
            ),
            "v9_routes": dict(
                sorted(
                    Counter(
                        route_rows[case_id]["route"] for case_id in relation_ids
                    ).items()
                )
            ),
        }
        jev_by_relation[relation] = {
            "calls": len(relation_remote),
            "verdict_counts": dict(
                sorted(
                    Counter(
                        jev_rows[case_id]["verdict"] for case_id in relation_remote
                    ).items()
                )
            ),
            "accepted_supported": sum(
                jev_rows[case_id]["verdict"] == "supported"
                and float(jev_rows[case_id]["probabilities"]["supported"]) >= 0.50
                for case_id in relation_remote
            ),
            "confidence_below_review_threshold": sum(
                float(jev_rows[case_id]["confidence"]) < REVIEW_CONFIDENCE
                for case_id in relation_remote
            ),
        }
    return {
        "schema_version": "contexttrace-v9-climate-fever-evaluation-1.0",
        "experiment": EXPERIMENT,
        "split": SPLIT,
        "policy_id": EXPECTED_POLICY_ID,
        "dataset_sha256": _sha256_json(dataset),
        "routes_sha256": _sha256_json(routes),
        "jev_result_sha256": _sha256_json(jev_result),
        "evaluation_used_for_selection": False,
        "eligible_as_fresh_release_evidence": True,
        "primary_binary": {
            "metrics": metrics,
            "operations": {
                "remote_calls": len(primary_remote),
                "remote_call_rate": round(len(primary_remote) / len(primary_ids), 4),
            },
            "local_only": {
                "network_calls": 0,
                "automatic_cases": len(local_decided),
                "automatic_coverage": round(len(local_decided) / len(primary_ids), 4),
                "abstentions": len(primary_remote),
                "metrics": local_metrics,
            },
            "gates": {**binary_gates, "all_met": all(binary_gates.values())},
        },
        "disputed_challenge": {
            **disputed,
            "gates": {**disputed_gates, "all_met": all(disputed_gates.values())},
        },
        "all_cases_operations": {
            "cases": len(examples),
            "remote_calls": len(expected_remote),
            "remote_call_rate": round(len(expected_remote) / len(examples), 4),
            "resolved_models": dict(
                sorted(
                    Counter(row["resolved_model"] for row in remote_predictions).items()
                )
            ),
            "tokens": {
                "input": sum(
                    int(row["usage"]["input_tokens"]) for row in remote_predictions
                ),
                "output": sum(
                    int(row["usage"]["output_tokens"]) for row in remote_predictions
                ),
                "total": sum(
                    int(row["usage"]["total_tokens"]) for row in remote_predictions
                ),
            },
            "latency_ms": {
                "total": round(
                    sum(float(row["latency_ms"]) for row in remote_predictions), 3
                ),
                "mean": round(
                    statistics.fmean(
                        float(row["latency_ms"]) for row in remote_predictions
                    ),
                    3,
                )
                if remote_predictions
                else 0.0,
                "p95": _percentile(
                    [float(row["latency_ms"]) for row in remote_predictions], 0.95
                ),
            },
        },
        "diagnostics": {
            "routing_by_relation": routing_by_relation,
            "jev_by_relation": jev_by_relation,
            "used_for_policy_selection": False,
        },
        "release_gates_met": all(binary_gates.values())
        and all(disputed_gates.values()),
        "stable_defaults_changed": False,
        "remote_provider_default_enabled": False,
        "local_only_network_calls": 0,
    }


def _validated_maps(
    dataset: dict[str, Any],
    local_scores: dict[str, Any],
    auxiliary_scores: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    _validate_dataset(dataset)
    if local_scores.get("split") != SPLIT or auxiliary_scores.get("split") != SPLIT:
        raise V9HoldoutError("Local score files do not match the holdout split.")
    if (
        local_scores.get("remote_inference_used") is not False
        or auxiliary_scores.get("remote_inference_used") is not False
    ):
        raise V9HoldoutError("Local score files must not use remote inference.")
    examples = _example_map(dataset)
    local = _row_map(local_scores)
    auxiliary = _row_map(auxiliary_scores)
    if set(examples) != set(local) or set(examples) != set(auxiliary):
        raise V9HoldoutError(
            "Dataset and local score files must cover identical cases."
        )
    return examples, local, auxiliary


def _validate_dataset(dataset: dict[str, Any]) -> None:
    if (
        dataset.get("split") != SPLIT
        or _sha256_json(dataset) != EXPECTED_DATASET_SHA256
    ):
        raise V9HoldoutError("Dataset does not match the frozen Climate-FEVER holdout.")
    examples = list(dataset.get("examples") or [])
    if len(examples) != 240 or any(row.get("split") != SPLIT for row in examples):
        raise V9HoldoutError("Frozen holdout must contain exactly 240 cases.")
    if any({"label", "target", "relation"} & set(row["input"]) for row in examples):
        raise V9HoldoutError("Evaluation labels must remain outside model inputs.")


def _validate_policies(v8: dict[str, Any], v9: dict[str, Any]) -> None:
    if v9.get("policy_id") != EXPECTED_POLICY_ID or v9.get("policy_id") != _sha256_json(
        v9.get("policy")
    ):
        raise V9HoldoutError("V9 policy does not match the frozen candidate.")
    if v9["policy"].get("base_policy_id") != v8.get("policy_id"):
        raise V9HoldoutError(
            "V9 policy does not reference the supplied V8 base policy."
        )


def _validate_routes(routes: dict[str, Any], dataset: dict[str, Any]) -> None:
    if (
        routes.get("split") != SPLIT
        or routes.get("dataset_sha256") != _sha256_json(dataset)
        or routes.get("policy_id") != EXPECTED_POLICY_ID
        or routes.get("evaluation_labels_used_for_routing") is not False
    ):
        raise V9HoldoutError("Route manifest does not match the frozen evaluation.")


def _validate_jev_row(
    case_id: str, prediction: dict[str, Any], example: dict[str, Any], model: str
) -> None:
    if prediction.get("requested_model") != model:
        raise V9HoldoutError(f"Jev model mismatch for {case_id}.")
    expected = hashlib.sha256(
        json.dumps(
            build_jev_state(example),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    audit = prediction.get("input_audit") or {}
    if (
        audit.get("state_sha256") != expected
        or audit.get("sent_fields") != ["claim", "selected_evidence"]
        or audit.get("evaluation_label_sent") is not False
    ):
        raise V9HoldoutError(f"Jev input audit mismatch for {case_id}.")


def _jev_payload(
    dataset: dict[str, Any],
    routes: dict[str, Any],
    model: str,
    route_ids: set[str],
    completed: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    rows = [completed[case_id] for case_id in sorted(completed) if case_id in route_ids]
    return {
        "schema_version": "contexttrace-v9-climate-fever-jev-1.0",
        "experiment": EXPERIMENT,
        "split": SPLIT,
        "dataset_sha256": _sha256_json(dataset),
        "routes_sha256": _sha256_json(routes),
        "policy_id": EXPECTED_POLICY_ID,
        "requested_model": model,
        "routed_case_ids": sorted(route_ids),
        "completed": len(rows),
        "complete": len(rows) == len(route_ids),
        "evaluation_labels_sent": False,
        "stable_defaults_changed": False,
        "remote_provider_default_enabled": False,
        "rows": rows,
    }


def _relation_breakdown(
    case_ids: list[str], examples: dict[str, Any], decisions: dict[str, Any]
) -> dict[str, Any]:
    output = {}
    for relation in ("Entailment", "Contradiction", "NotMentioned"):
        selected = [
            cid for cid in case_ids if examples[cid]["source"]["relation"] == relation
        ]
        target = relation == "Entailment"
        output[relation] = {
            "cases": len(selected),
            "predicted_supported": sum(
                decisions[cid]["verdict"] == "supported" for cid in selected
            ),
            "accuracy": round(
                sum(
                    (decisions[cid]["verdict"] == "supported") == target
                    for cid in selected
                )
                / len(selected),
                4,
            ),
        }
    return output


def _example_map(dataset: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = list(dataset.get("examples") or [])
    result = {str(row["id"]): row for row in rows}
    if not rows or len(result) != len(rows):
        raise V9HoldoutError("Dataset case IDs must be non-empty and unique.")
    return result


def _row_map(result: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = list(result.get("rows") or [])
    mapped = {str(row["case_id"]): row for row in rows}
    if not rows or len(mapped) != len(rows):
        raise V9HoldoutError("Score case IDs must be non-empty and unique.")
    return mapped


def _sha256_json(value: object) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise V9HoldoutError(f"{path} must contain a JSON object.")
    return value


def _write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    score = subparsers.add_parser("score-local")
    score.add_argument("--dataset", required=True)
    score.add_argument("--v3-model-path", required=True)
    score.add_argument("--v3-manifest", required=True)
    score.add_argument("--v5-model-path", required=True)
    score.add_argument("--v5-manifest", required=True)
    score.add_argument("--pinned-nli-path", required=True)
    score.add_argument("--local-output", required=True)
    score.add_argument("--auxiliary-output", required=True)
    score.add_argument("--batch-size", type=int, default=16)
    route = subparsers.add_parser("route")
    route.add_argument("--dataset", required=True)
    route.add_argument("--local-scores", required=True)
    route.add_argument("--auxiliary-scores", required=True)
    route.add_argument("--v8-policy", required=True)
    route.add_argument("--v9-policy", required=True)
    route.add_argument("--output", required=True)
    remote = subparsers.add_parser("run-jev")
    remote.add_argument("--dataset", required=True)
    remote.add_argument("--routes", required=True)
    remote.add_argument("--output", required=True)
    remote.add_argument("--model", default="jev-latest")
    remote.add_argument("--env-file")
    remote.add_argument("--allow-remote", action="store_true")
    evaluate = subparsers.add_parser("evaluate")
    evaluate.add_argument("--dataset", required=True)
    evaluate.add_argument("--routes", required=True)
    evaluate.add_argument("--jev-result", required=True)
    evaluate.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    if args.command == "score-local":
        local, auxiliary = score_local_holdout(
            args.dataset,
            v3_model_path=args.v3_model_path,
            v3_manifest_path=args.v3_manifest,
            v5_model_path=args.v5_model_path,
            v5_manifest_path=args.v5_manifest,
            pinned_nli_path=args.pinned_nli_path,
            batch_size=args.batch_size,
        )
        _write(Path(args.local_output), local)
        _write(Path(args.auxiliary_output), auxiliary)
        print(
            json.dumps(
                {
                    "cases": local["cases"],
                    "local_output": args.local_output,
                    "auxiliary_output": args.auxiliary_output,
                },
                indent=2,
            )
        )
    elif args.command == "route":
        result = route_holdout(
            _load(Path(args.dataset)),
            _load(Path(args.local_scores)),
            _load(Path(args.auxiliary_scores)),
            _load(Path(args.v8_policy)),
            _load(Path(args.v9_policy)),
        )
        _write(Path(args.output), result)
        print(
            json.dumps(
                {
                    "remote_calls": result["remote_calls"],
                    "remote_call_rate": result["remote_call_rate"],
                },
                indent=2,
            )
        )
    elif args.command == "run-jev":
        result = run_jev_holdout(
            args.dataset,
            args.routes,
            output_path=args.output,
            model=args.model,
            allow_remote=args.allow_remote,
            env_file=args.env_file,
        )
        _write(Path(args.output), result)
        print(
            json.dumps(
                {"completed": result["completed"], "complete": result["complete"]},
                indent=2,
            )
        )
    else:
        result = evaluate_holdout(
            _load(Path(args.dataset)),
            _load(Path(args.routes)),
            _load(Path(args.jev_result)),
        )
        _write(Path(args.output), result)
        print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
