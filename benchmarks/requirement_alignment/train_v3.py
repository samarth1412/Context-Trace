"""Train one fixed three-way relation model with dual development safety gates."""

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

from benchmarks.requirement_alignment.analyze_development import relation_metrics
from benchmarks.requirement_alignment.train import MAX_LENGTH
from benchmarks.requirement_alignment.train import _directory_manifest
from benchmarks.requirement_alignment.train import _freeze_for_transfer
from benchmarks.requirement_alignment.train import _seed_all
from benchmarks.requirement_alignment.train import binary_metrics
from benchmarks.requirement_alignment.train import binary_targets
from benchmarks.requirement_alignment.train import input_pair
from contexttrace.verify.semantic_core_v2.nli import verify_nli_artifact


SEED = 20260930
EXPECTED_BASE_ARTIFACT_SHA256 = (
    "330f0fd77aad129877e1a1a90d4a77e6f093ee238b97d535202816a116b9c9f3"
)
RELATION_IDS = {"contradiction": 0, "entailment": 1, "neutral": 2}
CONTRACT_RECALL_TARGET = 0.50
FALSE_POSITIVE_CAP = 0.05
WICE_V2_RECALL = 0.2754
WICE_RECALL_FLOOR = WICE_V2_RECALL - 0.05


class V3TrainingError(RuntimeError):
    """Raised when the v3 experiment violates its frozen protocol."""


class EncodedRelations:
    def __init__(
        self,
        examples: list[dict[str, Any]],
        *,
        tokenizer: Any,
        separator: str,
    ) -> None:
        pairs = [input_pair(row, separator=separator) for row in examples]
        evidence, hypotheses = zip(*pairs, strict=True)
        self.encodings = tokenizer(
            list(evidence),
            list(hypotheses),
            max_length=MAX_LENGTH,
            padding="max_length",
            truncation="only_first",
            return_tensors="pt",
        )
        try:
            self.targets = [RELATION_IDS[str(row["target"]["label"])] for row in examples]
        except KeyError as error:
            raise V3TrainingError("Unknown relation training target.") from error

    def __len__(self) -> int:
        return len(self.targets)

    def __getitem__(self, index: int) -> dict[str, Any]:
        item = {key: value[index] for key, value in self.encodings.items()}
        item["labels"] = self.targets[index]
        return item


def select_dual_threshold(
    contract_targets: list[int],
    contract_probabilities: list[float],
    wice_targets: list[int],
    wice_probabilities: list[float],
) -> dict[str, Any]:
    candidates = []
    for value in range(5, 105, 5):
        threshold = value / 100
        contract = binary_metrics(
            contract_targets, contract_probabilities, threshold=threshold
        )
        wice = binary_metrics(wice_targets, wice_probabilities, threshold=threshold)
        safety_eligible = (
            contract["false_positive_rate"] <= FALSE_POSITIVE_CAP
            and wice["false_positive_rate"] <= FALSE_POSITIVE_CAP
        )
        gates_met = (
            safety_eligible
            and contract["positive_recall"] >= CONTRACT_RECALL_TARGET
            and wice["positive_recall"] >= WICE_RECALL_FLOOR
        )
        candidates.append(
            {
                "threshold": threshold,
                "safety_eligible": safety_eligible,
                "promotion_gates_met": gates_met,
                "contract_development": contract,
                "wice_internal": wice,
            }
        )
    eligible = [row for row in candidates if row["safety_eligible"]]
    if not eligible:
        raise V3TrainingError("No threshold satisfies both false-positive caps.")
    selected = max(
        eligible,
        key=lambda row: (
            row["promotion_gates_met"],
            row["contract_development"]["positive_recall"],
            row["wice_internal"]["positive_recall"],
            statistics.fmean(
                [
                    row["contract_development"]["macro_f1"],
                    row["wice_internal"]["macro_f1"],
                ]
            ),
            row["threshold"],
        ),
    )
    return {"selected": selected, "candidates": candidates}


def _selection_key(record: dict[str, Any]) -> tuple[Any, ...]:
    selected = record["dual_threshold_policy"]["selected"]
    contract = selected["contract_development"]
    wice = selected["wice_internal"]
    return (
        bool(selected["promotion_gates_met"]),
        float(contract["positive_recall"]),
        float(wice["positive_recall"]),
        statistics.fmean([contract["macro_f1"], wice["macro_f1"]]),
        statistics.fmean([contract["roc_auc"], wice["roc_auc"]]),
        -int(record["epoch"]),
    )


def _predict_entailment(model: Any, loader: Any, *, torch: Any) -> list[float]:
    model.eval()
    output = []
    with torch.no_grad():
        for batch in loader:
            batch.pop("labels")
            logits = model(**batch).logits
            output.extend(torch.softmax(logits, dim=-1)[:, RELATION_IDS["entailment"]].tolist())
    return [float(value) for value in output]


