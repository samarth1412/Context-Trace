"""Shared, label-free input contract for ContextTrace-Unseen-v1 baselines."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Iterator, Mapping, Sequence


BASELINE_INPUT_SCHEMA_VERSION = "contexttrace-unseen-v1-baseline-input-1.0"


class BaselineInputError(RuntimeError):
    """Raised when a baseline input violates the frozen candidate identity."""


def canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_json(value)).hexdigest()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_json_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BaselineInputError(f"Could not load {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise BaselineInputError(f"{path} must contain a JSON object.")
    return value


def _require_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise BaselineInputError(f"{field} must be a non-empty string.")
    return value


def build_candidate_input(
    case: Mapping[str, Any],
    trace: Mapping[str, Any],
) -> dict[str, Any]:
    """Create the exact label-free candidate view shared by all baselines."""

    case_id = _require_text(case.get("case_id"), "case.case_id")
    if trace.get("case_id") != case_id:
        raise BaselineInputError(
            f"Case identity mismatch: manifest={case_id!r}, trace={trace.get('case_id')!r}."
        )

    retrieved = trace.get("retrieved_chunks")
    if not isinstance(retrieved, list) or not retrieved:
        raise BaselineInputError(f"{case_id}: retrieved_chunks must be a non-empty list.")

    chunks: list[dict[str, str]] = []
    seen_ids: set[str] = set()
    for index, raw_chunk in enumerate(retrieved):
        if not isinstance(raw_chunk, Mapping):
            raise BaselineInputError(f"{case_id}: chunk {index} must be an object.")
        chunk_id = _require_text(raw_chunk.get("id"), f"{case_id}.chunk[{index}].id")
        if chunk_id in seen_ids:
            raise BaselineInputError(f"{case_id}: duplicate chunk id {chunk_id!r}.")
        seen_ids.add(chunk_id)
        chunks.append(
            {
                "chunk_id": chunk_id,
                "source_id": _require_text(
                    raw_chunk.get("source_id"),
                    f"{case_id}.chunk[{index}].source_id",
                ),
                "text": _require_text(
                    raw_chunk.get("text"),
                    f"{case_id}.chunk[{index}].text",
                ),
            }
        )

    expected_retrieved = case.get("retrieved_chunk_ids")
    if not isinstance(expected_retrieved, list):
        raise BaselineInputError(f"{case_id}: manifest retrieved_chunk_ids is invalid.")
    actual_retrieved = [chunk["chunk_id"] for chunk in chunks]
    if actual_retrieved != expected_retrieved:
        raise BaselineInputError(f"{case_id}: retrieved chunk identity/order mismatch.")

    selected_ids = case.get("selected_context_ids")
    if not isinstance(selected_ids, list) or not selected_ids:
        raise BaselineInputError(f"{case_id}: selected_context_ids is invalid.")
    missing = [chunk_id for chunk_id in selected_ids if chunk_id not in seen_ids]
    if missing:
        raise BaselineInputError(
            f"{case_id}: selected contexts are absent from retrieval: {missing!r}."
        )
    by_id = {chunk["chunk_id"]: chunk for chunk in chunks}
    selected = [by_id[chunk_id] for chunk_id in selected_ids]

    candidate: dict[str, Any] = {
        "schema_version": BASELINE_INPUT_SCHEMA_VERSION,
        "dataset_id": "ContextTrace-Unseen-v1",
        "case_id": case_id,
        "track": _require_text(case.get("track"), f"{case_id}.track"),
        "query": _require_text(trace.get("query"), f"{case_id}.query"),
        "answer": _require_text(trace.get("answer"), f"{case_id}.answer"),
        "retrieved_chunks": chunks,
        "selected_context_ids": list(selected_ids),
        "selected_contexts": selected,
    }
    candidate["candidate_input_sha256"] = canonical_sha256(candidate)
    return candidate


def verify_manifest_identity(
    manifest: Mapping[str, Any],
    *,
    expected_payload_sha256: str,
) -> Sequence[Mapping[str, Any]]:
    seal = manifest.get("seal")
    if not isinstance(seal, Mapping):
        raise BaselineInputError("Frozen manifest seal is absent.")
    if seal.get("payload_sha256") != expected_payload_sha256:
        raise BaselineInputError("Frozen manifest payload hash does not match the lock.")
    cases = manifest.get("cases")
    if not isinstance(cases, list) or len(cases) != 493:
        raise BaselineInputError("Frozen manifest must contain exactly 493 cases.")
    ids = [case.get("case_id") for case in cases if isinstance(case, Mapping)]
    if len(ids) != len(cases) or len(set(ids)) != len(ids):
        raise BaselineInputError("Frozen manifest case IDs are invalid or duplicated.")
    return cases


def iter_frozen_candidates(
    manifest_path: Path,
    artifact_root: Path,
    *,
    expected_payload_sha256: str,
) -> Iterator[dict[str, Any]]:
    """Yield verified candidates without accepting any label-bearing input."""

    manifest = load_json_object(manifest_path)
    cases = verify_manifest_identity(
        manifest,
        expected_payload_sha256=expected_payload_sha256,
    )
    root = artifact_root.resolve()
    seen: set[str] = set()
    for case in cases:
        case_id = str(case["case_id"])
        relative = Path(str(case["trace_artifact_path"]))
        trace_path = (root / relative).resolve()
        if root not in trace_path.parents:
            raise BaselineInputError(f"{case_id}: trace path escapes artifact root.")
        if file_sha256(trace_path) != case["trace_sha256"]:
            raise BaselineInputError(f"{case_id}: trace hash mismatch.")
        if case_id in seen:
            raise BaselineInputError(f"Duplicate case input: {case_id}.")
        seen.add(case_id)
        yield build_candidate_input(case, load_json_object(trace_path))
