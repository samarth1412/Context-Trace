"""Run a pinned RefChecker pipeline with a local extractor and NLI checker.

The official RefChecker source performs triplet extraction and NLI checking.
Gemma 3 4B is served locally by Ollama for extraction; no provider is called.
All source and model identities are checked before any benchmark row is run.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import sys
import tempfile
import time
import urllib.error
import urllib.request
import zipfile
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from benchmarks.contexttrace_bench.adapt_candidate import (
    adapt_candidate_rows,
    write_candidate,
)
from benchmarks.external_baselines.run_minicheck import (
    _audit_files,
    _git_output,
    _mapping_sha256,
    _read_jsonl,
    _row_id,
    _streaming_sha256,
    _trace,
    _write_raw,
)

HERE = Path(__file__).resolve().parent
DEFAULT_RUNTIME_LOCK = HERE / "competitor-runtime-lock.json"


class RefCheckerAuditError(ValueError):
    """Raised when a pinned RefChecker dependency or input changed."""


def audit_runtime(
    lock_path: Path,
    source_dir: Path,
    nli_model_dir: Path,
    ollama_url: str,
    package_wheel: Path | None = None,
) -> dict[str, Any]:
    lock = _refchecker_lock(lock_path)
    source_revision = _audit_source(lock, source_dir, package_wheel)

    model_files = _audit_files(
        nli_model_dir,
        _string_map(lock, "checker_model_files"),
        artifact_name="RefChecker NLI model",
    )
    version_payload = _ollama_json(ollama_url, "/api/version")
    tags_payload = _ollama_json(ollama_url, "/api/tags")
    local_model = next(
        (
            model
            for model in tags_payload.get("models") or []
            if isinstance(model, dict) and model.get("name") == lock["extractor_model"]
        ),
        None,
    )
    if local_model is None:
        raise RefCheckerAuditError(
            f"Ollama model {lock['extractor_model']} is unavailable."
        )
    if local_model.get("digest") != lock["extractor_model_digest"]:
        raise RefCheckerAuditError(
            "Ollama extractor digest mismatch: expected "
            f"{lock['extractor_model_digest']}, found {local_model.get('digest')}."
        )
    actual_ollama_version = str(version_payload.get("version") or "")
    if actual_ollama_version != lock["ollama_version"]:
        raise RefCheckerAuditError(
            f"Ollama version mismatch: expected {lock['ollama_version']}, "
            f"found {actual_ollama_version}."
        )

    installed_version = importlib.metadata.version("refchecker")
    if installed_version != lock["package_version"]:
        raise RefCheckerAuditError(
            f"RefChecker package mismatch: expected {lock['package_version']}, "
            f"found {installed_version}."
        )
    dependencies = _audit_dependency_versions(lock)
    return {
        "source_url": lock["source_url"],
        "source_revision": source_revision,
        "package_version": installed_version,
        "extractor": {
            "runtime": "ollama",
            "runtime_version": actual_ollama_version,
            "model": lock["extractor_model"],
            "model_digest": lock["extractor_model_digest"],
            "temperature": 0,
            "seed": 2024,
            "claim_format": "triplet",
            "request_concurrency": int(lock["extractor_request_concurrency"]),
            "context_length": int(lock["extractor_context_length"]),
            "max_new_tokens": int(lock["extractor_max_new_tokens"]),
        },
        "checker": {
            "model_id": lock["checker_model_id"],
            "model_revision": lock["checker_model_revision"],
            "artifact_manifest_sha256": _mapping_sha256(model_files),
            "max_length": 512,
            "reference_segment_length": int(
                lock["checker_reference_segment_length"]
            ),
            "reference_unit": lock["checker_reference_unit"],
            "segmenter_model_wheel_sha256": lock[
                "segmenter_model_wheel_sha256"
            ],
            "segmenter_model_wheel_url": lock["segmenter_model_wheel_url"],
        },
        "dependencies": dependencies,
    }


def project_refchecker_labels(
    claim_labels: list[str], *, dataset: str
) -> tuple[list[str], str]:
    if not claim_labels:
        return ["should_have_abstained"], "should_have_abstained"
    normalized = [str(label).lower() for label in claim_labels]
    if all(label == "entailment" for label in normalized):
        return ["no_failure_detected"], "no_failure_detected"

    dataset_key = dataset.lower()
    if dataset_key.startswith("ares"):
        return (
            ["should_have_abstained", "unsupported_answer"],
            "should_have_abstained",
        )
    if dataset_key == "ragtruth":
        if "contradiction" in normalized:
            return ["contradicted_answer"], "conflicting_contexts"
        if all(label == "neutral" for label in normalized):
            return ["unsupported"], "answer_overreach"
        return ["partial_support"], "answer_overreach"
    return ["unsupported_answer"], "answer_overreach"


def run_refchecker(
    candidate_inputs: list[dict[str, Any]],
    *,
    dataset: str,
    runtime: dict[str, Any],
    source_dir: Path,
    nli_model_dir: Path,
    ollama_url: str,
    device: str = "auto",
    batch_size: int = 4,
    existing_rows: list[dict[str, Any]] | None = None,
    checkpoint_path: Path | None = None,
) -> dict[str, Any]:
    source_dir = source_dir.resolve()
    nli_model_dir = nli_model_dir.resolve()
    if checkpoint_path is not None:
        checkpoint_path = checkpoint_path.resolve()
    _activate_source(source_dir)
    from refchecker import LLMExtractor
    from refchecker.checker import NLIChecker

    resolved_device = _resolve_device(device)
    extractor = LLMExtractor(
        claim_format="triplet",
        model=str(runtime["extractor"]["model"]),
        batch_size=batch_size,
    )
    checker = NLIChecker(
        model=str(nli_model_dir),
        device=resolved_device,
        batch_size=max(1, batch_size * 8),
    )
    completed = {
        _row_id(row): row
        for row in existing_rows or []
        if not row.get("error") and _row_id(row)
    }
    output_by_id: dict[str, dict[str, Any]] = {}
    pending: list[dict[str, Any]] = []
    for row in candidate_inputs:
        case_id = _row_id(row)
        old_row = completed.get(case_id)
        if old_row is not None and _row_matches_trace(old_row, _trace(row)):
            output_by_id[case_id] = old_row
        else:
            pending.append(row)

    total_started = time.perf_counter()
    for chunk in _chunks(pending, max(1, batch_size)):
        started = time.perf_counter()
        traces = [_trace(row) for row in chunk]
        extraction_results = extractor.extract(
            batch_responses=[str(trace.get("answer") or "") for trace in traces],
            batch_questions=[str(trace.get("query") or "") for trace in traces],
            max_new_tokens=int(runtime["extractor"]["max_new_tokens"]),
            custom_llm_api_func=lambda prompts: _ollama_generate(
                ollama_url,
                model=str(runtime["extractor"]["model"]),
                prompts=prompts,
                concurrency=int(runtime["extractor"]["request_concurrency"]),
                context_length=int(runtime["extractor"]["context_length"]),
                max_new_tokens=int(runtime["extractor"]["max_new_tokens"]),
            ),
        )
        if extraction_results is None or len(extraction_results) != len(chunk):
            raise RefCheckerAuditError(
                "RefChecker extractor did not return exact batch coverage."
            )
        claims = [
            [claim.get_content() for claim in result.claims]
            for result in extraction_results
        ]
        references = [reference_passages(trace) for trace in traces]
        checked = checker.check(
            batch_claims=claims,
            batch_references=references,
            max_reference_segment_length=int(
                runtime["checker"]["reference_segment_length"]
            ),
            merge_psg=True,
            is_joint=False,
        )
        if len(checked) != len(chunk):
            raise RefCheckerAuditError(
                "RefChecker checker did not return exact batch coverage."
            )
        elapsed_ms = (time.perf_counter() - started) * 1000
        for input_row, trace, result, claim_texts, labels in zip(
            chunk,
            traces,
            extraction_results,
            claims,
            checked,
            strict=True,
        ):
            flattened_labels = [
                str(label[0] if isinstance(label, list) and len(label) == 1 else label)
                for label in labels
            ]
            predicted, root = project_refchecker_labels(
                flattened_labels,
                dataset=dataset,
            )
            verdicts = [_claim_verdict(label) for label in flattened_labels]
            counts = Counter(verdicts)
            contexts = trace.get("contexts") or []
            output_by_id[_row_id(input_row)] = {
                "id": _row_id(input_row),
                "query": str(trace.get("query") or ""),
                "response": str(trace.get("answer") or ""),
                "retrieved_context": [
                    {
                        "doc_id": str(context.get("id") or ""),
                        "text": str(context.get("text") or ""),
                    }
                    for context in contexts
                ],
                "extractor_response": result.extractor_response,
                "claims": [
                    {
                        "claim_index": index,
                        "text": claim_text,
                        "refchecker_label": label,
                    }
                    for index, (claim_text, label) in enumerate(
                        zip(claim_texts, flattened_labels, strict=True)
                    )
                ],
                "claim_verdicts": verdicts,
                "verdict_counts": {
                    "supported": counts["supported"],
                    "partially_supported": 0,
                    "unsupported": counts["unsupported"],
                    "contradicted": counts["contradicted"],
                    "unverifiable": counts["unverifiable"],
                },
                "predicted_labels": predicted,
                "predicted_primary_root_cause": root,
                "latency_ms": round(elapsed_ms / len(chunk), 3),
                "latency_measure": "amortized_batch",
                "error": None,
            }
        if checkpoint_path is not None:
            rows = [
                output_by_id[_row_id(row)]
                for row in candidate_inputs
                if _row_id(row) in output_by_id
            ]
            _write_raw(
                checkpoint_path,
                _raw_payload(
                    rows=rows,
                    dataset=dataset,
                    runtime=runtime,
                    device=resolved_device,
                    elapsed_ms=(time.perf_counter() - total_started) * 1000,
                    complete=len(rows) == len(candidate_inputs),
                ),
            )

    rows = [output_by_id[_row_id(row)] for row in candidate_inputs]
    return _raw_payload(
        rows=rows,
        dataset=dataset,
        runtime=runtime,
        device=resolved_device,
        elapsed_ms=(time.perf_counter() - total_started) * 1000,
        complete=len(rows) == len(candidate_inputs),
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
        "system": "RefChecker",
        "version": "0.2.17 / Gemma3-4B-Q4_K_M extractor / official NLI checker",
        "dataset": dataset,
        "runtime": {**runtime, "checker_device": device},
        "complete": complete,
        "elapsed_ms": round(elapsed_ms, 3),
        "rows": rows,
    }


def _activate_source(source_dir: Path) -> None:
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    current_dir = Path.cwd().resolve()
    sys.path[:] = [
        entry for entry in sys.path if entry and Path(entry).resolve() != current_dir
    ]
    os.chdir(tempfile.gettempdir())
    source_text = str(source_dir.resolve())
    if source_text not in sys.path:
        sys.path.insert(0, source_text)


def _resolve_device(requested: str) -> str:
    import torch

    if requested != "auto":
        if requested == "mps" and not torch.backends.mps.is_available():
            raise RefCheckerAuditError("MPS was requested but is unavailable.")
        if requested == "cuda" and not torch.cuda.is_available():
            raise RefCheckerAuditError("CUDA was requested but is unavailable.")
        return requested
    if torch.cuda.is_available():
        return "cuda"
    if torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def _ollama_generate(
    url: str,
    *,
    model: str,
    prompts: list[str],
    concurrency: int = 2,
    context_length: int = 4096,
    max_new_tokens: int = 500,
) -> list[str]:
    with ThreadPoolExecutor(max_workers=max(1, concurrency)) as executor:
        return list(
            executor.map(
                lambda prompt: _ollama_generate_one(
                    url,
                    model=model,
                    prompt=prompt,
                    context_length=context_length,
                    max_new_tokens=max_new_tokens,
                ),
                prompts,
            )
        )


def _ollama_generate_one(
    url: str,
    *,
    model: str,
    prompt: str,
    context_length: int,
    max_new_tokens: int,
) -> str:
    payload = _ollama_json(
        url,
        "/api/generate",
        {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "keep_alive": "30m",
            "options": {
                "temperature": 0,
                "seed": 2024,
                "num_ctx": context_length,
                "num_predict": max_new_tokens,
            },
        },
        timeout=600,
    )
    response = payload.get("response")
    if not isinstance(response, str):
        raise RefCheckerAuditError("Ollama returned a non-text response.")
    return response


def _ollama_json(
    url: str,
    path: str,
    payload: dict[str, Any] | None = None,
    *,
    timeout: int = 30,
) -> dict[str, Any]:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url.rstrip("/") + path,
        data=data,
        headers={"Content-Type": "application/json"},
        method="GET" if data is None else "POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            parsed = json.loads(response.read().decode("utf-8"))
    except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
        raise RefCheckerAuditError(f"Ollama request failed for {path}.") from exc
    if not isinstance(parsed, dict):
        raise RefCheckerAuditError(f"Ollama returned invalid JSON for {path}.")
    return parsed


def _claim_verdict(label: str) -> str:
    normalized = label.lower()
    if normalized == "entailment":
        return "supported"
    if normalized == "contradiction":
        return "contradicted"
    return "unverifiable"


def reference_passages(trace: dict[str, Any]) -> list[str]:
    """Preserve retrieved-document boundaries for RefChecker passage merging."""
    return [
        str(context.get("text") or "") for context in trace.get("contexts") or []
    ]


def _row_matches_trace(row: dict[str, Any], trace: dict[str, Any]) -> bool:
    expected_context = [
        {
            "doc_id": str(context.get("id") or ""),
            "text": str(context.get("text") or ""),
        }
        for context in trace.get("contexts") or []
    ]
    return (
        row.get("query") == str(trace.get("query") or "")
        and row.get("response") == str(trace.get("answer") or "")
        and row.get("retrieved_context") == expected_context
    )


def _chunks(rows: list[dict[str, Any]], size: int) -> list[list[dict[str, Any]]]:
    return [rows[index : index + size] for index in range(0, len(rows), size)]


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
        raise RefCheckerAuditError("Resume payload must be an object.")
    if dataset is not None and payload.get("dataset") != dataset:
        raise RefCheckerAuditError("Resume payload dataset changed.")
    saved_runtime = payload.get("runtime")
    if expected_runtime is not None and (
        not isinstance(saved_runtime, dict)
        or any(
            saved_runtime.get(key) != value for key, value in expected_runtime.items()
        )
    ):
        raise RefCheckerAuditError("Resume payload runtime changed.")
    rows = payload.get("rows")
    if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
        raise RefCheckerAuditError("Resume payload has invalid rows.")
    return rows


def _refchecker_lock(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    lock = payload.get("RefChecker") if isinstance(payload, dict) else None
    if not isinstance(lock, dict):
        raise RefCheckerAuditError("Runtime lock is missing RefChecker.")
    for field in (
        "source_url",
        "source_revision",
        "package_version",
        "package_wheel_sha256",
        "package_wheel_url",
        "extractor_model",
        "extractor_model_digest",
        "extractor_context_length",
        "extractor_max_new_tokens",
        "extractor_request_concurrency",
        "ollama_version",
        "checker_model_id",
        "checker_model_revision",
        "checker_reference_segment_length",
        "checker_reference_unit",
        "segmenter_model_wheel_sha256",
        "segmenter_model_wheel_url",
    ):
        if not str(lock.get(field) or "").strip():
            raise RefCheckerAuditError(f"Runtime lock is missing RefChecker.{field}.")
    return lock


def _audit_source(
    lock: dict[str, Any],
    source_dir: Path,
    package_wheel: Path | None,
) -> str:
    if (source_dir / ".git").exists():
        source_revision = _git_output(source_dir, "rev-parse", "HEAD")
        if source_revision != lock["source_revision"]:
            raise RefCheckerAuditError(
                "RefChecker source revision mismatch: expected "
                f"{lock['source_revision']}, found {source_revision}."
            )
        if _git_output(source_dir, "status", "--porcelain"):
            raise RefCheckerAuditError("RefChecker source tree must be clean.")
        return source_revision

    if package_wheel is None:
        raise RefCheckerAuditError(
            "RefChecker source checkout is unavailable; --package-wheel must point "
            "to the hash-locked official wheel."
        )
    _audit_installed_wheel(lock, package_wheel)
    return str(lock["source_revision"])


def _audit_installed_wheel(
    lock: dict[str, Any],
    package_wheel: Path,
    *,
    install_root: Path | None = None,
) -> dict[str, str]:
    expected_wheel_hash = str(lock["package_wheel_sha256"])
    actual_wheel_hash = _streaming_sha256(package_wheel)
    if actual_wheel_hash != expected_wheel_hash:
        raise RefCheckerAuditError(
            "RefChecker wheel SHA-256 mismatch: expected "
            f"{expected_wheel_hash}, found {actual_wheel_hash}."
        )

    if install_root is None:
        distribution = importlib.metadata.distribution("refchecker")
        install_root = Path(distribution.locate_file(""))
    install_root = install_root.resolve()
    audited: dict[str, str] = {}
    try:
        with zipfile.ZipFile(package_wheel) as archive:
            members = sorted(
                name
                for name in archive.namelist()
                if name.startswith("refchecker/") and not name.endswith("/")
            )
            if not members:
                raise RefCheckerAuditError(
                    "RefChecker wheel contains no package files."
                )
            for member in members:
                installed = (install_root / member).resolve()
                if not installed.is_relative_to(install_root) or not installed.is_file():
                    raise RefCheckerAuditError(
                        f"Installed RefChecker file is missing: {member}."
                    )
                wheel_hash = hashlib.sha256(archive.read(member)).hexdigest()
                installed_hash = _streaming_sha256(installed)
                if installed_hash != wheel_hash:
                    raise RefCheckerAuditError(
                        f"Installed RefChecker file changed: {member}."
                    )
                audited[member] = installed_hash
    except zipfile.BadZipFile as exc:
        raise RefCheckerAuditError("RefChecker wheel is not a valid archive.") from exc
    return audited


def _string_map(payload: dict[str, Any], field: str) -> dict[str, str]:
    value = payload.get(field)
    if not isinstance(value, dict) or not value:
        raise RefCheckerAuditError(f"Runtime lock is missing RefChecker.{field}.")
    return {str(key): str(item) for key, item in value.items()}


def _audit_dependency_versions(lock: dict[str, Any]) -> dict[str, str]:
    expected = _string_map(lock, "dependency_versions")
    actual = {name: importlib.metadata.version(name) for name in expected}
    if actual != expected:
        raise RefCheckerAuditError(
            f"RefChecker dependency mismatch: expected {expected}, found {actual}."
        )
    return actual


def _existing_rows_for_run(
    path: Path,
    *,
    resume: bool,
    expected_runtime: dict[str, Any],
    dataset: str,
) -> list[dict[str, Any]] | None:
    if path.exists() and not resume:
        raise RefCheckerAuditError(
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
    parser.add_argument("--package-wheel", type=Path)
    parser.add_argument("--nli-model-dir", type=Path, required=True)
    parser.add_argument("--ollama-url", default="http://127.0.0.1:11434")
    parser.add_argument("--runtime-lock", type=Path, default=DEFAULT_RUNTIME_LOCK)
    parser.add_argument("--raw-output", type=Path, required=True)
    parser.add_argument("--candidate-output", type=Path, required=True)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument(
        "--device", choices=("auto", "cpu", "mps", "cuda"), default="auto"
    )
    parser.add_argument("--batch-size", type=int, default=4)
    args = parser.parse_args(argv)

    args.candidate_inputs = args.candidate_inputs.resolve()
    args.source_dir = args.source_dir.resolve()
    if args.package_wheel is not None:
        args.package_wheel = args.package_wheel.resolve()
    args.nli_model_dir = args.nli_model_dir.resolve()
    args.runtime_lock = args.runtime_lock.resolve()
    args.raw_output = args.raw_output.resolve()
    args.candidate_output = args.candidate_output.resolve()

    runtime = audit_runtime(
        args.runtime_lock,
        args.source_dir,
        args.nli_model_dir,
        args.ollama_url,
        package_wheel=args.package_wheel,
    )
    runtime["extractor_batch_size"] = args.batch_size
    runtime["checker_batch_size"] = max(1, args.batch_size * 8)
    inputs = _read_jsonl(args.candidate_inputs)
    raw = run_refchecker(
        inputs,
        dataset=args.dataset,
        runtime=runtime,
        source_dir=args.source_dir,
        nli_model_dir=args.nli_model_dir,
        ollama_url=args.ollama_url,
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
        system="RefChecker",
        version=raw["version"],
        preset="minicheck",
    )
    write_candidate(candidate, args.candidate_output)
    print(f"Wrote {len(raw['rows'])} complete RefChecker rows.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
