"""Run a pinned, offline MiniCheck comparison over ContextTrace trace rows.

The runner imports the official source tree at a locked Git revision and loads a
pre-downloaded model snapshot whose files are hash checked before inference. It
never downloads a model or calls a provider.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import subprocess
import sys
import time
from collections import Counter
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from benchmarks.contexttrace_bench.adapt_candidate import (
    adapt_candidate_rows,
    write_candidate,
)

HERE = Path(__file__).resolve().parent
DEFAULT_RUNTIME_LOCK = HERE / "competitor-runtime-lock.json"


class MiniCheckAuditError(ValueError):
    """Raised when the source, model, data, or resume payload changed."""


def audit_runtime(
    lock_path: Path,
    source_dir: Path,
    model_dir: Path,
    nltk_data_dir: Path,
) -> dict[str, Any]:
    lock = _minicheck_lock(lock_path)
    source_revision = _git_output(source_dir, "rev-parse", "HEAD")
    if source_revision != lock["source_revision"]:
        raise MiniCheckAuditError(
            f"MiniCheck source revision mismatch: expected "
            f"{lock['source_revision']}, found {source_revision}."
        )
    if _git_output(source_dir, "status", "--porcelain"):
        raise MiniCheckAuditError("MiniCheck source tree must be clean.")

    model_files = _audit_files(
        model_dir,
        _string_map(lock, "model_files"),
        artifact_name="MiniCheck model",
    )
    nltk_files = _audit_files(
        nltk_data_dir,
        _string_map(lock, "nltk_files"),
        artifact_name="NLTK data",
    )
    dependencies = _audit_dependency_versions(lock)
    return {
        "source_url": lock["source_url"],
        "source_revision": source_revision,
        "package_version": lock["package_version"],
        "model_id": lock["model_id"],
        "model_revision": lock["model_revision"],
        "model_artifact_manifest_sha256": _mapping_sha256(model_files),
        "nltk_data_revision": lock["nltk_data_revision"],
        "nltk_artifact_manifest_sha256": _mapping_sha256(nltk_files),
        "configuration": {
            "claim_unit": lock["claim_unit"],
            "document_chunk_size": int(lock["document_chunk_size"]),
            "support_threshold": float(lock["support_threshold"]),
        },
        "dependencies": dependencies,
    }


def project_minicheck_labels(
    claim_labels: list[int], *, dataset: str
) -> tuple[list[str], str]:
    if not claim_labels:
        return ["should_have_abstained"], "should_have_abstained"
    unsupported = sum(label == 0 for label in claim_labels)
    if unsupported == 0:
        return ["no_failure_detected"], "no_failure_detected"

    dataset_key = dataset.lower()
    if dataset_key.startswith("ares"):
        return (
            ["should_have_abstained", "unsupported_answer"],
            "should_have_abstained",
        )
    if dataset_key == "ragtruth":
        label = "unsupported" if unsupported == len(claim_labels) else "partial_support"
        return [label], "answer_overreach"
    return ["unsupported_answer"], "answer_overreach"


def split_answer_claims(answer: str) -> list[str]:
    from minicheck.inference import sent_tokenize_with_newlines

    claims = [part.strip() for part in sent_tokenize_with_newlines(answer)]
    return [claim for claim in claims if claim and claim != "\n"]


def run_minicheck(
    candidate_inputs: list[dict[str, Any]],
    *,
    dataset: str,
    runtime: dict[str, Any],
    source_dir: Path,
    model_dir: Path,
    nltk_data_dir: Path,
    device: str = "auto",
    batch_size: int = 8,
    existing_rows: list[dict[str, Any]] | None = None,
    checkpoint_path: Path | None = None,
) -> dict[str, Any]:
    _activate_source(source_dir, nltk_data_dir)
    resolved_device = _resolve_device(device)
    scorer = _build_offline_scorer(
        model_dir=model_dir,
        device=resolved_device,
        batch_size=batch_size,
    )
    completed = {
        _row_id(row): row
        for row in existing_rows or []
        if not row.get("error") and _row_id(row)
    }
    output_rows: list[dict[str, Any]] = []
    total_started = time.perf_counter()
    for index, input_row in enumerate(candidate_inputs, start=1):
        case_id = _row_id(input_row)
        trace = _trace(input_row)
        old_row = completed.get(case_id)
        if old_row is not None and _row_matches_trace(old_row, trace):
            output_rows.append(old_row)
            continue

        started = time.perf_counter()
        answer = str(trace.get("answer") or "")
        claims = split_answer_claims(answer)
        document = "\n\n".join(
            str(context.get("text") or "") for context in trace.get("contexts") or []
        )
        labels: list[int]
        probabilities: list[float]
        used_chunks: list[list[str]]
        chunk_probabilities: list[list[float]]
        if claims:
            labels_raw, probabilities_raw, used_raw, chunk_probs_raw = scorer.score(
                docs=[document] * len(claims),
                claims=claims,
            )
            labels = [int(value) for value in labels_raw]
            probabilities = [float(value) for value in probabilities_raw]
            used_chunks = [[str(chunk) for chunk in chunks] for chunks in used_raw]
            chunk_probabilities = [
                [float(value) for value in values] for values in chunk_probs_raw
            ]
        else:
            labels, probabilities, used_chunks, chunk_probabilities = [], [], [], []

        predicted, root = project_minicheck_labels(labels, dataset=dataset)
        claim_verdicts = ["supported" if label else "unsupported" for label in labels]
        counts = Counter(claim_verdicts)
        output_rows.append(
            {
                "id": case_id,
                "query": str(trace.get("query") or ""),
                "response": answer,
                "retrieved_context": [
                    {
                        "doc_id": str(context.get("id") or ""),
                        "text": str(context.get("text") or ""),
                    }
                    for context in trace.get("contexts") or []
                ],
                "claims": [
                    {
                        "claim_index": claim_index,
                        "text": claim,
                        "label": label,
                        "support_probability": round(probability, 9),
                        "used_chunk_sha256": [
                            hashlib.sha256(chunk.encode("utf-8")).hexdigest()
                            for chunk in chunks
                        ],
                        "support_probability_per_chunk": [
                            round(value, 9) for value in per_chunk
                        ],
                    }
                    for claim_index, (
                        claim,
                        label,
                        probability,
                        chunks,
                        per_chunk,
                    ) in enumerate(
                        zip(
                            claims,
                            labels,
                            probabilities,
                            used_chunks,
                            chunk_probabilities,
                            strict=True,
                        )
                    )
                ],
                "claim_verdicts": claim_verdicts,
                "verdict_counts": {
                    "supported": counts["supported"],
                    "partially_supported": 0,
                    "unsupported": counts["unsupported"],
                    "contradicted": 0,
                    "unverifiable": 0,
                },
                "predicted_labels": predicted,
                "predicted_primary_root_cause": root,
                "latency_ms": round((time.perf_counter() - started) * 1000, 3),
                "error": None,
            }
        )
        if checkpoint_path is not None:
            _write_raw(
                checkpoint_path,
                _raw_payload(
                    rows=output_rows,
                    dataset=dataset,
                    runtime=runtime,
                    device=resolved_device,
                    elapsed_ms=(time.perf_counter() - total_started) * 1000,
                    complete=index == len(candidate_inputs),
                ),
            )

    return _raw_payload(
        rows=output_rows,
        dataset=dataset,
        runtime=runtime,
        device=resolved_device,
        elapsed_ms=(time.perf_counter() - total_started) * 1000,
        complete=len(output_rows) == len(candidate_inputs),
    )


def _raw_payload(
    *,
    rows: list[dict[str, Any]],
    dataset: str,
    runtime: dict[str, Any],
    device: str,
    elapsed_ms: float,
    complete: bool,
) -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "system": "MiniCheck",
        "version": "0.1.0 / MiniCheck-Flan-T5-Large",
        "dataset": dataset,
        "runtime": {**runtime, "device": device},
        "complete": complete,
        "elapsed_ms": round(elapsed_ms, 3),
        "rows": rows,
    }


def _activate_source(source_dir: Path, nltk_data_dir: Path) -> None:
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    source_text = str(source_dir.resolve())
    if source_text not in sys.path:
        sys.path.insert(0, source_text)
    import nltk

    data_text = str(nltk_data_dir.resolve())
    if data_text not in nltk.data.path:
        nltk.data.path.insert(0, data_text)


def _build_offline_scorer(*, model_dir: Path, device: str, batch_size: int) -> Any:
    from minicheck.minicheck import MiniCheck

    with _redirect_model_load(model_dir):
        scorer = MiniCheck(model_name="flan-t5-large", batch_size=batch_size)
    if device != "cpu":
        scorer.model.model.to(device)
    return scorer


@contextmanager
def _redirect_model_load(model_dir: Path) -> Iterator[None]:
    from minicheck import inference

    model_loader = inference.AutoModelForSeq2SeqLM.from_pretrained
    tokenizer_loader = inference.AutoTokenizer.from_pretrained

    def load_model(model_id: str, **kwargs: Any) -> Any:
        if model_id != "lytang/MiniCheck-Flan-T5-Large":
            raise MiniCheckAuditError(f"Unexpected MiniCheck model ID {model_id}.")
        kwargs.pop("cache_dir", None)
        kwargs.pop("device_map", None)
        return model_loader(str(model_dir), local_files_only=True, **kwargs)

    def load_tokenizer(model_id: str, **kwargs: Any) -> Any:
        if model_id != "lytang/MiniCheck-Flan-T5-Large":
            raise MiniCheckAuditError(f"Unexpected MiniCheck tokenizer ID {model_id}.")
        kwargs.pop("cache_dir", None)
        return tokenizer_loader(str(model_dir), local_files_only=True, **kwargs)

    inference.AutoModelForSeq2SeqLM.from_pretrained = load_model
    inference.AutoTokenizer.from_pretrained = load_tokenizer
    try:
        yield
    finally:
        inference.AutoModelForSeq2SeqLM.from_pretrained = model_loader
        inference.AutoTokenizer.from_pretrained = tokenizer_loader


def _resolve_device(requested: str) -> str:
    import torch

    if requested != "auto":
        if requested == "mps" and not torch.backends.mps.is_available():
            raise MiniCheckAuditError("MPS was requested but is unavailable.")
        if requested == "cuda" and not torch.cuda.is_available():
            raise MiniCheckAuditError("CUDA was requested but is unavailable.")
        return requested
    if torch.cuda.is_available():
        return "cuda"
    if torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def _audit_files(
    root: Path,
    expected: dict[str, str],
    *,
    artifact_name: str,
) -> dict[str, str]:
    actual: dict[str, str] = {}
    for relative, expected_hash in sorted(expected.items()):
        path = (root / relative).resolve()
        if not path.is_relative_to(root.resolve()) or not path.is_file():
            raise MiniCheckAuditError(f"{artifact_name} file is missing: {relative}.")
        actual_hash = _streaming_sha256(path)
        if actual_hash != expected_hash:
            raise MiniCheckAuditError(
                f"{artifact_name} SHA-256 mismatch for {relative}: expected "
                f"{expected_hash}, found {actual_hash}."
            )
        actual[relative] = actual_hash
    return actual


def _streaming_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _mapping_sha256(mapping: dict[str, str]) -> str:
    encoded = json.dumps(mapping, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _git_output(source_dir: Path, *args: str) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(source_dir), *args],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise MiniCheckAuditError("Could not audit MiniCheck source tree.") from exc
    return result.stdout.strip()


def _minicheck_lock(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    lock = payload.get("MiniCheck") if isinstance(payload, dict) else None
    if not isinstance(lock, dict):
        raise MiniCheckAuditError("Runtime lock is missing MiniCheck.")
    for field in (
        "source_url",
        "source_revision",
        "package_version",
        "model_id",
        "model_revision",
        "nltk_data_revision",
        "claim_unit",
        "document_chunk_size",
        "support_threshold",
    ):
        if not str(lock.get(field) or "").strip():
            raise MiniCheckAuditError(f"Runtime lock is missing MiniCheck.{field}.")
    return lock


def _string_map(payload: dict[str, Any], field: str) -> dict[str, str]:
    value = payload.get(field)
    if not isinstance(value, dict) or not value:
        raise MiniCheckAuditError(f"Runtime lock is missing MiniCheck.{field}.")
    return {str(key): str(item) for key, item in value.items()}


def _audit_dependency_versions(lock: dict[str, Any]) -> dict[str, str]:
    expected = _string_map(lock, "dependency_versions")
    actual = {name: importlib.metadata.version(name) for name in expected}
    if actual != expected:
        raise MiniCheckAuditError(
            f"MiniCheck dependency mismatch: expected {expected}, found {actual}."
        )
    return actual


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8-sig").splitlines()
        if line.strip()
    ]
    if not all(isinstance(row, dict) for row in rows):
        raise MiniCheckAuditError("Candidate input JSONL must contain objects.")
    return rows


def _read_existing(
    path: Path | None,
    *,
    expected_runtime: dict[str, Any] | None = None,
    dataset: str | None = None,
) -> list[dict[str, Any]]:
    if path is None or not path.is_file():
        return []
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise MiniCheckAuditError("Resume payload must be an object.")
    if dataset is not None and payload.get("dataset") != dataset:
        raise MiniCheckAuditError("Resume payload dataset changed.")
    runtime = payload.get("runtime")
    if expected_runtime is not None and (
        not isinstance(runtime, dict)
        or any(runtime.get(key) != value for key, value in expected_runtime.items())
    ):
        raise MiniCheckAuditError("Resume payload runtime changed.")
    rows = payload.get("rows")
    if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
        raise MiniCheckAuditError("Resume payload has invalid rows.")
    return rows


def _trace(row: dict[str, Any]) -> dict[str, Any]:
    trace = row.get("trace")
    if not isinstance(trace, dict):
        raise MiniCheckAuditError(f"Candidate row {_row_id(row)} is missing trace.")
    return trace


def _row_id(row: dict[str, Any]) -> str:
    value = row.get("id") or row.get("query_id") or row.get("case_id")
    return str(value or "").strip()


def _row_matches_trace(row: dict[str, Any], trace: dict[str, Any]) -> bool:
    expected_context = [
        {"doc_id": str(context.get("id") or ""), "text": str(context.get("text") or "")}
        for context in trace.get("contexts") or []
    ]
    return (
        row.get("query") == str(trace.get("query") or "")
        and row.get("response") == str(trace.get("answer") or "")
        and row.get("retrieved_context") == expected_context
    )


def _write_raw(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def _existing_rows_for_run(
    path: Path,
    *,
    resume: bool,
    expected_runtime: dict[str, Any],
    dataset: str,
) -> list[dict[str, Any]] | None:
    if path.exists() and not resume:
        raise MiniCheckAuditError(
            f"Refusing to overwrite existing output {path}. Use --resume to "
            "continue its exact audited runtime."
        )
    if not resume:
        return None
    return _read_existing(
        path,
        expected_runtime=expected_runtime,
        dataset=dataset,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-inputs", type=Path, required=True)
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--model-dir", type=Path, required=True)
    parser.add_argument("--nltk-data-dir", type=Path, required=True)
    parser.add_argument("--runtime-lock", type=Path, default=DEFAULT_RUNTIME_LOCK)
    parser.add_argument("--raw-output", type=Path, required=True)
    parser.add_argument("--candidate-output", type=Path, required=True)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument(
        "--device", choices=("auto", "cpu", "mps", "cuda"), default="auto"
    )
    parser.add_argument("--batch-size", type=int, default=8)
    args = parser.parse_args(argv)

    runtime = audit_runtime(
        args.runtime_lock,
        args.source_dir,
        args.model_dir,
        args.nltk_data_dir,
    )
    runtime["inference_batch_size"] = args.batch_size
    inputs = _read_jsonl(args.candidate_inputs)
    raw = run_minicheck(
        inputs,
        dataset=args.dataset,
        runtime=runtime,
        source_dir=args.source_dir,
        model_dir=args.model_dir,
        nltk_data_dir=args.nltk_data_dir,
        device=args.device,
        batch_size=args.batch_size,
        existing_rows=_existing_rows_for_run(
            args.raw_output,
            resume=args.resume,
            expected_runtime=runtime,
            dataset=args.dataset,
        ),
        checkpoint_path=args.raw_output,
    )
    _write_raw(args.raw_output, raw)
    candidate = adapt_candidate_rows(
        raw["rows"],
        system="MiniCheck",
        version=raw["version"],
        preset="minicheck",
    )
    write_candidate(candidate, args.candidate_output)
    print(f"Wrote {len(raw['rows'])} complete MiniCheck rows.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
