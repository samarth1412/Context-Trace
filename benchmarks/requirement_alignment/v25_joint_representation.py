"""Bounded offline V25 representation screen; inherited labels are diagnostic."""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path
from typing import Any

from benchmarks.jev_v2_verification.run import stable_prediction
from benchmarks.requirement_alignment.score_v12_relations import _verify_artifact
from benchmarks.requirement_alignment.v14_fiveway_policy import (
    LABELS,
    SEED,
    _folds,
    _out_of_fold_probabilities,
    _select_policy,
    _sha256_json,
    policy_metrics,
)
from contexttrace.verify.schema import TraceContext


def encoder_pairs(dataset: dict[str, Any]) -> list[tuple[str, str]]:
    """Only evidence and claim enter the frozen representation model."""
    if dataset.get("split") != "external_fiveway_v21_development":
        raise ValueError("V25 accepts development inputs only.")
    pairs = []
    for row in dataset["examples"]:
        state = row["input"]
        if set(state) != {"claim", "query", "evidence"} or state["query"]:
            raise ValueError("V25 expects claim/evidence with an empty query.")
        if not state["evidence"]:
            raise ValueError("Selected evidence is empty.")
        if any(set(span) != {"id", "text"} for span in state["evidence"]):
            raise ValueError("Evidence contains metadata or labels.")
        pairs.append(
            ("\n\n".join(span["text"] for span in state["evidence"]), state["claim"])
        )
    return pairs


def validate_protocol(
    original: dict[str, Any], restored: dict[str, Any], protocol: dict[str, Any]
) -> None:
    for name, data in [("original", original), ("restored", restored)]:
        if _sha256_json(data) != protocol[f"{name}_dataset_sha256"]:
            raise ValueError("Dataset differs from the frozen protocol.")
        encoder_pairs(data)
    ids = [[row["id"] for row in data["examples"]] for data in [original, restored]]
    if ids[0] != ids[1] or len(ids[0]) != len(set(ids[0])):
        raise ValueError("V25 IDs must be unique and identically ordered.")
    if [row["target"] for row in original["examples"]] != [
        row["target"] for row in restored["examples"]
    ]:
        raise ValueError("V25 must not relabel the development examples.")
    if protocol["release_gate_eligible"] is not False:
        raise ValueError("Inherited labels are not release-grade annotations.")


def encode(
    pairs: list[tuple[str, str]], model: Any, tokenizer: Any
) -> tuple[Any, dict[str, Any]]:
    import numpy as np
    import torch

    lengths = [len(tokenizer(a, b, truncation=False)["input_ids"]) for a, b in pairs]
    vectors = []
    token_counts = []
    started = time.perf_counter()
    with torch.inference_mode():
        for start in range(0, len(pairs), 8):
            batch = pairs[start : start + 8]
            values = tokenizer(
                [a for a, _ in batch],
                [b for _, b in batch],
                padding=True,
                max_length=512,
                truncation="only_first",
                return_tensors="pt",
            )
            token_counts.extend(values["attention_mask"].sum(dim=1).tolist())
            vectors.append(model(**values).last_hidden_state[:, 0, :].cpu().numpy())
            if start % 80 == 0:
                print(
                    f"Encoded {min(start + 8, len(pairs))}/{len(pairs)} cases",
                    flush=True,
                )
    return np.concatenate(vectors), {
        "seconds": round(time.perf_counter() - started, 4),
        "input_tokens_before_truncation": lengths,
        "input_tokens_processed": token_counts,
        "truncated_cases": sum(n > 512 for n in lengths),
        "output_tokens": 0,
    }


