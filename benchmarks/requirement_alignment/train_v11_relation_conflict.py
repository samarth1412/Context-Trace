"""Train V11 evidence relations and select an explicit conflict policy."""

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

from benchmarks.requirement_alignment.train import MAX_LENGTH, _freeze_for_transfer
from benchmarks.requirement_alignment.train_v5 import resolve_relation_ids
from benchmarks.requirement_alignment.v10_fourway import (
    DEVELOPMENT_SPLIT,
    DISPUTED_REVIEW_TARGET,
    FALSE_SUPPORT_CAP,
    LABELS,
    REVIEW_RATE_CAP,
    SUPPORT_RECALL_TARGET,
    four_way_metrics,
)
from contexttrace.verify.semantic_core_v2.constants import (
    NLI_ARTIFACT_MANIFEST_SHA256,
    NLI_MODEL_ID,
    NLI_MODEL_REVISION,
)
from contexttrace.verify.semantic_core_v2.nli import verify_nli_artifact


EXPERIMENT = "contexttrace_v11_relation_conflict"
TRAINING_SPLIT = "climate_fever_v11_span_training"
SEED = 20260927
RELATIONS = ("contradiction", "entailment", "neutral")
CONFLICT_METHODS = ("cross_span_product", "minimum", "product", "harmonic")


class V11TrainingError(RuntimeError):
    """Raised when V11 training or policy selection violates its contract."""


class _EncodedPairs:
    def __init__(
        self,
        pairs: list[tuple[str, str]],
        *,
        tokenizer: Any,
        labels: list[int] | None = None,
    ) -> None:
        evidence, claims = zip(*pairs, strict=True)
        self.values = tokenizer(
            list(evidence),
            list(claims),
            max_length=MAX_LENGTH,
            padding="max_length",
            truncation="only_first",
            return_tensors="pt",
        )
        self.labels = labels

    def __len__(self) -> int:
        return int(self.values["input_ids"].shape[0])

    def __getitem__(self, index: int) -> dict[str, Any]:
        item = {key: value[index] for key, value in self.values.items()}
        if self.labels is not None:
            item["labels"] = self.labels[index]
        return item


