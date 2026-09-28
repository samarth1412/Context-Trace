"""Score atomic claim requirements with the frozen local V11 relation model."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any

from benchmarks.requirement_alignment.score_v12_relations import (
    _sha256_file,
    _sha256_json,
    _verify_artifact,
)
from contexttrace.verify.atomic_coverage import AtomicCoverageJudge
from contexttrace.verify.local_nli import LocalNLIJudge
from contexttrace.verify.schema import TraceContext


DEVELOPMENT_SPLIT = "external_fiveway_v13_development"
CONFIRMATION_SPLIT = "external_fiveway_v19_confirmation"
ALLOWED_SPLITS = {DEVELOPMENT_SPLIT, CONFIRMATION_SPLIT}


class V15ScoringError(RuntimeError):
    """Raised when V15 atomic scoring violates its local-only contract."""


def score_atomic_requirements(
    dataset_path: str | Path,
    *,
    model_path: str | Path,
    model_manifest_path: str | Path,
) -> dict[str, Any]:
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
    try:
        import torch

        torch.set_num_threads(min(4, os.cpu_count() or 1))
    except ImportError:
        pass
    dataset = json.loads(Path(dataset_path).read_text(encoding="utf-8"))
    examples = list(dataset.get("examples") or [])
    split = str(dataset.get("split") or "")
    if split not in ALLOWED_SPLITS or not examples:
        raise V15ScoringError("Atomic scoring accepts only frozen V13/V19 data.")
    if any(
        {"label", "target", "verdict", "dataset"} & set(row["input"])
        for row in examples
    ):
        raise V15ScoringError("Evaluation labels or metadata appear in model inputs.")
    artifact = _verify_artifact(Path(model_path), Path(model_manifest_path))
    nli = LocalNLIJudge(
        model_path=str(model_path),
        tokenizer_path=str(model_path),
        backend="transformers",
        max_length=256,
    )
    judge = AtomicCoverageJudge(nli=nli)
    rows = []
    started = time.perf_counter()
    for example in examples:
        contexts = [
            TraceContext(id=str(row["id"]), text=str(row["text"]))
            for row in example["input"]["evidence"]
        ]
        case_started = time.perf_counter()
        verdict = judge.verify_claim(
            query=str(example["input"].get("query") or ""),
            claim=str(example["input"]["claim"]),
            contexts=contexts,
        )
        requirements = list(verdict.raw["requirements"])
        rows.append(
            {
                "case_id": str(example["id"]),
                "input_sha256": _sha256_json(example["input"]),
                "latency_ms": round((time.perf_counter() - case_started) * 1000.0, 3),
                "atomic_verdict": verdict.verdict,
                "atomic_confidence": verdict.confidence,
                "reason_code": verdict.raw["reason_code"],
                "coverage_summary": dict(verdict.raw["coverage_summary"]),
                "requirements": [
                    {
                        "requirement_sha256": hashlib.sha256(
                            str(requirement["requirement"]).encode("utf-8")
                        ).hexdigest(),
                        "status": str(requirement["status"]),
                        "confidence": float(requirement["confidence"]),
                        "evidence_context_ids": list(
                            requirement["evidence_context_ids"]
                        ),
                        "evidence_text_sha256": [
                            hashlib.sha256(str(text).encode("utf-8")).hexdigest()
                            for text in requirement["evidence_texts"]
                        ],
                        "nli_scores": {
                            relation: float(value)
                            for relation, value in requirement["nli_scores"].items()
                        },
                        "nli_label": str(requirement["nli_label"]),
                    }
                    for requirement in requirements
                ],
            }
        )
    seconds = time.perf_counter() - started
    requirement_count = sum(len(row["requirements"]) for row in rows)
    return {
        "schema_version": "contexttrace-v15-atomic-scores-1.0",
        "experiment": (
            "contexttrace_v19_untouched_confirmation"
            if split == CONFIRMATION_SPLIT
            else "contexttrace_v15_atomic_completeness"
        ),
        "split": split,
        "dataset_sha256": _sha256_json(dataset),
        "cases": len(rows),
        "requirements": requirement_count,
        "model": {
            "model_id": artifact["model_id"],
            "manifest_sha256": _sha256_file(Path(model_manifest_path)),
            "artifact_verified": True,
            "local_files_only": True,
        },
        "latency": {
            "seconds": round(seconds, 4),
            "requirements_per_second": round(requirement_count / seconds, 4),
        },
        "input_contract": {
            "selected_evidence_only": True,
            "evaluation_labels_sent": False,
            "requirement_and_evidence_text_committed": False,
        },
        "remote_inference_used": False,
        "stable_defaults_changed": False,
        "rows": rows,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--model-path", required=True)
    parser.add_argument("--model-manifest", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    result = score_atomic_requirements(
        args.dataset,
        model_path=args.model_path,
        model_manifest_path=args.model_manifest,
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "cases": result["cases"],
                "requirements": result["requirements"],
                "latency": result["latency"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
