"""Collect the authorized ContextTrace-Unseen-v1 Natural OOD schedule.

This module is intentionally separate from ContextTrace's verifier packages.
It only performs the locked RAG data-generation pipeline and writes private,
unlabeled candidate artifacts.  Model calls require the exact authorized
schedule SHA-256 on the command line.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import math
import os
import platform
import re
import subprocess
import sys
import time
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import httpx
import numpy as np

from benchmarks.contexttrace_unseen_v1.build_generation_schedule import (
    validate_schedule,
)
from benchmarks.contexttrace_unseen_v1.validate_acquisition import (
    validate_acquisition,
)


AUTHORIZED_SCHEDULE_SHA256 = (
    "e850d3eb6d374547cdbc70b2c0da02e0db8d9ff043633a577d9319f3d69e1695"
)
COLLECTION_PROTOCOL_VERSION = "contexttrace-unseen-natural-ood-v1"
TRACE_SCHEMA_VERSION = "candidate-trace-v1"
WORD_OR_PUNCTUATION = re.compile(r"\w+|[^\w\s]", re.UNICODE)
LEXICAL_TOKEN = re.compile(r"\w+", re.UNICODE)
FILE_MARKER = re.compile(r"^===== FILE: (.+?) =====\n?", re.MULTILINE)
RETRYABLE_HTTP_STATUS = {408, 429, 500, 502, 503, 504}
REQUIRED_PACKAGE_VERSIONS = {
    "httpx": "0.28.1",
    "numpy": "2.5.0",
    "sentence-transformers": "5.6.1",
    "torch": "2.13.0",
    "transformers": "5.14.1",
}


class CollectionError(RuntimeError):
    """A fail-closed collection invariant was violated."""


class PendingAttemptError(CollectionError):
    """A prior process may have issued an unrecorded model call."""


@dataclass(frozen=True)
class Document:
    path: str
    text: str


@dataclass(frozen=True)
class Chunk:
    id: str
    text: str
    document_path: str
    chunk_index: int


@dataclass(frozen=True)
class ModelResult:
    text: str
    raw: Mapping[str, Any]
    completed_at: str
    elapsed_ms: float
    usage: Mapping[str, Any] | None = None


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CollectionError(f"Could not load required JSON artifact {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise CollectionError(f"Required JSON artifact is not an object: {path}")
    return value


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def component_index(schedule: Mapping[str, Any], group: str) -> dict[str, dict[str, Any]]:
    values = schedule["components"][group]
    if isinstance(values, dict):
        return {str(values["id"]): dict(values)}
    return {str(value["id"]): dict(value) for value in values}


def parse_documents(text: str) -> list[Document]:
    markers = list(FILE_MARKER.finditer(text))
    documents: list[Document] = []
    for index, marker in enumerate(markers):
        start = marker.end()
        end = markers[index + 1].start() if index + 1 < len(markers) else len(text)
        body = text[start:end]
        if body.strip():
            documents.append(Document(path=marker.group(1), text=body))
    if not documents and text.strip():
        documents.append(Document(path="normalized-source", text=text))
    return documents


def token_matches(text: str) -> list[re.Match[str]]:
    return list(WORD_OR_PUNCTUATION.finditer(text))


def deterministic_seed_excerpt(
    documents: Sequence[Document],
    *,
    case_seed: int,
) -> tuple[str, str]:
    candidates: list[tuple[str, str, int, int]] = []
    for document in documents:
        matches = token_matches(document.text)
        for start_token in range(0, len(matches), 768):
            window = matches[start_token : start_token + 768]
            if len(window) < 384:
                continue
            excerpt = document.text[window[0].start() : window[-1].end()]
            candidate_id = f"{document.path}:{start_token}:{len(window)}"
            order_hash = sha256_bytes(
                f"{case_seed}:{candidate_id}".encode("utf-8")
            )
            candidates.append((order_hash, excerpt, start_token, len(window)))
    if not candidates:
        raise CollectionError("Source has no deterministic 384-768-token seed excerpt.")
    order_hash, excerpt, start_token, length = min(candidates, key=lambda value: value[0])
    excerpt_id = f"{order_hash[:16]}:{start_token}:{length}"
    return excerpt, excerpt_id


def chunk_documents(
    documents: Sequence[Document],
    *,
    source_id: str,
    size: int,
    overlap: int,
) -> list[Chunk]:
    if size < 1 or overlap < 0 or overlap >= size:
        raise CollectionError("Invalid locked chunk size or overlap.")
    chunks: list[Chunk] = []
    stride = size - overlap
    ordinal = 0
    for document in documents:
        matches = token_matches(document.text)
        for start_token in range(0, len(matches), stride):
            window = matches[start_token : start_token + size]
            if not window:
                continue
            text = document.text[window[0].start() : window[-1].end()]
            chunks.append(
                Chunk(
                    id=f"{source_id}/chunk-{ordinal:06d}",
                    text=text,
                    document_path=document.path,
                    chunk_index=ordinal,
                )
            )
            ordinal += 1
            if start_token + size >= len(matches):
                break
    if not chunks:
        raise CollectionError(f"Chunking produced no chunks for {source_id}.")
    return chunks


def lexical_tokens(text: str) -> list[str]:
    return [match.group(0).casefold() for match in LEXICAL_TOKEN.finditer(text)]


def bm25_scores(
    query: str,
    chunks: Sequence[Chunk],
    *,
    k1: float,
    b: float,
) -> np.ndarray:
    tokenized = [lexical_tokens(chunk.text) for chunk in chunks]
    query_terms = sorted(set(lexical_tokens(query)))
    lengths = np.asarray([len(tokens) for tokens in tokenized], dtype=np.float64)
    average_length = float(lengths.mean()) if len(lengths) else 0.0
    scores = np.zeros(len(chunks), dtype=np.float64)
    if not query_terms or not average_length:
        return scores
    frequencies = [Counter(tokens) for tokens in tokenized]
    document_count = len(chunks)
    for term in query_terms:
        document_frequency = sum(term in frequency for frequency in frequencies)
        if not document_frequency:
            continue
        inverse_document_frequency = math.log(
            1.0 + (document_count - document_frequency + 0.5) / (document_frequency + 0.5)
        )
        for index, frequency in enumerate(frequencies):
            count = frequency.get(term, 0)
            if not count:
                continue
            denominator = count + k1 * (
                1.0 - b + b * lengths[index] / average_length
            )
            scores[index] += inverse_document_frequency * count * (k1 + 1.0) / denominator
    return scores


def stable_top_indices(
    scores: Sequence[float],
    chunks: Sequence[Chunk],
    limit: int,
) -> list[int]:
    return sorted(
        range(len(chunks)),
        key=lambda index: (-float(scores[index]), chunks[index].id),
    )[:limit]


def rrf_indices(
    lexical: Sequence[int],
    vector: Sequence[int],
    chunks: Sequence[Chunk],
    *,
    rrf_k: int,
    limit: int,
) -> list[int]:
    scores: dict[int, float] = {}
    for ranking in (lexical, vector):
        for rank, index in enumerate(ranking, start=1):
            scores[index] = scores.get(index, 0.0) + 1.0 / (rrf_k + rank)
    return sorted(
        scores,
        key=lambda index: (-scores[index], chunks[index].id),
    )[:limit]


class DenseEncoder:
    def __init__(self, component: Mapping[str, Any]) -> None:
        specification = component["embedding_model"]
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise CollectionError("sentence-transformers is required by the lock.") from exc
        self.model = SentenceTransformer(
            specification["model_id"],
            revision=specification["revision"],
            trust_remote_code=False,
        )
        self.dimensions = int(specification["dimensions"])

    def encode(self, texts: Sequence[str]) -> np.ndarray:
        values = self.model.encode(
            list(texts),
            batch_size=32,
            show_progress_bar=False,
            convert_to_numpy=True,
            normalize_embeddings=True,
        )
        array = np.asarray(values, dtype=np.float32)
        if array.ndim != 2 or array.shape[1] != self.dimensions:
            raise CollectionError(
                f"Pinned embedding model returned unexpected shape {array.shape}."
            )
        return array


class EmbeddingCache:
    def __init__(self, root: Path, encoder: DenseEncoder) -> None:
        self.root = root
        self.encoder = encoder
        self.memory: dict[str, np.ndarray] = {}

    def embeddings(
        self,
        *,
        source: Mapping[str, Any],
        chunking: Mapping[str, Any],
        chunks: Sequence[Chunk],
    ) -> np.ndarray:
        identity = {
            "normalized_content_sha256": source["normalized_content_sha256"],
            "chunking_configuration_sha256": chunking["configuration_sha256"],
            "chunk_ids_and_text": [
                [chunk.id, sha256_bytes(chunk.text.encode("utf-8"))] for chunk in chunks
            ],
        }
        key = sha256_bytes(canonical_json(identity).encode("utf-8"))
        if key in self.memory:
            return self.memory[key]
        path = self.root / f"{key}.npy"
        if path.is_file():
            values = np.load(path, allow_pickle=False)
        else:
            values = self.encoder.encode([chunk.text for chunk in chunks])
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_name(f".{path.name}.tmp")
            with temporary.open("wb") as handle:
                np.save(handle, values, allow_pickle=False)
            os.replace(temporary, path)
        if values.shape != (len(chunks), self.encoder.dimensions):
            raise CollectionError(f"Embedding cache shape mismatch for {key}.")
        self.memory[key] = values
        return values


def retrieve(
    query: str,
    chunks: Sequence[Chunk],
    retrieval: Mapping[str, Any],
    *,
    embeddings: np.ndarray | None,
    encoder: DenseEncoder | None,
) -> list[int]:
    limit = int(retrieval["candidate_k"])
    family = retrieval["family"]
    lexical_ranking: list[int] | None = None
    vector_ranking: list[int] | None = None
    if family in {"bm25", "hybrid"}:
        parameters = (
            retrieval["parameters"]
            if family == "bm25"
            else {"k1": 1.2, "b": 0.75}
        )
        lexical_scores = bm25_scores(
            query, chunks, k1=float(parameters["k1"]), b=float(parameters["b"])
        )
        lexical_ranking = stable_top_indices(lexical_scores, chunks, limit)
    if family in {"vector", "hybrid"}:
        if embeddings is None or encoder is None:
            raise CollectionError("Dense retrieval requested without pinned embeddings.")
        query_vector = encoder.encode([query])[0]
        vector_scores = embeddings @ query_vector
        vector_ranking = stable_top_indices(vector_scores, chunks, limit)
    if family == "bm25":
        assert lexical_ranking is not None
        return lexical_ranking
    if family == "vector":
        assert vector_ranking is not None
        return vector_ranking
    if family == "hybrid":
        assert lexical_ranking is not None and vector_ranking is not None
        parameters = retrieval["parameters"]
        return rrf_indices(
            lexical_ranking,
            vector_ranking,
            chunks,
            rrf_k=int(parameters["rrf_k"]),
            limit=limit,
        )
    raise CollectionError(f"Unsupported locked retrieval family: {family}")


def rerank(
    query: str,
    candidate_indices: Sequence[int],
    chunks: Sequence[Chunk],
    component: Mapping[str, Any],
) -> list[int]:
    if not component["enabled"]:
        return list(candidate_indices)
    candidates = [chunks[index] for index in candidate_indices]
    parameters = component["parameters"]
    scores = bm25_scores(
        query,
        candidates,
        k1=float(parameters["k1"]),
        b=float(parameters["b"]),
    )
    phrase = " ".join(lexical_tokens(query))
    for index, chunk in enumerate(candidates):
        normalized = " ".join(lexical_tokens(chunk.text))
        if phrase and phrase in normalized:
            scores[index] += float(parameters["exact_phrase_bonus"])
    ordered_local = sorted(
        range(len(candidates)),
        key=lambda index: (
            -float(scores[index]),
            index,
            candidates[index].id,
        ),
    )
    return [candidate_indices[index] for index in ordered_local]


def ollama_payload(
    component: Mapping[str, Any],
    *,
    system_prompt: str,
    user_prompt: str,
    seed: int,
) -> dict[str, Any]:
    parameters = component["parameters"]
    return {
        "model": component["model"],
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "stream": False,
        "options": {
            "temperature": parameters["temperature"],
            "top_k": parameters["top_k"],
            "top_p": parameters["top_p"],
            "seed": seed,
            "num_predict": parameters["num_predict"],
        },
    }


def openai_payload(
    component: Mapping[str, Any],
    *,
    system_prompt: str,
    user_prompt: str,
) -> dict[str, Any]:
    parameters = component["parameters"]
    return {
        "model": component["model"],
        "input": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "max_output_tokens": parameters["max_output_tokens"],
        "reasoning": parameters["reasoning"],
        "service_tier": parameters["service_tier"],
        "store": parameters["store"],
        "text": parameters["text"],
        "tools": parameters["tools"],
        "truncation": parameters["truncation"],
    }


def extract_openai_text(payload: Mapping[str, Any]) -> str:
    pieces: list[str] = []
    for item in payload.get("output", []):
        if not isinstance(item, Mapping) or item.get("type") != "message":
            continue
        for content in item.get("content", []):
            if isinstance(content, Mapping) and content.get("type") == "output_text":
                text = content.get("text")
                if isinstance(text, str):
                    pieces.append(text)
    return "".join(pieces)


class TransportClient:
    def __init__(self, controls: Mapping[str, Any]) -> None:
        timeouts = controls["timeouts_seconds"]
        self.local_timeout = httpx.Timeout(
            connect=float(timeouts["local_connect"]),
            read=float(timeouts["local_read"]),
            write=30.0,
            pool=10.0,
        )
        self.hosted_timeout = httpx.Timeout(
            connect=float(timeouts["hosted_connect"]),
            read=float(timeouts["hosted_read"]),
            write=30.0,
            pool=10.0,
        )

    def ollama(self, payload: Mapping[str, Any]) -> ModelResult:
        started = time.perf_counter()
        response = httpx.post(
            "http://127.0.0.1:11434/api/chat",
            json=payload,
            timeout=self.local_timeout,
        )
        if response.status_code in RETRYABLE_HTTP_STATUS:
            raise RetryableTransportError(f"HTTP {response.status_code}")
        response.raise_for_status()
        raw = response.json()
        text = raw.get("message", {}).get("content")
        if not isinstance(text, str) or not text:
            raise RetryableTransportError("empty transport response")
        return ModelResult(
            text=text,
            raw=raw,
            completed_at=utc_now(),
            elapsed_ms=(time.perf_counter() - started) * 1000.0,
        )

    def openai(self, payload: Mapping[str, Any]) -> ModelResult:
        key = os.environ.get("OPENAI_API_KEY")
        if not key:
            raise CollectionError("OPENAI_API_KEY is required for hosted cases.")
        started = time.perf_counter()
        response = httpx.post(
            "https://api.openai.com/v1/responses",
            headers={"Authorization": f"Bearer {key}"},
            json=payload,
            timeout=self.hosted_timeout,
        )
        if response.status_code in RETRYABLE_HTTP_STATUS:
            raise RetryableTransportError(f"HTTP {response.status_code}")
        response.raise_for_status()
        raw = response.json()
        text = extract_openai_text(raw)
        if not text:
            raise RetryableTransportError("empty transport response")
        usage = raw.get("usage")
        return ModelResult(
            text=text,
            raw=raw,
            completed_at=utc_now(),
            elapsed_ms=(time.perf_counter() - started) * 1000.0,
            usage=usage if isinstance(usage, Mapping) else None,
        )


class RetryableTransportError(CollectionError):
    pass


def request_upper_cost(payload: Mapping[str, Any], guard: Mapping[str, Any]) -> float:
    payload_bytes = len(canonical_json(payload).encode("utf-8"))
    maximum = int(guard["maximum_request_input_utf8_bytes"])
    if payload_bytes > maximum:
        raise CollectionError(
            f"Hosted request is oversized ({payload_bytes} UTF-8 bytes > {maximum})."
        )
    prices = guard["prices_per_million_tokens"]
    return (
        payload_bytes * float(prices["uncached_input"])
        + int(guard["maximum_output_tokens_per_attempt"])
        * float(prices["output_and_reasoning"])
    ) / 1_000_000.0


def actual_openai_cost(
    usage: Mapping[str, Any] | None,
    *,
    upper_cost: float,
    guard: Mapping[str, Any],
) -> tuple[float, str]:
    if usage is None:
        return upper_cost, "conservative_missing_usage"
    try:
        input_tokens = int(usage["input_tokens"])
        output_tokens = int(usage["output_tokens"])
        details = usage.get("input_tokens_details") or {}
        cached_tokens = int(details.get("cached_tokens", 0))
    except (KeyError, TypeError, ValueError):
        return upper_cost, "conservative_invalid_usage"
    uncached_tokens = max(0, input_tokens - cached_tokens)
    prices = guard["prices_per_million_tokens"]
    cost = (
        uncached_tokens * float(prices["uncached_input"])
        + cached_tokens * float(prices["cached_input"])
        + output_tokens * float(prices["output_and_reasoning"])
    ) / 1_000_000.0
    return cost, "provider_usage"


class BudgetLedger:
    def __init__(self, path: Path, schedule_sha256: str, guard: Mapping[str, Any]) -> None:
        self.path = path
        self.schedule_sha256 = schedule_sha256
        self.guard = guard
        if path.is_file():
            self.value = load_json(path)
            if self.value.get("schedule_sha256") != schedule_sha256:
                raise CollectionError("Budget ledger belongs to a different schedule.")
        else:
            self.value = {
                "schema_version": "1.0",
                "record_kind": "contexttrace_unseen_v1_hosted_budget",
                "schedule_sha256": schedule_sha256,
                "hard_limit_usd": float(guard["hard_limit"]),
                "attempts": [],
            }
            atomic_json(path, self.value)
        pending = [
            attempt
            for attempt in self.value["attempts"]
            if attempt.get("status") == "reserved"
        ]
        if pending:
            ids = ", ".join(str(item["attempt_id"]) for item in pending)
            raise PendingAttemptError(
                f"Unsettled hosted request reservation(s): {ids}. Manual reconciliation "
                "is required before any further hosted call."
            )

    def charged_total(self) -> float:
        return sum(float(item["charged_cost_usd"]) for item in self.value["attempts"])

    def reserve(self, attempt_id: str, upper_cost: float, payload_sha256: str) -> None:
        if any(item["attempt_id"] == attempt_id for item in self.value["attempts"]):
            raise CollectionError(f"Duplicate hosted attempt ID: {attempt_id}")
        projected = self.charged_total() + upper_cost
        if projected > float(self.guard["hard_limit"]):
            raise CollectionError(
                f"Hosted hard ceiling would be exceeded: ${projected:.6f} > "
                f"${float(self.guard['hard_limit']):.2f}."
            )
        self.value["attempts"].append(
            {
                "attempt_id": attempt_id,
                "status": "reserved",
                "reserved_at": utc_now(),
                "payload_sha256": payload_sha256,
                "upper_cost_usd": upper_cost,
                "charged_cost_usd": upper_cost,
            }
        )
        atomic_json(self.path, self.value)

    def settle(
        self,
        attempt_id: str,
        *,
        status: str,
        charged_cost: float,
        charge_basis: str,
        usage: Mapping[str, Any] | None,
    ) -> None:
        attempt = next(
            (item for item in self.value["attempts"] if item["attempt_id"] == attempt_id),
            None,
        )
        if attempt is None or attempt["status"] != "reserved":
            raise CollectionError(f"Hosted attempt cannot be settled: {attempt_id}")
        attempt.update(
            {
                "status": status,
                "settled_at": utc_now(),
                "charged_cost_usd": charged_cost,
                "charge_basis": charge_basis,
                "usage": dict(usage) if usage is not None else None,
            }
        )
        atomic_json(self.path, self.value)


def validate_query(text: str) -> str | None:
    if not text.strip():
        return "empty query"
    nonempty_lines = [line for line in text.splitlines() if line.strip()]
    if len(nonempty_lines) != 1:
        return "query must contain exactly one non-empty line"
    if len(text) > 240:
        return "query exceeds 240 characters"
    if not text.endswith("?"):
        return "query does not end in '?'"
    return None


def format_contexts(chunks: Sequence[Chunk]) -> str:
    return "\n\n".join(
        f"Context [{index}]\nID: {chunk.id}\n{chunk.text}"
        for index, chunk in enumerate(chunks, start=1)
    )


def extract_citations(
    answer: str,
    *,
    citation_format: str,
    selected: Sequence[Chunk],
) -> list[dict[str, Any]]:
    citations: list[dict[str, Any]] = []
    seen: set[str] = set()
    if citation_format == "inline_numeric":
        for match in re.finditer(r"\[(\d+)\]", answer):
            position = int(match.group(1))
            if 1 <= position <= len(selected):
                chunk = selected[position - 1]
                if chunk.id not in seen:
                    citations.append(
                        {
                            "source_id": chunk.id.split("/", 1)[0],
                            "chunk_id": chunk.id,
                            "raw": match.group(0),
                        }
                    )
                    seen.add(chunk.id)
    elif citation_format == "source_id":
        for chunk in selected:
            raw = f"[{chunk.id}]"
            if raw in answer and chunk.id not in seen:
                citations.append(
                    {
                        "source_id": chunk.id.split("/", 1)[0],
                        "chunk_id": chunk.id,
                        "raw": raw,
                    }
                )
                seen.add(chunk.id)
    return citations


def verify_environment(schedule: Mapping[str, Any], *, require_hosted: bool) -> dict[str, Any]:
    reference = schedule["execution_controls"]["reference_environment"]
    installed: dict[str, str] = {}
    for package, expected in REQUIRED_PACKAGE_VERSIONS.items():
        try:
            actual = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError as exc:
            raise CollectionError(f"Pinned dependency is missing: {package}=={expected}") from exc
        if actual != expected:
            raise CollectionError(
                f"Pinned dependency mismatch for {package}: expected {expected}, got {actual}."
            )
        installed[package] = actual
    python_version = platform.python_version()
    if python_version != str(reference["python"]):
        raise CollectionError(
            f"Pinned Python mismatch: expected {reference['python']}, got {python_version}."
        )
    ollama = subprocess.run(
        ["ollama", "--version"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if str(reference["ollama"]) not in ollama:
        raise CollectionError(f"Pinned Ollama mismatch: expected {reference['ollama']}.")
    model_manifest = (
        Path.home()
        / ".ollama/models/manifests/registry.ollama.ai/library/gemma3/4b"
    )
    expected_manifest = schedule["components"]["query_authoring"]["manifest_digest"].split(
        ":", 1
    )[1]
    if not model_manifest.is_file() or sha256_file(model_manifest) != expected_manifest:
        raise CollectionError("Pinned Ollama Gemma manifest digest does not match.")
    modelfile = subprocess.run(
        ["ollama", "show", "gemma3:4b", "--modelfile"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    expected_weight = schedule["components"]["query_authoring"]["weight_digest"].replace(
        ":", "-"
    )
    if expected_weight not in modelfile:
        raise CollectionError("Pinned Ollama Gemma weight digest does not match.")
    if require_hosted and not os.environ.get("OPENAI_API_KEY"):
        raise CollectionError("OPENAI_API_KEY is absent; hosted generation cannot start.")
    return {
        "python": python_version,
        "platform": f"macOS-{platform.mac_ver()[0]}-{platform.machine()}",
        "packages": installed,
        "ollama": str(reference["ollama"]),
        "ollama_manifest_sha256": expected_manifest,
        "ollama_weight_sha256": expected_weight.removeprefix("sha256-"),
        "hosted_key_present": bool(os.environ.get("OPENAI_API_KEY")),
    }


def preflight(
    *,
    project_root: Path,
    acquisition_root: Path,
    collection_root: Path,
    authorized_schedule_sha256: str,
    require_hosted: bool,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    base = project_root / "benchmarks/contexttrace_unseen_v1"
    schedule_path = base / "generation_schedule.json"
    source_path = base / "candidate_source_manifest.json"
    actual_schedule_hash = sha256_file(schedule_path)
    if authorized_schedule_sha256 != AUTHORIZED_SCHEDULE_SHA256:
        raise CollectionError("CLI authorization hash is not the recorded authorization.")
    if actual_schedule_hash != authorized_schedule_sha256:
        raise CollectionError("Generation schedule hash differs from the authorization.")
    sidecar_text = schedule_path.with_suffix(".json.sha256").read_text(
        encoding="utf-8"
    )
    sidecar_fields = sidecar_text.split()
    sidecar = sidecar_fields[0] if sidecar_fields else ""
    if sidecar != actual_schedule_hash:
        raise CollectionError("Generation schedule hash sidecar differs from the schedule.")
    authorization = (base / "NATURAL_OOD_RUN_AUTHORIZATION.md").read_text(
        encoding="utf-8"
    )
    if authorized_schedule_sha256 not in authorization or "$10 hard ceiling" not in authorization:
        raise CollectionError("Recorded authorization text is absent or incomplete.")
    schedule = load_json(schedule_path)
    sources = load_json(source_path)
    validate_schedule(schedule, sources)
    if sha256_file(source_path) != schedule["source_manifest"]["sha256"]:
        raise CollectionError("Source manifest differs from the generation lock.")
    acquisition = validate_acquisition(
        catalog=load_json(base / "pre_acquisition_catalog.json"),
        calibration=load_json(base / "calibration/registry.json"),
        manifest=sources,
        ledger=load_json(base / "acquisition_ledger.json"),
        workspace=acquisition_root,
        source_schema=base / "source_manifest.schema.json",
    )
    if schedule["scope"]["temporal_source_condition"]["scheduled_cases"] != 0:
        raise CollectionError("Temporal cases unexpectedly appear in the authorized schedule.")
    if len(schedule["cases"]) != 396:
        raise CollectionError("Authorized Natural OOD case count is not 396.")
    environment = verify_environment(schedule, require_hosted=require_hosted)
    collection_root.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(collection_root, 0o700)
    record = {
        "status": "valid",
        "checked_at": utc_now(),
        "schedule_sha256": actual_schedule_hash,
        "case_count": len(schedule["cases"]),
        "source_validation": acquisition,
        "environment": environment,
        "model_calls": 0,
        "verifier_calls": 0,
        "labels_accessible": False,
    }
    atomic_json(collection_root / "preflight.json", record)
    return schedule, sources, record


class CollectionRunner:
    def __init__(
        self,
        *,
        schedule: Mapping[str, Any],
        sources: Mapping[str, Any],
        acquisition_root: Path,
        output_root: Path,
        transport: TransportClient | None = None,
    ) -> None:
        self.schedule = schedule
        self.output_root = output_root
        self.acquisition_root = acquisition_root
        self.transport = transport or TransportClient(schedule["execution_controls"])
        self.source_index = {
            str(source["source_id"]): dict(source) for source in sources["sources"]
        }
        self.chunking = component_index(schedule, "chunking")
        self.retrieval = component_index(schedule, "retrieval")
        self.reranking = component_index(schedule, "reranking")
        self.generators = component_index(schedule, "generators")
        self.prompts = component_index(schedule, "prompts")
        self.query_author = dict(schedule["components"]["query_authoring"])
        vector_component = next(
            value for value in self.retrieval.values() if value["family"] == "vector"
        )
        self.encoder = DenseEncoder(vector_component)
        self.embedding_cache = EmbeddingCache(output_root / "cache/embeddings", self.encoder)
        self.budget = BudgetLedger(
            output_root / "budget_ledger.json",
            AUTHORIZED_SCHEDULE_SHA256,
            schedule["execution_controls"]["hosted_cost_guard_usd"],
        )
        self.documents: dict[str, list[Document]] = {}
        self.chunks: dict[tuple[str, str], list[Chunk]] = {}

    def state_path(self, case_id: str) -> Path:
        return self.output_root / "records" / f"{case_id}.json"

    def raw_path(self, case_id: str, stage: str, attempt: int) -> Path:
        return self.output_root / "raw" / f"{case_id}.{stage}.attempt-{attempt}.json"

    def load_state(self, case: Mapping[str, Any]) -> dict[str, Any]:
        path = self.state_path(str(case["case_id"]))
        if not path.is_file():
            return {
                "schema_version": "1.0",
                "case_id": case["case_id"],
                "configuration_sha256": case["configuration_sha256"],
                "schedule_sha256": AUTHORIZED_SCHEDULE_SHA256,
                "status": "not_started",
                "attempts": [],
            }
        state = load_json(path)
        if (
            state.get("configuration_sha256") != case["configuration_sha256"]
            or state.get("schedule_sha256") != AUTHORIZED_SCHEDULE_SHA256
        ):
            raise CollectionError(f"Resume state mismatch for {case['case_id']}.")
        pending = [item for item in state["attempts"] if item["status"] == "reserved"]
        if pending:
            raise PendingAttemptError(
                f"Case {case['case_id']} has an unsettled local/provider attempt."
            )
        return state

    def save_state(self, state: Mapping[str, Any]) -> None:
        atomic_json(self.state_path(str(state["case_id"])), state)

    def source_documents(self, source: Mapping[str, Any]) -> list[Document]:
        source_id = str(source["source_id"])
        if source_id not in self.documents:
            path = self.acquisition_root / str(source["normalized_text_path"])
            self.documents[source_id] = parse_documents(path.read_text(encoding="utf-8"))
        return self.documents[source_id]

    def source_chunks(
        self,
        source: Mapping[str, Any],
        chunking: Mapping[str, Any],
    ) -> list[Chunk]:
        key = (str(source["source_id"]), str(chunking["id"]))
        if key not in self.chunks:
            self.chunks[key] = chunk_documents(
                self.source_documents(source),
                source_id=str(source["source_id"]),
                size=int(chunking["size"]),
                overlap=int(chunking["overlap"]),
            )
        return self.chunks[key]

    def _attempt_local(
        self,
        *,
        case_id: str,
        stage: str,
        payload: Mapping[str, Any],
        state: dict[str, Any],
    ) -> ModelResult:
        maximum = int(
            self.schedule["execution_controls"]["retry_policy"]["maximum_attempts"]
        )
        for attempt_number in range(1, maximum + 1):
            attempt_id = f"{case_id}:{stage}:{attempt_number}"
            attempt = {
                "attempt_id": attempt_id,
                "stage": stage,
                "attempt_number": attempt_number,
                "provider": "Ollama",
                "payload_sha256": sha256_bytes(canonical_json(payload).encode("utf-8")),
                "status": "reserved",
                "reserved_at": utc_now(),
            }
            state["attempts"].append(attempt)
            self.save_state(state)
            try:
                result = self.transport.ollama(payload)
            except (httpx.ConnectTimeout, httpx.ReadTimeout, RetryableTransportError) as exc:
                attempt.update(
                    {
                        "status": "retryable_transport_failure",
                        "settled_at": utc_now(),
                        "error_type": type(exc).__name__,
                    }
                )
                self.save_state(state)
                if attempt_number < maximum:
                    time.sleep(2)
                    continue
                raise
            except Exception as exc:
                attempt.update(
                    {
                        "status": "nonretryable_failure",
                        "settled_at": utc_now(),
                        "error_type": type(exc).__name__,
                    }
                )
                self.save_state(state)
                raise
            raw_path = self.raw_path(case_id, stage, attempt_number)
            atomic_json(raw_path, result.raw)
            attempt.update(
                {
                    "status": "completed",
                    "settled_at": utc_now(),
                    "raw_artifact": str(raw_path.relative_to(self.output_root)),
                    "raw_sha256": sha256_file(raw_path),
                    "elapsed_ms": result.elapsed_ms,
                }
            )
            self.save_state(state)
            return result
        raise AssertionError("unreachable")

    def _attempt_openai(
        self,
        *,
        case_id: str,
        payload: Mapping[str, Any],
        state: dict[str, Any],
    ) -> ModelResult:
        guard = self.schedule["execution_controls"]["hosted_cost_guard_usd"]
        maximum = int(self.schedule["execution_controls"]["retry_policy"]["maximum_attempts"])
        upper_cost = request_upper_cost(payload, guard)
        payload_hash = sha256_bytes(canonical_json(payload).encode("utf-8"))
        for attempt_number in range(1, maximum + 1):
            attempt_id = f"{case_id}:answer:{attempt_number}"
            attempt = {
                "attempt_id": attempt_id,
                "stage": "answer",
                "attempt_number": attempt_number,
                "provider": "OpenAI",
                "payload_sha256": payload_hash,
                "status": "reserved",
                "reserved_at": utc_now(),
            }
            state["attempts"].append(attempt)
            self.save_state(state)
            self.budget.reserve(attempt_id, upper_cost, payload_hash)
            try:
                result = self.transport.openai(payload)
            except (httpx.ConnectTimeout, httpx.ReadTimeout, RetryableTransportError) as exc:
                self.budget.settle(
                    attempt_id,
                    status="retryable_transport_failure",
                    charged_cost=upper_cost,
                    charge_basis="conservative_failed_attempt",
                    usage=None,
                )
                attempt.update(
                    {
                        "status": "retryable_transport_failure",
                        "settled_at": utc_now(),
                        "error_type": type(exc).__name__,
                    }
                )
                self.save_state(state)
                if attempt_number < maximum:
                    time.sleep(2)
                    continue
                raise
            except Exception as exc:
                self.budget.settle(
                    attempt_id,
                    status="nonretryable_failure",
                    charged_cost=upper_cost,
                    charge_basis="conservative_failed_attempt",
                    usage=None,
                )
                attempt.update(
                    {
                        "status": "nonretryable_failure",
                        "settled_at": utc_now(),
                        "error_type": type(exc).__name__,
                    }
                )
                self.save_state(state)
                raise
            charged, basis = actual_openai_cost(
                result.usage, upper_cost=upper_cost, guard=guard
            )
            self.budget.settle(
                attempt_id,
                status="completed",
                charged_cost=charged,
                charge_basis=basis,
                usage=result.usage,
            )
            raw_path = self.raw_path(case_id, "answer", attempt_number)
            atomic_json(raw_path, result.raw)
            attempt.update(
                {
                    "status": "completed",
                    "settled_at": utc_now(),
                    "raw_artifact": str(raw_path.relative_to(self.output_root)),
                    "raw_sha256": sha256_file(raw_path),
                    "elapsed_ms": result.elapsed_ms,
                }
            )
            self.save_state(state)
            return result
        raise AssertionError("unreachable")

    def collect_case(self, case: Mapping[str, Any]) -> str:
        case_id = str(case["case_id"])
        state = self.load_state(case)
        if state["status"] == "completed":
            return "resumed_completed"
        if state["status"] == "collection_failure":
            return "resumed_failure"
        source = self.source_index[str(case["source_id"])]
        documents = self.source_documents(source)
        if "query" not in state:
            excerpt, excerpt_id = deterministic_seed_excerpt(
                documents, case_seed=int(case["case_seed"])
            )
            query_user = self.query_author["user_template"].format(
                question_style=case["query_plan"]["question_style"],
                source_family=case["source_family"],
                seed_excerpt=excerpt,
            )
            query_payload = ollama_payload(
                self.query_author,
                system_prompt=self.query_author["system"],
                user_prompt=query_user,
                seed=int(case["case_seed"]),
            )
            try:
                query_result = self._attempt_local(
                    case_id=case_id,
                    stage="query",
                    payload=query_payload,
                    state=state,
                )
            except Exception as exc:
                state.update(
                    {
                        "status": "collection_failure",
                        "failed_stage": "query_transport",
                        "failure_type": type(exc).__name__,
                        "failed_at": utc_now(),
                    }
                )
                self.save_state(state)
                return "failed"
            invalid = validate_query(query_result.text)
            if invalid:
                state.update(
                    {
                        "status": "collection_failure",
                        "failed_stage": "query_validation",
                        "failure_type": invalid,
                        "failed_at": utc_now(),
                    }
                )
                self.save_state(state)
                return "failed"
            state.update(
                {
                    "status": "query_completed",
                    "query": query_result.text,
                    "query_completed_at": query_result.completed_at,
                    "seed_excerpt_id": excerpt_id,
                    "seed_excerpt_sha256": sha256_bytes(excerpt.encode("utf-8")),
                }
            )
            self.save_state(state)
        query = str(state["query"])
        chunking = self.chunking[str(case["chunking_configuration_id"])]
        retrieval = self.retrieval[str(case["retrieval_configuration_id"])]
        reranking_component = self.reranking[str(case["reranking_configuration_id"])]
        chunks = self.source_chunks(source, chunking)
        embeddings: np.ndarray | None = None
        if retrieval["family"] in {"vector", "hybrid"}:
            embeddings = self.embedding_cache.embeddings(
                source=source, chunking=chunking, chunks=chunks
            )
        candidate_indices = retrieve(
            query,
            chunks,
            retrieval,
            embeddings=embeddings,
            encoder=self.encoder,
        )
        ranked_indices = rerank(query, candidate_indices, chunks, reranking_component)
        retrieved_chunks = [chunks[index] for index in ranked_indices]
        selected = retrieved_chunks[: int(case["selected_context_count"])]
        if len(selected) != int(case["selected_context_count"]):
            state.update(
                {
                    "status": "collection_failure",
                    "failed_stage": "retrieval_structure",
                    "failure_type": "insufficient_locked_contexts",
                    "available_contexts": len(selected),
                    "required_contexts": int(case["selected_context_count"]),
                    "failed_at": utc_now(),
                }
            )
            self.save_state(state)
            return "failed"
        prompt = self.prompts[str(case["prompt_id"])]
        answer_user = prompt["user_template"].format(
            question=query,
            contexts=format_contexts(selected),
            length_instruction=prompt["length_instruction"],
            citation_instruction=prompt["citation_instruction"],
        )
        generator = self.generators[str(case["generator_configuration_id"])]
        try:
            if generator["provider"] == "Ollama":
                answer_payload = ollama_payload(
                    generator,
                    system_prompt=prompt["system"],
                    user_prompt=answer_user,
                    seed=int(case["case_seed"]),
                )
                answer_result = self._attempt_local(
                    case_id=case_id,
                    stage="answer",
                    payload=answer_payload,
                    state=state,
                )
            elif generator["provider"] == "OpenAI":
                answer_payload = openai_payload(
                    generator,
                    system_prompt=prompt["system"],
                    user_prompt=answer_user,
                )
                answer_result = self._attempt_openai(
                    case_id=case_id,
                    payload=answer_payload,
                    state=state,
                )
            else:
                raise CollectionError(f"Unsupported locked generator: {generator['provider']}")
        except Exception as exc:
            state.update(
                {
                    "status": "collection_failure",
                    "failed_stage": "answer_transport",
                    "failure_type": type(exc).__name__,
                    "failed_at": utc_now(),
                }
            )
            self.save_state(state)
            return "failed"
        trace = {
            "case_id": case_id,
            "query": query,
            "answer": answer_result.text,
            "retrieved_chunks": [
                {
                    "id": chunk.id,
                    "text": chunk.text,
                    "source_id": source["source_id"],
                    "document_path": chunk.document_path,
                    "chunk_index": chunk.chunk_index,
                }
                for chunk in retrieved_chunks
            ],
            "selected_context_ids": [chunk.id for chunk in selected],
            "citations": extract_citations(
                answer_result.text,
                citation_format=str(case["citation_format"]),
                selected=selected,
            ),
        }
        trace_path = self.output_root / "traces" / f"{case_id}.json"
        atomic_json(trace_path, trace)
        rerank_enabled = bool(reranking_component["enabled"])
        manifest_case = {
            "case_id": case_id,
            "track": "natural_ood",
            "split": "untouched_test_candidate",
            "source_ids": [source["source_id"]],
            "primary_source_id": source["source_id"],
            "source_family": source["source_family"],
            "source_document_id": source["source_document_id"],
            "domain_group": source["domain_group"],
            "domain_id": source["domain_id"],
            "publication_window": source["publication_window"],
            "source_url": source["source_url"],
            "canonical_identifier": source["canonical_identifier"],
            "source_snapshot_sha256": source["snapshot_sha256"],
            "retrieval": {
                "family": retrieval["family"],
                "implementation": retrieval["implementation"],
                "revision": retrieval["revision"],
                "top_k": retrieval["candidate_k"],
                "configuration_sha256": retrieval["configuration_sha256"],
            },
            "chunking": {
                "strategy": chunking["strategy"],
                "size": chunking["size"],
                "overlap": chunking["overlap"],
                "unit": chunking["unit"],
                "configuration_sha256": chunking["configuration_sha256"],
            },
            "reranking": {
                "enabled": rerank_enabled,
                "implementation": reranking_component["implementation"],
                "revision": reranking_component["revision"],
                "top_n": len(selected) if rerank_enabled else None,
                "configuration_sha256": reranking_component["configuration_sha256"],
            },
            "generator": {
                "provider": generator["provider"],
                "model": generator["model"],
                "model_family": generator["model_family"],
                "revision": generator.get("manifest_digest", generator["model"]),
                "configuration_sha256": generator["configuration_sha256"],
            },
            "prompt_sha256": prompt["configuration_sha256"],
            "generation_parameters": generator["parameters"],
            "collection_timestamp": answer_result.completed_at,
            "trace_schema_version": TRACE_SCHEMA_VERSION,
            "license_access": {
                "license_ids": [source["license"]["license_id"]],
                "redistribution": source["license"]["redistribution"],
            },
            "privacy_classification": (
                "public_pii_reviewed"
                if source["privacy_classification"] == "public_pii_review_required"
                else "public"
            ),
            "origin": "natural_rag_run",
            "untouched_eligible": True,
            "labels_accessible_at_generation": False,
            "verifier_history": [],
            "trace_artifact_path": str(trace_path.relative_to(self.output_root)),
            "trace_sha256": sha256_file(trace_path),
            "retrieved_chunk_ids": [chunk.id for chunk in retrieved_chunks],
            "selected_context_ids": [chunk.id for chunk in selected],
            "citation_format": case["citation_format"],
            "answer_length_chars": len(answer_result.text),
            "context_count": len(selected),
            "generation_status": "completed",
            "configuration_sha256": case["configuration_sha256"],
            "metadata": {
                "answer_length": case["answer_length"],
                "question_style": case["query_plan"]["question_style"],
                "case_seed": case["case_seed"],
                "query_authoring_configuration_sha256": self.query_author[
                    "configuration_sha256"
                ],
            },
        }
        state.update(
            {
                "status": "completed",
                "completed_at": answer_result.completed_at,
                "trace_artifact": str(trace_path.relative_to(self.output_root)),
                "trace_sha256": sha256_file(trace_path),
                "manifest_case": manifest_case,
            }
        )
        self.save_state(state)
        return "completed"

    def write_candidate_manifest(self) -> dict[str, Any]:
        completed: list[dict[str, Any]] = []
        failures: list[dict[str, Any]] = []
        for case in self.schedule["cases"]:
            path = self.state_path(str(case["case_id"]))
            if not path.is_file():
                continue
            state = load_json(path)
            if state["status"] == "completed":
                completed.append(state["manifest_case"])
            elif state["status"] == "collection_failure":
                failures.append(
                    {
                        "case_id": state["case_id"],
                        "failed_stage": state["failed_stage"],
                        "failure_type": state["failure_type"],
                    }
                )
        manifest = {
            "schema_version": "1.0",
            "manifest_kind": "contexttrace_unseen_v1_cases",
            "created_at": utc_now(),
            "collection_protocol_version": COLLECTION_PROTOCOL_VERSION,
            "claim_policy_version": "contexttrace-unseen-claim-policy-v1",
            "label_access": {
                "labels_created": False,
                "labels_accessible": False,
                "first_accessed_at": None,
                "custodian": None,
            },
            "cases": sorted(completed, key=lambda value: value["case_id"]),
        }
        atomic_json(self.output_root / "candidate_case_manifest.json", manifest)
        summary = {
            "status": (
                "complete"
                if len(completed) + len(failures) == len(self.schedule["cases"])
                else "in_progress"
            ),
            "updated_at": utc_now(),
            "schedule_sha256": AUTHORIZED_SCHEDULE_SHA256,
            "scheduled_cases": len(self.schedule["cases"]),
            "completed_cases": len(completed),
            "collection_failures": failures,
            "hosted_charged_cost_usd": self.budget.charged_total(),
            "hard_ceiling_usd": float(self.budget.guard["hard_limit"]),
            "labels_created": False,
            "verifier_calls": 0,
        }
        atomic_json(self.output_root / "collection_summary.json", summary)
        return summary

    def run(self, *, case_limit: int | None = None) -> dict[str, Any]:
        cases = list(self.schedule["cases"])
        if case_limit is not None:
            if case_limit < 1:
                raise CollectionError("--case-limit must be positive.")
            cases = cases[:case_limit]
        for index, case in enumerate(cases, start=1):
            outcome = self.collect_case(case)
            print(
                json.dumps(
                    {
                        "progress": f"{index}/{len(cases)}",
                        "case_id": case["case_id"],
                        "outcome": outcome,
                        "hosted_charged_cost_usd": round(
                            self.budget.charged_total(), 8
                        ),
                    },
                    sort_keys=True,
                ),
                flush=True,
            )
        return self.write_candidate_manifest()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        choices=("preflight", "run"),
        help="preflight makes no model calls; run executes the exact locked schedule",
    )
    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path("."),
    )
    parser.add_argument(
        "--acquisition-root",
        type=Path,
        default=Path(".tmp-contexttrace-unseen-v1-acquisition"),
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path(".tmp-contexttrace-unseen-v1-collection"),
    )
    parser.add_argument(
        "--authorized-schedule-sha256",
        required=True,
        help="must exactly match the recorded project-owner authorization",
    )
    parser.add_argument(
        "--case-limit",
        type=int,
        help="run only the first N scheduled cases; intended for controlled pilot/resume",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        schedule, sources, record = preflight(
            project_root=args.project_root.resolve(),
            acquisition_root=args.acquisition_root.resolve(),
            collection_root=args.output_root.resolve(),
            authorized_schedule_sha256=args.authorized_schedule_sha256,
            require_hosted=args.command == "run",
        )
        if args.command == "preflight":
            print(json.dumps(record, indent=2, sort_keys=True))
            return 0
        runner = CollectionRunner(
            schedule=schedule,
            sources=sources,
            acquisition_root=args.acquisition_root.resolve(),
            output_root=args.output_root.resolve(),
        )
        result = runner.run(case_limit=args.case_limit)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except (
        CollectionError,
        OSError,
        ValueError,
        subprocess.SubprocessError,
        httpx.HTTPError,
    ) as exc:
        print(f"Natural OOD collection stopped: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
