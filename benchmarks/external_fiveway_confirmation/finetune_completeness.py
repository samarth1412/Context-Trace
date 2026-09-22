"""Fine-tune and run a local MiniLM complete-support classifier."""

from __future__ import annotations

import argparse
import hashlib
import json
import random
from collections import Counter
from pathlib import Path
from typing import Any

from benchmarks.external_fiveway_confirmation.adapter import _wice_cases
from benchmarks.external_fiveway_confirmation.local_completeness import (
    ENCODER_ID,
    ENCODER_REVISION,
    TRAIN_SHA256,
)
from benchmarks.jev_v2_verification.run import shared_input


RANDOM_SEED = 20260923
MAX_LENGTH = 512
LABEL_TO_ID = {"partially_supported": 0, "supported": 1}


class FineTuneError(RuntimeError):
    """Raised when local fine-tuning or scoring cannot be reproduced."""


def train(
    source_path: str | Path,
    *,
    base_model_path: str | Path,
    output_dir: str | Path,
    epochs: int = 4,
    batch_size: int = 8,
) -> dict[str, Any]:
    import numpy as np
    import torch
    from sklearn.metrics import accuracy_score, average_precision_score, roc_auc_score
    from torch.utils.data import DataLoader
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    _seed_all(torch)
    source = Path(source_path)
    source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    if source_hash != TRAIN_SHA256:
        raise FineTuneError("WiCE training source hash does not match the pinned file.")
    cases = [
        case
        for case in _wice_cases(source)
        if case["expected_verdict"] in LABEL_TO_ID and shared_input(case)[0]
    ]
    training, validation = _stratified_split(cases, validation_fraction=0.15)
    tokenizer = AutoTokenizer.from_pretrained(str(base_model_path), local_files_only=True)
    model = AutoModelForSequenceClassification.from_pretrained(
        str(base_model_path),
        num_labels=2,
        id2label={0: "partially_supported", 1: "supported"},
        label2id=LABEL_TO_ID,
        local_files_only=True,
        ignore_mismatched_sizes=True,
    )
    train_dataset = _EncodedDataset(training, tokenizer=tokenizer)
    validation_dataset = _EncodedDataset(validation, tokenizer=tokenizer)
    generator = torch.Generator().manual_seed(RANDOM_SEED)
    train_loader = DataLoader(
        train_dataset,
        batch_size=batch_size,
        shuffle=True,
        generator=generator,
    )
    validation_loader = DataLoader(validation_dataset, batch_size=batch_size, shuffle=False)
    counts = Counter(LABEL_TO_ID[case["expected_verdict"]] for case in training)
    weights = torch.tensor(
        [len(training) / (2 * counts[index]) for index in range(2)], dtype=torch.float32
    )
    loss_function = torch.nn.CrossEntropyLoss(weight=weights)
    optimizer = torch.optim.AdamW(model.parameters(), lr=2e-5, weight_decay=0.01)
    best_state = None
    best_auc = -1.0
    history = []
    for epoch in range(1, epochs + 1):
        model.train()
        losses = []
        for batch in train_loader:
            labels = batch.pop("labels")
            optimizer.zero_grad(set_to_none=True)
            logits = model(**batch).logits
            loss = loss_function(logits, labels)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            losses.append(float(loss.detach()))
        probabilities, targets = _predict(model, validation_loader, torch=torch)
        auc = float(roc_auc_score(targets, probabilities))
        record = {
            "epoch": epoch,
            "train_loss": round(sum(losses) / len(losses), 6),
            "validation_roc_auc": round(auc, 4),
            "validation_average_precision": round(
                float(average_precision_score(targets, probabilities)), 4
            ),
            "validation_accuracy_at_0_5": round(
                float(accuracy_score(targets, np.asarray(probabilities) >= 0.5)), 4
            ),
        }
        history.append(record)
        if auc > best_auc:
            best_auc = auc
            best_state = {
                key: value.detach().cpu().clone() for key, value in model.state_dict().items()
            }
    if best_state is None:
        raise FineTuneError("Fine-tuning produced no model state.")
    model.load_state_dict(best_state)
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(output, safe_serialization=True)
    tokenizer.save_pretrained(output)
    manifest = _directory_manifest(output)
    model_id = hashlib.sha256(
        json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    metadata = {
        "schema_version": "local-completeness-finetune-1.0",
        "model_id": model_id,
        "base_encoder": {"id": ENCODER_ID, "revision": ENCODER_REVISION},
        "training_source": {
            "dataset": "WiCE",
            "split": "train",
            "sha256": source_hash,
            "train_cases": len(training),
            "internal_validation_cases": len(validation),
        },
        "training": {
            "epochs_requested": epochs,
            "best_epoch": max(history, key=lambda row: row["validation_roc_auc"])["epoch"],
            "batch_size": batch_size,
            "learning_rate": 2e-5,
            "weight_decay": 0.01,
            "max_length": MAX_LENGTH,
            "random_seed": RANDOM_SEED,
            "device": "cpu",
        },
        "history": history,
        "files": manifest,
        "stable_defaults_changed": False,
        "runtime_network_required": False,
    }
    (output / "contexttrace_completeness.json").write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return metadata


def augment_result(
    result: dict[str, Any],
    *,
    model_path: str | Path,
    batch_size: int = 8,
) -> dict[str, Any]:
    import torch
    from torch.utils.data import DataLoader
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    path = Path(model_path)
    metadata = json.loads((path / "contexttrace_completeness.json").read_text(encoding="utf-8"))
    tokenizer = AutoTokenizer.from_pretrained(path, local_files_only=True)
    model = AutoModelForSequenceClassification.from_pretrained(path, local_files_only=True)
    rows = json.loads(json.dumps(result.get("rows") or []))
    inputs = [row["input_audit"]["exact_shared_input"] for row in rows]
    dataset = _EncodedInputs(inputs, tokenizer=tokenizer)
    loader = DataLoader(dataset, batch_size=batch_size, shuffle=False)
    probabilities, _ = _predict(model, loader, torch=torch, has_labels=False)
    for row, probability in zip(rows, probabilities, strict=True):
        row["signals"]["local_support_probability"] = round(float(probability), 8)
        row["signals"]["local_support_model_id"] = metadata["model_id"]
    return {
        **{key: value for key, value in result.items() if key != "rows"},
        "schema_version": "jev-finetuned-completeness-signals-1.0",
        "local_support_model_id": metadata["model_id"],
        "local_runtime_network_used": False,
        "rows": rows,
    }


def _stratified_split(
    cases: list[dict[str, Any]], *, validation_fraction: float
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = {label: [] for label in LABEL_TO_ID}
    for case in cases:
        groups[str(case["expected_verdict"])].append(case)
    training = []
    validation = []
    for label, rows in groups.items():
        ordered = sorted(
            rows,
            key=lambda row: hashlib.sha256(
                ("%s:%s:%s" % (RANDOM_SEED, label, row["id"])).encode("utf-8")
            ).hexdigest(),
        )
        count = max(1, round(len(ordered) * validation_fraction))
        validation.extend(ordered[:count])
        training.extend(ordered[count:])
    return training, validation


def _input_pair(value: dict[str, Any]) -> tuple[str, str]:
    claim = str(value["claim"])
    evidence = " [SEP] ".join(str(item["text"]) for item in value["selected_evidence"])
    return claim, evidence


class _EncodedInputs:
    def __init__(self, inputs: list[dict[str, Any]], *, tokenizer: object) -> None:
        claims, evidence = zip(*(_input_pair(value) for value in inputs), strict=True)
        self.encodings = tokenizer(  # type: ignore[operator]
            list(claims),
            list(evidence),
            max_length=MAX_LENGTH,
            padding=True,
            truncation="only_second",
            return_tensors="pt",
        )

    def __len__(self) -> int:
        return int(self.encodings["input_ids"].shape[0])

    def __getitem__(self, index: int) -> dict[str, Any]:
        return {key: value[index] for key, value in self.encodings.items()}


class _EncodedDataset(_EncodedInputs):
    def __init__(self, cases: list[dict[str, Any]], *, tokenizer: object) -> None:
        inputs = []
        self.labels = []
        for case in cases:
            contexts, _ = shared_input(case)
            inputs.append(
                {
                    "claim": case["claim"],
                    "selected_evidence": [
                        {"id": value.id, "text": value.text} for value in contexts
                    ],
                }
            )
            self.labels.append(LABEL_TO_ID[str(case["expected_verdict"])])
        super().__init__(inputs, tokenizer=tokenizer)

    def __getitem__(self, index: int) -> dict[str, Any]:
        item = super().__getitem__(index)
        item["labels"] = self.labels[index]
        return item


def _predict(
    model: object,
    loader: object,
    *,
    torch: Any,
    has_labels: bool = True,
) -> tuple[list[float], list[int]]:
    model.eval()  # type: ignore[attr-defined]
    probabilities = []
    targets = []
    with torch.no_grad():
        for batch in loader:  # type: ignore[union-attr]
            if has_labels:
                targets.extend(int(value) for value in batch.pop("labels"))
            logits = model(**batch).logits  # type: ignore[operator]
            probabilities.extend(float(value) for value in torch.softmax(logits, dim=-1)[:, 1])
    return probabilities, targets


def _seed_all(torch: Any) -> None:
    random.seed(RANDOM_SEED)
    torch.manual_seed(RANDOM_SEED)
    torch.use_deterministic_algorithms(True)


def _directory_manifest(path: Path) -> list[dict[str, Any]]:
    return [
        {
            "path": str(file.relative_to(path)),
            "bytes": file.stat().st_size,
            "sha256": hashlib.sha256(file.read_bytes()).hexdigest(),
        }
        for file in sorted(path.rglob("*"))
        if file.is_file() and file.name != "contexttrace_completeness.json"
    ]


def _write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    train_parser = subparsers.add_parser("train")
    train_parser.add_argument("--train-source", required=True)
    train_parser.add_argument("--base-model", required=True)
    train_parser.add_argument("--output-dir", required=True)
    train_parser.add_argument("--report-output", required=True)
    train_parser.add_argument("--epochs", type=int, default=4)
    train_parser.add_argument("--batch-size", type=int, default=8)
    augment_parser = subparsers.add_parser("augment")
    augment_parser.add_argument("--result", required=True)
    augment_parser.add_argument("--model", required=True)
    augment_parser.add_argument("--output", required=True)
    augment_parser.add_argument("--batch-size", type=int, default=8)
    args = parser.parse_args(argv)
    if args.command == "train":
        report = train(
            args.train_source,
            base_model_path=args.base_model,
            output_dir=args.output_dir,
            epochs=args.epochs,
            batch_size=args.batch_size,
        )
        _write(Path(args.report_output), report)
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        result = json.loads(Path(args.result).read_text(encoding="utf-8"))
        augmented = augment_result(result, model_path=args.model, batch_size=args.batch_size)
        _write(Path(args.output), augmented)
        print(
            json.dumps(
                {
                    "cases": len(augmented["rows"]),
                    "model_id": augmented["local_support_model_id"],
                },
                indent=2,
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