def train_v11(
    training_dataset_path: str | Path,
    development_dataset_path: str | Path,
    *,
    base_model_path: str | Path,
    output_dir: str | Path,
    epochs: int = 3,
    batch_size: int = 16,
    learning_rate: float = 1e-5,
) -> tuple[dict[str, Any], dict[str, Any]]:
    import torch
    from torch.utils.data import DataLoader
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    if epochs < 1 or batch_size < 1:
        raise V11TrainingError("Epochs and batch size must be positive.")
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
    torch.set_num_threads(min(4, os.cpu_count() or 1))
    _seed_all(torch)

    training_path = Path(training_dataset_path)
    development_path = Path(development_dataset_path)
    training = json.loads(training_path.read_text(encoding="utf-8"))
    development = json.loads(development_path.read_text(encoding="utf-8"))
    train_rows = list(training.get("examples") or [])
    dev_rows = list(development.get("examples") or [])
    _validate_datasets(training, train_rows, development, dev_rows)

    artifact = verify_nli_artifact(Path(base_model_path))
    if artifact["artifact_manifest_sha256"] != NLI_ARTIFACT_MANIFEST_SHA256:
        raise V11TrainingError("Pinned NLI artifact does not match its frozen lock.")
    tokenizer = AutoTokenizer.from_pretrained(
        str(base_model_path), local_files_only=True
    )
    model = AutoModelForSequenceClassification.from_pretrained(
        str(base_model_path), local_files_only=True, dtype=torch.float32
    )
    relation_ids = resolve_relation_ids(model.config)
    train_pairs = [
        (str(row["input"]["evidence"]["text"]), str(row["input"]["claim"]))
        for row in train_rows
    ]
    train_labels = [relation_ids[str(row["target"]["relation"])] for row in train_rows]
    dev_pairs, dev_claim_indexes = _development_pairs(dev_rows)
    train_dataset = _EncodedPairs(train_pairs, tokenizer=tokenizer, labels=train_labels)
    dev_dataset = _EncodedPairs(dev_pairs, tokenizer=tokenizer)
    generator = torch.Generator().manual_seed(SEED)
    train_loader = DataLoader(
        train_dataset,
        batch_size=batch_size,
        shuffle=True,
        generator=generator,
    )
    dev_loader = DataLoader(dev_dataset, batch_size=batch_size, shuffle=False)
    trainable_parameters = _freeze_for_transfer(model)
    total_parameters = sum(parameter.numel() for parameter in model.parameters())
    counts = Counter(train_labels)
    weights = torch.tensor(
        [len(train_labels) / (len(RELATIONS) * counts[index]) for index in range(3)],
        dtype=torch.float32,
    )
    loss_function = torch.nn.CrossEntropyLoss(weight=weights)
    optimizer = torch.optim.AdamW(
        [parameter for parameter in model.parameters() if parameter.requires_grad],
        lr=learning_rate,
        weight_decay=0.01,
    )
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    evaluations = []
    best_key: tuple[Any, ...] | None = None
    best_epoch: int | None = None

    def evaluate(epoch: int, loss: float | None, seconds: float) -> dict[str, Any]:
        probabilities, latency = _predict(model, dev_loader, torch=torch)
        record = evaluate_development(
            dev_rows,
            dev_claim_indexes,
            probabilities,
            relation_ids,
        )
        record.update(
            {
                "epoch": epoch,
                "mean_train_loss": round(loss, 6) if loss is not None else None,
                "training_seconds": round(seconds, 3),
                "development_inference": latency,
            }
        )
        return record

    for epoch in range(epochs + 1):
        if epoch == 0:
            record = evaluate(0, None, 0.0)
        else:
            model.train()
            losses = []
            started = time.perf_counter()
            for step, batch in enumerate(train_loader, start=1):
                labels = batch.pop("labels")
                optimizer.zero_grad(set_to_none=True)
                logits = model(**batch).logits
                loss = loss_function(logits, labels)
                loss.backward()
                torch.nn.utils.clip_grad_norm_(
                    [
                        parameter
                        for parameter in model.parameters()
                        if parameter.requires_grad
                    ],
                    1.0,
                )
                optimizer.step()
                losses.append(float(loss.detach()))
                if step % 50 == 0 or step == len(train_loader):
                    print(
                        "epoch %d/%d step %d/%d loss %.4f"
                        % (
                            epoch,
                            epochs,
                            step,
                            len(train_loader),
                            statistics.fmean(losses[-50:]),
                        ),
                        flush=True,
                    )
            record = evaluate(
                epoch,
                statistics.fmean(losses),
                time.perf_counter() - started,
            )
        evaluations.append(record)
        key = _selection_key(record)
        if best_key is None or key > best_key:
            best_key = key
            best_epoch = epoch
            model.save_pretrained(output, safe_serialization=True)
            tokenizer.save_pretrained(output)
        _print_evaluation(record)

    if best_epoch is None:
        raise V11TrainingError("No V11 checkpoint was selected.")
    selected = next(row for row in evaluations if row["epoch"] == best_epoch)
    artifact_files = _directory_manifest(output)
    artifact_id = _sha256_json(artifact_files)
    report = {
        "schema_version": "contexttrace-v11-relation-conflict-training-1.0",
        "experiment": EXPERIMENT,
        "datasets": {
            "training": {
                "sha256": _sha256_json(training),
                "spans": len(train_rows),
            },
            "development": {
                "sha256": _sha256_json(development),
                "claims": len(dev_rows),
                "evidence_spans": len(dev_pairs),
                "selection_only": True,
            },
        },
        "base_model": {
            "model_id": NLI_MODEL_ID,
            "revision": NLI_MODEL_REVISION,
            "artifact_manifest_sha256": artifact["artifact_manifest_sha256"],
            "local_files_only": True,
        },
        "training": {
            "epochs": epochs,
            "batch_size": batch_size,
            "learning_rate": learning_rate,
            "max_length": MAX_LENGTH,
            "random_seed": SEED,
            "device": "cpu",
            "trainable_scope": "last_two_encoder_layers_pooler_and_three_way_classifier",
            "trainable_parameters": trainable_parameters,
            "total_parameters": total_parameters,
            "relation_ids": relation_ids,
            "class_weights_by_id": [round(float(value), 6) for value in weights],
            "evaluation_labels_in_model_inputs": False,
        },
        "promotion_gates": {
            "support_recall_minimum": SUPPORT_RECALL_TARGET,
            "false_support_rate_maximum": FALSE_SUPPORT_CAP,
            "zero_refutation_false_supports": True,
            "disputed_review_coverage_minimum": DISPUTED_REVIEW_TARGET,
            "review_rate_maximum": REVIEW_RATE_CAP,
        },
        "epoch_evaluations": evaluations,
        "selection": {
            "selected_epoch": best_epoch,
            "selected": selected,
            "promotion_gates_met": selected["policy"]["gates"]["all_met"],
        },
        "artifact": {
            "model_id": artifact_id,
            "output_path_name": output.name,
            "bytes": sum(int(row["bytes"]) for row in artifact_files),
            "files": artifact_files,
        },
        "decision": (
            "freeze_before_external_confirmation"
            if selected["policy"]["gates"]["all_met"]
            else "do_not_promote"
        ),
        "v9_holdout_reused": False,
        "remote_inference_used": False,
        "stable_defaults_changed": False,
        "remote_provider_default_enabled": False,
        "local_only_network_calls": 0,
    }
    manifest = {
        "schema_version": "contexttrace-v11-relation-model-manifest-1.0",
        "experiment": EXPERIMENT,
        "model_id": artifact_id,
        "selected_epoch": best_epoch,
        "promotion_gates_met": selected["policy"]["gates"]["all_met"],
        "relation_ids": relation_ids,
        "files": artifact_files,
        "runtime_network_required": False,
        "stable_defaults_changed": False,
    }
    return report, manifest