def train_v3(
    training_dataset_path: str | Path,
    *,
    contract_development_path: str | Path,
    wice_dataset_path: str | Path,
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
        raise V3TrainingError("epochs and batch size must be positive.")
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
    torch.set_num_threads(min(4, os.cpu_count() or 1))
    base_artifact = verify_nli_artifact(base_model_path)
    if base_artifact["artifact_manifest_sha256"] != EXPECTED_BASE_ARTIFACT_SHA256:
        raise V3TrainingError("The native NLI artifact does not match its lock.")

    training_path = Path(training_dataset_path)
    contract_path = Path(contract_development_path)
    wice_path = Path(wice_dataset_path)
    training = json.loads(training_path.read_text(encoding="utf-8")).get("examples") or []
    contract_development = json.loads(contract_path.read_text(encoding="utf-8")).get(
        "examples"
    ) or []
    wice_examples = json.loads(wice_path.read_text(encoding="utf-8")).get("examples") or []
    wice_development = [
        row
        for row in wice_examples
        if row["split"] == "internal_validation"
        and row["task"] == "claim_group_completeness"
        and row["source"]["construction"]
        in {"gold_complete_group", "gold_partial_group"}
    ]
    if not training or not contract_development or not wice_development:
        raise V3TrainingError("A required training or development partition is empty.")
    if any(row.get("split") != "training" for row in training):
        raise V3TrainingError("The v3 training artifact contains non-training rows.")
    if any(row.get("split") != "development" for row in contract_development):
        raise V3TrainingError("The ContractNLI evaluation partition is not development-only.")

    _seed_all(torch)
    tokenizer = AutoTokenizer.from_pretrained(str(base_model_path), local_files_only=True)
    separator = str(tokenizer.sep_token or "[SEP]")
    train_dataset = EncodedRelations(training, tokenizer=tokenizer, separator=separator)
    contract_dataset = _BinaryEncodedExamples(
        contract_development, tokenizer=tokenizer, separator=separator
    )
    wice_dataset = _BinaryEncodedExamples(
        wice_development, tokenizer=tokenizer, separator=separator
    )
    generator = torch.Generator().manual_seed(SEED)
    train_loader = DataLoader(
        train_dataset,
        batch_size=batch_size,
        shuffle=True,
        generator=generator,
    )
    contract_loader = DataLoader(contract_dataset, batch_size=batch_size, shuffle=False)
    wice_loader = DataLoader(wice_dataset, batch_size=batch_size, shuffle=False)
    model = AutoModelForSequenceClassification.from_pretrained(
        str(base_model_path), local_files_only=True
    )
    if int(model.config.num_labels) != 3:
        raise V3TrainingError("The native NLI model must retain its three-way head.")
    trainable = _freeze_for_transfer(model)
    counts = Counter(train_dataset.targets)
    class_weights = torch.tensor(
        [len(training) / (3 * counts[index]) for index in range(3)],
        dtype=torch.float32,
    )
    loss_function = torch.nn.CrossEntropyLoss(weight=class_weights)
    optimizer = torch.optim.AdamW(
        [parameter for parameter in model.parameters() if parameter.requires_grad],
        lr=learning_rate,
        weight_decay=0.01,
    )
    contract_targets = binary_targets(contract_development)
    wice_targets = binary_targets(wice_development)
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    evaluations = []
    best_key = None
    best_epoch = None

    def evaluate(epoch: int, train_loss: float | None, seconds: float) -> dict[str, Any]:
        contract_probabilities = _predict_entailment(
            model, contract_loader, torch=torch
        )
        wice_probabilities = _predict_entailment(model, wice_loader, torch=torch)
        policy = select_dual_threshold(
            contract_targets,
            contract_probabilities,
            wice_targets,
            wice_probabilities,
        )
        selected_threshold = float(policy["selected"]["threshold"])
        return {
            "epoch": epoch,
            "mean_train_loss": round(train_loss, 6) if train_loss is not None else None,
            "training_seconds": round(seconds, 3),
            "dual_threshold_policy": policy,
            "contract_relation_metrics": relation_metrics(
                contract_development,
                contract_probabilities,
                threshold=selected_threshold,
            ),
        }

    baseline = evaluate(0, None, 0.0)
    evaluations.append(baseline)
    best_key = _selection_key(baseline)
    best_epoch = 0
    model.save_pretrained(output, safe_serialization=True)
    tokenizer.save_pretrained(output)
    print(
        "epoch 0: contract recall %.4f FPR %.4f; WiCE recall %.4f FPR %.4f"
        % (
            baseline["dual_threshold_policy"]["selected"]["contract_development"][
                "positive_recall"
            ],
            baseline["dual_threshold_policy"]["selected"]["contract_development"][
                "false_positive_rate"
            ],
            baseline["dual_threshold_policy"]["selected"]["wice_internal"][
                "positive_recall"
            ],
            baseline["dual_threshold_policy"]["selected"]["wice_internal"][
                "false_positive_rate"
            ],
        ),
        flush=True,
    )

    for epoch in range(1, epochs + 1):
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
                [parameter for parameter in model.parameters() if parameter.requires_grad], 1.0
            )
            optimizer.step()
            losses.append(float(loss.detach()))
            if step % 25 == 0 or step == len(train_loader):
                print(
                    "epoch %d/%d step %d/%d loss %.4f"
                    % (
                        epoch,
                        epochs,
                        step,
                        len(train_loader),
                        statistics.fmean(losses[-25:]),
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
        if key > best_key:
            best_key = key
            best_epoch = epoch
            model.save_pretrained(output, safe_serialization=True)
            tokenizer.save_pretrained(output)
        selected = record["dual_threshold_policy"]["selected"]
        print(
            "epoch %d complete: contract recall %.4f FPR %.4f; WiCE recall %.4f FPR %.4f; gates %s"
            % (
                epoch,
                selected["contract_development"]["positive_recall"],
                selected["contract_development"]["false_positive_rate"],
                selected["wice_internal"]["positive_recall"],
                selected["wice_internal"]["false_positive_rate"],
                selected["promotion_gates_met"],
            ),
            flush=True,
        )

    if best_epoch is None:
        raise V3TrainingError("No v3 checkpoint was selected.")
    best = next(row for row in evaluations if row["epoch"] == best_epoch)
    selected = best["dual_threshold_policy"]["selected"]
    artifact_files = _directory_manifest(output)
    artifact_id = hashlib.sha256(
        json.dumps(artifact_files, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    report = {
        "schema_version": "contexttrace-requirement-v3-training-report-1.0",
        "datasets": {
            "training": _dataset_record(training_path, len(training)),
            "contract_development": _dataset_record(
                contract_path, len(contract_development)
            ),
            "wice_internal_source": _dataset_record(wice_path, len(wice_examples)),
            "wice_internal_cases": len(wice_development),
        },
        "base_model": {
            "path_name": Path(base_model_path).name,
            "artifact_manifest_sha256": base_artifact["artifact_manifest_sha256"],
            "native_relation_labels": model.config.id2label,
            "local_files_only": True,
        },
        "training": {
            "epochs": epochs,
            "batch_size": batch_size,
            "learning_rate": learning_rate,
            "max_length": MAX_LENGTH,
            "random_seed": SEED,
            "trainable_scope": "last_two_encoder_layers_pooler_and_three_way_classifier",
            "trainable_parameters": trainable,
            "relation_counts": dict(sorted(counts.items())),
            "class_weights": [round(float(value), 6) for value in class_weights],
        },
        "promotion_gates": {
            "contract_entailment_recall_minimum": CONTRACT_RECALL_TARGET,
            "contract_false_positive_rate_maximum": FALSE_POSITIVE_CAP,
            "wice_false_positive_rate_maximum": FALSE_POSITIVE_CAP,
            "wice_v2_recall_reference": WICE_V2_RECALL,
            "wice_recall_floor": WICE_RECALL_FLOOR,
        },
        "epoch_evaluations": evaluations,
        "selection": {
            "selected_epoch": best_epoch,
            "selected_threshold": selected["threshold"],
            "promotion_gates_met": selected["promotion_gates_met"],
            "contract_development": selected["contract_development"],
            "wice_internal": selected["wice_internal"],
            "next_step": (
                "freeze_model_and_prepare_untouched_confirmation"
                if selected["promotion_gates_met"]
                else "stop_small_model_finetuning"
            ),
        },
        "artifact": {
            "model_id": artifact_id,
            "output_path_name": output.name,
            "files": artifact_files,
        },
        "stable_defaults_changed": False,
        "remote_inference_used": False,
        "jev_labels_used": False,
        "contract_test_split_accessed": False,
    }
    manifest = {
        "schema_version": "contexttrace-requirement-alignment-model-manifest-v3-1.0",
        "model_id": artifact_id,
        "selected_epoch": best_epoch,
        "selected_threshold": selected["threshold"],
        "relation_labels": model.config.id2label,
        "files": artifact_files,
        "promotion_gates_met": selected["promotion_gates_met"],
        "stable_defaults_changed": False,
        "runtime_network_required": False,
    }
    return report, manifest


class _BinaryEncodedExamples:
    def __init__(
        self,
        examples: list[dict[str, Any]],
        *,
        tokenizer: Any,
        separator: str,
    ) -> None:
        pairs = [input_pair(row, separator=separator) for row in examples]
        evidence, hypotheses = zip(*pairs, strict=True)
        self.encodings = tokenizer(
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


def _dataset_record(path: Path, examples: int) -> dict[str, Any]:
    return {
        "path": str(path),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "examples": examples,
    }


def _write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--training-dataset", required=True)
    parser.add_argument("--contract-development", required=True)
    parser.add_argument("--wice-dataset", required=True)
    parser.add_argument("--base-model-path", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--report-output", required=True)
    parser.add_argument("--model-manifest-output", required=True)
    parser.add_argument("--epochs", type=int, default=2)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--learning-rate", type=float, default=1e-5)
    args = parser.parse_args(argv)
    report, manifest = train_v3(
        args.training_dataset,
        contract_development_path=args.contract_development,
        wice_dataset_path=args.wice_dataset,
        base_model_path=args.base_model_path,
        output_dir=args.output_dir,
        epochs=args.epochs,
        batch_size=args.batch_size,
        learning_rate=args.learning_rate,
    )
    _write(Path(args.report_output), report)
    _write(Path(args.model_manifest_output), manifest)
    print(json.dumps(report["selection"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
