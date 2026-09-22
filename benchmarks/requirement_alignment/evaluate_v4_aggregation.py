"""Evaluate fixed hierarchical evidence aggregation policies with frozen v3."""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import time
from copy import deepcopy
from pathlib import Path
from typing import Any

from benchmarks.requirement_alignment.analyze_development import relation_metrics
from benchmarks.requirement_alignment.train import binary_targets
from benchmarks.requirement_alignment.train_v2 import verify_source_model
from benchmarks.requirement_alignment.train_v3 import RELATION_IDS
from benchmarks.requirement_alignment.train_v3 import _BinaryEncodedExamples
from benchmarks.requirement_alignment.train_v3 import select_dual_threshold


POLICIES = ("concatenated", "max_entailment", "contradiction_veto")
CONTRADICTION_VETO_THRESHOLD = 0.50


class AggregationEvaluationError(RuntimeError):
    """Raised when the frozen aggregation experiment is invalid."""


def explode_evidence(
    examples: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[int]]:
    exploded = []
    owners = []
    for owner, row in enumerate(examples):
        evidence = list(row["input"].get("evidence") or [])
        if not evidence:
            raise AggregationEvaluationError("Every example must contain evidence.")
        for index, item in enumerate(evidence):
            single = deepcopy(row)
            single["id"] = "%s::evidence::%d" % (row["id"], index)
            single["input"]["evidence"] = [deepcopy(item)]
            exploded.append(single)
            owners.append(owner)
    return exploded, owners


def aggregate_probabilities(
    *,
    policy: str,
    concatenated: list[list[float]],
    per_span: list[list[float]],
    owners: list[int],
) -> tuple[list[float], dict[str, Any]]:
    if policy not in POLICIES:
        raise AggregationEvaluationError("Unknown aggregation policy: %s" % policy)
    if policy == "concatenated":
        return [row[RELATION_IDS["entailment"]] for row in concatenated], {
            "vetoed_examples": 0,
            "mean_evidence_spans": round(len(owners) / len(concatenated), 4),
        }
    grouped: list[list[list[float]]] = [[] for _ in concatenated]
    for probability, owner in zip(per_span, owners, strict=True):
        grouped[owner].append(probability)
    output = []
    vetoed = 0
    for rows in grouped:
        if not rows:
            raise AggregationEvaluationError("An example has no per-span scores.")
        entailment = max(row[RELATION_IDS["entailment"]] for row in rows)
        contradiction = max(row[RELATION_IDS["contradiction"]] for row in rows)
        if (
            policy == "contradiction_veto"
            and contradiction >= CONTRADICTION_VETO_THRESHOLD
        ):
            entailment = 0.0
            vetoed += 1
        output.append(entailment)
    return output, {
        "vetoed_examples": vetoed,
        "mean_evidence_spans": round(len(owners) / len(concatenated), 4),
    }


def error_records(
    examples: list[dict[str, Any]],
    probabilities: list[float],
    *,
    threshold: float,
) -> list[dict[str, Any]]:
    output = []
    for row, target, probability in zip(
        examples, binary_targets(examples), probabilities, strict=True
    ):
        prediction = int(probability >= threshold)
        if prediction == target:
            continue
        source = row["source"]
        output.append(
            {
                "id": row["id"],
                "relation": source.get("relation"),
                "hypothesis_id": source.get("hypothesis_id"),
                "target": row["target"]["label"],
                "prediction": "covered" if prediction else "missing",
                "covered_probability": round(probability, 6),
                "evidence_ids": [item["id"] for item in row["input"]["evidence"]],
            }
        )
    return output


def _policy_selection_key(record: dict[str, Any]) -> tuple[Any, ...]:
    selected = record["dual_threshold_policy"]["selected"]
    contract = selected["contract_development"]
    wice = selected["wice_internal"]
    return (
        bool(selected["promotion_gates_met"]),
        float(contract["positive_recall"]),
        float(wice["positive_recall"]),
        statistics.fmean([contract["macro_f1"], wice["macro_f1"]]),
        statistics.fmean([contract["roc_auc"], wice["roc_auc"]]),
        -POLICIES.index(str(record["policy"])),
    )


