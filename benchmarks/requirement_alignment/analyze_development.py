"""Compare frozen requirement-alignment models on direct development labels."""

from __future__ import annotations

import argparse
import json
import statistics
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from benchmarks.requirement_alignment.train import EncodedExamples
from benchmarks.requirement_alignment.train import binary_metrics
from benchmarks.requirement_alignment.train import binary_targets
from benchmarks.requirement_alignment.train_v2 import select_safe_recall_threshold
from benchmarks.requirement_alignment.train_v2 import verify_source_model


class DevelopmentAnalysisError(RuntimeError):
    """Raised when frozen-model development analysis is invalid."""


def relation_metrics(
    examples: list[dict[str, Any]],
    probabilities: list[float],
    *,
    threshold: float,
) -> dict[str, Any]:
    output = {}
    for relation in sorted({str(row["source"]["relation"]) for row in examples}):
        indexes = [
            index
            for index, row in enumerate(examples)
            if row["source"]["relation"] == relation
        ]
        values = [probabilities[index] for index in indexes]
        targets = binary_targets([examples[index] for index in indexes])
        predictions = [int(value >= threshold) for value in values]
        output[relation] = {
            "cases": len(indexes),
            "target": "covered" if targets[0] else "missing",
            "mean_covered_probability": round(statistics.fmean(values), 4),
            "median_covered_probability": round(statistics.median(values), 4),
            "predicted_covered_rate": round(statistics.fmean(predictions), 4),
            "accuracy": round(
                sum(target == prediction for target, prediction in zip(targets, predictions, strict=True))
                / len(targets),
                4,
            ),
        }
    return output


def hypothesis_metrics(
    examples: list[dict[str, Any]],
    probabilities: list[float],
    *,
    threshold: float,
) -> list[dict[str, Any]]:
    indexes_by_hypothesis: dict[str, list[int]] = defaultdict(list)
    for index, row in enumerate(examples):
        indexes_by_hypothesis[str(row["source"]["hypothesis_id"])].append(index)
    output = []
    for hypothesis_id, indexes in sorted(indexes_by_hypothesis.items()):
        targets = binary_targets([examples[index] for index in indexes])
        predictions = [int(probabilities[index] >= threshold) for index in indexes]
        false_support = sum(
            target == 0 and prediction == 1
            for target, prediction in zip(targets, predictions, strict=True)
        )
        missed_support = sum(
            target == 1 and prediction == 0
            for target, prediction in zip(targets, predictions, strict=True)
        )
        output.append(
            {
                "hypothesis_id": hypothesis_id,
                "description": examples[indexes[0]]["source"]["hypothesis_description"],
                "cases": len(indexes),
                "covered_targets": sum(targets),
                "missing_targets": len(targets) - sum(targets),
                "accuracy": round(
                    sum(
                        target == prediction
                        for target, prediction in zip(targets, predictions, strict=True)
                    )
                    / len(targets),
                    4,
                ),
                "false_support": false_support,
                "missed_support": missed_support,
                "mean_covered_probability": round(
                    statistics.fmean(probabilities[index] for index in indexes), 4
                ),
            }
        )
    return output


