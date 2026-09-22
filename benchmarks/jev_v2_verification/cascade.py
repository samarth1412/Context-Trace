"""Calibrate and evaluate a frozen local-first stable-plus-Jev cascade."""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
from pathlib import Path
from typing import Any

from benchmarks.jev_v2_verification.extension_analysis import exact_mcnemar

class CascadeError(RuntimeError):
    """Raised when cascade calibration or frozen evaluation is invalid."""


ROUTING_THRESHOLDS = (0.80, 0.85, 0.90, 0.95, 0.99, 1.00)
SUPPORT_GATES = (0.00, 0.50, 0.60, 0.65, 0.70, 0.75, 0.80, 0.85, 0.90)
REVIEW_THRESHOLD = 0.80
MAX_DEVELOPMENT_FALSE_SUPPORT_RATE = 0.05


def calibrate_policy(
    development_result: dict[str, Any],
    *,
    source_sha256: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Choose a policy using development predictions and labels only."""

    _require_split(development_result, "development")
    rows = _validated_rows(development_result)
    baseline_policy = {
        "local_supported_confidence": 1.01,
        "jev_supported_probability": 0.0,
        "review_confidence": REVIEW_THRESHOLD,
        "always_review_supported": True,
    }
    baseline = evaluate_rows(rows, policy=baseline_policy)
    candidates: list[dict[str, Any]] = []
    for routing_threshold in ROUTING_THRESHOLDS:
        for support_gate in SUPPORT_GATES:
            policy = {
                "local_supported_confidence": routing_threshold,
                "jev_supported_probability": support_gate,
                "review_confidence": REVIEW_THRESHOLD,
                "always_review_supported": True,
            }
            result = evaluate_rows(rows, policy=policy)
            qualifies = bool(
                result["metrics"]["five_way_accuracy"]
                >= baseline["metrics"]["five_way_accuracy"]
                and result["metrics"]["binary_accuracy"]
                >= baseline["metrics"]["binary_accuracy"]
                and (result["metrics"]["false_support_rate"] or 0.0)
                <= MAX_DEVELOPMENT_FALSE_SUPPORT_RATE
            )
            candidates.append(
                {
                    "policy": policy,
                    "qualifies": qualifies,
                    "metrics": result["metrics"],
                    "operations": result["operations"],
                }
            )
    qualified = [candidate for candidate in candidates if candidate["qualifies"]]
    if not qualified:
        raise CascadeError("No development policy satisfied the frozen safety constraints.")
    selected = max(
        qualified,
        key=lambda candidate: (
            candidate["operations"]["remote_calls_saved"],
            candidate["metrics"]["binary_accuracy"],
            candidate["metrics"]["five_way_accuracy"],
            candidate["metrics"]["supported_recall"],
            candidate["policy"]["local_supported_confidence"],
            -candidate["policy"]["jev_supported_probability"],
        ),
    )
    policy_core = dict(selected["policy"])
    policy_id = _sha256_json(policy_core)
    manifest = {
        "schema_version": "1.0",
        "experiment": "contexttrace_local_first_jev_cascade",
        "policy_id": policy_id,
        "selection_split": "development",
        "development_source_sha256": source_sha256,
        "heldout_used_for_selection": False,
        "stable_defaults_changed": False,
        "remote_provider_default_enabled": False,
        "policy": policy_core,
        "decision_order": [
            "Run the stable semantic verifier locally.",
            "Accept a local supported verdict only at or above local_supported_confidence.",
            "Otherwise call Jev on the already-selected claim-evidence input.",
            "If Jev predicts supported below jev_supported_probability, use the local verdict.",
            "Require review for every final supported verdict and every low-confidence Jev verdict.",
        ],
        "development_constraints": {
            "five_way_accuracy_at_least_always_jev": True,
            "binary_accuracy_at_least_always_jev": True,
            "maximum_false_support_rate": MAX_DEVELOPMENT_FALSE_SUPPORT_RATE,
        },
    }
    analysis = {
        "schema_version": "1.0",
        "selection_split": "development",
        "source_sha256": source_sha256,
        "baseline_always_jev": baseline,
        "selected_policy_id": policy_id,
        "selected": selected,
        "candidate_count": len(candidates),
        "qualifying_candidate_count": len(qualified),
        "candidates": candidates,
    }
    return manifest, analysis


def evaluate_frozen(
    result: dict[str, Any],
    *,
    manifest: dict[str, Any],
    expected_split: str,
    source_sha256: str,
) -> dict[str, Any]:
    """Evaluate one split with a pre-existing development-selected policy."""

    _validate_manifest(manifest)
    _require_split(result, expected_split)
    evaluated = evaluate_rows(_validated_rows(result), policy=dict(manifest["policy"]))
    return {
        "schema_version": "1.0",
        "experiment": "contexttrace_local_first_jev_cascade",
        "split": expected_split,
        "source_sha256": source_sha256,
        "policy_id": manifest["policy_id"],
        "policy_selection_split": manifest["selection_split"],
        "heldout_used_for_selection": manifest["heldout_used_for_selection"],
        "stable_defaults_changed": False,
        "remote_provider_default_enabled": False,
        **evaluated,
    }


def evaluate_rows(
    rows: list[dict[str, Any]],
    *,
    policy: dict[str, Any],
) -> dict[str, Any]:
    decisions = [cascade_decision(row["predictions"], policy=policy) for row in rows]
    gold = [str(row["expected_verdict"]) for row in rows]
    predictions = [str(decision["verdict"]) for decision in decisions]
    jev_predictions = [str(row["predictions"]["jev"]["verdict"]) for row in rows]
    five_way_correct = sum(left == right for left, right in zip(gold, predictions, strict=True))
    binary_gold = [value == "supported" for value in gold]
    binary_predictions = [value == "supported" for value in predictions]
    jev_binary_predictions = [value == "supported" for value in jev_predictions]
    binary_correct = sum(
        left == right for left, right in zip(binary_gold, binary_predictions, strict=True)
    )
    supported_total = sum(binary_gold)
    negative_total = len(rows) - supported_total
    supported_true = sum(
        expected and predicted
        for expected, predicted in zip(binary_gold, binary_predictions, strict=True)
    )
    false_supported = [
        str(row["case_id"])
        for row, expected, predicted in zip(rows, binary_gold, binary_predictions, strict=True)
        if not expected and predicted
    ]
    auto_rows = [
        (row, decision)
        for row, decision in zip(rows, decisions, strict=True)
        if not decision["review_required"]
    ]
    auto_correct = sum(
        decision["verdict"] == row["expected_verdict"] for row, decision in auto_rows
    )
    auto_false_supported = [
        str(row["case_id"])
        for row, decision in auto_rows
        if row["expected_verdict"] != "supported" and decision["verdict"] == "supported"
    ]
    remote_calls = sum(bool(decision["remote_called"]) for decision in decisions)
    all_input_tokens = sum(
        int(row["predictions"]["jev"]["usage"]["input_tokens"]) for row in rows
    )
    all_output_tokens = sum(
        int(row["predictions"]["jev"]["usage"]["output_tokens"]) for row in rows
    )
    used_input_tokens = sum(
        int(row["predictions"]["jev"]["usage"]["input_tokens"])
        for row, decision in zip(rows, decisions, strict=True)
        if decision["remote_called"]
    )
    used_output_tokens = sum(
        int(row["predictions"]["jev"]["usage"]["output_tokens"])
        for row, decision in zip(rows, decisions, strict=True)
        if decision["remote_called"]
    )
    latencies = [
        float(row["predictions"]["stable_semantic"]["latency_ms"])
        + (
            float(row["predictions"]["jev"]["latency_ms"])
            if decision["remote_called"]
            else 0.0
        )
        for row, decision in zip(rows, decisions, strict=True)
    ]
    return {
        "policy": dict(policy),
        "metrics": {
            "cases": len(rows),
            "five_way_accuracy": _ratio(five_way_correct, len(rows)),
            "observed_label_macro_f1": _macro_f1(gold, predictions),
            "binary_accuracy": _ratio(binary_correct, len(rows)),
            "supported_recall": _ratio(supported_true, supported_total),
            "false_support_rate": _ratio(len(false_supported), negative_total),
            "false_support_count": len(false_supported),
            "false_support_case_ids": false_supported,
            "automatic_coverage": _ratio(len(auto_rows), len(rows)),
            "automatic_accuracy": _ratio(auto_correct, len(auto_rows)),
            "automatic_false_support_count": len(auto_false_supported),
            "automatic_false_support_case_ids": auto_false_supported,
            "review_count": len(rows) - len(auto_rows),
        },
        "operations": {
            "remote_calls": remote_calls,
            "remote_call_rate": _ratio(remote_calls, len(rows)),
            "remote_calls_saved": len(rows) - remote_calls,
            "remote_call_reduction": _ratio(len(rows) - remote_calls, len(rows)),
            "tokens": {
                "input": used_input_tokens,
                "output": used_output_tokens,
                "total": used_input_tokens + used_output_tokens,
                "always_jev_total": all_input_tokens + all_output_tokens,
                "saved": (all_input_tokens + all_output_tokens)
                - (used_input_tokens + used_output_tokens),
            },
            "sequential_latency_ms": {
                "mean": round(statistics.fmean(latencies), 3),
                "p50": _percentile(latencies, 0.50),
                "p95": _percentile(latencies, 0.95),
            },
        },
        "paired_vs_always_jev": {
            "five_way": exact_mcnemar(gold, predictions, jev_predictions),
            "binary": exact_mcnemar(
                ["supported" if value else "not_supported" for value in binary_gold],
                ["supported" if value else "not_supported" for value in binary_predictions],
                ["supported" if value else "not_supported" for value in jev_binary_predictions],
            ),
        },
        "rows": [
            {
                "case_id": row["case_id"],
                "expected_verdict": row["expected_verdict"],
                "decision": decision,
            }
            for row, decision in zip(rows, decisions, strict=True)
        ],
    }


def cascade_decision(
    predictions: dict[str, Any],
    *,
    policy: dict[str, Any],
) -> dict[str, Any]:
    """Apply a policy without reading an evaluation label."""

    stable = predictions["stable_semantic"]
    jev = predictions["jev"]
    use_local = bool(
        stable["verdict"] == "supported"
        and float(stable["confidence"]) >= float(policy["local_supported_confidence"])
    )
    remote_called = not use_local
    verdict = str(stable["verdict"] if use_local else jev["verdict"])
    source = "stable_semantic" if use_local else "jev"
    support_gate_applied = False
    if (
        remote_called
        and verdict == "supported"
        and float(jev["probabilities"]["supported"])
        < float(policy["jev_supported_probability"])
    ):
        verdict = str(stable["verdict"])
        source = "stable_fallback_after_jev_support_gate"
        support_gate_applied = True
    review_reasons: list[str] = []
    if bool(policy["always_review_supported"]) and verdict == "supported":
        review_reasons.append("supported_verdict")
    if remote_called and float(jev["top_probability"]) < float(policy["review_confidence"]):
        review_reasons.append("jev_confidence_below_threshold")
    if verdict == "unverifiable":
        review_reasons.append("unverifiable_verdict")
    return {
        "verdict": verdict,
        "decision_source": source,
        "remote_called": remote_called,
        "support_gate_applied": support_gate_applied,
        "review_required": bool(review_reasons),
        "review_reasons": review_reasons,
    }


def _validated_rows(result: dict[str, Any]) -> list[dict[str, Any]]:
    rows = result.get("rows")
    if not isinstance(rows, list) or not rows:
        raise CascadeError("Result must contain non-empty rows.")
    for row in rows:
        predictions = row.get("predictions") or {}
        if "stable_semantic" not in predictions or "jev" not in predictions:
            raise CascadeError("Each row must contain stable_semantic and Jev predictions.")
        if predictions["jev"].get("reason") is not None:
            raise CascadeError("Jev explanation must remain absent in cascade inputs.")
    return rows


def _require_split(result: dict[str, Any], expected: str) -> None:
    split = result.get("split") or {}
    actual = str(split.get("split") if isinstance(split, dict) else split)
    if actual != expected:
        raise CascadeError("Expected %s result, got %s." % (expected, actual or "unknown"))


def _validate_manifest(manifest: dict[str, Any]) -> None:
    if manifest.get("selection_split") != "development":
        raise CascadeError("Frozen cascade policy must be selected on development data.")
    if manifest.get("heldout_used_for_selection") is not False:
        raise CascadeError("Cascade policy does not attest held-out isolation.")
    policy = manifest.get("policy")
    if not isinstance(policy, dict) or manifest.get("policy_id") != _sha256_json(policy):
        raise CascadeError("Cascade policy id does not match its frozen policy.")


def _macro_f1(gold: list[str], predictions: list[str]) -> float:
    labels = sorted(set(gold))
    scores = []
    for label in labels:
        tp = sum(g == p == label for g, p in zip(gold, predictions, strict=True))
        fp = sum(g != label and p == label for g, p in zip(gold, predictions, strict=True))
        fn = sum(g == label and p != label for g, p in zip(gold, predictions, strict=True))
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        scores.append(
            2 * precision * recall / (precision + recall) if precision + recall else 0.0
        )
    return round(statistics.fmean(scores), 4)


def _ratio(numerator: int, denominator: int) -> float | None:
    return round(numerator / denominator, 4) if denominator else None


def _percentile(values: list[float], quantile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = int(round((len(ordered) - 1) * quantile))
    return round(ordered[index], 3)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _sha256_json(value: dict[str, Any]) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise CascadeError("%s must contain a JSON object." % path)
    return value


def _write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    calibrate = subparsers.add_parser("calibrate")
    calibrate.add_argument("--development-result", required=True)
    calibrate.add_argument("--policy-output", required=True)
    calibrate.add_argument("--analysis-output", required=True)
    evaluate = subparsers.add_parser("evaluate")
    evaluate.add_argument("--result", required=True)
    evaluate.add_argument("--policy", required=True)
    evaluate.add_argument("--expected-split", required=True, choices=("development", "heldout"))
    evaluate.add_argument("--output", required=True)
    args = parser.parse_args(argv)

    source = Path(args.development_result if args.command == "calibrate" else args.result)
    if args.command == "calibrate":
        manifest, analysis = calibrate_policy(_load(source), source_sha256=_sha256(source))
        _write(Path(args.policy_output), manifest)
        _write(Path(args.analysis_output), analysis)
        print(json.dumps(analysis["selected"], indent=2, sort_keys=True))
    else:
        output = evaluate_frozen(
            _load(source),
            manifest=_load(Path(args.policy)),
            expected_split=args.expected_split,
            source_sha256=_sha256(source),
        )
        _write(Path(args.output), output)
        print(json.dumps({"metrics": output["metrics"], "operations": output["operations"]}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
