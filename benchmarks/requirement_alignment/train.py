"""Train fixed local cross-encoder variants for evidence coverage."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import statistics
import time
from collections import Counter
from pathlib import Path
from typing import Any

from contexttrace.verify.semantic_core_v2.nli import verify_nli_artifact


SEED = 20260927
MAX_LENGTH = 256
VARIANTS = ("human_group", "group_with_weak_negatives", "multitask")
POSITIVE_LABELS = {"complete", "covered"}
EXPECTED_BASE_ARTIFACT_SHA256 = (
    "330f0fd77aad129877e1a1a90d4a77e6f093ee238b97d535202816a116b9c9f3"
)


class AlignmentTrainingError(RuntimeError):
    """Raised when local alignment training cannot be reproduced."""


def variant_examples(examples: list[dict[str, Any]], variant: str) -> list[dict[str, Any]]:
    if variant not in VARIANTS:
        raise AlignmentTrainingError("Unknown training variant: %s" % variant)
    if variant == "human_group":
        return [
            row
            for row in examples
            if row["task"] == "claim_group_completeness"
            and row["source"]["construction"]
            in {"gold_complete_group", "gold_partial_group"}
        ]
    if variant == "group_with_weak_negatives":
        return [row for row in examples if row["task"] == "claim_group_completeness"]
    return list(examples)


def input_pair(example: dict[str, Any], *, separator: str) -> tuple[str, str]:
    value = example["input"]
    evidence = (" %s " % separator).join(
        str(item["text"]) for item in value["evidence"]
    )
    requirement = value.get("requirement")
    if requirement:
        hypothesis = "Claim: %s Requirement: %s" % (
            value["claim"],
            requirement["text"],
        )
    else:
        hypothesis = "Claim: %s" % value["claim"]
    return evidence, hypothesis


def binary_targets(examples: list[dict[str, Any]]) -> list[int]:
    return [int(str(row["target"]["label"]) in POSITIVE_LABELS) for row in examples]


def binary_metrics(
    targets: list[int], probabilities: list[float], *, threshold: float
) -> dict[str, Any]:
    from sklearn.metrics import average_precision_score, roc_auc_score

    if len(set(targets)) != 2:
        raise AlignmentTrainingError("Binary metrics require both target classes.")
    predictions = [int(value >= threshold) for value in probabilities]
    true_positive = sum(gold == guess == 1 for gold, guess in zip(targets, predictions, strict=True))
    true_negative = sum(gold == guess == 0 for gold, guess in zip(targets, predictions, strict=True))
    false_positive = sum(gold == 0 and guess == 1 for gold, guess in zip(targets, predictions, strict=True))
    false_negative = sum(gold == 1 and guess == 0 for gold, guess in zip(targets, predictions, strict=True))
    positive_recall = true_positive / (true_positive + false_negative)
    negative_recall = true_negative / (true_negative + false_positive)
    positive_precision = true_positive / (true_positive + false_positive) if true_positive + false_positive else 0.0
    negative_precision = true_negative / (true_negative + false_negative) if true_negative + false_negative else 0.0
    positive_f1 = 2 * positive_precision * positive_recall / (positive_precision + positive_recall) if positive_precision + positive_recall else 0.0
    negative_f1 = 2 * negative_precision * negative_recall / (negative_precision + negative_recall) if negative_precision + negative_recall else 0.0
    return {
        "cases": len(targets),
        "threshold": threshold,
        "roc_auc": round(float(roc_auc_score(targets, probabilities)), 4),
        "average_precision": round(float(average_precision_score(targets, probabilities)), 4),
        "accuracy": round((true_positive + true_negative) / len(targets), 4),
        "macro_f1": round(statistics.fmean([positive_f1, negative_f1]), 4),
        "positive_recall": round(positive_recall, 4),
        "negative_recall": round(negative_recall, 4),
        "false_positive_rate": round(false_positive / (true_negative + false_positive), 4),
        "confusion": {
            "negative": {"negative": true_negative, "positive": false_positive},
            "positive": {"negative": false_negative, "positive": true_positive},
        },
    }


def select_threshold(targets: list[int], probabilities: list[float]) -> dict[str, Any]:
    candidates = []
    for value in range(5, 100, 5):
        threshold = value / 100
        result = binary_metrics(targets, probabilities, threshold=threshold)
        candidates.append(
            {
                "threshold": threshold,
                "meets_false_positive_cap": result["false_positive_rate"] <= 0.05,
                "metrics": result,
            }
        )
    eligible = [row for row in candidates if row["meets_false_positive_cap"]]
    if not eligible:
        raise AlignmentTrainingError("No internal threshold meets the false-positive cap.")
    selected = max(
        eligible,
        key=lambda row: (
            row["metrics"]["macro_f1"],
            row["metrics"]["positive_recall"],
            row["metrics"]["accuracy"],
            row["threshold"],
        ),
    )
    return {"threshold": selected["threshold"], "metrics": selected["metrics"], "candidates": candidates}


def train_variants(
    dataset_path: str | Path,
    *,
    base_model_path: str | Path,
    output_dir: str | Path,
    epochs: int = 2,
    batch_size: int = 8,
    learning_rate: float = 1e-5,
) -> tuple[dict[str, Any], dict[str, Any]]:
    import torch
    from torch.utils.data import DataLoader
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    if epochs < 1 or batch_size < 1:
        raise AlignmentTrainingError("epochs and batch_size must be positive.")
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
    base_artifact = verify_nli_artifact(base_model_path)
    if (
        base_artifact["artifact_manifest_sha256"]
        != EXPECTED_BASE_ARTIFACT_SHA256
    ):
        raise AlignmentTrainingError("The base NLI artifact does not match its lock.")
    torch.set_num_threads(min(4, os.cpu_count() or 1))
    dataset_file = Path(dataset_path)
    payload = json.loads(dataset_file.read_text(encoding="utf-8"))
    examples = list(payload.get("examples") or [])
    if not examples:
        raise AlignmentTrainingError("The alignment dataset is empty.")
    tokenizer = AutoTokenizer.from_pretrained(
        str(base_model_path), local_files_only=True
    )
    separator = str(tokenizer.sep_token or "[SEP]")
    common_validation = [
        row
        for row in examples
        if row["split"] == "internal_validation"
        and row["task"] == "claim_group_completeness"
        and row["source"]["construction"]
        in {"gold_complete_group", "gold_partial_group"}
    ]
    results = []
    best_key = None
    best_variant = None
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    for variant in VARIANTS:
        _seed_all(torch)
        selected = variant_examples(examples, variant)
        training = [row for row in selected if row["split"] == "training"]
        validation = [row for row in selected if row["split"] == "internal_validation"]
        model = AutoModelForSequenceClassification.from_pretrained(
            str(base_model_path),
            num_labels=2,
            id2label={0: "incomplete", 1: "complete"},
            label2id={"incomplete": 0, "complete": 1},
            ignore_mismatched_sizes=True,
            local_files_only=True,
        )
        trainable = _freeze_for_transfer(model)
        train_dataset = EncodedExamples(
            training,
            tokenizer=tokenizer,
            separator=separator,
        )
        validation_dataset = EncodedExamples(
            validation,
            tokenizer=tokenizer,
            separator=separator,
        )
        common_dataset = EncodedExamples(
            common_validation,
            tokenizer=tokenizer,
            separator=separator,
        )
        generator = torch.Generator().manual_seed(SEED)
        train_loader = DataLoader(
            train_dataset,
            batch_size=batch_size,
            shuffle=True,
            generator=generator,
        )
        validation_loader = DataLoader(
            validation_dataset, batch_size=batch_size, shuffle=False
        )
        common_loader = DataLoader(
            common_dataset, batch_size=batch_size, shuffle=False
        )
        counts = Counter(binary_targets(training))
        weights = torch.tensor(
            [len(training) / (2 * counts[index]) for index in (0, 1)],
            dtype=torch.float32,
        )
        loss_function = torch.nn.CrossEntropyLoss(weight=weights)
        optimizer = torch.optim.AdamW(
            [parameter for parameter in model.parameters() if parameter.requires_grad],
            lr=learning_rate,
            weight_decay=0.01,
        )
        history = []
        started_variant = time.perf_counter()
        for epoch in range(1, epochs + 1):
            model.train()
            losses = []
            started_epoch = time.perf_counter()
            for step, batch in enumerate(train_loader, start=1):
                labels = batch.pop("labels")
                optimizer.zero_grad(set_to_none=True)
                logits = model(**batch).logits
                loss = loss_function(logits, labels)
                loss.backward()
                torch.nn.utils.clip_grad_norm_(
                    [parameter for parameter in model.parameters() if parameter.requires_grad],
                    1.0,
                )
                optimizer.step()
                losses.append(float(loss.detach()))
                if step % 25 == 0 or step == len(train_loader):
                    print(
                        "%s epoch %d/%d step %d/%d loss %.4f"
                        % (
                            variant,
                            epoch,
                            epochs,
                            step,
                            len(train_loader),
                            statistics.fmean(losses[-25:]),
                        ),
                        flush=True,
                    )
            probabilities = _predict(model, validation_loader, torch=torch)
            targets = binary_targets(validation)
            epoch_metrics = binary_metrics(targets, probabilities, threshold=0.5)
            history.append(
                {
                    "epoch": epoch,
                    "mean_train_loss": round(statistics.fmean(losses), 6),
                    "seconds": round(time.perf_counter() - started_epoch, 3),
                    "validation_at_0_5": epoch_metrics,
                }
            )
        validation_probabilities = _predict(model, validation_loader, torch=torch)
        validation_targets = binary_targets(validation)
        common_probabilities = _predict(model, common_loader, torch=torch)
        common_targets = binary_targets(common_validation)
        threshold_policy = select_threshold(common_targets, common_probabilities)
        full_metrics = binary_metrics(
            validation_targets,
            validation_probabilities,
            threshold=float(threshold_policy["threshold"]),
        )
        common_metrics = threshold_policy["metrics"]
        task_metrics = {}
        for task in sorted({str(row["task"]) for row in validation}):
            indexes = [index for index, row in enumerate(validation) if row["task"] == task]
            task_targets = [validation_targets[index] for index in indexes]
            if len(set(task_targets)) == 2:
                task_metrics[task] = binary_metrics(
                    task_targets,
                    [validation_probabilities[index] for index in indexes],
                    threshold=float(threshold_policy["threshold"]),
                )
        record = {
            "variant": variant,
            "training_examples": len(training),
            "internal_validation_examples": len(validation),
            "training_target_counts": dict(sorted(counts.items())),
            "trainable_parameters": trainable,
            "epochs": epochs,
            "history": history,
            "threshold_policy_selected_on_common_human_group_validation": threshold_policy,
            "common_human_group_validation": common_metrics,
            "full_variant_validation": full_metrics,
            "validation_by_task": task_metrics,
            "training_seconds": round(time.perf_counter() - started_variant, 3),
        }
        results.append(record)
        key = (
            float(common_metrics["roc_auc"]),
            float(common_metrics["average_precision"]),
            float(common_metrics["macro_f1"]),
        )
        if best_key is None or key > best_key:
            best_key = key
            best_variant = variant
            model.save_pretrained(output, safe_serialization=True)
            tokenizer.save_pretrained(output)
        del model, optimizer, train_loader, validation_loader, common_loader
        print(
            "%s complete: common AUC %.4f macro F1 %.4f"
            % (variant, common_metrics["roc_auc"], common_metrics["macro_f1"]),
            flush=True,
        )
    if best_variant is None:
        raise AlignmentTrainingError("Training did not select a variant.")
    artifact_files = _directory_manifest(output)
    artifact_id = hashlib.sha256(
        json.dumps(artifact_files, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    best_record = next(row for row in results if row["variant"] == best_variant)
    metadata = {
        "schema_version": "contexttrace-requirement-alignment-training-1.0",
        "dataset": {
            "path": str(dataset_file),
            "sha256": hashlib.sha256(dataset_file.read_bytes()).hexdigest(),
            "examples": len(examples),
        },
        "base_model": {
            "path_name": Path(base_model_path).name,
            "artifact_manifest_sha256": base_artifact["artifact_manifest_sha256"],
            "local_files_only": True,
        },
        "training": {
            "variants": list(VARIANTS),
            "epochs": epochs,
            "batch_size": batch_size,
            "learning_rate": learning_rate,
            "max_length": MAX_LENGTH,
            "random_seed": SEED,
            "device": "cpu",
            "trainable_scope": "last_two_encoder_layers_pooler_and_classifier",
        },
        "variant_results": results,
        "selection": {
            "split": "internal_validation.common_human_group",
            "rule": "maximize ROC AUC, average precision, then safety-constrained macro F1",
            "selected_variant": best_variant,
            "selected_threshold": best_record[
                "threshold_policy_selected_on_common_human_group_validation"
            ]["threshold"],
        },
        "artifact": {
            "model_id": artifact_id,
            "output_path_name": output.name,
            "files": artifact_files,
        },
        "stable_defaults_changed": False,
        "remote_inference_used": False,
        "development_or_heldout_examples_used_for_training": False,
    }
    model_manifest = {
        "schema_version": "contexttrace-requirement-alignment-model-manifest-1.0",
        "model_id": artifact_id,
        "selected_variant": best_variant,
        "selected_threshold": metadata["selection"]["selected_threshold"],
        "files": artifact_files,
        "stable_defaults_changed": False,
        "runtime_network_required": False,
    }
    return metadata, model_manifest


class EncodedExamples:
    def __init__(
        self,
        examples: list[dict[str, Any]],
        *,
        tokenizer: object,
        separator: str,
    ) -> None:
        pairs = [input_pair(row, separator=separator) for row in examples]
        evidence, hypotheses = zip(*pairs, strict=True)
        self.encodings = tokenizer(  # type: ignore[operator]
            list(evidence),
            list(hypotheses),
            max_length=MAX_LENGTH,
            padding="max_length",
            truncation="only_first",
            return_tensors="pt",
        )
        self.targets = binary_targets(examples)

    def __len__(self) -> int:
        return len(self.targets)

    def __getitem__(self, index: int) -> dict[str, Any]:
        item = {key: value[index] for key, value in self.encodings.items()}
        item["labels"] = self.targets[index]
        return item


def _freeze_for_transfer(model: object) -> int:
    for parameter in model.parameters():  # type: ignore[attr-defined]
        parameter.requires_grad = False
    encoder = getattr(getattr(model, "deberta", None), "encoder", None)
    layers = list(getattr(encoder, "layer", []) or [])
    if len(layers) < 2:
        raise AlignmentTrainingError("Expected at least two DeBERTa encoder layers.")
    for layer in layers[-2:]:
        for parameter in layer.parameters():
            parameter.requires_grad = True
    for name in ("pooler", "classifier"):
        module = getattr(model, name, None)
        if module is not None:
            for parameter in module.parameters():
                parameter.requires_grad = True
    count = sum(
        parameter.numel()
        for parameter in model.parameters()  # type: ignore[attr-defined]
        if parameter.requires_grad
    )
    if count <= 0:
        raise AlignmentTrainingError("Transfer setup left no trainable parameters.")
    return int(count)


def _predict(model: object, loader: object, *, torch: Any) -> list[float]:
    model.eval()  # type: ignore[attr-defined]
    output = []
    with torch.no_grad():
        for batch in loader:  # type: ignore[union-attr]
            batch.pop("labels")
            logits = model(**batch).logits  # type: ignore[operator]
            output.extend(torch.softmax(logits, dim=-1)[:, 1].tolist())
    return [float(value) for value in output]


def _seed_all(torch: Any) -> None:
    random.seed(SEED)
    try:
        import numpy as np

        np.random.seed(SEED)
    except ImportError:
        pass
    torch.manual_seed(SEED)
    torch.use_deterministic_algorithms(True)


def _directory_manifest(path: Path) -> list[dict[str, Any]]:
    rows = []
    for file in sorted(value for value in path.rglob("*") if value.is_file()):
        rows.append(
            {
                "path": str(file.relative_to(path)),
                "bytes": file.stat().st_size,
                "sha256": hashlib.sha256(file.read_bytes()).hexdigest(),
            }
        )
    return rows


def _write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--base-model-path", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--report-output", required=True)
    parser.add_argument("--model-manifest-output", required=True)
    parser.add_argument("--epochs", type=int, default=2)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--learning-rate", type=float, default=1e-5)
    args = parser.parse_args(argv)
    report, model_manifest = train_variants(
        args.dataset,
        base_model_path=args.base_model_path,
        output_dir=args.output_dir,
        epochs=args.epochs,
        batch_size=args.batch_size,
        learning_rate=args.learning_rate,
    )
    _write(Path(args.report_output), report)
    _write(Path(args.model_manifest_output), model_manifest)
    print(json.dumps(report["selection"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