def compare_predictions(
    examples: list[dict[str, Any]],
    first: list[float],
    second: list[float],
    *,
    first_threshold: float,
    second_threshold: float,
) -> dict[str, Any]:
    targets = binary_targets(examples)
    transitions = Counter()
    disagreements = []
    for row, target, first_probability, second_probability in zip(
        examples, targets, first, second, strict=True
    ):
        first_prediction = int(first_probability >= first_threshold)
        second_prediction = int(second_probability >= second_threshold)
        first_correct = first_prediction == target
        second_correct = second_prediction == target
        if first_correct and second_correct:
            transition = "both_correct"
        elif first_correct:
            transition = "v1_only_correct"
        elif second_correct:
            transition = "v2_only_correct"
        else:
            transition = "both_wrong"
        transitions[transition] += 1
        if first_prediction != second_prediction:
            disagreements.append(
                {
                    "id": row["id"],
                    "relation": row["source"]["relation"],
                    "hypothesis_id": row["source"]["hypothesis_id"],
                    "target": row["target"]["label"],
                    "v1_probability": round(first_probability, 6),
                    "v1_prediction": "covered" if first_prediction else "missing",
                    "v2_probability": round(second_probability, 6),
                    "v2_prediction": "covered" if second_prediction else "missing",
                    "transition": transition,
                }
            )
    return {
        "transition_counts": dict(sorted(transitions.items())),
        "prediction_disagreements": disagreements,
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
        if target == prediction:
            continue
        output.append(
            {
                "id": row["id"],
                "document_id": row["source"]["document_id"],
                "hypothesis_id": row["source"]["hypothesis_id"],
                "hypothesis_description": row["source"]["hypothesis_description"],
                "relation": row["source"]["relation"],
                "target": row["target"]["label"],
                "prediction": "covered" if prediction else "missing",
                "covered_probability": round(probability, 6),
                "evidence_selection": row["source"]["evidence_selection"],
                "evidence_span_indexes": row["source"]["evidence_span_indexes"],
            }
        )
    return output


def prediction_records(
    examples: list[dict[str, Any]],
    probabilities: list[float],
    *,
    threshold: float,
) -> list[dict[str, Any]]:
    return [
        {
            "id": row["id"],
            "relation": row["source"]["relation"],
            "hypothesis_id": row["source"]["hypothesis_id"],
            "target": row["target"]["label"],
            "prediction": "covered" if probability >= threshold else "missing",
            "covered_probability": round(probability, 6),
        }
        for row, probability in zip(examples, probabilities, strict=True)
    ]


def analyze_models(
    dataset_path: str | Path,
    *,
    v1_model_path: str | Path,
    v1_manifest_path: str | Path,
    v2_model_path: str | Path,
    v2_manifest_path: str | Path,
    batch_size: int = 8,
) -> dict[str, Any]:
    import torch
    from torch.utils.data import DataLoader
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    if batch_size < 1:
        raise DevelopmentAnalysisError("batch size must be positive.")
    dataset_file = Path(dataset_path)
    dataset = json.loads(dataset_file.read_text(encoding="utf-8"))
    examples = list(dataset.get("examples") or [])
    if not examples or any(row.get("split") != "development" for row in examples):
        raise DevelopmentAnalysisError("Expected a non-empty development-only dataset.")
    v1_manifest = verify_source_model(v1_model_path, v1_manifest_path)
    v2_manifest = verify_source_model(v2_model_path, v2_manifest_path)
    model_specs = [
        ("v1", Path(v1_model_path), v1_manifest),
        ("v2", Path(v2_model_path), v2_manifest),
    ]
    model_results = {}
    predictions = {}
    torch.set_num_threads(min(4, __import__("os").cpu_count() or 1))
    for name, model_path, manifest in model_specs:
        tokenizer = AutoTokenizer.from_pretrained(str(model_path), local_files_only=True)
        encoded = EncodedExamples(
            examples,
            tokenizer=tokenizer,
            separator=str(tokenizer.sep_token or "[SEP]"),
        )
        loader = DataLoader(encoded, batch_size=batch_size, shuffle=False)
        model = AutoModelForSequenceClassification.from_pretrained(
            str(model_path), local_files_only=True
        )
        started = time.perf_counter()
        probabilities = _predict(model, loader, torch=torch)
        seconds = time.perf_counter() - started
        threshold = float(manifest["selected_threshold"])
        targets = binary_targets(examples)
        diagnostic_policy = select_safe_recall_threshold(targets, probabilities)
        diagnostic_threshold = float(diagnostic_policy["threshold"])
        predictions[name] = probabilities
        model_results[name] = {
            "model_id": manifest["model_id"],
            "threshold": threshold,
            "threshold_source": "committed_model_manifest",
            "overall": binary_metrics(targets, probabilities, threshold=threshold),
            "brier_score": round(
                statistics.fmean(
                    (probability - target) ** 2
                    for probability, target in zip(probabilities, targets, strict=True)
                ),
                4,
            ),
            "inference_seconds": round(seconds, 3),
            "milliseconds_per_case": round(1000 * seconds / len(examples), 3),
            "by_relation": relation_metrics(
                examples, probabilities, threshold=threshold
            ),
            "by_hypothesis": hypothesis_metrics(
                examples, probabilities, threshold=threshold
            ),
            "errors": error_records(examples, probabilities, threshold=threshold),
            "predictions": prediction_records(
                examples, probabilities, threshold=threshold
            ),
            "development_safe_threshold_diagnostic": {
                "selection_warning": (
                    "Selected on development data for diagnosis only; not a confirmation result."
                ),
                "policy": diagnostic_policy,
                "by_relation": relation_metrics(
                    examples, probabilities, threshold=diagnostic_threshold
                ),
                "errors": error_records(
                    examples, probabilities, threshold=diagnostic_threshold
                ),
            },
        }
        del model, loader, encoded
    comparison = compare_predictions(
        examples,
        predictions["v1"],
        predictions["v2"],
        first_threshold=float(v1_manifest["selected_threshold"]),
        second_threshold=float(v2_manifest["selected_threshold"]),
    )
    v1 = model_results["v1"]["overall"]
    v2 = model_results["v2"]["overall"]
    comparison["v2_minus_v1"] = {
        key: round(float(v2[key]) - float(v1[key]), 4)
        for key in (
            "accuracy",
            "macro_f1",
            "positive_recall",
            "false_positive_rate",
            "roc_auc",
            "average_precision",
        )
    }
    return {
        "schema_version": "contexttrace-requirement-development-analysis-1.0",
        "dataset": {
            "path": str(dataset_file),
            "sha256": __import__("hashlib").sha256(dataset_file.read_bytes()).hexdigest(),
            "examples": len(examples),
            "split": "development",
        },
        "protocol": {
            "model_artifacts_verified": True,
            "thresholds_locked_before_development_scoring": True,
            "threshold_tuning_performed": False,
            "remote_inference_used": False,
            "test_split_accessed": False,
        },
        "models": model_results,
        "comparison": comparison,
        "stable_defaults_changed": False,
    }


def _predict(model: Any, loader: Any, *, torch: Any) -> list[float]:
    model.eval()
    output = []
    with torch.no_grad():
        for batch in loader:
            batch.pop("labels")
            logits = model(**batch).logits
            output.extend(torch.softmax(logits, dim=-1)[:, 1].tolist())
    return [float(value) for value in output]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--v1-model-path", required=True)
    parser.add_argument("--v1-manifest", required=True)
    parser.add_argument("--v2-model-path", required=True)
    parser.add_argument("--v2-manifest", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--batch-size", type=int, default=8)
    args = parser.parse_args(argv)
    report = analyze_models(
        args.dataset,
        v1_model_path=args.v1_model_path,
        v1_manifest_path=args.v1_manifest,
        v2_model_path=args.v2_model_path,
        v2_manifest_path=args.v2_manifest,
        batch_size=args.batch_size,
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        name: {
            "overall": value["overall"],
            "by_relation": value["by_relation"],
        }
        for name, value in report["models"].items()
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