def evaluate_development(
    examples: list[dict[str, Any]],
    claim_indexes: list[int],
    probabilities: list[list[float]],
    relation_ids: dict[str, int],
) -> dict[str, Any]:
    grouped = [[] for _ in examples]
    for claim_index, values in zip(claim_indexes, probabilities, strict=True):
        grouped[claim_index].append(
            {relation: float(values[index]) for relation, index in relation_ids.items()}
        )
    if any(
        len(rows) != len(examples[index]["input"]["evidence"])
        for index, rows in enumerate(grouped)
    ):
        raise V11TrainingError("Development relation probabilities are misaligned.")
    targets = [str(row["source"]["claim_label"]) for row in examples]
    span_targets = [
        str(audit["evidence_label"])
        for row in examples
        for audit in row["source"]["evidence_audit"]
    ]
    span_predictions = [
        _relation_label(max(row, key=row.get)) for values in grouped for row in values
    ]
    relation_metrics = _classification_metrics(
        [_claim_label(value) for value in span_targets],
        [_claim_label(value) for value in span_predictions],
        ("NOT_ENOUGH_INFO", "REFUTES", "SUPPORTS"),
    )
    direct = _select_direct_policy(targets, grouped)
    routed = _select_routing_policy(
        [str(row["id"]) for row in examples], targets, grouped
    )
    return {
        "evidence_relation": relation_metrics,
        "direct_four_way": direct,
        "policy": routed,
    }


def _select_direct_policy(
    targets: list[str], grouped: list[list[dict[str, float]]]
) -> dict[str, Any]:
    entailment = [max(row["entailment"] for row in values) for values in grouped]
    contradiction = [max(row["contradiction"] for row in values) for values in grouped]
    candidates = []
    for entailment_minimum in sorted({0.0, 1.0, *entailment}):
        for contradiction_minimum in sorted({0.0, 1.0, *contradiction}):
            predictions = [
                _four_way_label(
                    support >= entailment_minimum,
                    refute >= contradiction_minimum,
                )
                for support, refute in zip(entailment, contradiction, strict=True)
            ]
            metrics = four_way_metrics(targets, predictions)
            candidates.append(
                {
                    "entailment_minimum": entailment_minimum,
                    "contradiction_minimum": contradiction_minimum,
                    "metrics": metrics,
                }
            )
    return max(
        candidates,
        key=lambda row: (
            float(row["metrics"]["macro_f1"]),
            float(row["metrics"]["accuracy"]),
            float(row["entailment_minimum"]),
            float(row["contradiction_minimum"]),
        ),
    )


