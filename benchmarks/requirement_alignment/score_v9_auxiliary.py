"""Score V9 development inputs with local span and pinned-NLI models only."""

from __future__ import annotations

import argparse
import gc
import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any

from benchmarks.requirement_alignment.train import MAX_LENGTH, input_pair
from benchmarks.requirement_alignment.train_v2 import verify_source_model
from benchmarks.requirement_alignment.train_v5 import resolve_relation_ids
from contexttrace.verify.semantic_core_v2.constants import (
    NLI_ARTIFACT_MANIFEST_SHA256,
    NLI_MODEL_ID,
    NLI_MODEL_REVISION,
)
from contexttrace.verify.semantic_core_v2.nli import verify_nli_artifact


SPLIT = "scifact_development"
LABELS = ("entailment", "contradiction", "neutral")


class V9AuxiliaryScoringError(RuntimeError):
    """Raised when local-only auxiliary scoring cannot be reproduced."""


def score_auxiliary(
    dataset_path: str | Path,
    *,
    v3_model_path: str | Path,
    v3_manifest_path: str | Path,
    v5_model_path: str | Path,
    v5_manifest_path: str | Path,
    pinned_nli_path: str | Path,
    batch_size: int = 16,
) -> dict[str, Any]:
    if batch_size < 1:
        raise V9AuxiliaryScoringError("batch_size must be positive.")
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
    source = Path(dataset_path)
    payload = json.loads(source.read_text(encoding="utf-8"))
    examples = list(payload.get("examples") or [])
    if payload.get("split") != SPLIT or not examples:
        raise V9AuxiliaryScoringError("Expected a non-empty SciFact development set.")
    if any(
        any(key in row["input"] for key in ("label", "target", "relation"))
        for row in examples
    ):
        raise V9AuxiliaryScoringError(
            "Evaluation labels must not appear in model inputs."
        )
    spans = _explode(examples)
    v3_predictions, v3_record = _score_alignment_spans(
        spans, Path(v3_model_path), Path(v3_manifest_path), batch_size=batch_size
    )
    v5_predictions, v5_record = _score_alignment_spans(
        spans, Path(v5_model_path), Path(v5_manifest_path), batch_size=batch_size
    )
    pinned_group, pinned_span, pinned_record = _score_pinned_nli(
        examples, spans, Path(pinned_nli_path), batch_size=batch_size
    )
    v3_map = dict(zip((row["span_id"] for row in spans), v3_predictions, strict=True))
    v5_map = dict(zip((row["span_id"] for row in spans), v5_predictions, strict=True))
    pinned_span_map = dict(
        zip((row["span_id"] for row in spans), pinned_span, strict=True)
    )
    pinned_group_map = dict(
        zip((row["id"] for row in examples), pinned_group, strict=True)
    )
    rows = []
    for example in examples:
        case_id = str(example["id"])
        per_evidence = []
        for index, evidence in enumerate(example["input"]["evidence"]):
            span_id = f"{case_id}::evidence::{index}"
            per_evidence.append(
                {
                    "evidence_id": str(evidence["id"]),
                    "evidence_sha256": hashlib.sha256(
                        str(evidence["text"]).encode("utf-8")
                    ).hexdigest(),
                    "v3": v3_map[span_id],
                    "v5": v5_map[span_id],
                    "pinned_nli": pinned_span_map[span_id],
                }
            )
        rows.append(
            {
                "case_id": case_id,
                "input_sha256": _sha256_json(example["input"]),
                "pinned_nli_group": pinned_group_map[case_id],
                "per_evidence": per_evidence,
            }
        )
    return {
        "schema_version": "contexttrace-v9-auxiliary-scores-1.0",
        "experiment": "contexttrace_v9_local_meta_router",
        "split": SPLIT,
        "dataset_sha256": _sha256_file(source),
        "cases": len(rows),
        "evaluation_split_accessed": False,
        "evaluation_labels_sent": False,
        "remote_inference_used": False,
        "stable_defaults_changed": False,
        "models": {"v3": v3_record, "v5": v5_record, "pinned_nli": pinned_record},
        "rows": rows,
    }


