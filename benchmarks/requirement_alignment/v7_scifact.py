"""Run the frozen v6 verifier policy on the cross-domain SciFact v7 evaluation."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from benchmarks.requirement_alignment.score_v6_cascade import score_local_models
from benchmarks.requirement_alignment.v6_cascade import (
    _baseline_metrics,
    _example_map,
    _jev_map,
    _local_map,
    _validate_policy,
    evaluate_rows,
    local_route,
    run_jev,
)


EXPERIMENT = "contexttrace_v7_scifact_transfer"
EVALUATION_SPLIT = "scifact_evaluation"


class V7SciFactError(RuntimeError):
    """Raised when the frozen cross-domain evaluation contract is violated."""


def score_local_transfer(
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
        expected_split=EVALUATION_SPLIT,
        v3_model_path=v3_model_path,
        v3_manifest_path=v3_manifest_path,
        v5_model_path=v5_model_path,
        v5_manifest_path=v5_manifest_path,
        batch_size=batch_size,
    )
    result.update(
        {
            "schema_version": "contexttrace-scifact-v7-local-scores-1.0",
            "experiment": EXPERIMENT,
            "source_dataset": "SciFact",
            "frozen_v6_policy_transfer": True,
            "scifact_used_for_model_training": False,
            "scifact_used_for_threshold_selection": False,
        }
    )
    return result


def run_jev_transfer(
    dataset_path: str | Path,
    local_scores_path: str | Path,
    *,
    output_path: str | Path,
    policy_path: str | Path,
    model: str,
    allow_remote: bool,
    env_file: str | Path | None,
) -> dict[str, Any]:
    result = run_jev(
        dataset_path,
        local_scores_path,
        expected_split=EVALUATION_SPLIT,
        output_path=output_path,
        all_cases=False,
        policy_path=policy_path,
        model=model,
        allow_remote=allow_remote,
        env_file=env_file,
    )
    result.update(
        {
            "schema_version": "contexttrace-scifact-v7-jev-result-1.0",
            "experiment": EXPERIMENT,
            "source_dataset": "SciFact",
            "frozen_v6_policy_transfer": True,
            "scifact_used_for_prompt_or_threshold_selection": False,
            "evaluation_labels_sent": False,
        }
    )
    _write(Path(output_path), result)
    return result


def evaluate_transfer(
    dataset_path: str | Path,
    local_scores_path: str | Path,
    jev_result_path: str | Path,
    policy_path: str | Path,
) -> dict[str, Any]:
    dataset_file = Path(dataset_path)
    local_file = Path(local_scores_path)
    jev_file = Path(jev_result_path)
    policy_file = Path(policy_path)
    dataset = _load(dataset_file)
    local_scores = _load(local_file)
    jev_result = _load(jev_file)
    policy_manifest = _load(policy_file)
    examples = list(dataset.get("examples") or [])
    if not examples or any(row.get("split") != EVALUATION_SPLIT for row in examples):
        raise V7SciFactError("Dataset must contain only the frozen SciFact evaluation split.")
    if local_scores.get("split") != EVALUATION_SPLIT:
        raise V7SciFactError("Local scores do not match the SciFact evaluation split.")
    if jev_result.get("split") != EVALUATION_SPLIT:
        raise V7SciFactError("Jev results do not match the SciFact evaluation split.")
    _validate_policy(policy_manifest)
    example_map = _example_map(dataset)
    local_map = _local_map(local_scores)
    jev_map = _jev_map(jev_result)
    if set(example_map) != set(local_map):
        raise V7SciFactError("Local scores must cover every frozen evaluation case.")
    expected_routes = {
        case_id
        for case_id, row in local_map.items()
        if local_route(row["predictions"], policy_manifest["policy"]) == "route"
    }
    if set(jev_map) != expected_routes:
        raise V7SciFactError("Jev results must cover exactly the frozen routed cases.")
    evaluated = evaluate_rows(
        example_map,
        local_map,
        jev_map,
        policy=dict(policy_manifest["policy"]),
        require_all_jev=False,
    )
    baselines = {
        "v3_threshold_0_90": _baseline_metrics(example_map, local_map, "v3", 0.90),
        "v5_threshold_0_90": _baseline_metrics(example_map, local_map, "v5", 0.90),
    }
    optional = evaluated["optional_jev"]["metrics"]
    local_only = evaluated["local_only"]["metrics"]
    relation_breakdown = optional["relation_breakdown"]
    contradiction_fp = relation_breakdown["Contradiction"]["predicted_supported"]
    missing_fp = relation_breakdown["NotMentioned"]["predicted_supported"]
    absolute_gates = {
        "supported_recall_at_least_0_50": optional["positive_recall"] >= 0.50,
        "false_support_rate_at_most_0_05": optional["false_positive_rate"] <= 0.05,
        "zero_contradiction_false_support": contradiction_fp == 0,
        "local_only_false_support_rate_at_most_0_05": (
            local_only["automatic_false_positive_rate"] or 0.0
        )
        <= 0.05,
    }
    non_regression = {
        "accuracy_at_least_v3": optional["accuracy"]
        >= baselines["v3_threshold_0_90"]["accuracy"],
        "supported_recall_at_least_v3": optional["positive_recall"]
        >= baselines["v3_threshold_0_90"]["positive_recall"],
    }
    return {
        "schema_version": "contexttrace-scifact-v7-evaluation-1.0",
        "experiment": EXPERIMENT,
        "split": EVALUATION_SPLIT,
        "dataset_sha256": _sha256(dataset_file),
        "local_scores_sha256": _sha256(local_file),
        "jev_result_sha256": _sha256(jev_file),
        "policy_sha256": _sha256(policy_file),
        "policy_id": policy_manifest["policy_id"],
        "policy_selection_uses_scifact": False,
        "evaluation_used_for_selection": False,
        "baselines": baselines,
        **evaluated,
        "relation_false_support": {
            "Contradiction": contradiction_fp,
            "NotMentioned": missing_fp,
        },
        "transfer_gates": {
            "absolute": absolute_gates,
            "non_regression": non_regression,
            "absolute_gates_met": all(absolute_gates.values()),
            "non_regression_met": all(non_regression.values()),
            "all_gates_met": all(absolute_gates.values()) and all(non_regression.values()),
        },
        "scope": {
            "supported": True,
            "contradiction": True,
            "not_mentioned": True,
            "partial_support": False,
            "ambiguous": False,
        },
        "stable_defaults_changed": False,
        "remote_provider_default_enabled": False,
        "local_only_network_calls": 0,
    }


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise V7SciFactError("%s must contain a JSON object." % path)
    return value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


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
    jev.add_argument("--policy", required=True)
    jev.add_argument("--output", required=True)
    jev.add_argument("--model", default="jev-latest")
    jev.add_argument("--env-file")
    jev.add_argument("--allow-remote", action="store_true")
    evaluate = subparsers.add_parser("evaluate")
    evaluate.add_argument("--dataset", required=True)
    evaluate.add_argument("--local-scores", required=True)
    evaluate.add_argument("--jev-result", required=True)
    evaluate.add_argument("--policy", required=True)
    evaluate.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    if args.command == "score-local":
        result = score_local_transfer(
            args.dataset,
            v3_model_path=args.v3_model_path,
            v3_manifest_path=args.v3_manifest,
            v5_model_path=args.v5_model_path,
            v5_manifest_path=args.v5_manifest,
            batch_size=args.batch_size,
        )
        _write(Path(args.output), result)
    elif args.command == "run-jev":
        result = run_jev_transfer(
            args.dataset,
            args.local_scores,
            output_path=args.output,
            policy_path=args.policy,
            model=args.model,
            allow_remote=args.allow_remote,
            env_file=args.env_file,
        )
    else:
        result = evaluate_transfer(
            args.dataset,
            args.local_scores,
            args.jev_result,
            args.policy,
        )
        _write(Path(args.output), result)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