def run(
    original: dict[str, Any],
    restored: dict[str, Any],
    protocol: dict[str, Any],
    model_path: Path,
    manifest_path: Path,
) -> dict[str, Any]:
    import torch
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    from transformers import AutoModel, AutoTokenizer

    validate_protocol(original, restored, protocol)
    artifact = _verify_artifact(model_path, manifest_path)
    if artifact["model_id"] != protocol["model_id"]:
        raise ValueError("Model differs from the frozen protocol.")
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    os.environ["TOKENIZERS_PARALLELISM"] = "false"
    torch.set_num_threads(4)
    tokenizer = AutoTokenizer.from_pretrained(str(model_path), local_files_only=True)
    model = AutoModel.from_pretrained(
        str(model_path), local_files_only=True, dtype=torch.float32
    )
    model.eval()
    targets = [row["target"]["verdict"] for row in original["examples"]]
    folds = _folds(targets)
    variants = {}
    for name, dataset in zip(protocol["variants"], [original, restored], strict=True):
        print(f"Starting {name}", flush=True)
        vectors, timing = encode(encoder_pairs(dataset), model, tokenizer)
        estimator = make_pipeline(
            StandardScaler(),
            LogisticRegression(
                C=0.1,
                class_weight="balanced",
                max_iter=5000,
                random_state=SEED,
            ),
        )
        training_started = time.perf_counter()
        probabilities = _out_of_fold_probabilities(
            vectors.tolist(), targets, folds, estimator=estimator
        )
        training_seconds = time.perf_counter() - training_started
        direct = [
            LABELS[max(range(len(row)), key=row.__getitem__)] for row in probabilities
        ]
        policy = _select_policy(targets, probabilities)
        predictions = policy.pop("predictions")
        rows = []
        for index, (example, probs, prediction) in enumerate(
            zip(dataset["examples"], probabilities, predictions, strict=True)
        ):
            state = example["input"]
            baseline = stable_prediction(
                {"id": example["id"], "claim": state["claim"]},
                [
                    TraceContext(id=span["id"], text=span["text"])
                    for span in state["evidence"]
                ],
            )
            rows.append(
                {
                    "case_id": example["id"],
                    "expected_verdict": targets[index],
                    "input_sha256": _sha256_json(state),
                    "direct_prediction": direct[index],
                    "prediction": prediction,
                    "probabilities": {
                        label: float(p) for label, p in zip(LABELS, probs, strict=True)
                    },
                    "confidence": max(probs),
                    "confidence_semantics": "uncalibrated_classifier_max_probability",
                    "stable_baseline": baseline,
                    "input_tokens_before_truncation": timing[
                        "input_tokens_before_truncation"
                    ][index],
                    "input_tokens_processed": timing["input_tokens_processed"][index],
                }
            )
        baseline_predictions = [row["stable_baseline"]["verdict"] for row in rows]
        variants[name] = {
            "dataset_sha256": _sha256_json(dataset),
            "representation_dimensions": int(vectors.shape[1]),
            "direct_metrics": policy_metrics(targets, direct),
            "policy": policy,
            "stable_baseline_metrics": policy_metrics(targets, baseline_predictions),
            "disagreements_with_baseline": sum(
                a != b for a, b in zip(predictions, baseline_predictions, strict=True)
            ),
            "candidate_only_false_supports": [
                row["case_id"]
                for row in rows
                if row["prediction"] == "supported"
                and row["expected_verdict"] != "supported"
                and row["stable_baseline"]["verdict"] != "supported"
            ],
            "encoder_seconds": timing["seconds"],
            "head_training_seconds": round(training_seconds, 4),
            "truncated_cases": timing["truncated_cases"],
            "input_tokens_processed": sum(timing["input_tokens_processed"]),
            "output_tokens": 0,
            "rows": rows,
        }
        print(
            json.dumps(
                {
                    "variant": name,
                    "direct": variants[name]["direct_metrics"]["macro_f1"],
                    "support_recall": policy["metrics"]["support_recall"],
                    "all_gates": policy["metrics"]["gates"]["all_met"],
                }
            ),
            flush=True,
        )
    return {
        "experiment": protocol["experiment"],
        "protocol_sha256": _sha256_json(protocol),
        "model_id": artifact["model_id"],
        "resolved_model_revision": artifact["revision"],
        "model_files_verified": True,
        "status": "diagnostic_complete_release_blocked",
        "encoder_labels_sent": False,
        "head_training_uses_development_targets": True,
        "remote_inference_used": False,
        "local_only_network_calls": 0,
        "stable_defaults_changed": False,
        "future_confirmation_loaded": False,
        "release_gate_eligible": False,
        "variants": variants,
        "decision": "require_selected_evidence_label_review_before_confirmation_or_release",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in [
        "original",
        "restored",
        "protocol",
        "model-path",
        "model-manifest",
        "output",
    ]:
        parser.add_argument(f"--{name}", required=True)
    args = parser.parse_args()

    def load(path: str) -> dict[str, Any]:
        return json.loads(Path(path).read_text())

    result = run(
        load(args.original),
        load(args.restored),
        load(args.protocol),
        Path(args.model_path),
        Path(args.model_manifest),
    )
    Path(args.output).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
