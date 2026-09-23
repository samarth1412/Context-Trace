"""Train the fixed v5 three-way verifier with a stronger pinned backbone."""

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

from benchmarks.requirement_alignment.analyze_development import relation_metrics
from benchmarks.requirement_alignment.train import MAX_LENGTH
from benchmarks.requirement_alignment.train import _freeze_for_transfer
from benchmarks.requirement_alignment.train import binary_metrics
from benchmarks.requirement_alignment.train import binary_targets
from benchmarks.requirement_alignment.train import input_pair
from benchmarks.requirement_alignment.train_v3 import _BinaryEncodedExamples


SEED = 20261001
SOURCE_REPOSITORY = "MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli"
SOURCE_REVISION = "6f5cf0a2b59cabb106aca4c287eed12e357e90eb"
SOURCE_LICENSE = "mit"
SOURCE_ARTIFACT_SHA256 = (
    "4c94466fb55da3fc09e5cb48b4c7da3303008ac8903b9400f55d4eabd46f24f6"
)
SOURCE_FILES = {
    "config.json": "a6c616d6dabeacf90fd0e776c741d3f0f30a05533ccf0bd3b5b62e94cfaa8d57",
    "model.safetensors": "06d6fd89edd4f97816831626daafbdb0b029cf63bae8edc0bccab1d64e2e7707",
    "special_tokens_map.json": "9463f61e1b109a8eb4688b829260d7c6b1e6dff04c98ff7269bb89e2b92369b9",
    "spm.model": "c679fbf93643d19aab7ee10c0b99e460bdbc02fedf34b92b05af343b4af586fd",
    "tokenizer.json": "05402ffae6dd382a8491b1d29bfc139bec5d332662e86a026f433ce54c25c202",
    "tokenizer_config.json": "557b3d33d3f41b81ad769244e506549e98a1857d41dd58160aacd4d98d710b5a",
}
CONTRACT_RECALL_TARGET = 0.50
FALSE_POSITIVE_CAP = 0.05
WICE_V2_RECALL = 0.2754
WICE_RECALL_FLOOR = WICE_V2_RECALL - 0.05


class V5TrainingError(RuntimeError):
    """Raised when the v5 experiment violates its frozen protocol."""


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _manifest_hash(rows: list[dict[str, Any]]) -> str:
    value = json.dumps(rows, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(value).hexdigest()


def verify_source_artifact(model_path: str | Path) -> dict[str, Any]:
    root = Path(model_path)
    if not root.is_dir():
        raise V5TrainingError("The v5 source model path must be a local directory.")
    rows = []
    for relative, expected in sorted(SOURCE_FILES.items()):
        path = root / relative
        if not path.is_file():
            raise V5TrainingError("The v5 source artifact is missing %s." % relative)
        digest = _file_sha256(path)
        if digest != expected:
            raise V5TrainingError("The v5 source artifact hash differs for %s." % relative)
        rows.append(
            {"path": relative, "bytes": path.stat().st_size, "sha256": digest}
        )
    artifact_sha256 = _manifest_hash(rows)
    if artifact_sha256 != SOURCE_ARTIFACT_SHA256:
        raise V5TrainingError("The v5 source artifact manifest does not match its lock.")
    return {
        "repository": SOURCE_REPOSITORY,
        "revision": SOURCE_REVISION,
        "license": SOURCE_LICENSE,
        "artifact_manifest_sha256": artifact_sha256,
        "files": rows,
        "bytes": sum(int(row["bytes"]) for row in rows),
    }


def resolve_relation_ids(config: Any) -> dict[str, int]:
    """Resolve semantic relation IDs without assuming a checkpoint's class order."""
    label2id = {
        str(label).strip().lower().replace(" ", "_"): int(index)
        for label, index in dict(getattr(config, "label2id", {}) or {}).items()
    }
    aliases = {"not_mentioned": "neutral"}
    normalized = {aliases.get(label, label): index for label, index in label2id.items()}
    required = {"entailment", "neutral", "contradiction"}
    if set(normalized) != required or len(set(normalized.values())) != 3:
        raise V5TrainingError(
            "The source checkpoint must expose distinct entailment, neutral, and contradiction labels."
        )
    return {label: normalized[label] for label in sorted(required)}


class EncodedRelations:
    def __init__(
        self,
        examples: list[dict[str, Any]],
        *,
        tokenizer: Any,
        separator: str,
        relation_ids: dict[str, int],
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
            self.targets = [
                relation_ids[str(row["target"]["label"])] for row in examples
            ]
        except KeyError as error:
            raise V5TrainingError("Unknown v5 relation training target.") from error

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
        raise V5TrainingError("No threshold satisfies both false-positive caps.")
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


def _predict_entailment(
    model: Any,
    loader: Any,
    *,
    entailment_id: int,
    torch: Any,
) -> tuple[list[float], dict[str, Any]]:
    model.eval()
    output = []
    started = time.perf_counter()
    with torch.no_grad():
        for batch in loader:
            batch.pop("labels")
            logits = model(**batch).logits
            output.extend(torch.softmax(logits, dim=-1)[:, entailment_id].tolist())
    seconds = time.perf_counter() - started
    return [float(value) for value in output], {
        "seconds": round(seconds, 4),
        "examples_per_second": round(len(output) / seconds, 4),
        "examples": len(output),
    }


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
                "sha256": _file_sha256(file),
            }
        )
    return rows