def evaluate_aggregation(
    *,
    model_path: str | Path,
    model_manifest_path: str | Path,
    contract_development_path: str | Path,
    wice_dataset_path: str | Path,
    batch_size: int = 8,
) -> dict[str, Any]:
    import torch
    from torch.utils.data import DataLoader
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    if batch_size < 1:
        raise AggregationEvaluationError("batch size must be positive.")
    manifest = verify_source_model(model_path, model_manifest_path)
    contract_path = Path(contract_development_path)
    wice_path = Path(wice_dataset_path)
    contract_examples = json.loads(contract_path.read_text(encoding="utf-8"))[
        "examples"
    ]
    wice_payload = json.loads(wice_path.read_text(encoding="utf-8"))
    wice_examples = [
        row
        for row in wice_payload["examples"]
        if row["split"] == "internal_validation"
        and row["task"] == "claim_group_completeness"
        and row["source"]["construction"]
        in {"gold_complete_group", "gold_partial_group"}
    ]
    tokenizer = AutoTokenizer.from_pretrained(str(model_path), local_files_only=True)
    separator = str(tokenizer.sep_token or "[SEP]")
    model = AutoModelForSequenceClassification.from_pretrained(
        str(model_path), local_files_only=True
    )

    def predict(rows: list[dict[str, Any]]) -> tuple[list[list[float]], float]:
        dataset = _BinaryEncodedExamples(
            rows, tokenizer=tokenizer, separator=separator
        )
        loader = DataLoader(dataset, batch_size=batch_size, shuffle=False)
        probabilities = []
        started = time.perf_counter()
        model.eval()
        with torch.no_grad():
            for batch in loader:
                batch.pop("labels")
                values = torch.softmax(model(**batch).logits, dim=-1).tolist()
                probabilities.extend(
                    [[float(item) for item in row] for row in values]
                )
        return probabilities, time.perf_counter() - started

    contract_spans, contract_owners = explode_evidence(contract_examples)
    wice_spans, wice_owners = explode_evidence(wice_examples)
    contract_concat, contract_concat_seconds = predict(contract_examples)
    contract_span_probs, contract_span_seconds = predict(contract_spans)
    wice_concat, wice_concat_seconds = predict(wice_examples)
    wice_span_probs, wice_span_seconds = predict(wice_spans)
    contract_targets = binary_targets(contract_examples)
    wice_targets = binary_targets(wice_examples)

    results = []
    for policy in POLICIES:
        contract_scores, contract_audit = aggregate_probabilities(
            policy=policy,
            concatenated=contract_concat,
            per_span=contract_span_probs,
            owners=contract_owners,
        )
        wice_scores, wice_audit = aggregate_probabilities(
            policy=policy,
            concatenated=wice_concat,
            per_span=wice_span_probs,
            owners=wice_owners,
        )
        threshold_policy = select_dual_threshold(
            contract_targets,
            contract_scores,
            wice_targets,
            wice_scores,
        )
        threshold = float(threshold_policy["selected"]["threshold"])
        results.append(
            {
                "policy": policy,
                "configuration": {
                    "contradiction_veto_threshold": (
                        CONTRADICTION_VETO_THRESHOLD
                        if policy == "contradiction_veto"
                        else None
                    )
                },
                "contract_aggregation_audit": contract_audit,
                "wice_aggregation_audit": wice_audit,
                "dual_threshold_policy": threshold_policy,
                "contract_relation_metrics": relation_metrics(
                    contract_examples, contract_scores, threshold=threshold
                ),
                "contract_errors": error_records(
                    contract_examples, contract_scores, threshold=threshold
                ),
                "wice_errors": error_records(
                    wice_examples, wice_scores, threshold=threshold
                ),
            }
        )
    selected = max(results, key=_policy_selection_key)
    selected_policy = selected["policy"]
    selected_threshold = selected["dual_threshold_policy"]["selected"]
    return {
        "schema_version": "contexttrace-requirement-v4-aggregation-1.0",
        "model": {
            "model_id": manifest["model_id"],
            "artifact_verified": True,
            "weights_changed": False,
        },
        "datasets": {
            "contract_development": {
                "path": str(contract_path),
                "sha256": hashlib.sha256(contract_path.read_bytes()).hexdigest(),
                "examples": len(contract_examples),
                "exploded_span_examples": len(contract_spans),
            },
            "wice_internal": {
                "path": str(wice_path),
                "sha256": hashlib.sha256(wice_path.read_bytes()).hexdigest(),
                "examples": len(wice_examples),
                "exploded_span_examples": len(wice_spans),
            },
        },
        "protocol": {
            "policies": list(POLICIES),
            "contradiction_veto_threshold": CONTRADICTION_VETO_THRESHOLD,
            "shared_threshold_grid": "0.05 through 1.00 in increments of 0.05",
            "promotion_gates_unchanged_from_v3": True,
            "contract_test_split_accessed": False,
            "remote_inference_used": False,
            "jev_used": False,
        },
        "inference": {
            "contract_concatenated_seconds": round(contract_concat_seconds, 3),
            "contract_per_span_seconds": round(contract_span_seconds, 3),
            "wice_concatenated_seconds": round(wice_concat_seconds, 3),
            "wice_per_span_seconds": round(wice_span_seconds, 3),
        },
        "policy_results": results,
        "selection": {
            "selected_policy": selected_policy,
            "selected_threshold": selected_threshold["threshold"],
            "promotion_gates_met": selected_threshold["promotion_gates_met"],
            "contract_development": selected_threshold["contract_development"],
            "wice_internal": selected_threshold["wice_internal"],
            "next_step": (
                "freeze_v4_and_run_untouched_confirmation"
                if selected_threshold["promotion_gates_met"]
                else "move_to_stronger_local_backbone"
            ),
        },
        "stable_defaults_changed": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-path", required=True)
    parser.add_argument("--model-manifest", required=True)
    parser.add_argument("--contract-development", required=True)
    parser.add_argument("--wice-dataset", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--batch-size", type=int, default=8)
    args = parser.parse_args(argv)
    report = evaluate_aggregation(
        model_path=args.model_path,
        model_manifest_path=args.model_manifest,
        contract_development_path=args.contract_development,
        wice_dataset_path=args.wice_dataset,
        batch_size=args.batch_size,
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report["selection"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
