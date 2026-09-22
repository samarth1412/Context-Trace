"""Improve safe positive recall from the frozen requirement-alignment v1 model."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import statistics
import time
from collections import Counter
from pathlib import Path
from typing import Any

from benchmarks.requirement_alignment.train import EncodedExamples
from benchmarks.requirement_alignment.train import _freeze_for_transfer
from benchmarks.requirement_alignment.train import _predict
from benchmarks.requirement_alignment.train import _seed_all
from benchmarks.requirement_alignment.train import binary_metrics
from benchmarks.requirement_alignment.train import binary_targets


SEED = 20260927
VARIANTS = ("confidence_filtered", "focal", "hard_positive_margin")
WEAK_NEGATIVE_CONSTRUCTIONS = {
    "same_document_hard_negative",
    "synthetic_drop_one",
}
FILTER_THRESHOLD = 0.70
HARD_POSITIVE_THRESHOLD = 0.50
FOCAL_GAMMA = 2.0
FOCAL_POSITIVE_ALPHA = 0.65
MARGIN = 0.50
MARGIN_WEIGHT = 0.25


class AlignmentV2TrainingError(RuntimeError):
    """Raised when the v2 experiment cannot be reproduced safely."""


def directory_manifest(path: str | Path) -> list[dict[str, Any]]:
    root = Path(path)
    return [
        {
            "path": str(file.relative_to(root)),
            "bytes": file.stat().st_size,
            "sha256": hashlib.sha256(file.read_bytes()).hexdigest(),
        }
        for file in sorted(value for value in root.rglob("*") if value.is_file())
    ]


def verify_source_model(
    model_path: str | Path, manifest_path: str | Path
) -> dict[str, Any]:
    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    expected_files = manifest.get("files")
    if not isinstance(expected_files, list) or not expected_files:
        raise AlignmentV2TrainingError("The v1 model manifest has no files.")
    actual_files = directory_manifest(model_path)
    if actual_files != expected_files:
        raise AlignmentV2TrainingError("The local v1 model does not match its manifest.")
    actual_id = hashlib.sha256(
        json.dumps(actual_files, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    if actual_id != manifest.get("model_id"):
        raise AlignmentV2TrainingError("The local v1 model ID does not match its manifest.")
    return manifest


def select_safe_recall_threshold(
    targets: list[int], probabilities: list[float]
) -> dict[str, Any]:
    """Select recall first on a fixed grid while enforcing a five-percent FPR cap."""
    candidates = []
    for value in range(5, 105, 5):
        threshold = value / 100
        metrics = binary_metrics(targets, probabilities, threshold=threshold)
        candidates.append(
            {
                "threshold": threshold,
                "meets_false_positive_cap": metrics["false_positive_rate"] <= 0.05,
                "metrics": metrics,
            }
        )
    eligible = [row for row in candidates if row["meets_false_positive_cap"]]
    if not eligible:
        raise AlignmentV2TrainingError("No threshold meets the false-positive cap.")
    selected = max(
        eligible,
        key=lambda row: (
            row["metrics"]["positive_recall"],
            row["metrics"]["macro_f1"],
            row["metrics"]["roc_auc"],
            row["threshold"],
        ),
    )
    return {
        "threshold": selected["threshold"],
        "metrics": selected["metrics"],
        "candidates": candidates,
    }


def prepare_variant_examples(
    training: list[dict[str, Any]],
    v1_probabilities: list[float],
    variant: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if variant not in VARIANTS:
        raise AlignmentV2TrainingError("Unknown v2 variant: %s" % variant)
    if len(training) != len(v1_probabilities):
        raise AlignmentV2TrainingError("Training rows and v1 scores are misaligned.")

    if variant == "confidence_filtered":
        removed = [
            (row, probability)
            for row, probability in zip(training, v1_probabilities, strict=True)
            if binary_targets([row])[0] == 0
            and row["source"]["construction"] in WEAK_NEGATIVE_CONSTRUCTIONS
            and probability >= FILTER_THRESHOLD
        ]
        removed_ids = {id(row) for row, _ in removed}
        selected = [row for row in training if id(row) not in removed_ids]
        return selected, {
            "filter_threshold": FILTER_THRESHOLD,
            "removed_weak_negatives": len(removed),
            "removed_probability_min": (
                round(min(probability for _, probability in removed), 6)
                if removed
                else None
            ),
        }

    if variant == "hard_positive_margin":
        hard = [
            row
            for row, probability in zip(training, v1_probabilities, strict=True)
            if binary_targets([row])[0] == 1
            and probability < HARD_POSITIVE_THRESHOLD
        ]
        return training + hard, {
            "hard_positive_threshold": HARD_POSITIVE_THRESHOLD,
            "hard_positives_duplicated_once": len(hard),
            "pairwise_margin": MARGIN,
            "pairwise_margin_weight": MARGIN_WEIGHT,
        }

    return list(training), {
        "focal_gamma": FOCAL_GAMMA,
        "focal_positive_alpha": FOCAL_POSITIVE_ALPHA,
        "focal_negative_alpha": round(1.0 - FOCAL_POSITIVE_ALPHA, 2),
    }


def focal_loss(logits: Any, labels: Any, *, torch: Any) -> Any:
    losses = torch.nn.functional.cross_entropy(logits, labels, reduction="none")
    probability = torch.softmax(logits, dim=-1).gather(1, labels[:, None]).squeeze(1)
    alpha = torch.where(
        labels == 1,
        torch.tensor(FOCAL_POSITIVE_ALPHA, dtype=logits.dtype),
        torch.tensor(1.0 - FOCAL_POSITIVE_ALPHA, dtype=logits.dtype),
    )
    return (alpha * (1.0 - probability).pow(FOCAL_GAMMA) * losses).mean()


def hard_positive_margin_loss(
    logits: Any, labels: Any, *, class_weights: Any, torch: Any
) -> Any:
    base = torch.nn.functional.cross_entropy(logits, labels, weight=class_weights)
    scores = logits[:, 1] - logits[:, 0]
    positives = scores[labels == 1]
    negatives = scores[labels == 0]
    if not len(positives) or not len(negatives):
        return base
    margin = torch.relu(MARGIN - positives[:, None] + negatives[None, :]).mean()
    return base + MARGIN_WEIGHT * margin


def _metrics_by_task(
    examples: list[dict[str, Any]],
    targets: list[int],
    probabilities: list[float],
    threshold: float,
) -> dict[str, Any]:
    output = {}
    for task in sorted({str(row["task"]) for row in examples}):
        indexes = [index for index, row in enumerate(examples) if row["task"] == task]
        task_targets = [targets[index] for index in indexes]
        if len(set(task_targets)) == 2:
            output[task] = binary_metrics(
                task_targets,
                [probabilities[index] for index in indexes],
                threshold=threshold,
            )
    return output


def train_v2_variants(
    dataset_path: str | Path,
    *,
    source_model_path: str | Path,
    source_manifest_path: str | Path,
    output_dir: str | Path,
    epochs: int = 1,
    batch_size: int = 8,
    learning_rate: float = 5e-6,
) -> tuple[dict[str, Any], dict[str, Any]]:
    import torch
    from torch.utils.data import DataLoader
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    if epochs < 1 or batch_size < 1:
        raise AlignmentV2TrainingError("epochs and batch size must be positive.")
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
    torch.set_num_threads(min(4, os.cpu_count() or 1))
    source_manifest = verify_source_model(source_model_path, source_manifest_path)
    dataset_file = Path(dataset_path)
    examples = json.loads(dataset_file.read_text(encoding="utf-8")).get("examples") or []
    if not examples:
        raise AlignmentV2TrainingError("The alignment dataset is empty.")
    training = [row for row in examples if row["split"] == "training"]
    validation = [row for row in examples if row["split"] == "internal_validation"]
    common_validation = [
        row
        for row in validation
        if row["task"] == "claim_group_completeness"
        and row["source"]["construction"]
        in {"gold_complete_group", "gold_partial_group"}
    ]

    tokenizer = AutoTokenizer.from_pretrained(str(source_model_path), local_files_only=True)
    separator = str(tokenizer.sep_token or "[SEP]")
    training_dataset = EncodedExamples(training, tokenizer=tokenizer, separator=separator)
    validation_dataset = EncodedExamples(validation, tokenizer=tokenizer, separator=separator)
    common_dataset = EncodedExamples(
        common_validation, tokenizer=tokenizer, separator=separator
    )
    training_loader = DataLoader(training_dataset, batch_size=batch_size, shuffle=False)
    validation_loader = DataLoader(validation_dataset, batch_size=batch_size, shuffle=False)
    common_loader = DataLoader(common_dataset, batch_size=batch_size, shuffle=False)

    source_model = AutoModelForSequenceClassification.from_pretrained(
        str(source_model_path), local_files_only=True
    )
    v1_training_probabilities = _predict(source_model, training_loader, torch=torch)
    v1_validation_probabilities = _predict(source_model, validation_loader, torch=torch)
    v1_common_probabilities = _predict(source_model, common_loader, torch=torch)
    validation_targets = binary_targets(validation)
    common_targets = binary_targets(common_validation)
    baseline_policy = select_safe_recall_threshold(
        common_targets, v1_common_probabilities
    )
    baseline_threshold = float(baseline_policy["threshold"])
    baseline = {
        "model_id": source_manifest["model_id"],
        "threshold_policy": baseline_policy,
        "full_validation": binary_metrics(
            validation_targets,
            v1_validation_probabilities,
            threshold=baseline_threshold,
        ),
        "validation_by_task": _metrics_by_task(
            validation,
            validation_targets,
            v1_validation_probabilities,
            baseline_threshold,
        ),
    }
    del source_model, training_loader

    results = []
    best_key = None
    best_variant = None
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    for variant in VARIANTS:
        _seed_all(torch)
        variant_training, intervention = prepare_variant_examples(
            training, v1_training_probabilities, variant
        )
        variant_dataset = EncodedExamples(
            variant_training, tokenizer=tokenizer, separator=separator
        )
        generator = torch.Generator().manual_seed(SEED)
        variant_loader = DataLoader(
            variant_dataset,
            batch_size=batch_size,
            shuffle=True,
            generator=generator,
        )
        model = AutoModelForSequenceClassification.from_pretrained(
            str(source_model_path), local_files_only=True
        )
        trainable = _freeze_for_transfer(model)
        counts = Counter(binary_targets(variant_training))
        class_weights = torch.tensor(
            [len(variant_training) / (2 * counts[index]) for index in (0, 1)],
            dtype=torch.float32,
        )
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
            for step, batch in enumerate(variant_loader, start=1):
                labels = batch.pop("labels")
                optimizer.zero_grad(set_to_none=True)
                logits = model(**batch).logits
                if variant == "focal":
                    loss = focal_loss(logits, labels, torch=torch)
                elif variant == "hard_positive_margin":
                    loss = hard_positive_margin_loss(
                        logits,
                        labels,
                        class_weights=class_weights,
                        torch=torch,
                    )
                else:
                    loss = torch.nn.functional.cross_entropy(
                        logits, labels, weight=class_weights
                    )
                loss.backward()
                torch.nn.utils.clip_grad_norm_(
                    [parameter for parameter in model.parameters() if parameter.requires_grad],
                    1.0,
                )
                optimizer.step()
                losses.append(float(loss.detach()))
                if step % 25 == 0 or step == len(variant_loader):
                    print(
                        "%s epoch %d/%d step %d/%d loss %.4f"
                        % (
                            variant,
                            epoch,
                            epochs,
                            step,
                            len(variant_loader),
                            statistics.fmean(losses[-25:]),
                        ),
                        flush=True,
                    )
            history.append(
                {
                    "epoch": epoch,
                    "mean_train_loss": round(statistics.fmean(losses), 6),
                    "seconds": round(time.perf_counter() - started_epoch, 3),
                }
            )

        probabilities = _predict(model, validation_loader, torch=torch)
        common_probabilities = _predict(model, common_loader, torch=torch)
        threshold_policy = select_safe_recall_threshold(
            common_targets, common_probabilities
        )
        threshold = float(threshold_policy["threshold"])
        common_metrics = threshold_policy["metrics"]
        record = {
            "variant": variant,
            "training_examples_after_intervention": len(variant_training),
            "training_target_counts": dict(sorted(counts.items())),
            "intervention": intervention,
            "trainable_parameters": trainable,
            "history": history,
            "threshold_policy_selected_on_common_human_group_validation": threshold_policy,
            "common_human_group_validation": common_metrics,
            "full_validation": binary_metrics(
                validation_targets, probabilities, threshold=threshold
            ),
            "validation_by_task": _metrics_by_task(
                validation, validation_targets, probabilities, threshold
            ),
            "training_seconds": round(time.perf_counter() - started_variant, 3),
        }
        results.append(record)
        key = (
            float(common_metrics["positive_recall"]),
            float(common_metrics["macro_f1"]),
            float(common_metrics["roc_auc"]),
            float(common_metrics["average_precision"]),
        )
        if best_key is None or key > best_key:
            best_key = key
            best_variant = variant
            model.save_pretrained(output, safe_serialization=True)
            tokenizer.save_pretrained(output)
        del model, optimizer, variant_loader
        print(
            "%s complete: recall %.4f FPR %.4f macro F1 %.4f"
            % (
                variant,
                common_metrics["positive_recall"],
                common_metrics["false_positive_rate"],
                common_metrics["macro_f1"],
            ),
            flush=True,
        )

    if best_variant is None:
        raise AlignmentV2TrainingError("Training did not select a v2 variant.")
    artifact_files = directory_manifest(output)
    artifact_id = hashlib.sha256(
        json.dumps(artifact_files, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    best_record = next(row for row in results if row["variant"] == best_variant)
    selected_metrics = best_record["common_human_group_validation"]
    target_met = (
        selected_metrics["positive_recall"] >= 0.50
        and selected_metrics["false_positive_rate"] <= 0.05
    )
    report = {
        "schema_version": "contexttrace-requirement-alignment-training-v2-1.0",
        "dataset": {
            "path": str(dataset_file),
            "sha256": hashlib.sha256(dataset_file.read_bytes()).hexdigest(),
            "training_examples": len(training),
            "internal_validation_examples": len(validation),
            "common_human_group_validation_examples": len(common_validation),
        },
        "source_model": {
            "path_name": Path(source_model_path).name,
            "model_id": source_manifest["model_id"],
            "verified_against_manifest": True,
            "local_files_only": True,
        },
        "training": {
            "variants": list(VARIANTS),
            "epochs": epochs,
            "batch_size": batch_size,
            "learning_rate": learning_rate,
            "random_seed": SEED,
            "device": "cpu",
            "trainable_scope": "last_two_encoder_layers_pooler_and_classifier",
        },
        "baseline_v1": baseline,
        "variant_results": results,
        "selection": {
            "split": "internal_validation.common_human_group",
            "threshold_rule": (
                "maximize positive recall, then macro F1, on the fixed 0.05 grid "
                "subject to false-positive rate <= 0.05"
            ),
            "variant_rule": (
                "maximize positive recall, then macro F1, ROC AUC, and average precision"
            ),
            "selected_variant": best_variant,
            "selected_threshold": best_record[
                "threshold_policy_selected_on_common_human_group_validation"
            ]["threshold"],
            "safe_recall_target": 0.50,
            "safe_recall_target_met": target_met,
            "next_step": (
                "freeze_disjoint_confirmation_pack"
                if target_met
                else "do_not_run_new_confirmation_pack"
            ),
        },
        "artifact": {
            "model_id": artifact_id,
            "output_path_name": output.name,
            "files": artifact_files,
        },
        "stable_defaults_changed": False,
        "remote_inference_used": False,
        "development_or_heldout_examples_used_for_training": False,
        "existing_evaluation_packs_used_for_selection": False,
    }
    model_manifest = {
        "schema_version": "contexttrace-requirement-alignment-model-manifest-v2-1.0",
        "model_id": artifact_id,
        "source_model_id": source_manifest["model_id"],
        "selected_variant": best_variant,
        "selected_threshold": report["selection"]["selected_threshold"],
        "files": artifact_files,
        "stable_defaults_changed": False,
        "runtime_network_required": False,
    }
    return report, model_manifest


def _write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--source-model-path", required=True)
    parser.add_argument("--source-manifest", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--report-output", required=True)
    parser.add_argument("--model-manifest-output", required=True)
    parser.add_argument("--epochs", type=int, default=1)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--learning-rate", type=float, default=5e-6)
    args = parser.parse_args(argv)
    report, model_manifest = train_v2_variants(
        args.dataset,
        source_model_path=args.source_model_path,
        source_manifest_path=args.source_manifest,
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