def _select_routing_policy(
    case_ids: list[str],
    targets: list[str],
    grouped: list[list[dict[str, float]]],
) -> dict[str, Any]:
    entailment = [max(row["entailment"] for row in values) for values in grouped]
    contradiction = [max(row["contradiction"] for row in values) for values in grouped]
    conflict = {
        "minimum": [
            min(left, right)
            for left, right in zip(entailment, contradiction, strict=True)
        ],
        "product": [
            left * right for left, right in zip(entailment, contradiction, strict=True)
        ],
        "harmonic": [
            _ratio(2 * left * right, left + right)
            for left, right in zip(entailment, contradiction, strict=True)
        ],
        "cross_span_product": [
            max(
                first["entailment"] * second["contradiction"]
                for left_index, first in enumerate(values)
                for right_index, second in enumerate(values)
                if left_index != right_index
            )
            for values in grouped
        ],
    }
    max_review = int(len(targets) * REVIEW_RATE_CAP)
    candidates = []
    for method in CONFLICT_METHODS:
        ranked = sorted(
            range(len(targets)),
            key=lambda index: (-conflict[method][index], case_ids[index]),
        )
        for review_count in range(max_review + 1):
            review = set(ranked[:review_count])
            for support_minimum in sorted({0.0, 1.0, *entailment}):
                for contradiction_maximum in sorted({0.0, 1.0, *contradiction}):
                    supported = {
                        index
                        for index in range(len(targets))
                        if index not in review
                        and entailment[index] >= support_minimum
                        and contradiction[index] <= contradiction_maximum
                    }
                    row = _routing_metrics(targets, supported, review)
                    row.update(
                        {
                            "conflict_method": method,
                            "review_cases": review_count,
                            "review_rate": _ratio(review_count, len(targets)),
                            "support_probability_minimum": support_minimum,
                            "contradiction_probability_maximum": contradiction_maximum,
                        }
                    )
                    candidates.append(row)
    passing = [row for row in candidates if row["gates"]["all_met"]]
    safe = [
        row
        for row in candidates
        if row["gates"]["false_support_rate"]
        and row["gates"]["zero_refutation_false_supports"]
        and row["gates"]["review_rate"]
    ]
    selected = max(
        passing or safe,
        key=lambda row: (
            float(row["support_recall"]),
            float(row["disputed_review_coverage"]),
            -float(row["false_support_rate"]),
            -int(row["review_cases"]),
        ),
    )
    return {
        **selected,
        "candidate_count": len(candidates),
        "all_gate_candidate_count": len(passing),
        "selected_kind": "all_gates" if passing else "best_safety_eligible_diagnostic",
    }


def _routing_metrics(
    targets: list[str], supported: set[int], review: set[int]
) -> dict[str, Any]:
    support_total = sum(value == "SUPPORTS" for value in targets)
    negative_total = len(targets) - support_total
    true_support = sum(targets[index] == "SUPPORTS" for index in supported)
    false_support = sum(targets[index] != "SUPPORTS" for index in supported)
    refute_false_support = sum(targets[index] == "REFUTES" for index in supported)
    disputed_total = sum(value == "DISPUTED" for value in targets)
    disputed_reviewed = sum(targets[index] == "DISPUTED" for index in review)
    recall = _ratio(true_support, support_total)
    false_rate = _ratio(false_support, negative_total)
    dispute_coverage = _ratio(disputed_reviewed, disputed_total)
    review_rate = _ratio(len(review), len(targets))
    gates = {
        "support_recall": recall >= SUPPORT_RECALL_TARGET,
        "false_support_rate": false_rate <= FALSE_SUPPORT_CAP,
        "zero_refutation_false_supports": refute_false_support == 0,
        "disputed_review_coverage": dispute_coverage >= DISPUTED_REVIEW_TARGET,
        "review_rate": review_rate <= REVIEW_RATE_CAP,
    }
    return {
        "support_recall": round(recall, 4),
        "false_support_rate": round(false_rate, 4),
        "refutation_false_supports": refute_false_support,
        "disputed_review_coverage": round(dispute_coverage, 4),
        "true_supports": true_support,
        "false_supports": false_support,
        "gates": {**gates, "all_met": all(gates.values())},
    }


def _classification_metrics(
    targets: list[str], predictions: list[str], labels: tuple[str, ...]
) -> dict[str, Any]:
    if len(targets) != len(predictions) or not targets:
        raise V11TrainingError("Classification inputs must be non-empty and aligned.")
    confusion = {gold: {guess: 0 for guess in labels} for gold in labels}
    for gold, guess in zip(targets, predictions, strict=True):
        if gold not in labels or guess not in labels:
            raise V11TrainingError("Classification input contains an unknown label.")
        confusion[gold][guess] += 1
    f1s = []
    per_class = {}
    for label in labels:
        true_positive = confusion[label][label]
        false_positive = sum(confusion[gold][label] for gold in labels if gold != label)
        false_negative = sum(
            confusion[label][guess] for guess in labels if guess != label
        )
        precision = _ratio(true_positive, true_positive + false_positive)
        recall = _ratio(true_positive, true_positive + false_negative)
        f1 = _ratio(2 * precision * recall, precision + recall)
        f1s.append(f1)
        per_class[label] = {
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
            "support": sum(confusion[label].values()),
        }
    return {
        "accuracy": round(
            _ratio(sum(confusion[label][label] for label in labels), len(targets)),
            4,
        ),
        "macro_f1": round(statistics.fmean(f1s), 4),
        "per_class": per_class,
        "confusion": confusion,
    }


