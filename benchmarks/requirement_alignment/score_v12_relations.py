"""Score V12 claim evidence with the selected local V11 relation model."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any

from benchmarks.requirement_alignment.train import MAX_LENGTH
from benchmarks.requirement_alignment.train_v5 import resolve_relation_ids


ALLOWED_SPLITS = (
    "climate_fever_v12_conflict_training",
    "climate_fever_v10_development",
)


class V12ScoringError(RuntimeError):
    """Raised when V12 local relation scoring violates its artifact contract."""


class _EncodedPairs:
    def __init__(self, pairs: list[tuple[str, str]], tokenizer: Any) -> None:
        evidence, claims = zip(*pairs, strict=True)
        self.values = tokenizer(
            list(evidence),
            list(claims),
            max_length=MAX_LENGTH,
            padding="max_length",
            truncation="only_first",
            return_tensors="pt",
        )

    def __len__(self) -> int:
        return int(self.values["input_ids"].shape[0])

    def __getitem__(self, index: int) -> dict[str, Any]:
        return {key: value[index] for key, value in self.values.items()}


def score_relations(
    dataset_path: str | Path,
    *,
    expected_split: str,
    model_path: str | Path,
    model_manifest_path: str | Path,
    batch_size: int = 16,
) -> dict[str, Any]:
    import torch
    from torch.utils.data import DataLoader
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    if expected_split not in ALLOWED_SPLITS or batch_size < 1:
        raise V12ScoringError("V12 split or batch size is invalid.")
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
    torch.set_num_threads(min(4, os.cpu_count() or 1))
    dataset = json.loads(Path(dataset_path).read_text(encoding="utf-8"))
    examples = list(dataset.get("examples") or [])
    if dataset.get("split") != expected_split or not examples:
        raise V12ScoringError("Dataset is empty or does not match its split.")
    if any({"label", "target", "relation"} & set(row["input"]) for row in examples):
        raise V12ScoringError("Evaluation labels must not appear in model inputs.")
    artifact = _verify_artifact(Path(model_path), Path(model_manifest_path))
    tokenizer = AutoTokenizer.from_pretrained(str(model_path), local_files_only=True)
    model = AutoModelForSequenceClassification.from_pretrained(
        str(model_path), local_files_only=True, dtype=torch.float32
    )
    relation_ids = resolve_relation_ids(model.config)
    pairs = []
    locations = []
    for case_index, example in enumerate(examples):
        claim = str(example["input"]["claim"])
        for evidence_index, evidence in enumerate(example["input"]["evidence"]):
            pairs.append((str(evidence["text"]), claim))
            locations.append((case_index, evidence_index))
    loader = DataLoader(
        _EncodedPairs(pairs, tokenizer), batch_size=batch_size, shuffle=False
    )
    model.eval()
    probabilities = []
    started = time.perf_counter()
    with torch.no_grad():
        for batch in loader:
            probabilities.extend(torch.softmax(model(**batch).logits, dim=-1).tolist())
    seconds = time.perf_counter() - started
    grouped: list[list[dict[str, Any]]] = [[] for _ in examples]
    for (case_index, evidence_index), values in zip(
        locations, probabilities, strict=True
    ):
        evidence = examples[case_index]["input"]["evidence"][evidence_index]
        grouped[case_index].append(
            {
                "evidence_id": str(evidence["id"]),
                "evidence_sha256": hashlib.sha256(
                    str(evidence["text"]).encode("utf-8")
                ).hexdigest(),
                "probabilities": {
                    relation: float(values[index])
                    for relation, index in relation_ids.items()
                },
            }
        )
    rows = [
        {
            "case_id": str(example["id"]),
            "input_sha256": _sha256_json(example["input"]),
            "per_evidence": grouped[index],
        }
        for index, example in enumerate(examples)
    ]
    return {
        "schema_version": "contexttrace-v12-local-relation-scores-1.0",
        "experiment": "contexttrace_v12_conflict_ranking",
        "split": expected_split,
        "dataset_sha256": _sha256_json(dataset),
        "cases": len(rows),
        "evidence_spans": len(probabilities),
        "model": {
            "model_id": artifact["model_id"],
            "manifest_sha256": _sha256_file(Path(model_manifest_path)),
            "relation_ids": relation_ids,
            "artifact_verified": True,
            "local_files_only": True,
        },
        "latency": {
            "seconds": round(seconds, 4),
            "spans_per_second": round(len(probabilities) / seconds, 4),
        },
        "evaluation_labels_sent": False,
        "remote_inference_used": False,
        "stable_defaults_changed": False,
        "rows": rows,
    }


def _verify_artifact(model_path: Path, manifest_path: Path) -> dict[str, Any]:
    if not model_path.is_dir() or not manifest_path.is_file():
        raise V12ScoringError("V11 model artifact or manifest is missing.")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    files = list(manifest.get("files") or [])
    actual = []
    for record in files:
        relative = str(record["path"])
        path = model_path / relative
        if not path.is_file() or _sha256_file(path) != str(record["sha256"]):
            raise V12ScoringError(f"V11 model artifact differs for {relative}.")
        actual.append(
            {
                "path": relative,
                "bytes": path.stat().st_size,
                "sha256": _sha256_file(path),
            }
        )
    if not actual or _sha256_json(actual) != str(manifest.get("model_id")):
        raise V12ScoringError("V11 model artifact ID does not match its files.")
    return manifest


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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--split", required=True, choices=ALLOWED_SPLITS)
    parser.add_argument("--model-path", required=True)
    parser.add_argument("--model-manifest", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--batch-size", type=int, default=16)
    args = parser.parse_args(argv)
    result = score_relations(
        args.dataset,
        expected_split=args.split,
        model_path=args.model_path,
        model_manifest_path=args.model_manifest,
        batch_size=args.batch_size,
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "split": result["split"],
                "cases": result["cases"],
                "evidence_spans": result["evidence_spans"],
                "latency": result["latency"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