def _dataset_record(path: Path, examples: int) -> dict[str, Any]:
    return {"path": str(path), "sha256": _file_sha256(path), "examples": examples}


def train_v5(
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
        raise V5TrainingError("epochs and batch size must be positive.")
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
    torch.set_num_threads(min(4, os.cpu_count() or 1))
    source_artifact = verify_source_artifact(base_model_path)

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
        raise V5TrainingError("A required training or development partition is empty.")
    if any(row.get("split") != "training" for row in training):
        raise V5TrainingError("The v5 training artifact contains non-training rows.")
    if any(row.get("split") != "development" for row in contract_development):
        raise V5TrainingError("Contract evaluation must be development-only.")

    _seed_all(torch)
    tokenizer = AutoTokenizer.from_pretrained(str(base_model_path), local_files_only=True)
    separator = str(tokenizer.sep_token or "[SEP]")
    model = AutoModelForSequenceClassification.from_pretrained(
        str(base_model_path), local_files_only=True, dtype=torch.float32
    )
    if int(model.config.num_labels) != 3:
        raise V5TrainingError("The v5 source model must retain its three-way head.")
    relation_ids = resolve_relation_ids(model.config)
    train_dataset = EncodedRelations(
        training,
        tokenizer=tokenizer,
        separator=separator,
        relation_ids=relation_ids,
    )
    contract_dataset = _BinaryEncodedExamples(
        contract_development, tokenizer=tokenizer, separator=separator
    )
    wice_dataset = _BinaryEncodedExamples(
        wice_development, tokenizer=tokenizer, separator=separator
    )
    generator = torch.Generator().manual_seed(SEED)
    train_loader = DataLoader(
        train_dataset, batch_size=batch_size, shuffle=True, generator=generator
    )
    contract_loader = DataLoader(contract_dataset, batch_size=batch_size, shuffle=False)
    wice_loader = DataLoader(wice_dataset, batch_size=batch_size, shuffle=False)
    trainable = _freeze_for_transfer(model)
    total_parameters = sum(parameter.numel() for parameter in model.parameters())
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
        contract_probabilities, contract_latency = _predict_entailment(
            model,
            contract_loader,
            entailment_id=relation_ids["entailment"],
            torch=torch,
        )
        wice_probabilities, wice_latency = _predict_entailment(
            model,
            wice_loader,
            entailment_id=relation_ids["entailment"],
            torch=torch,
        )
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
            "cpu_inference": {
                "contract_development": contract_latency,
                "wice_internal": wice_latency,
            },
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
    _print_result(baseline)

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
                [parameter for parameter in model.parameters() if parameter.requires_grad],
                1.0,
            )
            optimizer.step()
            losses.append(float(loss.detach()))
            if step % 25 == 0 or step == len(train_loader):
                print(
                    "epoch %d/%d step %d/%d loss %.4f"
                    % (epoch, epochs, step, len(train_loader), statistics.fmean(losses[-25:])),
                    flush=True,
                )
        record = evaluate(epoch, statistics.fmean(losses), time.perf_counter() - started)
        evaluations.append(record)
        key = _selection_key(record)
        if key > best_key:
            best_key = key
            best_epoch = epoch
            model.save_pretrained(output, safe_serialization=True)
            tokenizer.save_pretrained(output)
        _print_result(record)

    if best_epoch is None:
        raise V5TrainingError("No v5 checkpoint was selected.")
    best = next(row for row in evaluations if row["epoch"] == best_epoch)
    selected = best["dual_threshold_policy"]["selected"]
    artifact_files = _directory_manifest(output)
    artifact_id = _manifest_hash(artifact_files)
    artifact_bytes = sum(int(row["bytes"]) for row in artifact_files)
    report = {
        "schema_version": "contexttrace-requirement-v5-training-report-1.0",
        "datasets": {
            "training": _dataset_record(training_path, len(training)),
            "contract_development": _dataset_record(contract_path, len(contract_development)),
            "wice_internal_source": _dataset_record(wice_path, len(wice_examples)),
            "wice_internal_cases": len(wice_development),
        },
        "base_model": {
            **source_artifact,
            "path_name": Path(base_model_path).name,
            "native_relation_ids": relation_ids,
            "local_files_only": True,
        },
        "training": {
            "epochs": epochs,
            "batch_size": batch_size,
            "learning_rate": learning_rate,
            "max_length": MAX_LENGTH,
            "random_seed": SEED,
            "device": "cpu",
            "loaded_dtype": str(next(model.parameters()).dtype),
            "trainable_scope": "last_two_encoder_layers_pooler_and_three_way_classifier",
            "trainable_parameters": trainable,
            "total_parameters": total_parameters,
            "relation_counts_by_id": {str(key): value for key, value in sorted(counts.items())},
            "class_weights_by_id": [round(float(value), 6) for value in class_weights],
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
            "cpu_inference": best["cpu_inference"],
            "next_step": (
                "freeze_model_and_prepare_untouched_confirmation"
                if selected["promotion_gates_met"]
                else "stop_encoder_finetuning_and_investigate_new_verifier_family"
            ),
        },
        "artifact": {
            "model_id": artifact_id,
            "output_path_name": output.name,
            "bytes": artifact_bytes,
            "files": artifact_files,
        },
        "stable_defaults_changed": False,
        "remote_inference_used": False,
        "jev_labels_used": False,
        "contract_test_split_accessed": False,
    }
    manifest = {
        "schema_version": "contexttrace-requirement-alignment-model-manifest-v5-1.0",
        "model_id": artifact_id,
        "source_repository": SOURCE_REPOSITORY,
        "source_revision": SOURCE_REVISION,
        "source_license": SOURCE_LICENSE,
        "selected_epoch": best_epoch,
        "selected_threshold": selected["threshold"],
        "relation_ids": relation_ids,
        "bytes": artifact_bytes,
        "files": artifact_files,
        "promotion_gates_met": selected["promotion_gates_met"],
        "stable_defaults_changed": False,
        "runtime_network_required": False,
    }
    return report, manifest


def _print_result(record: dict[str, Any]) -> None:
    selected = record["dual_threshold_policy"]["selected"]
    print(
        "epoch %d: contract recall %.4f FPR %.4f; WiCE recall %.4f FPR %.4f; gates %s"
        % (
            record["epoch"],
            selected["contract_development"]["positive_recall"],
            selected["contract_development"]["false_positive_rate"],
            selected["wice_internal"]["positive_recall"],
            selected["wice_internal"]["false_positive_rate"],
            selected["promotion_gates_met"],
        ),
        flush=True,
    )


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
    report, manifest = train_v5(
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
