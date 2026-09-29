"""Preserve the frozen NLI head as features in a matched V25 ablation."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import time
from typing import Any

import numpy as np

from benchmarks.requirement_alignment.score_v12_relations import _verify_artifact
from benchmarks.requirement_alignment.train_v5 import resolve_relation_ids
from benchmarks.requirement_alignment.v14_fiveway_policy import (
    LABELS,
    _folds,
    _out_of_fold_probabilities,
    _select_policy,
    _sha256_json,
    policy_metrics,
)
from benchmarks.requirement_alignment.v25_joint_representation import encoder_pairs


def validate_inputs(
    dataset: dict[str, Any], source: dict[str, Any], protocol: dict[str, Any]
) -> list[tuple[str, str]]:
    if (
        _sha256_json(dataset) != protocol["dataset_sha256"]
        or _sha256_json(source) != protocol["v25_source_sha256"]
    ):
        raise ValueError("Input differs from the frozen dataset or score artifact.")
    if (
        protocol["release_gate_eligible"] is not False
        or source["future_confirmation_loaded"] is not False
    ):
        raise ValueError("This experiment accepts development diagnostics only.")
    rows = source["variants"]["restored_selected_qa"]["rows"]
    if len(rows) != len(dataset["examples"]):
        raise ValueError("Case coverage differs.")
    for case, row in zip(dataset["examples"], rows, strict=True):
        if (case["id"], _sha256_json(case["input"]), case["target"]["verdict"]) != (
            row["case_id"],
            row["input_sha256"],
            row["expected_verdict"],
        ):
            raise ValueError("Case input or target binding differs.")
    policy = protocol["input_policy"]
    flags = [
        {"case_id": r["id"], "input_sha256": _sha256_json(r["input"])}
        for r in dataset["examples"]
        if any(
            re.search(policy["indicator_regex"], e["text"], re.I)
            for e in r["input"]["evidence"]
        )
    ]
    if flags != policy["indicator_flags"]:
        raise ValueError(
            "Source-assessment audit differs from the frozen input policy."
        )
    return encoder_pairs(dataset)


def feature_variants(cls: Any, logits: Any) -> dict[str, np.ndarray]:
    cls, logits = np.asarray(cls), np.asarray(logits)
    if (
        cls.ndim != 2
        or logits.shape != (len(cls), 3)
        or not np.isfinite(cls).all()
        or not np.isfinite(logits).all()
    ):
        raise ValueError("Expected finite aligned CLS and three NLI logit features.")
    return {
        "cls_control": cls,
        "cls_plus_pretrained_nli_logits": np.concatenate([cls, logits], axis=1),
    }


def encode(
    pairs: list[tuple[str, str]], model: Any, tokenizer: Any, protocol: dict[str, Any]
) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    import torch

    lengths = [len(tokenizer(a, b, truncation=False)["input_ids"]) for a, b in pairs]
    vectors, logits, tokens, batch_times = [], [], [], []
    started = time.perf_counter()
    with torch.inference_mode():
        for start in range(0, len(pairs), protocol["batch_size"]):
            batch = pairs[start : start + protocol["batch_size"]]
            tick = time.perf_counter()
            encoded = tokenizer(
                [a for a, _ in batch],
                [b for _, b in batch],
                padding=True,
                max_length=protocol["maximum_tokens"],
                truncation="only_first",
                return_tensors="pt",
            )
            output = model(**encoded, output_hidden_states=True, return_dict=True)
            vectors.append(output.hidden_states[-1][:, 0, :].cpu().numpy())
            logits.append(output.logits.cpu().numpy())
            tokens.extend(encoded["attention_mask"].sum(dim=1).tolist())
            batch_times.append(
                {
                    "first_case_index": start,
                    "cases": len(batch),
                    "seconds": time.perf_counter() - tick,
                }
            )
            if start % 80 == 0:
                print(
                    f"Encoded {min(start + len(batch), len(pairs))}/{len(pairs)}",
                    flush=True,
                )
    return (
        np.concatenate(vectors),
        np.concatenate(logits),
        {
            "encoder_seconds": time.perf_counter() - started,
            "batch_timings": batch_times,
            "tokens_before_truncation": lengths,
            "tokens_processed": tokens,
            "output_tokens": 0,
            "truncated_cases": sum(x > protocol["maximum_tokens"] for x in lengths),
        },
    )


def run(
    dataset: dict[str, Any],
    source: dict[str, Any],
    protocol: dict[str, Any],
    model_path: Path,
    manifest_path: Path,
) -> dict[str, Any]:
    import torch
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    pairs = validate_inputs(dataset, source, protocol)
    artifact = _verify_artifact(model_path, manifest_path)
    if (
        artifact["model_id"] != protocol["model_id"]
        or artifact["revision"] != protocol["resolved_revision"]
    ):
        raise ValueError("Unexpected model identity.")
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    os.environ["TOKENIZERS_PARALLELISM"] = "false"
    torch.set_num_threads(4)
    tokenizer = AutoTokenizer.from_pretrained(str(model_path), local_files_only=True)
    model = AutoModelForSequenceClassification.from_pretrained(
        str(model_path), local_files_only=True, dtype=torch.float32
    )
    model.eval()
    relation_ids = resolve_relation_ids(model.config)
    cls, logits, timing = encode(pairs, model, tokenizer, protocol)
    variants = feature_variants(cls, logits)
    if list(variants) != protocol["variants"]:
        raise ValueError("Variant list differs from protocol.")
    examples = dataset["examples"]
    targets = [r["target"]["verdict"] for r in examples]
    folds = _folds(targets)
    baseline = source["variants"]["restored_selected_qa"]
    flags = {r["case_id"] for r in protocol["input_policy"]["indicator_flags"]}
    clean_indices = [i for i, r in enumerate(examples) if r["id"] not in flags]
    results = {}
    max_difference = None
    for name, matrix in variants.items():
        settings = protocol["classifier"]
        estimator = make_pipeline(
            StandardScaler(),
            LogisticRegression(
                C=settings["C"],
                class_weight=settings["class_weight"],
                max_iter=settings["max_iter"],
                random_state=protocol["seed"],
            ),
        )
        tick = time.perf_counter()
        probs = _out_of_fold_probabilities(
            matrix.tolist(), targets, folds, estimator=estimator
        )
        if name == "cls_control":
            expected = [
                [r["probabilities"][label] for label in LABELS]
                for r in baseline["rows"]
            ]
            max_difference = float(
                np.max(np.abs(np.asarray(probs) - np.asarray(expected)))
            )
            if max_difference > 1e-6:
                raise ValueError(
                    f"Control does not reproduce V25 probabilities: {max_difference}"
                )
        direct = [LABELS[int(np.argmax(row))] for row in probs]
        policy = _select_policy(targets, probs)
        predictions = policy.pop("predictions")
        result_rows = []
        for i, (case, probability, prediction) in enumerate(
            zip(examples, probs, predictions, strict=True)
        ):
            result_rows.append(
                {
                    "case_id": case["id"],
                    "input_sha256": _sha256_json(case["input"]),
                    "expected_verdict": targets[i],
                    "direct_prediction": direct[i],
                    "prediction": prediction,
                    "probabilities": dict(zip(LABELS, probability, strict=True)),
                    "confidence": max(probability),
                    "confidence_semantics": "uncalibrated_fiveway_classifier_max_probability",
                    "pretrained_nli_logits": {
                        rel: float(logits[i, j]) for rel, j in relation_ids.items()
                    },
                    "source_assessment_indicator": case["id"] in flags,
                    "input_tokens_before_truncation": timing[
                        "tokens_before_truncation"
                    ][i],
                    "input_tokens_processed": timing["tokens_processed"][i],
                }
            )
        results[name] = {
            "feature_dimensions": int(matrix.shape[1]),
            "direct_metrics": policy_metrics(targets, direct),
            "policy": policy,
            "training_and_policy_seconds": time.perf_counter() - tick,
            "unflagged_evaluation_sensitivity": {
                "cases": len(clean_indices),
                "training_assessment_examples_removed": False,
                "label_validity_established": False,
                "policy_metrics": policy_metrics(
                    [targets[i] for i in clean_indices],
                    [predictions[i] for i in clean_indices],
                ),
            },
            "rows": result_rows,
        }
        print(
            json.dumps(
                {
                    "variant": name,
                    "direct": results[name]["direct_metrics"]["macro_f1"],
                    "policy": policy["metrics"],
                }
            ),
            flush=True,
        )
    return {
        "experiment": protocol["experiment"],
        "protocol_sha256": _sha256_json(protocol),
        "dataset_sha256": _sha256_json(dataset),
        "model_id": artifact["model_id"],
        "resolved_model_revision": artifact["revision"],
        "model_files_verified": True,
        "control_probability_max_absolute_difference": max_difference,
        "timing": timing,
        "source_assessment_flags": len(flags),
        "variants": results,
        "status": "development_diagnostic_only",
        "release_gate_eligible": False,
        "stable_defaults_changed": False,
        "future_confirmation_loaded": False,
        "remote_inference_used": False,
        "local_only_network_calls": 0,
        "evaluation_label_fields_sent_to_encoder": False,
        "source_assessments_may_reveal_labels": True,
        "labels_changed": False,
        "evidence_changed": False,
        "limitations": [
            "Inherited target validity unresolved.",
            "Source annotation assessments remain in selected text.",
            "Policy selected using the same development OOF predictions; independent confirmation required.",
            "Public pretrained model overlap unknown. All partial targets come from WiCE.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for field in (
        "dataset",
        "source",
        "protocol",
        "model-path",
        "model-manifest",
        "output",
    ):
        parser.add_argument(f"--{field}", required=True)
    args = parser.parse_args()

    def load(path: str) -> dict[str, Any]:
        return json.loads(Path(path).read_text())

    result = run(
        load(args.dataset),
        load(args.source),
        load(args.protocol),
        Path(args.model_path),
        Path(args.model_manifest),
    )
    Path(args.output).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
