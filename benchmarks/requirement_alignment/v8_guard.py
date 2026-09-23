"""Calibrate a contradiction-aware local-first cascade on SciFact development."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import statistics
from pathlib import Path
from typing import Any

from contexttrace.config import load_config

from benchmarks.requirement_alignment.score_v6_cascade import score_local_models
from benchmarks.requirement_alignment.v6_cascade import (
    V6JevJudge,
    _baseline_metrics,
    _binary_metrics,
    _example_map,
    _jev_map,
    _local_map,
    _percentile,
    _ratio,
    _relation_breakdown,
    _load_env_file,
    build_jev_state,
    enforce_remote_policy,
    run_jev,
)


EXPERIMENT = "contexttrace_v8_contradiction_guard"
DEVELOPMENT_SPLIT = "scifact_development"
EVALUATION_SPLIT = "scifact_evaluation"
MISSING_THRESHOLDS = (0.50, 0.60, 0.70)
SUPPORTED_THRESHOLDS = (0.80, 0.825, 0.85, 0.875, 0.90)
CONTRADICTION_VETO_THRESHOLDS = (0.01, 0.02, 0.03, 0.04, 0.05, 0.075, 0.10, 0.20)
JEV_SUPPORT_THRESHOLDS = (0.50, 0.60, 0.70, 0.80, 0.90)
FALSE_POSITIVE_CAP = 0.05
RECALL_TARGET = 0.50
REMOTE_CALL_RATE_TARGET = 0.30
REVIEW_CONFIDENCE = 0.80


class V8GuardError(RuntimeError):
    """Raised when the v8 calibration contract is violated."""


def score_development(
    dataset_path: str | Path,
    *,
    v3_model_path: str | Path,
    v3_manifest_path: str | Path,
    v5_model_path: str | Path,
    v5_manifest_path: str | Path,
    batch_size: int = 8,
) -> dict[str, Any]:
    result = score_local_models(
        dataset_path,
        expected_split=DEVELOPMENT_SPLIT,
        v3_model_path=v3_model_path,
        v3_manifest_path=v3_manifest_path,
        v5_model_path=v5_model_path,
        v5_manifest_path=v5_manifest_path,
        batch_size=batch_size,
    )
    result.update(
        {
            "schema_version": "contexttrace-scifact-v8-local-scores-1.0",
            "experiment": EXPERIMENT,
            "source_dataset": "SciFact",
            "selection_split": DEVELOPMENT_SPLIT,
            "evaluation_split_accessed": False,
        }
    )
    return result


def run_jev_development(
    dataset_path: str | Path,
    local_scores_path: str | Path,
    *,
    output_path: str | Path,
    model: str,
    allow_remote: bool,
    env_file: str | Path | None,
) -> dict[str, Any]:
    result = run_jev(
        dataset_path,
        local_scores_path,
        expected_split=DEVELOPMENT_SPLIT,
        output_path=output_path,
        all_cases=True,
        policy_path=None,
        model=model,
        allow_remote=allow_remote,
        env_file=env_file,
    )
    result.update(
        {
            "schema_version": "contexttrace-scifact-v8-jev-development-1.0",
            "experiment": EXPERIMENT,
            "source_dataset": "SciFact",
            "selection_split": DEVELOPMENT_SPLIT,
            "evaluation_labels_sent": False,
            "evaluation_split_accessed": False,
        }
    )
    _write(Path(output_path), result)
    return result


def guarded_local_route(predictions: dict[str, Any], policy: dict[str, Any]) -> str:
    entailment = [
        float(predictions[model]["probabilities"]["entailment"])
        for model in ("v3", "v5")
    ]
    contradiction = [
        float(predictions[model]["probabilities"]["contradiction"])
        for model in ("v3", "v5")
    ]
    if min(entailment) >= float(policy["local_supported_threshold"]) and max(
        contradiction
    ) <= float(policy["local_contradiction_veto_threshold"]):
        return "supported"
    if max(entailment) <= float(policy["local_missing_threshold"]):
        return "missing"
    return "route"


def guarded_cascade_decision(
    predictions: dict[str, Any],
    *,
    policy: dict[str, Any],
    jev: dict[str, Any] | None,
) -> dict[str, Any]:
    local = guarded_local_route(predictions, policy)
    if local != "route":
        verdict = local
        source = "local_guarded_agreement"
        remote_called = False
        confidence = None
        jev_support_gate_applied = False
    elif jev is None:
        return {
            "verdict": "abstain",
            "decision_source": "local_uncertainty",
            "remote_called": False,
            "review_required": True,
            "review_reasons": ["local_uncertainty"],
            "jev_support_gate_applied": False,
        }
    else:
        confidence = float(jev["confidence"])
        remote_called = True
        trusted_support = bool(
            jev["verdict"] == "supported"
            and float(jev["probabilities"]["supported"])
            >= float(policy["jev_supported_probability"])
        )
        verdict = "supported" if trusted_support else "missing"
        source = "jev"
        jev_support_gate_applied = bool(
            jev["verdict"] == "supported" and not trusted_support
        )
    review_reasons = []
    if verdict == "supported":
        review_reasons.append("supported_verdict")
    if (
        remote_called
        and confidence is not None
        and confidence < float(policy["review_confidence"])
    ):
        review_reasons.append("jev_confidence_below_threshold")
    return {
        "verdict": verdict,
        "decision_source": source,
        "remote_called": remote_called,
        "review_required": bool(review_reasons),
        "review_reasons": review_reasons,
        "jev_support_gate_applied": jev_support_gate_applied,
    }


def evaluate_guarded_rows(
    examples: dict[str, dict[str, Any]],
    local_rows: dict[str, dict[str, Any]],
    jev_rows: dict[str, dict[str, Any]],
    *,
    policy: dict[str, Any],
    require_all_jev: bool = True,
) -> dict[str, Any]:
    case_ids = sorted(examples)
    if set(local_rows) != set(case_ids):
        raise V8GuardError("Local scores must cover every evaluated case.")
    expected_routes = {
        case_id
        for case_id in case_ids
        if guarded_local_route(local_rows[case_id]["predictions"], policy) == "route"
    }
    expected_jev = set(case_ids) if require_all_jev else expected_routes
    if set(jev_rows) != expected_jev:
        raise V8GuardError("Development inputs must cover identical case IDs.")
    local_decisions = []
    optional_decisions = []
    targets = []
    relations = []
    for case_id in case_ids:
        target = str(examples[case_id]["target"]["label"])
        targets.append(target == "covered")
        relations.append(str(examples[case_id]["source"]["relation"]))
        predictions = local_rows[case_id]["predictions"]
        local_decisions.append(
            guarded_cascade_decision(predictions, policy=policy, jev=None)
        )
        optional_decisions.append(
            guarded_cascade_decision(
                predictions,
                policy=policy,
                jev=(jev_rows.get(case_id) or {}).get("prediction"),
            )
        )

    optional_predictions = [row["verdict"] == "supported" for row in optional_decisions]
    optional_metrics = _binary_metrics(targets, optional_predictions)
    optional_metrics["false_support_case_ids"] = [
        case_id
        for case_id, target, prediction in zip(
            case_ids, targets, optional_predictions, strict=True
        )
        if not target and prediction
    ]
    optional_metrics["relation_breakdown"] = _relation_breakdown(
        relations, targets, optional_predictions
    )

    remote_ids = [
        case_id
        for case_id, decision in zip(case_ids, optional_decisions, strict=True)
        if decision["remote_called"]
    ]
    used_jev = [jev_rows[case_id]["prediction"] for case_id in remote_ids]
    automatic_rows = [
        (target, prediction, case_id)
        for target, prediction, case_id, decision in zip(
            targets, optional_predictions, case_ids, optional_decisions, strict=True
        )
        if not decision["review_required"]
    ]
    automatic_false_support = [
        case_id
        for target, prediction, case_id in automatic_rows
        if not target and prediction
    ]
    optional_operations = {
        "remote_calls": len(remote_ids),
        "remote_call_rate": _ratio(len(remote_ids), len(case_ids)),
        "routed_case_ids": remote_ids,
        "tokens": {
            "input": sum(int(row["usage"]["input_tokens"]) for row in used_jev),
            "output": sum(int(row["usage"]["output_tokens"]) for row in used_jev),
            "total": sum(int(row["usage"]["total_tokens"]) for row in used_jev),
        },
        "jev_latency_ms": {
            "total": round(sum(float(row["latency_ms"]) for row in used_jev), 3),
            "mean": (
                round(statistics.fmean(float(row["latency_ms"]) for row in used_jev), 3)
                if used_jev
                else 0.0
            ),
            "p95": _percentile([float(row["latency_ms"]) for row in used_jev], 0.95),
        },
        "automatic_coverage": _ratio(len(automatic_rows), len(case_ids)),
        "automatic_accuracy": _ratio(
            sum(target == prediction for target, prediction, _ in automatic_rows),
            len(automatic_rows),
        ),
        "automatic_false_support_count": len(automatic_false_support),
        "automatic_false_support_case_ids": automatic_false_support,
    }

    decided_local = [
        (target, decision["verdict"] == "supported", case_id, relation)
        for target, decision, case_id, relation in zip(
            targets, local_decisions, case_ids, relations, strict=True
        )
        if decision["verdict"] != "abstain"
    ]
    local_negative_decided = sum(not target for target, _, _, _ in decided_local)
    local_false_support = [
        case_id
        for target, prediction, case_id, _ in decided_local
        if not target and prediction
    ]
    local_contradiction_false_support = [
        case_id
        for target, prediction, case_id, relation in decided_local
        if not target and prediction and relation == "Contradiction"
    ]
    local_metrics = {
        "cases": len(case_ids),
        "automatic_cases": len(decided_local),
        "automatic_coverage": _ratio(len(decided_local), len(case_ids)),
        "automatic_accuracy": _ratio(
            sum(target == prediction for target, prediction, _, _ in decided_local),
            len(decided_local),
        ),
        "automatic_false_positive_rate": _ratio(
            len(local_false_support), local_negative_decided
        ),
        "automatic_false_support_count": len(local_false_support),
        "automatic_false_support_case_ids": local_false_support,
        "contradiction_false_support_count": len(local_contradiction_false_support),
        "contradiction_false_support_case_ids": local_contradiction_false_support,
        "abstentions": len(case_ids) - len(decided_local),
    }
    return {
        "policy": dict(policy),
        "local_only": {
            "metrics": local_metrics,
            "network_calls": 0,
            "privacy_behavior": "uncertain cases abstain without remote inference",
        },
        "optional_jev": {
            "metrics": optional_metrics,
            "operations": optional_operations,
        },
    }


def run_jev_evaluation(
    dataset_path: str | Path,
    local_scores_path: str | Path,
    policy_path: str | Path,
    *,
    output_path: str | Path,
    reuse_result_paths: list[str | Path],
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
        raise V8GuardError("TYPESAFE_API_KEY is not set.")
    dataset_file = Path(dataset_path)
    local_file = Path(local_scores_path)
    policy_file = Path(policy_path)
    dataset = _load(dataset_file)
    local_scores = _load(local_file)
    policy_manifest = _load(policy_file)
    validate_policy(policy_manifest)
    examples = _example_map(dataset)
    local_rows = _local_map(local_scores)
    if (
        any(row.get("split") != EVALUATION_SPLIT for row in examples.values())
        or local_scores.get("split") != EVALUATION_SPLIT
        or set(examples) != set(local_rows)
    ):
        raise V8GuardError("Evaluation inputs must match the SciFact evaluation split.")
    policy = dict(policy_manifest["policy"])
    route_ids = {
        case_id
        for case_id, row in local_rows.items()
        if guarded_local_route(row["predictions"], policy) == "route"
    }
    completed: dict[str, dict[str, Any]] = {}
    for result_path in reuse_result_paths:
        prior = _load(Path(result_path))
        for row in prior.get("rows") or []:
            case_id = str(row["case_id"])
            if case_id not in route_ids:
                continue
            prediction = row["prediction"]
            expected_state_hash = _sha256_json(build_jev_state(examples[case_id]))
            if prediction["input_audit"]["state_sha256"] != expected_state_hash:
                raise V8GuardError(
                    "Reused Jev row does not match current selected evidence."
                )
            if prediction.get("requested_model") != model:
                raise V8GuardError("Reused Jev row used a different requested model.")
            completed[case_id] = {"case_id": case_id, "prediction": prediction}

    output_file = Path(output_path)
    if output_file.is_file():
        checkpoint = _load(output_file)
        if (
            checkpoint.get("dataset_sha256") != _sha256_file(dataset_file)
            or checkpoint.get("local_scores_sha256") != _sha256_file(local_file)
            or checkpoint.get("policy_id") != policy_manifest["policy_id"]
            or checkpoint.get("requested_model") != model
            or set(checkpoint.get("routed_case_ids") or []) != route_ids
        ):
            raise V8GuardError("Existing v8 Jev checkpoint does not match this run.")
        completed.update(
            {str(row["case_id"]): row for row in checkpoint.get("rows") or []}
        )

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
        missing_ids = sorted(route_ids - set(completed))
        for index, case_id in enumerate(missing_ids, start=1):
            prediction = judge.verify(examples[case_id])
            completed[case_id] = {"case_id": case_id, "prediction": prediction}
            _write(
                output_file,
                _evaluation_jev_payload(
                    dataset_file=dataset_file,
                    local_file=local_file,
                    policy_manifest=policy_manifest,
                    model=model,
                    route_ids=route_ids,
                    completed=completed,
                    reused_result_paths=reuse_result_paths,
                ),
            )
            print("jev %d/%d %s" % (index, len(missing_ids), case_id), flush=True)
    finally:
        close = getattr(client, "close", None)
        if callable(close):
            close()
    return _evaluation_jev_payload(
        dataset_file=dataset_file,
        local_file=local_file,
        policy_manifest=policy_manifest,
        model=model,
        route_ids=route_ids,
        completed=completed,
        reused_result_paths=reuse_result_paths,
    )


def evaluate_posthoc(
    dataset_path: str | Path,
    local_scores_path: str | Path,
    jev_result_path: str | Path,
    policy_path: str | Path,
    *,
    v7_result_path: str | Path,
) -> dict[str, Any]:
    dataset_file = Path(dataset_path)
    local_file = Path(local_scores_path)
    jev_file = Path(jev_result_path)
    policy_file = Path(policy_path)
    dataset = _load(dataset_file)
    local_scores = _load(local_file)
    jev_result = _load(jev_file)
    policy_manifest = _load(policy_file)
    v7_result = _load(Path(v7_result_path))
    validate_policy(policy_manifest)
    examples = _example_map(dataset)
    local_rows = _local_map(local_scores)
    jev_rows = _jev_map(jev_result)
    if (
        any(row.get("split") != EVALUATION_SPLIT for row in examples.values())
        or local_scores.get("split") != EVALUATION_SPLIT
        or jev_result.get("split") != EVALUATION_SPLIT
    ):
        raise V8GuardError("Post-hoc inputs must use SciFact evaluation.")
    evaluated = evaluate_guarded_rows(
        examples,
        local_rows,
        jev_rows,
        policy=dict(policy_manifest["policy"]),
        require_all_jev=False,
    )
    baselines = {
        "v3_threshold_0_90": _baseline_metrics(examples, local_rows, "v3", 0.90),
        "v5_threshold_0_90": _baseline_metrics(examples, local_rows, "v5", 0.90),
    }
    candidate = {
        "policy": dict(policy_manifest["policy"]),
        "local_only": evaluated["local_only"],
        "optional_jev": evaluated["optional_jev"],
    }
    gates = _candidate_gates(candidate, baselines)
    old_false_support = set(
        v7_result["optional_jev"]["metrics"]["false_support_case_ids"]
    )
    new_false_support = set(
        evaluated["optional_jev"]["metrics"]["false_support_case_ids"]
    )
    return {
        "schema_version": "contexttrace-scifact-v8-posthoc-evaluation-1.0",
        "experiment": EXPERIMENT,
        "split": EVALUATION_SPLIT,
        "policy_id": policy_manifest["policy_id"],
        "policy_selection_split": DEVELOPMENT_SPLIT,
        "evaluation_used_for_selection": False,
        "evaluation_previously_consumed_by_v7": True,
        "eligible_as_fresh_release_evidence": False,
        "dataset_sha256": _sha256_file(dataset_file),
        "local_scores_sha256": _sha256_file(local_file),
        "jev_result_sha256": _sha256_file(jev_file),
        "policy_sha256": _sha256_file(policy_file),
        "baselines": baselines,
        **evaluated,
        "diagnostic_gates": gates,
        "comparison_to_v7": {
            "v7_false_support_case_ids": sorted(old_false_support),
            "v8_false_support_case_ids": sorted(new_false_support),
            "eliminated_false_support_case_ids": sorted(
                old_false_support - new_false_support
            ),
            "introduced_false_support_case_ids": sorted(
                new_false_support - old_false_support
            ),
        },
        "stable_defaults_changed": False,
        "remote_provider_default_enabled": False,
        "local_only_network_calls": 0,
    }


def _evaluation_jev_payload(
    *,
    dataset_file: Path,
    local_file: Path,
    policy_manifest: dict[str, Any],
    model: str,
    route_ids: set[str],
    completed: dict[str, dict[str, Any]],
    reused_result_paths: list[str | Path],
) -> dict[str, Any]:
    rows = [completed[key] for key in sorted(completed) if key in route_ids]
    return {
        "schema_version": "contexttrace-scifact-v8-jev-evaluation-1.0",
        "experiment": EXPERIMENT,
        "split": EVALUATION_SPLIT,
        "dataset_sha256": _sha256_file(dataset_file),
        "local_scores_sha256": _sha256_file(local_file),
        "policy_id": policy_manifest["policy_id"],
        "requested_model": model,
        "routed_case_ids": sorted(route_ids),
        "all_cases_requested": len(route_ids),
        "completed": len(rows),
        "complete": len(rows) == len(route_ids),
        "reused_result_files": [str(Path(path)) for path in reused_result_paths],
        "evaluation_labels_sent": False,
        "evaluation_previously_consumed_by_v7": True,
        "stable_defaults_changed": False,
        "remote_provider_default_enabled": False,
        "rows": rows,
    }


def calibrate_guard(
    dataset: dict[str, Any],
    local_scores: dict[str, Any],
    jev_result: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    _require_development_inputs(dataset, local_scores, jev_result)
    examples = _example_map(dataset)
    local_rows = _local_map(local_scores)
    jev_rows = _jev_map(jev_result)
    if set(examples) != set(local_rows) or set(examples) != set(jev_rows):
        raise V8GuardError("Calibration inputs must cover identical case IDs.")
    baselines = {
        "v3_threshold_0_90": _baseline_metrics(examples, local_rows, "v3", 0.90),
        "v5_threshold_0_90": _baseline_metrics(examples, local_rows, "v5", 0.90),
    }
    candidates = []
    for low in MISSING_THRESHOLDS:
        for high in SUPPORTED_THRESHOLDS:
            for contradiction_veto in CONTRADICTION_VETO_THRESHOLDS:
                for jev_gate in JEV_SUPPORT_THRESHOLDS:
                    policy = {
                        "local_missing_threshold": low,
                        "local_supported_threshold": high,
                        "local_contradiction_veto_threshold": contradiction_veto,
                        "jev_supported_probability": jev_gate,
                        "review_confidence": REVIEW_CONFIDENCE,
                        "always_review_supported": True,
                    }
                    evaluated = evaluate_guarded_rows(
                        examples, local_rows, jev_rows, policy=policy
                    )
                    candidate = {
                        "policy": policy,
                        "local_only": evaluated["local_only"],
                        "optional_jev": evaluated["optional_jev"],
                    }
                    candidate["gates"] = _candidate_gates(candidate, baselines)
                    candidates.append(candidate)
    selected = max(candidates, key=_candidate_key)
    policy_core = dict(selected["policy"])
    policy_id = _sha256_json(policy_core)
    policy_manifest = {
        "schema_version": "contexttrace-scifact-v8-guard-policy-1.0",
        "experiment": EXPERIMENT,
        "policy_id": policy_id,
        "selection_split": DEVELOPMENT_SPLIT,
        "evaluation_split_accessed": False,
        "policy": policy_core,
        "release_gates": {
            "positive_recall_minimum": RECALL_TARGET,
            "false_positive_rate_maximum": FALSE_POSITIVE_CAP,
            "local_automatic_false_positive_rate_maximum": FALSE_POSITIVE_CAP,
            "zero_contradiction_false_support": True,
            "remote_call_rate_maximum": REMOTE_CALL_RATE_TARGET,
            "accuracy_at_least_v3_threshold_0_90": True,
            "positive_recall_at_least_v3_threshold_0_90": True,
        },
        "decision_order": [
            "Run v3 and v5 locally on the same selected evidence.",
            "Accept supported only when both entailment probabilities meet local_supported_threshold and neither contradiction probability exceeds local_contradiction_veto_threshold.",
            "Accept missing only when both entailment probabilities are at or below local_missing_threshold.",
            "Under local_only, abstain on every remaining case without network access.",
            "When remote use is explicitly enabled, route remaining cases to one Jev Choice judgment.",
            "Accept routed support only when Jev selects supported and its supported probability meets jev_supported_probability.",
            "Require review for every supported decision and every low-confidence Jev decision.",
        ],
        "stable_defaults_changed": False,
        "remote_provider_default_enabled": False,
    }
    analysis = {
        "schema_version": "contexttrace-scifact-v8-guard-calibration-1.0",
        "experiment": EXPERIMENT,
        "policy_id": policy_id,
        "selection_split": DEVELOPMENT_SPLIT,
        "evaluation_split_accessed": False,
        "candidate_count": len(candidates),
        "release_ready_candidate_count": sum(
            bool(row["gates"]["all_release_gates_met"]) for row in candidates
        ),
        "quality_candidate_count": sum(
            bool(row["gates"]["quality_gates_met"]) for row in candidates
        ),
        "baselines": baselines,
        "selected": _candidate_summary(selected),
        "candidates": [_candidate_summary(row) for row in candidates],
        "stable_defaults_changed": False,
        "remote_provider_default_enabled": False,
    }
    return policy_manifest, analysis


def _candidate_gates(
    candidate: dict[str, Any], baselines: dict[str, dict[str, Any]]
) -> dict[str, bool]:
    optional = candidate["optional_jev"]
    metrics = optional["metrics"]
    operations = optional["operations"]
    local = candidate["local_only"]["metrics"]
    relation = metrics["relation_breakdown"]
    gates = {
        "positive_recall_at_least_0_50": metrics["positive_recall"] >= RECALL_TARGET,
        "false_positive_rate_at_most_0_05": metrics["false_positive_rate"]
        <= FALSE_POSITIVE_CAP,
        "zero_contradiction_false_support": relation["Contradiction"][
            "predicted_supported"
        ]
        == 0,
        "local_false_positive_rate_at_most_0_05": (
            local["automatic_false_positive_rate"] or 0.0
        )
        <= FALSE_POSITIVE_CAP,
        "local_zero_contradiction_false_support": local[
            "contradiction_false_support_count"
        ]
        == 0,
        "accuracy_at_least_v3": metrics["accuracy"]
        >= baselines["v3_threshold_0_90"]["accuracy"],
        "positive_recall_at_least_v3": metrics["positive_recall"]
        >= baselines["v3_threshold_0_90"]["positive_recall"],
        "remote_call_rate_at_most_0_30": operations["remote_call_rate"]
        <= REMOTE_CALL_RATE_TARGET,
    }
    quality_keys = tuple(key for key in gates if key != "remote_call_rate_at_most_0_30")
    gates["quality_gates_met"] = all(gates[key] for key in quality_keys)
    gates["all_release_gates_met"] = all(gates[key] for key in gates)
    return gates


def _candidate_key(candidate: dict[str, Any]) -> tuple[Any, ...]:
    gates = candidate["gates"]
    metrics = candidate["optional_jev"]["metrics"]
    operations = candidate["optional_jev"]["operations"]
    local = candidate["local_only"]["metrics"]
    return (
        gates["all_release_gates_met"],
        gates["quality_gates_met"],
        gates["zero_contradiction_false_support"],
        gates["local_zero_contradiction_false_support"],
        gates["false_positive_rate_at_most_0_05"],
        gates["local_false_positive_rate_at_most_0_05"],
        -float(operations["remote_call_rate"]),
        float(metrics["positive_recall"]),
        float(metrics["macro_f1"]),
        float(local["automatic_coverage"]),
        float(candidate["policy"]["jev_supported_probability"]),
    )


def _candidate_summary(candidate: dict[str, Any]) -> dict[str, Any]:
    metrics = candidate["optional_jev"]["metrics"]
    operations = candidate["optional_jev"]["operations"]
    local = candidate["local_only"]["metrics"]
    return {
        "policy": candidate["policy"],
        "gates": candidate["gates"],
        "optional_accuracy": metrics["accuracy"],
        "optional_macro_f1": metrics["macro_f1"],
        "optional_positive_recall": metrics["positive_recall"],
        "optional_false_positive_rate": metrics["false_positive_rate"],
        "optional_false_support_case_ids": metrics["false_support_case_ids"],
        "optional_relation_breakdown": metrics["relation_breakdown"],
        "remote_calls": operations["remote_calls"],
        "remote_call_rate": operations["remote_call_rate"],
        "routed_tokens": operations["tokens"],
        "routed_jev_latency_ms": operations["jev_latency_ms"],
        "local_automatic_coverage": local["automatic_coverage"],
        "local_automatic_accuracy": local["automatic_accuracy"],
        "local_automatic_false_positive_rate": local["automatic_false_positive_rate"],
        "local_false_support_case_ids": local["automatic_false_support_case_ids"],
        "local_contradiction_false_support_case_ids": local[
            "contradiction_false_support_case_ids"
        ],
    }


def _require_development_inputs(
    dataset: dict[str, Any],
    local_scores: dict[str, Any],
    jev_result: dict[str, Any],
) -> None:
    examples = list(dataset.get("examples") or [])
    if not examples or any(row.get("split") != DEVELOPMENT_SPLIT for row in examples):
        raise V8GuardError("Dataset must contain only SciFact development cases.")
    if local_scores.get("split") != DEVELOPMENT_SPLIT:
        raise V8GuardError("Local scores must use SciFact development.")
    if jev_result.get("split") != DEVELOPMENT_SPLIT:
        raise V8GuardError("Jev results must use SciFact development.")
    if jev_result.get("all_cases_requested") != len(examples):
        raise V8GuardError("Jev calibration must score every development case.")
    if jev_result.get("complete") is not True:
        raise V8GuardError("Jev development results are incomplete.")


def validate_policy(manifest: dict[str, Any]) -> None:
    policy = manifest.get("policy")
    if (
        manifest.get("selection_split") != DEVELOPMENT_SPLIT
        or manifest.get("evaluation_split_accessed") is not False
        or not isinstance(policy, dict)
        or manifest.get("policy_id") != _sha256_json(policy)
    ):
        raise V8GuardError("Frozen v8 policy manifest is invalid.")


def _sha256_json(value: object) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise V8GuardError("%s must contain a JSON object." % path)
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
    score.add_argument("--output", required=True)
    score.add_argument("--batch-size", type=int, default=8)
    jev = subparsers.add_parser("run-jev")
    jev.add_argument("--dataset", required=True)
    jev.add_argument("--local-scores", required=True)
    jev.add_argument("--output", required=True)
    jev.add_argument("--model", default="jev-latest")
    jev.add_argument("--env-file")
    jev.add_argument("--allow-remote", action="store_true")
    evaluation_jev = subparsers.add_parser("run-evaluation-jev")
    evaluation_jev.add_argument("--dataset", required=True)
    evaluation_jev.add_argument("--local-scores", required=True)
    evaluation_jev.add_argument("--policy", required=True)
    evaluation_jev.add_argument("--reuse-result", action="append", default=[])
    evaluation_jev.add_argument("--output", required=True)
    evaluation_jev.add_argument("--model", default="jev-latest")
    evaluation_jev.add_argument("--env-file")
    evaluation_jev.add_argument("--allow-remote", action="store_true")
    calibrate = subparsers.add_parser("calibrate")
    calibrate.add_argument("--dataset", required=True)
    calibrate.add_argument("--local-scores", required=True)
    calibrate.add_argument("--jev-result", required=True)
    calibrate.add_argument("--policy-output", required=True)
    calibrate.add_argument("--analysis-output", required=True)
    evaluate = subparsers.add_parser("evaluate-posthoc")
    evaluate.add_argument("--dataset", required=True)
    evaluate.add_argument("--local-scores", required=True)
    evaluate.add_argument("--jev-result", required=True)
    evaluate.add_argument("--policy", required=True)
    evaluate.add_argument("--v7-result", required=True)
    evaluate.add_argument("--output", required=True)
    args = parser.parse_args(argv)

    if args.command == "score-local":
        result = score_development(
            args.dataset,
            v3_model_path=args.v3_model_path,
            v3_manifest_path=args.v3_manifest,
            v5_model_path=args.v5_model_path,
            v5_manifest_path=args.v5_manifest,
            batch_size=args.batch_size,
        )
        _write(Path(args.output), result)
    elif args.command == "run-jev":
        result = run_jev_development(
            args.dataset,
            args.local_scores,
            output_path=args.output,
            model=args.model,
            allow_remote=args.allow_remote,
            env_file=args.env_file,
        )
        _write(Path(args.output), result)
    elif args.command == "run-evaluation-jev":
        result = run_jev_evaluation(
            args.dataset,
            args.local_scores,
            args.policy,
            output_path=args.output,
            reuse_result_paths=args.reuse_result,
            model=args.model,
            allow_remote=args.allow_remote,
            env_file=args.env_file,
        )
        _write(Path(args.output), result)
    elif args.command == "calibrate":
        policy, analysis = calibrate_guard(
            _load(Path(args.dataset)),
            _load(Path(args.local_scores)),
            _load(Path(args.jev_result)),
        )
        _write(Path(args.policy_output), policy)
        _write(Path(args.analysis_output), analysis)
        print(json.dumps(analysis["selected"], indent=2, sort_keys=True))
    else:
        result = evaluate_posthoc(
            args.dataset,
            args.local_scores,
            args.jev_result,
            args.policy,
            v7_result_path=args.v7_result,
        )
        _write(Path(args.output), result)
        print(json.dumps(result["diagnostic_gates"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