def _explode(examples: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for example in examples:
        for index, evidence in enumerate(example["input"]["evidence"]):
            rows.append(
                {
                    "span_id": f"{example['id']}::evidence::{index}",
                    "claim": str(example["input"]["claim"]),
                    "requirement": dict(example["input"]["requirement"]),
                    "evidence": dict(evidence),
                }
            )
    return rows


def _score_alignment_spans(
    spans: list[dict[str, Any]],
    model_path: Path,
    manifest_path: Path,
    *,
    batch_size: int,
) -> tuple[list[dict[str, float]], dict[str, Any]]:
    artifact = verify_source_model(model_path, manifest_path)
    examples = [
        {
            "input": {
                "claim": row["claim"],
                "requirement": row["requirement"],
                "evidence": [row["evidence"]],
            }
        }
        for row in spans
    ]
    predictions, relation_ids, latency = _score_model(
        examples, model_path, raw_claim=False, batch_size=batch_size
    )
    return predictions, {
        "model_id": artifact["model_id"],
        "manifest_sha256": _sha256_file(manifest_path),
        "relation_ids": relation_ids,
        "artifact_verified": True,
        "local_files_only": True,
        "latency": latency,
    }


def _score_pinned_nli(
    examples: list[dict[str, Any]],
    spans: list[dict[str, Any]],
    model_path: Path,
    *,
    batch_size: int,
) -> tuple[list[dict[str, float]], list[dict[str, float]], dict[str, Any]]:
    artifact = verify_nli_artifact(model_path)
    span_examples = [
        {
            "input": {
                "claim": row["claim"],
                "requirement": row["requirement"],
                "evidence": [row["evidence"]],
            }
        }
        for row in spans
    ]
    group, relation_ids, group_latency = _score_model(
        examples, model_path, raw_claim=True, batch_size=batch_size
    )
    per_span, span_relation_ids, span_latency = _score_model(
        span_examples, model_path, raw_claim=True, batch_size=batch_size
    )
    if relation_ids != span_relation_ids:
        raise V9AuxiliaryScoringError(
            "Pinned NLI relation mapping changed between runs."
        )
    if artifact["artifact_manifest_sha256"] != NLI_ARTIFACT_MANIFEST_SHA256:
        raise V9AuxiliaryScoringError(
            "Pinned NLI manifest does not match the frozen lock."
        )
    return (
        group,
        per_span,
        {
            "model_id": NLI_MODEL_ID,
            "model_revision": NLI_MODEL_REVISION,
            "artifact_manifest_sha256": artifact["artifact_manifest_sha256"],
            "relation_ids": relation_ids,
            "artifact_verified": True,
            "local_files_only": True,
            "latency": {"group": group_latency, "per_evidence": span_latency},
        },
    )


def _score_model(
    examples: list[dict[str, Any]],
    model_path: Path,
    *,
    raw_claim: bool,
    batch_size: int,
) -> tuple[list[dict[str, float]], dict[str, int], dict[str, Any]]:
    import torch
    from torch.utils.data import DataLoader, Dataset
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    torch.set_num_threads(min(4, os.cpu_count() or 1))
    tokenizer = AutoTokenizer.from_pretrained(str(model_path), local_files_only=True)
    separator = str(tokenizer.sep_token or "[SEP]")
    pairs = []
    for example in examples:
        if raw_claim:
            evidence = (f" {separator} ").join(
                str(row["text"]) for row in example["input"]["evidence"]
            )
            pairs.append((evidence, str(example["input"]["claim"])))
        else:
            pairs.append(input_pair(example, separator=separator))

    class EncodedPairs(Dataset):
        def __init__(self, pair_tokenizer: Any) -> None:
            left, right = zip(*pairs, strict=True)
            self.values = pair_tokenizer(
                list(left),
                list(right),
                max_length=MAX_LENGTH,
                padding="max_length",
                truncation="only_first",
                return_tensors="pt",
            )

        def __len__(self) -> int:
            return int(self.values["input_ids"].shape[0])

        def __getitem__(self, index: int) -> dict[str, Any]:
            return {key: value[index] for key, value in self.values.items()}

    dataset = EncodedPairs(tokenizer)
    loader = DataLoader(dataset, batch_size=batch_size, shuffle=False)
    model = AutoModelForSequenceClassification.from_pretrained(
        str(model_path), local_files_only=True, dtype=torch.float32
    )
    relation_ids = resolve_relation_ids(model.config)
    model.eval()
    output: list[dict[str, float]] = []
    started = time.perf_counter()
    with torch.no_grad():
        for batch in loader:
            probabilities = torch.softmax(model(**batch).logits, dim=-1).tolist()
            output.extend(
                {label: float(row[index]) for label, index in relation_ids.items()}
                for row in probabilities
            )
    seconds = time.perf_counter() - started
    if len(output) != len(examples):
        raise V9AuxiliaryScoringError("Local model output count does not match inputs.")
    del model, loader, dataset, tokenizer
    gc.collect()
    return (
        output,
        relation_ids,
        {
            "seconds": round(seconds, 4),
            "examples": len(output),
            "examples_per_second": round(len(output) / seconds, 4),
        },
    )


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
    parser.add_argument("--v3-model-path", required=True)
    parser.add_argument("--v3-manifest", required=True)
    parser.add_argument("--v5-model-path", required=True)
    parser.add_argument("--v5-manifest", required=True)
    parser.add_argument("--pinned-nli-path", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--batch-size", type=int, default=16)
    args = parser.parse_args(argv)
    result = score_auxiliary(
        args.dataset,
        v3_model_path=args.v3_model_path,
        v3_manifest_path=args.v3_manifest,
        v5_model_path=args.v5_model_path,
        v5_manifest_path=args.v5_manifest,
        pinned_nli_path=args.pinned_nli_path,
        batch_size=args.batch_size,
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps({"cases": result["cases"], "models": result["models"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
