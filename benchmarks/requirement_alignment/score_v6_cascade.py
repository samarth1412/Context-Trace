"""Export aligned v3/v5 probabilities for the v6 cascade without remote calls."""

from __future__ import annotations

import argparse
import gc
import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any

from benchmarks.requirement_alignment.train import MAX_LENGTH
from benchmarks.requirement_alignment.train import input_pair
from benchmarks.requirement_alignment.train_v2 import verify_source_model
from benchmarks.requirement_alignment.train_v5 import resolve_relation_ids


class V6ScoringError(RuntimeError):
    """Raised when local v6 scoring violates its artifact or input contract."""


class EncodedInputs:
    def __init__(self, examples: list[dict[str, Any]], *, tokenizer: Any) -> None:
        separator = str(tokenizer.sep_token or "[SEP]")
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

    def __len__(self) -> int:
        return int(self.encodings["input_ids"].shape[0])

    def __getitem__(self, index: int) -> dict[str, Any]:
        return {key: value[index] for key, value in self.encodings.items()}


def score_local_models(
    dataset_path: str | Path,
    *,
    expected_split: str,
    v3_model_path: str | Path,
    v3_manifest_path: str | Path,
    v5_model_path: str | Path,
    v5_manifest_path: str | Path,
    batch_size: int = 8,
) -> dict[str, Any]:
    import torch
    from torch.utils.data import DataLoader
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    if batch_size < 1:
        raise V6ScoringError("batch_size must be positive.")
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
    torch.set_num_threads(min(4, os.cpu_count() or 1))
    dataset_file = Path(dataset_path)
    payload = json.loads(dataset_file.read_text(encoding="utf-8"))
    examples = list(payload.get("examples") or [])
    if not examples or any(row.get("split") != expected_split for row in examples):
        raise V6ScoringError("Dataset is empty or does not match the expected split.")
    if any(
        any(key in row["input"] for key in ("label", "target", "relation"))
        for row in examples
    ):
        raise V6ScoringError("Evaluation labels must not appear in model inputs.")

    model_specs = (
        ("v3", Path(v3_model_path), Path(v3_manifest_path)),
        ("v5", Path(v5_model_path), Path(v5_manifest_path)),
    )
    predictions_by_model: dict[str, list[dict[str, Any]]] = {}
    model_records: dict[str, dict[str, Any]] = {}
    for name, model_path, manifest_path in model_specs:
        artifact = verify_source_model(model_path, manifest_path)
        tokenizer = AutoTokenizer.from_pretrained(str(model_path), local_files_only=True)
        dataset = EncodedInputs(examples, tokenizer=tokenizer)
        loader = DataLoader(dataset, batch_size=batch_size, shuffle=False)
        model = AutoModelForSequenceClassification.from_pretrained(
            str(model_path), local_files_only=True, dtype=torch.float32
        )
        relation_ids = resolve_relation_ids(model.config)
        model.eval()
        output = []
        started = time.perf_counter()
        with torch.no_grad():
            for batch in loader:
                probabilities = torch.softmax(model(**batch).logits, dim=-1).tolist()
                for values in probabilities:
                    relation_probabilities = {
                        relation: float(values[index])
                        for relation, index in relation_ids.items()
                    }
                    output.append(
                        {
                            "entailment_probability": relation_probabilities["entailment"],
                            "probabilities": relation_probabilities,
                        }
                    )
        seconds = time.perf_counter() - started
        if len(output) != len(examples):
            raise V6ScoringError("Local model output count does not match inputs.")
        predictions_by_model[name] = output
        model_records[name] = {
            "model_id": artifact["model_id"],
            "manifest_sha256": _sha256(manifest_path),
            "relation_ids": relation_ids,
            "artifact_verified": True,
            "local_files_only": True,
            "latency": {
                "seconds": round(seconds, 4),
                "examples": len(output),
                "examples_per_second": round(len(output) / seconds, 4),
            },
        }
        del model, loader, dataset, tokenizer
        gc.collect()

    rows = []
    for index, example in enumerate(examples):
        model_input = {
            "claim": example["input"]["claim"],
            "requirement": example["input"].get("requirement"),
            "evidence": example["input"]["evidence"],
        }
        rows.append(
            {
                "case_id": example["id"],
                "split": expected_split,
                "input_audit": {
                    "state_sha256": _sha256_json(model_input),
                    "evidence": [
                        {
                            "id": item["id"],
                            "sha256": hashlib.sha256(
                                str(item["text"]).encode("utf-8")
                            ).hexdigest(),
                            "characters": len(str(item["text"])),
                        }
                        for item in example["input"]["evidence"]
                    ],
                    "evaluation_label_sent": False,
                },
                "predictions": {
                    name: predictions_by_model[name][index]
                    for name in ("v3", "v5")
                },
            }
        )
    return {
        "schema_version": "contexttrace-requirement-v6-local-scores-1.0",
        "experiment": "contexttrace_v6_uncertainty_cascade",
        "split": expected_split,
        "dataset_sha256": _sha256(dataset_file),
        "cases": len(rows),
        "models": model_records,
        "stable_defaults_changed": False,
        "remote_inference_used": False,
        "contractnli_test_accessed": False,
        "rows": rows,
    }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _sha256_json(value: object) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", required=True)
    parser.add_argument(
        "--split", required=True, choices=("cascade_calibration", "cascade_evaluation")
    )
    parser.add_argument("--v3-model-path", required=True)
    parser.add_argument("--v3-manifest", required=True)
    parser.add_argument("--v5-model-path", required=True)
    parser.add_argument("--v5-manifest", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--batch-size", type=int, default=8)
    args = parser.parse_args(argv)
    result = score_local_models(
        args.dataset,
        expected_split=args.split,
        v3_model_path=args.v3_model_path,
        v3_manifest_path=args.v3_manifest,
        v5_model_path=args.v5_model_path,
        v5_manifest_path=args.v5_manifest,
        batch_size=args.batch_size,
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"cases": result["cases"], "models": result["models"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
