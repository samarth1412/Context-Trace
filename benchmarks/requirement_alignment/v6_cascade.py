"""Calibrate and evaluate the local-first v6 verifier cascade with optional Jev."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import statistics
import time
from pathlib import Path
from typing import Any, Callable, Mapping

from contexttrace.config import load_config


LABELS = (
    "supported",
    "partially_supported",
    "unsupported",
    "contradicted",
    "unverifiable",
)
LABEL_CRITERIA = {
    "supported": "The selected evidence directly entails every material part of the claim.",
    "partially_supported": "The selected evidence supports some material parts of the claim, while other material parts are missing.",
    "unsupported": "The selected evidence is related to the claim but does not support what the claim asserts.",
    "contradicted": "The selected evidence conflicts with the claim, including a wrong entity, date, number, negation, causal direction, or attribution.",
    "unverifiable": "The selected evidence is too ambiguous to decide whether the claim is supported or contradicted.",
}
VERDICT_INSTRUCTIONS = (
    "Classify how the selected evidence relates to the claim. Judge only from the selected "
    "evidence. Do not use outside knowledge or infer facts from evidence that was not supplied."
)
LOW_THRESHOLDS = (0.10, 0.20, 0.30, 0.40, 0.50)
HIGH_THRESHOLDS = (0.80, 0.85, 0.90, 0.95)
JEV_SUPPORT_GATES = (0.50, 0.60, 0.70, 0.75, 0.80, 0.85, 0.90)
REVIEW_CONFIDENCE = 0.80
FALSE_POSITIVE_CAP = 0.05
RECALL_TARGET = 0.50


class V6CascadeError(RuntimeError):
    """Raised when v6 routing, remote use, or evaluation violates its protocol."""


def build_jev_state(example: dict[str, Any]) -> dict[str, Any]:
    """Construct the complete remote state from claim and selected evidence only."""
    return {
        "claim": str(example["input"]["claim"]),
        "selected_evidence": [
            {"id": str(item["id"]), "text": str(item["text"])}
            for item in example["input"]["evidence"]
        ],
    }


class V6JevJudge:
    def __init__(
        self,
        *,
        client: Any,
        choice_factory: Callable[..., object],
        model: str = "jev-latest",
    ) -> None:
        self.client = client
        self.choice_factory = choice_factory
        self.requested_model = model

    def verify(self, example: dict[str, Any]) -> dict[str, Any]:
        state = build_jev_state(example)
        questions = {
            "verdict": self.choice_factory(
                instructions=VERDICT_INSTRUCTIONS,
                criteria=LABEL_CRITERIA,
            )
        }
        started = time.perf_counter()
        response = self.client.system_one(
            state=state,
            questions=questions,
            model=self.requested_model,
        )
        latency_ms = round((time.perf_counter() - started) * 1000.0, 3)
        answers = getattr(response, "answers", None)
        if not isinstance(answers, Mapping) or "verdict" not in answers:
            raise V6CascadeError("TypeSafe response omitted answers['verdict'].")
        answer = answers["verdict"]
        verdict = str(getattr(answer, "choice", "")).strip().lower().replace("-", "_")
        if verdict not in LABELS:
            raise V6CascadeError("TypeSafe returned an unknown verdict: %r." % verdict)
        raw_probabilities = getattr(answer, "probabilities", None)
        if not isinstance(raw_probabilities, Mapping):
            raise V6CascadeError("TypeSafe response omitted verdict probabilities.")
        probabilities = {
            str(label): _unit_float(value, "probability[%s]" % label)
            for label, value in raw_probabilities.items()
        }
        missing = [label for label in LABELS if label not in probabilities]
        if missing:
            raise V6CascadeError(
                "TypeSafe response omitted verdict probabilities: %s."
                % ", ".join(missing)
            )
        confidence = _unit_float(getattr(answer, "confidence", None), "confidence")
        resolved_model = str(getattr(response, "model", "") or "").strip()
        if not resolved_model:
            raise V6CascadeError("TypeSafe response omitted the resolved model version.")
        usage = getattr(response, "usage", None)
        if usage is None:
            raise V6CascadeError("TypeSafe response omitted token usage.")
        input_tokens = _nonnegative_int(getattr(usage, "input_tokens", None), "input_tokens")
        output_tokens = _nonnegative_int(
            getattr(usage, "output_tokens", None), "output_tokens"
        )
        state_json = json.dumps(
            state, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
        return {
            "verdict": verdict,
            "probabilities": probabilities,
            "confidence": confidence,
            "requested_model": self.requested_model,
            "resolved_model": resolved_model,
            "latency_ms": latency_ms,
            "usage": {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": input_tokens + output_tokens,
            },
            "reason": None,
            "matched_facts": [],
            "missing_facts": [],
            "conflicting_facts": [],
            "input_audit": {
                "sent_fields": ["claim", "selected_evidence"],
                "state_sha256": hashlib.sha256(state_json.encode("utf-8")).hexdigest(),
                "selected_evidence_count": len(state["selected_evidence"]),
                "query_sent": False,
                "context_metadata_sent": False,
                "evaluation_label_sent": False,
            },
        }


def local_route(predictions: dict[str, Any], policy: dict[str, Any]) -> str:
    p3 = float(predictions["v3"]["entailment_probability"])
    p5 = float(predictions["v5"]["entailment_probability"])
    if min(p3, p5) >= float(policy["local_supported_threshold"]):
        return "supported"
    if max(p3, p5) <= float(policy["local_missing_threshold"]):
        return "missing"
    return "route"


def cascade_decision(
    predictions: dict[str, Any],
    *,
    policy: dict[str, Any],
    jev: dict[str, Any] | None,
) -> dict[str, Any]:
    local = local_route(predictions, policy)
    if local != "route":
        verdict = local
        source = "local_agreement"
        remote_called = False
        jev_support_gate_applied = False
        confidence = None
    else:
        if jev is None:
            return {
                "verdict": "abstain",
                "decision_source": "local_uncertainty",
                "remote_called": False,
                "review_required": True,
                "review_reasons": ["local_uncertainty"],
                "jev_support_gate_applied": False,
            }
        remote_called = True
        confidence = float(jev["confidence"])
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
    if remote_called and confidence is not None and confidence < float(
        policy["review_confidence"]
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


def calibrate_policy(
    dataset: dict[str, Any],
    local_scores: dict[str, Any],
    jev_result: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    _require_split(dataset, "cascade_calibration")
    _require_result_split(local_scores, "cascade_calibration")
    _require_result_split(jev_result, "cascade_calibration")
    examples = _example_map(dataset)
    local_rows = _local_map(local_scores)
    jev_rows = _jev_map(jev_result)
    if set(examples) != set(local_rows) or set(examples) != set(jev_rows):
        raise V6CascadeError("Calibration inputs must cover identical case IDs.")
    baselines = {
        "v3_threshold_0_90": _baseline_metrics(examples, local_rows, "v3", 0.90),
        "v5_threshold_0_90": _baseline_metrics(examples, local_rows, "v5", 0.90),
    }
    v3_baseline = baselines["v3_threshold_0_90"]
    candidates = []
    for low in LOW_THRESHOLDS:
        for high in HIGH_THRESHOLDS:
            for jev_gate in JEV_SUPPORT_GATES:
                policy = {
                    "local_missing_threshold": low,
                    "local_supported_threshold": high,
                    "jev_supported_probability": jev_gate,
                    "review_confidence": REVIEW_CONFIDENCE,
                    "always_review_supported": True,
                }
                evaluation = evaluate_rows(
                    examples,
                    local_rows,
                    jev_rows,
                    policy=policy,
                    require_all_jev=False,
                )
                metrics = evaluation["optional_jev"]["metrics"]
                local_metrics = evaluation["local_only"]["metrics"]
                promotion = bool(
                    metrics["false_positive_rate"] <= FALSE_POSITIVE_CAP
                    and metrics["positive_recall"] >= RECALL_TARGET
                    and metrics["accuracy"] >= v3_baseline["accuracy"]
                    and metrics["positive_recall"] >= v3_baseline["positive_recall"]
                    and (local_metrics["automatic_false_positive_rate"] or 0.0)
                    <= FALSE_POSITIVE_CAP
                )
                candidates.append(
                    {
                        "policy": policy,
                        "promotion_gates_met": promotion,
                        "optional_jev": {
                            "metrics": metrics,
                            "operations": evaluation["optional_jev"]["operations"],
                        },
                        "local_only": evaluation["local_only"],
                    }
                )
    selected = max(candidates, key=_candidate_key)
    policy_core = dict(selected["policy"])
    policy_id = _sha256_json(policy_core)
    manifest = {
        "schema_version": "contexttrace-requirement-v6-cascade-policy-1.0",
        "experiment": "contexttrace_v6_uncertainty_cascade",
        "policy_id": policy_id,
        "selection_split": "cascade_calibration",
        "evaluation_used_for_selection": False,
        "policy": policy_core,
        "promotion_gates": {
            "positive_recall_minimum": RECALL_TARGET,
            "false_positive_rate_maximum": FALSE_POSITIVE_CAP,
            "local_automatic_false_positive_rate_maximum": FALSE_POSITIVE_CAP,
            "accuracy_at_least_v3_threshold_0_90": True,
            "positive_recall_at_least_v3_threshold_0_90": True,
        },
        "decision_order": [
            "Run v3 and v5 locally on the same selected evidence.",
            "Accept supported only when both entailment probabilities meet local_supported_threshold.",
            "Accept missing only when both entailment probabilities are at or below local_missing_threshold.",
            "Under local_only, abstain on every remaining case without network access.",
            "When remote use is explicitly enabled, route remaining cases to one Jev Choice judgment.",
            "Accept routed support only when Jev selects supported and its supported probability meets jev_supported_probability.",
            "Require review for every supported decision and every low-confidence Jev decision.",
        ],
        "stable_defaults_changed": False,
        "remote_provider_default_enabled": False,
        "contractnli_test_accessed": False,
    }
    analysis = {
        "schema_version": "contexttrace-requirement-v6-cascade-calibration-1.0",
        "policy_id": policy_id,
        "selection_split": "cascade_calibration",
        "dataset_sha256": _sha256_json(dataset),
        "local_scores_sha256": _sha256_json(local_scores),
        "jev_result_sha256": _sha256_json(jev_result),
        "candidate_count": len(candidates),
        "qualifying_candidate_count": sum(
            bool(row["promotion_gates_met"]) for row in candidates
        ),
        "baselines": baselines,
        "selected": selected,
        "candidates": [_candidate_summary(row) for row in candidates],
        "evaluation_used_for_selection": False,
    }
    return manifest, analysis


def evaluate_frozen_policy(
    dataset: dict[str, Any],
    local_scores: dict[str, Any],
    jev_result: dict[str, Any],
    policy_manifest: dict[str, Any],
) -> dict[str, Any]:
    _require_split(dataset, "cascade_evaluation")
    _require_result_split(local_scores, "cascade_evaluation")
    _require_result_split(jev_result, "cascade_evaluation")
    _validate_policy(policy_manifest)
    examples = _example_map(dataset)
    local_rows = _local_map(local_scores)
    jev_rows = _jev_map(jev_result)
    if set(examples) != set(local_rows):
        raise V6CascadeError("Evaluation local scores do not match the dataset.")
    expected_routes = {
        case_id
        for case_id, row in local_rows.items()
        if local_route(row["predictions"], policy_manifest["policy"]) == "route"
    }
    if set(jev_rows) != expected_routes:
        raise V6CascadeError("Evaluation Jev rows must exactly match frozen routed IDs.")
    evaluated = evaluate_rows(
        examples,
        local_rows,
        jev_rows,
        policy=dict(policy_manifest["policy"]),
        require_all_jev=False,
    )
    optional_metrics = evaluated["optional_jev"]["metrics"]
    baselines = {
        "v3_threshold_0_90": _baseline_metrics(examples, local_rows, "v3", 0.90),
        "v5_threshold_0_90": _baseline_metrics(examples, local_rows, "v5", 0.90),
    }
    v3_baseline = baselines["v3_threshold_0_90"]
    absolute_gates_met = bool(
        optional_metrics["false_positive_rate"] <= FALSE_POSITIVE_CAP
        and optional_metrics["positive_recall"] >= RECALL_TARGET
        and (
            evaluated["local_only"]["metrics"]["automatic_false_positive_rate"]
            or 0.0
        )
        <= FALSE_POSITIVE_CAP
    )
    baseline_non_regression_met = bool(
        optional_metrics["accuracy"] >= v3_baseline["accuracy"]
        and optional_metrics["positive_recall"] >= v3_baseline["positive_recall"]
    )
    evaluation_gates_met = absolute_gates_met and baseline_non_regression_met
    return {
        "schema_version": "contexttrace-requirement-v6-cascade-evaluation-1.0",
        "experiment": "contexttrace_v6_uncertainty_cascade",
        "split": "cascade_evaluation",
        "policy_id": policy_manifest["policy_id"],
        "policy_selection_split": policy_manifest["selection_split"],
        "evaluation_used_for_selection": False,
        "absolute_gates_met": absolute_gates_met,
        "baseline_non_regression_met": baseline_non_regression_met,
        "evaluation_gates_met": evaluation_gates_met,
        "baselines": baselines,
        **evaluated,
        "stable_defaults_changed": False,
        "remote_provider_default_enabled": False,
        "contractnli_test_accessed": False,
    }


def evaluate_rows(
    examples: dict[str, dict[str, Any]],
    local_rows: dict[str, dict[str, Any]],
    jev_rows: dict[str, dict[str, Any]],
    *,
    policy: dict[str, Any],
    require_all_jev: bool,
) -> dict[str, Any]:
    case_ids = sorted(examples)
    if set(local_rows) != set(case_ids):
        raise V6CascadeError("Local rows do not cover the evaluated cases.")
    if require_all_jev and set(jev_rows) != set(case_ids):
        raise V6CascadeError("Jev rows do not cover the evaluated cases.")
    local_decisions = []
    optional_decisions = []
    targets = []
    relations = []
    for case_id in case_ids:
        target = str(examples[case_id]["target"]["label"])
        targets.append(target == "covered")
        relations.append(str(examples[case_id]["source"]["relation"]))
        predictions = local_rows[case_id]["predictions"]
        local_decisions.append(cascade_decision(predictions, policy=policy, jev=None))
        optional_decisions.append(
            cascade_decision(
                predictions,
                policy=policy,
                jev=(jev_rows.get(case_id) or {}).get("prediction"),
            )
        )
    optional_predictions = [row["verdict"] == "supported" for row in optional_decisions]
    optional_metrics = _binary_metrics(targets, optional_predictions)
    false_support_ids = [
        case_id
        for case_id, target, prediction in zip(
            case_ids, targets, optional_predictions, strict=True
        )
        if not target and prediction
    ]
    optional_metrics["false_support_case_ids"] = false_support_ids
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
        (target, decision["verdict"] == "supported", case_id)
        for target, decision, case_id in zip(
            targets, local_decisions, case_ids, strict=True
        )
        if decision["verdict"] != "abstain"
    ]
    local_negative_decided = sum(not target for target, _, _ in decided_local)
    local_false_support = [
        case_id
        for target, prediction, case_id in decided_local
        if not target and prediction
    ]
    local_metrics = {
        "cases": len(case_ids),
        "automatic_cases": len(decided_local),
        "automatic_coverage": _ratio(len(decided_local), len(case_ids)),
        "automatic_accuracy": _ratio(
            sum(target == prediction for target, prediction, _ in decided_local),
            len(decided_local),
        ),
        "automatic_false_positive_rate": _ratio(
            len(local_false_support), local_negative_decided
        ),
        "automatic_false_support_count": len(local_false_support),
        "automatic_false_support_case_ids": local_false_support,
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
        "rows": [
            {
                "case_id": case_id,
                "relation": relation,
                "target": "covered" if target else "missing",
                "local_only": local_decision,
                "optional_jev": optional_decision,
            }
            for case_id, relation, target, local_decision, optional_decision in zip(
                case_ids,
                relations,
                targets,
                local_decisions,
                optional_decisions,
                strict=True,
            )
        ],
    }


def run_jev(
    dataset_path: str | Path,
    local_scores_path: str | Path,
    *,
    expected_split: str,
    output_path: str | Path,
    all_cases: bool,
    policy_path: str | Path | None,
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
        raise V6CascadeError("TYPESAFE_API_KEY is not set.")
    dataset_file = Path(dataset_path)
    local_file = Path(local_scores_path)
    dataset = _load(dataset_file)
    local_scores = _load(local_file)
    _require_split(dataset, expected_split)
    _require_result_split(local_scores, expected_split)
    examples = _example_map(dataset)
    local_rows = _local_map(local_scores)
    if set(examples) != set(local_rows):
        raise V6CascadeError("Jev dataset and local scores do not match.")
    if all_cases:
        route_ids = set(examples)
        policy_id = None
    else:
        if policy_path is None:
            raise V6CascadeError("Frozen policy is required for routed evaluation.")
        policy_manifest = _load(Path(policy_path))
        _validate_policy(policy_manifest)
        route_ids = {
            case_id
            for case_id, row in local_rows.items()
            if local_route(row["predictions"], policy_manifest["policy"]) == "route"
        }
        policy_id = policy_manifest["policy_id"]

    output_file = Path(output_path)
    completed: dict[str, dict[str, Any]] = {}
    if output_file.is_file():
        checkpoint = _load(output_file)
        if (
            checkpoint.get("dataset_sha256") != _sha256(dataset_file)
            or checkpoint.get("local_scores_sha256") != _sha256(local_file)
            or checkpoint.get("requested_model") != model
            or set(checkpoint.get("routed_case_ids") or []) != route_ids
        ):
            raise V6CascadeError("Existing Jev checkpoint does not match this run.")
        completed = {
            str(row["case_id"]): row for row in checkpoint.get("rows") or []
        }

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
        for index, case_id in enumerate(sorted(route_ids), start=1):
            if case_id in completed:
                continue
            prediction = judge.verify(examples[case_id])
            completed[case_id] = {"case_id": case_id, "prediction": prediction}
            payload = _jev_payload(
                expected_split=expected_split,
                dataset_file=dataset_file,
                local_file=local_file,
                requested_model=model,
                route_ids=route_ids,
                policy_id=policy_id,
                completed=completed,
            )
            _write(output_file, payload)
            print("jev %d/%d %s" % (index, len(route_ids), case_id), flush=True)
    finally:
        close = getattr(client, "close", None)
        if callable(close):
            close()
    return _jev_payload(
        expected_split=expected_split,
        dataset_file=dataset_file,
        local_file=local_file,
        requested_model=model,
        route_ids=route_ids,
        policy_id=policy_id,
        completed=completed,
    )


def enforce_remote_policy(*, local_only: bool, allow_remote: bool) -> None:
    if local_only:
        raise V6CascadeError(
            "Jev is blocked while ContextTrace local_only is enabled. Set "
            "CONTEXTTRACE_LOCAL_ONLY=false and pass --allow-remote."
        )
    if not allow_remote:
        raise V6CascadeError("Remote Jev use requires the explicit --allow-remote flag.")


def _jev_payload(
    *,
    expected_split: str,
    dataset_file: Path,
    local_file: Path,
    requested_model: str,
    route_ids: set[str],
    policy_id: str | None,
    completed: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    rows = [completed[key] for key in sorted(completed)]
    return {
        "schema_version": "contexttrace-requirement-v6-jev-result-1.0",
        "experiment": "contexttrace_v6_uncertainty_cascade",
        "split": expected_split,
        "dataset_sha256": _sha256(dataset_file),
        "local_scores_sha256": _sha256(local_file),
        "requested_model": requested_model,
        "policy_id": policy_id,
        "all_cases_requested": len(route_ids),
        "routed_case_ids": sorted(route_ids),
        "completed": len(rows),
        "complete": len(rows) == len(route_ids),
        "stable_defaults_changed": False,
        "remote_provider_default_enabled": False,
        "contractnli_test_accessed": False,
        "rows": rows,
    }


def _candidate_key(candidate: dict[str, Any]) -> tuple[Any, ...]:
    optional = candidate["optional_jev"]
    metrics = optional["metrics"]
    operations = optional["operations"]
    return (
        bool(candidate["promotion_gates_met"]),
        metrics["false_positive_rate"] <= FALSE_POSITIVE_CAP,
        -float(operations["remote_call_rate"]),
        float(metrics["positive_recall"]),
        float(metrics["macro_f1"]),
        float(candidate["local_only"]["metrics"]["automatic_coverage"]),
        float(candidate["policy"]["jev_supported_probability"]),
    )


def _candidate_summary(candidate: dict[str, Any]) -> dict[str, Any]:
    metrics = candidate["optional_jev"]["metrics"]
    operations = candidate["optional_jev"]["operations"]
    local = candidate["local_only"]["metrics"]
    return {
        "policy": candidate["policy"],
        "promotion_gates_met": candidate["promotion_gates_met"],
        "optional_accuracy": metrics["accuracy"],
        "optional_macro_f1": metrics["macro_f1"],
        "optional_positive_recall": metrics["positive_recall"],
        "optional_false_positive_rate": metrics["false_positive_rate"],
        "remote_calls": operations["remote_calls"],
        "remote_call_rate": operations["remote_call_rate"],
        "local_automatic_coverage": local["automatic_coverage"],
        "local_automatic_false_positive_rate": local[
            "automatic_false_positive_rate"
        ],
    }


def _baseline_metrics(
    examples: dict[str, dict[str, Any]],
    local_rows: dict[str, dict[str, Any]],
    model: str,
    threshold: float,
) -> dict[str, Any]:
    case_ids = sorted(examples)
    targets = [examples[key]["target"]["label"] == "covered" for key in case_ids]
    predictions = [
        float(local_rows[key]["predictions"][model]["entailment_probability"])
        >= threshold
        for key in case_ids
    ]
    result = _binary_metrics(targets, predictions)
    result["threshold"] = threshold
    return result


def _binary_metrics(targets: list[bool], predictions: list[bool]) -> dict[str, Any]:
    tp = sum(target and prediction for target, prediction in zip(targets, predictions, strict=True))
    tn = sum(not target and not prediction for target, prediction in zip(targets, predictions, strict=True))
    fp = sum(not target and prediction for target, prediction in zip(targets, predictions, strict=True))
    fn = sum(target and not prediction for target, prediction in zip(targets, predictions, strict=True))
    positive_recall = tp / (tp + fn) if tp + fn else 0.0
    negative_recall = tn / (tn + fp) if tn + fp else 0.0
    positive_precision = tp / (tp + fp) if tp + fp else 0.0
    negative_precision = tn / (tn + fn) if tn + fn else 0.0
    positive_f1 = (
        2 * positive_precision * positive_recall / (positive_precision + positive_recall)
        if positive_precision + positive_recall
        else 0.0
    )
    negative_f1 = (
        2 * negative_precision * negative_recall / (negative_precision + negative_recall)
        if negative_precision + negative_recall
        else 0.0
    )
    return {
        "cases": len(targets),
        "accuracy": round((tp + tn) / len(targets), 4),
        "macro_f1": round(statistics.fmean((positive_f1, negative_f1)), 4),
        "positive_recall": round(positive_recall, 4),
        "negative_recall": round(negative_recall, 4),
        "false_positive_rate": round(fp / (tn + fp), 4),
        "confusion": {
            "negative": {"negative": tn, "positive": fp},
            "positive": {"negative": fn, "positive": tp},
        },
    }


def _relation_breakdown(
    relations: list[str], targets: list[bool], predictions: list[bool]
) -> dict[str, Any]:
    output = {}
    for relation in sorted(set(relations)):
        indexes = [index for index, value in enumerate(relations) if value == relation]
        output[relation] = {
            "cases": len(indexes),
            "predicted_supported": sum(predictions[index] for index in indexes),
            "accuracy": round(
                sum(targets[index] == predictions[index] for index in indexes)
                / len(indexes),
                4,
            ),
        }
    return output


def _example_map(dataset: dict[str, Any]) -> dict[str, dict[str, Any]]:
    examples = list(dataset.get("examples") or [])
    output = {str(row["id"]): row for row in examples}
    if not examples or len(output) != len(examples):
        raise V6CascadeError("Dataset cases must be non-empty and unique.")
    return output


def _local_map(result: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = list(result.get("rows") or [])
    output = {str(row["case_id"]): row for row in rows}
    if not rows or len(output) != len(rows):
        raise V6CascadeError("Local score rows must be non-empty and unique.")
    return output


def _jev_map(result: dict[str, Any]) -> dict[str, dict[str, Any]]:
    if result.get("complete") is not True:
        raise V6CascadeError("Jev result is incomplete.")
    rows = list(result.get("rows") or [])
    output = {str(row["case_id"]): row for row in rows}
    if len(output) != len(rows):
        raise V6CascadeError("Jev result rows must have unique case IDs.")
    return output


def _require_split(dataset: dict[str, Any], expected: str) -> None:
    examples = list(dataset.get("examples") or [])
    if not examples or any(row.get("split") != expected for row in examples):
        raise V6CascadeError("Dataset does not match expected split %s." % expected)


def _require_result_split(result: dict[str, Any], expected: str) -> None:
    if result.get("split") != expected:
        raise V6CascadeError("Result does not match expected split %s." % expected)


def _validate_policy(manifest: dict[str, Any]) -> None:
    policy = manifest.get("policy")
    if (
        manifest.get("selection_split") != "cascade_calibration"
        or manifest.get("evaluation_used_for_selection") is not False
        or not isinstance(policy, dict)
        or manifest.get("policy_id") != _sha256_json(policy)
    ):
        raise V6CascadeError("Frozen v6 policy manifest is invalid.")


def _unit_float(value: object, field: str) -> float:
    try:
        number = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError) as error:
        raise V6CascadeError("TypeSafe %s was not numeric." % field) from error
    if not 0.0 <= number <= 1.0:
        raise V6CascadeError("TypeSafe %s must be between zero and one." % field)
    return number


def _nonnegative_int(value: object, field: str) -> int:
    if isinstance(value, bool):
        raise V6CascadeError("TypeSafe %s was not an integer." % field)
    try:
        number = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError) as error:
        raise V6CascadeError("TypeSafe %s was not an integer." % field) from error
    if number < 0:
        raise V6CascadeError("TypeSafe %s must be nonnegative." % field)
    return number


def _ratio(numerator: int, denominator: int) -> float | None:
    return round(numerator / denominator, 4) if denominator else None


def _percentile(values: list[float], quantile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    rank = (len(ordered) - 1) * quantile
    lower = int(rank)
    upper = min(lower + 1, len(ordered) - 1)
    return round(ordered[lower] + (ordered[upper] - ordered[lower]) * (rank - lower), 3)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _sha256_json(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise V6CascadeError("%s must contain a JSON object." % path)
    return value


def _write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _load_env_file(path: str | Path) -> None:
    for raw_line in Path(path).read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key not in {"TYPESAFE_API_KEY", "TYPESAFE_BASE_URL", "TYPESAFE_ENDPOINT"}:
            continue
        os.environ.setdefault(key, value.strip().strip("\"'"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    run = subparsers.add_parser("run-jev")
    run.add_argument("--dataset", required=True)
    run.add_argument("--local-scores", required=True)
    run.add_argument(
        "--split", required=True, choices=("cascade_calibration", "cascade_evaluation")
    )
    run.add_argument("--output", required=True)
    run.add_argument("--all-cases", action="store_true")
    run.add_argument("--policy")
    run.add_argument("--model", default="jev-latest")
    run.add_argument("--allow-remote", action="store_true")
    run.add_argument("--env-file")

    calibrate = subparsers.add_parser("calibrate")
    calibrate.add_argument("--dataset", required=True)
    calibrate.add_argument("--local-scores", required=True)
    calibrate.add_argument("--jev-result", required=True)
    calibrate.add_argument("--policy-output", required=True)
    calibrate.add_argument("--analysis-output", required=True)

    evaluate = subparsers.add_parser("evaluate")
    evaluate.add_argument("--dataset", required=True)
    evaluate.add_argument("--local-scores", required=True)
    evaluate.add_argument("--jev-result", required=True)
    evaluate.add_argument("--policy", required=True)
    evaluate.add_argument("--output", required=True)

    args = parser.parse_args(argv)
    if args.command == "run-jev":
        result = run_jev(
            args.dataset,
            args.local_scores,
            expected_split=args.split,
            output_path=args.output,
            all_cases=args.all_cases,
            policy_path=args.policy,
            model=args.model,
            allow_remote=args.allow_remote,
            env_file=args.env_file,
        )
        _write(Path(args.output), result)
        print(json.dumps({"completed": result["completed"], "complete": result["complete"]}, indent=2))
    elif args.command == "calibrate":
        policy, analysis = calibrate_policy(
            _load(Path(args.dataset)),
            _load(Path(args.local_scores)),
            _load(Path(args.jev_result)),
        )
        _write(Path(args.policy_output), policy)
        _write(Path(args.analysis_output), analysis)
        print(json.dumps(analysis["selected"], indent=2, sort_keys=True))
    else:
        result = evaluate_frozen_policy(
            _load(Path(args.dataset)),
            _load(Path(args.local_scores)),
            _load(Path(args.jev_result)),
            _load(Path(args.policy)),
        )
        _write(Path(args.output), result)
        print(
            json.dumps(
                {
                    "evaluation_gates_met": result["evaluation_gates_met"],
                    "local_only": result["local_only"],
                    "optional_jev": result["optional_jev"],
                },
                indent=2,
                sort_keys=True,
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