def _development_pairs(
    examples: list[dict[str, Any]],
) -> tuple[list[tuple[str, str]], list[int]]:
    pairs = []
    indexes = []
    for index, row in enumerate(examples):
        claim = str(row["input"]["claim"])
        for evidence in row["input"]["evidence"]:
            pairs.append((str(evidence["text"]), claim))
            indexes.append(index)
    return pairs, indexes


def _predict(
    model: Any, loader: Any, *, torch: Any
) -> tuple[list[list[float]], dict[str, Any]]:
    model.eval()
    output = []
    started = time.perf_counter()
    with torch.no_grad():
        for batch in loader:
            output.extend(torch.softmax(model(**batch).logits, dim=-1).tolist())
    seconds = time.perf_counter() - started
    return [[float(value) for value in row] for row in output], {
        "seconds": round(seconds, 4),
        "spans": len(output),
        "spans_per_second": round(_ratio(len(output), seconds), 4),
    }


def _validate_datasets(
    training: dict[str, Any],
    train_rows: list[dict[str, Any]],
    development: dict[str, Any],
    dev_rows: list[dict[str, Any]],
) -> None:
    if training.get("split") != TRAINING_SPLIT or not train_rows:
        raise V11TrainingError("V11 training split is empty or invalid.")
    if development.get("split") != DEVELOPMENT_SPLIT or not dev_rows:
        raise V11TrainingError("V10 development split is empty or invalid.")
    if any(
        {"label", "target", "relation"} & set(row["input"])
        for row in train_rows + dev_rows
    ):
        raise V11TrainingError("Evaluation labels must not appear in model inputs.")
    if any(
        str(row.get("target", {}).get("relation")) not in RELATIONS
        for row in train_rows
    ):
        raise V11TrainingError("V11 training contains an unknown relation target.")
    if any(str(row["source"]["claim_label"]) not in LABELS for row in dev_rows):
        raise V11TrainingError("V10 development contains an unknown claim label.")


def _selection_key(record: dict[str, Any]) -> tuple[Any, ...]:
    policy = record["policy"]
    direct = record["direct_four_way"]["metrics"]
    return (
        bool(policy["gates"]["all_met"]),
        sum(bool(value) for key, value in policy["gates"].items() if key != "all_met"),
        float(direct["macro_f1"]),
        float(policy["disputed_review_coverage"]),
        float(policy["support_recall"]),
        -float(policy["false_support_rate"]),
        -int(record["epoch"]),
    )


def _relation_label(relation: str) -> str:
    return {
        "entailment": "SUPPORTS",
        "contradiction": "REFUTES",
        "neutral": "NOT_ENOUGH_INFO",
    }[relation]


def _claim_label(evidence_label: str) -> str:
    if evidence_label not in {"SUPPORTS", "REFUTES", "NOT_ENOUGH_INFO"}:
        raise V11TrainingError("Unknown evidence label in development audit.")
    return evidence_label


def _four_way_label(support: bool, refute: bool) -> str:
    if support and refute:
        return "DISPUTED"
    if support:
        return "SUPPORTS"
    if refute:
        return "REFUTES"
    return "NOT_ENOUGH_INFO"


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
                "sha256": _sha256_file(file),
            }
        )
    return rows


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _sha256_json(value: object) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _ratio(numerator: float, denominator: float) -> float:
    return float(numerator / denominator) if denominator else 0.0


def _print_evaluation(record: dict[str, Any]) -> None:
    direct = record["direct_four_way"]["metrics"]
    policy = record["policy"]
    print(
        "epoch %d: macro-F1 %.4f accuracy %.4f; support recall %.4f FPR %.4f; disputed review %.4f; gates %s"
        % (
            record["epoch"],
            direct["macro_f1"],
            direct["accuracy"],
            policy["support_recall"],
            policy["false_support_rate"],
            policy["disputed_review_coverage"],
            policy["gates"]["all_met"],
        ),
        flush=True,
    )


def _write(path: str | Path, value: dict[str, Any]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--training-dataset", required=True)
    parser.add_argument("--development-dataset", required=True)
    parser.add_argument("--base-model-path", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--report-output", required=True)
    parser.add_argument("--manifest-output", required=True)
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--learning-rate", type=float, default=1e-5)
    args = parser.parse_args(argv)
    report, manifest = train_v11(
        args.training_dataset,
        args.development_dataset,
        base_model_path=args.base_model_path,
        output_dir=args.output_dir,
        epochs=args.epochs,
        batch_size=args.batch_size,
        learning_rate=args.learning_rate,
    )
    _write(args.report_output, report)
    _write(args.manifest_output, manifest)
    print(json.dumps(report["selection"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
