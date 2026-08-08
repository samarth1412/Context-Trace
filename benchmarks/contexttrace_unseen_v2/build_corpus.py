"""Acquire and freeze the unlabeled ContextTrace-Unseen-v2 RAG corpus.

The module is intentionally independent of ContextTrace verifier packages. It
downloads only the precommitted source catalog, performs real BM25/vector/hybrid
retrieval, calls two local Ollama generators, and writes no diagnostic labels.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import math
import os
import re
import subprocess
import tempfile
import time
import xml.etree.ElementTree as ET
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

import httpx
import numpy as np

HERE = Path(__file__).resolve().parent
DEFAULT_CATALOG = HERE / "SOURCE_CATALOG.json"
TRACE_SCHEMA_VERSION = "contexttrace-unseen-v2-unlabeled-trace-1.0"
MANIFEST_SCHEMA_VERSION = "contexttrace-unseen-v2-unlabeled-manifest-1.0"
SUPPORTED_SUFFIXES = {
    ".adoc",
    ".html",
    ".htm",
    ".md",
    ".mdx",
    ".rst",
    ".sgml",
    ".txt",
    ".xml",
    ".yaml",
    ".yml",
}
TOKEN_RE = re.compile(r"\w+|[^\w\s]", re.UNICODE)
LEXICAL_RE = re.compile(r"[A-Za-z0-9_./:+#-]+", re.UNICODE)
QUESTION_LINE_RE = re.compile(r"^\s*(?:Q\s*)?\d+[.):]\s*(.+?)\s*$", re.MULTILINE)
LABEL_KEYS = {
    "abstention_requirement",
    "adjudication",
    "claim_verdict",
    "failure_label",
    "gold",
    "gold_label",
    "labels",
    "primary_root_cause",
    "source_condition_label",
    "verdict",
}
MAX_SOURCE_CHARS = 1_500_000
NATURAL_CASES_PER_SOURCE = 10
TEMPORAL_CASES_PER_PAIR = 5
OLLAMA_URL = "http://127.0.0.1:11434/api/chat"
GENERATOR_MODELS = ("gemma3:4b", "qwen3:1.7b")


class CorpusBuildError(RuntimeError):
    """Raised when a frozen corpus invariant would be violated."""


@dataclass(frozen=True)
class Document:
    path: str
    text: str


@dataclass(frozen=True)
class Chunk:
    id: str
    source_id: str
    document_path: str
    index: int
    text: str


class _HTMLText(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self._ignored_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        del attrs
        if tag in {"script", "style", "svg", "noscript"}:
            self._ignored_depth += 1
        elif tag in {
            "br",
            "dd",
            "div",
            "dt",
            "h1",
            "h2",
            "h3",
            "h4",
            "li",
            "p",
            "pre",
            "tr",
        }:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "svg", "noscript"}:
            self._ignored_depth = max(0, self._ignored_depth - 1)
        elif tag in {"dd", "div", "dt", "h1", "h2", "h3", "h4", "li", "p", "pre", "tr"}:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._ignored_depth:
            self.parts.append(data)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    parser.add_argument("--candidate-freeze", type=Path, required=True)
    parser.add_argument("--development-manifest", type=Path, required=True)
    parser.add_argument("--embedding-model-path", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args(argv)
    result = build_corpus(
        catalog_path=args.catalog,
        candidate_freeze_path=args.candidate_freeze,
        development_manifest_path=args.development_manifest,
        embedding_model_path=args.embedding_model_path,
        output_root=args.output_root,
        resume=args.resume,
    )
    print(
        json.dumps(
            {
                "case_count": result["case_count"],
                "manifest_payload_sha256": result["seal"]["payload_sha256"],
                "source_count": result["source_count"],
                "status": result["status"],
            },
            sort_keys=True,
        )
    )
    return 0


def build_corpus(
    *,
    catalog_path: Path,
    candidate_freeze_path: Path,
    development_manifest_path: Path,
    embedding_model_path: Path,
    output_root: Path,
    resume: bool = False,
) -> dict[str, Any]:
    catalog = _read_object(catalog_path)
    candidate_freeze = _read_object(candidate_freeze_path)
    development = _read_object(development_manifest_path)
    _validate_boundaries(catalog, candidate_freeze, development)
    if output_root.exists() and not resume:
        raise FileExistsError("Corpus output exists; pass --resume to continue it.")
    output_root.mkdir(parents=True, exist_ok=True)
    manifest_path = output_root / "contexttrace_unseen_v2_frozen_unlabeled.json"
    if manifest_path.exists():
        raise FileExistsError("The frozen Unseen-v2 manifest already exists.")
    lock_path = output_root / ".collection.lock"
    lock_fd = _acquire_lock(lock_path)
    try:
        return _build_locked(
            catalog=catalog,
            catalog_path=catalog_path,
            candidate_freeze=candidate_freeze,
            candidate_freeze_path=candidate_freeze_path,
            development=development,
            embedding_model_path=embedding_model_path,
            output_root=output_root,
            manifest_path=manifest_path,
        )
    finally:
        os.close(lock_fd)
        lock_path.unlink(missing_ok=True)


def _build_locked(
    *,
    catalog: Mapping[str, Any],
    catalog_path: Path,
    candidate_freeze: Mapping[str, Any],
    candidate_freeze_path: Path,
    development: Mapping[str, Any],
    embedding_model_path: Path,
    output_root: Path,
    manifest_path: Path,
) -> dict[str, Any]:
    source_root = output_root / "sources"
    trace_root = output_root / "traces"
    source_root.mkdir(exist_ok=True)
    trace_root.mkdir(exist_ok=True)
    client = httpx.Client(
        timeout=httpx.Timeout(180.0, connect=30.0),
        follow_redirects=True,
        headers={"User-Agent": "ContextTrace-Unseen-v2 research corpus"},
    )
    try:
        natural_sources = [
            _acquire_source(source, source_root, client)
            for source in catalog["natural_sources"]
        ]
        temporal_pairs = [
            _acquire_pair(pair, source_root, client)
            for pair in catalog["temporal_pairs"]
        ]
    finally:
        client.close()

    all_sources = [
        *natural_sources,
        *(source for pair in temporal_pairs for source in pair["sources"]),
    ]
    _validate_acquired_sources(all_sources, development)
    encoder = _DenseEncoder(embedding_model_path)
    ollama_lock = _ollama_lock()
    journal_path = output_root / "generation-journal.jsonl"
    completed = _read_journal(journal_path)
    completed_by_id = {str(row["case_id"]): row for row in completed}
    if len(completed_by_id) != len(completed):
        raise CorpusBuildError("Generation journal contains duplicate case IDs.")

    natural_records: list[dict[str, Any]] = []
    with journal_path.open(
        "a" if journal_path.exists() else "x", encoding="utf-8"
    ) as journal:
        for source in natural_sources:
            questions = _load_or_generate_questions(
                output_root=output_root,
                key=str(source["source_id"]),
                documents=_documents_from_record(source),
                count=NATURAL_CASES_PER_SOURCE,
                model="gemma3:4b",
                seed=_seed(str(source["source_id"])),
                temporal=False,
            )
            for index, question in enumerate(questions, start=1):
                case_id = f"ctu2_natural_{source['source_family']}_{index:02d}"
                row = completed_by_id.get(case_id)
                if row is None:
                    row = _generate_case(
                        case_id=case_id,
                        track="natural_ood",
                        question=question,
                        source_records=[source],
                        index=index - 1,
                        encoder=encoder,
                        trace_root=trace_root,
                    )
                    journal.write(
                        json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"
                    )
                    journal.flush()
                    completed_by_id[case_id] = row
                else:
                    _validate_completed_case(
                        row,
                        case_id=case_id,
                        track="natural_ood",
                        source_ids=[str(source["source_id"])],
                        trace_root=trace_root,
                    )
                natural_records.append(row)

        temporal_records: list[dict[str, Any]] = []
        for pair in temporal_pairs:
            questions = _load_or_generate_questions(
                output_root=output_root,
                key=str(pair["pair_id"]),
                documents=[
                    document
                    for source in pair["sources"]
                    for document in _documents_from_record(source)
                ],
                count=TEMPORAL_CASES_PER_PAIR,
                model="gemma3:4b",
                seed=_seed(str(pair["pair_id"])),
                temporal=True,
            )
            for index, question in enumerate(questions, start=1):
                case_id = f"ctu2_temporal_{pair['pair_id']}_{index:02d}"
                row = completed_by_id.get(case_id)
                if row is None:
                    row = _generate_case(
                        case_id=case_id,
                        track="temporal_source_condition",
                        question=question,
                        source_records=list(pair["sources"]),
                        index=index - 1,
                        encoder=encoder,
                        trace_root=trace_root,
                        pair=pair,
                    )
                    journal.write(
                        json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"
                    )
                    journal.flush()
                    completed_by_id[case_id] = row
                else:
                    _validate_completed_case(
                        row,
                        case_id=case_id,
                        track="temporal_source_condition",
                        source_ids=[
                            str(source["source_id"]) for source in pair["sources"]
                        ],
                        trace_root=trace_root,
                    )
                temporal_records.append(row)

    rows = [*natural_records, *temporal_records]
    if len(rows) != 400 or len({row["case_id"] for row in rows}) != 400:
        raise CorpusBuildError("The generated corpus is not exactly 400 unique cases.")
    artifacts = _artifact_manifest(output_root, rows, all_sources)
    manifest: dict[str, Any] = {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "manifest_kind": "frozen_unlabeled_test_manifest",
        "dataset_id": "ContextTrace-Unseen-v2",
        "status": "frozen_unlabeled_unscored_unannotated",
        "frozen_at": _utc_now(),
        "candidate_freeze": {
            "file_sha256": _file_sha256(candidate_freeze_path),
            "payload_sha256": candidate_freeze["freeze_payload_sha256"],
            "candidate_git_commit": candidate_freeze["candidate"]["git_commit"],
            "candidate_profile_sha256": candidate_freeze["candidate"]["profile_sha256"],
        },
        "source_catalog_sha256": _file_sha256(catalog_path),
        "development_manifest_payload_sha256": development["seal"]["payload_sha256"],
        "collection_implementation": {
            "module": "benchmarks.contexttrace_unseen_v2.build_corpus",
            "file_sha256": _file_sha256(Path(__file__)),
        },
        "embedding_model": encoder.lock,
        "generators": ollama_lock,
        "case_count": len(rows),
        "source_count": len(all_sources),
        "composition": {
            "natural_ood": len(natural_records),
            "temporal_source_condition": len(temporal_records),
            "domain_groups": _counter(row["domain_group"] for row in natural_records),
            "retrieval_families": _counter(row["retrieval"]["family"] for row in rows),
            "generator_models": _counter(row["generator"]["model"] for row in rows),
            "chunk_sizes": _counter(row["chunking"]["size"] for row in rows),
            "reranking": _counter(row["reranking"]["enabled"] for row in rows),
        },
        "sources": [_public_source_record(source) for source in all_sources],
        "cases": rows,
        "artifacts": artifacts,
        "integrity": {
            "labels_present": False,
            "verifier_calls": 0,
            "nli_calls": 0,
            "competitor_calls": 0,
            "paid_api_calls": 0,
            "source_family_overlap_with_development": 0,
            "domain_id_overlap_with_development": 0,
            "normalized_content_overlap_with_development": 0,
        },
    }
    if _contains_label_key(manifest):
        raise CorpusBuildError(
            "The unlabeled manifest contains a prohibited label key."
        )
    manifest["seal"] = {
        "algorithm": "sha256",
        "payload_sha256": _canonical_sha256(manifest),
    }
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    sidecar = manifest_path.with_suffix(manifest_path.suffix + ".sha256")
    sidecar.write_text(
        f"{_file_sha256(manifest_path)}  {manifest_path.name}\n", encoding="utf-8"
    )
    freeze_record = {
        "schema_version": "1.0",
        "record_kind": "contexttrace_unseen_v2_unlabeled_freeze",
        "status": "complete_pending_independent_annotation",
        "manifest_file_sha256": _file_sha256(manifest_path),
        "manifest_payload_sha256": manifest["seal"]["payload_sha256"],
        "case_count": 400,
        "source_count": len(all_sources),
        "labels_created": False,
        "candidate_executed": False,
        "evaluation_authorized": False,
    }
    freeze_record["payload_sha256"] = _canonical_sha256(freeze_record)
    (output_root / "freeze-record.json").write_text(
        json.dumps(freeze_record, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest


def _acquire_source(
    source: Mapping[str, Any], source_root: Path, client: httpx.Client
) -> dict[str, Any]:
    source_id = str(source["source_id"])
    record_path = source_root / f"{source_id}.json"
    normalized_path = source_root / f"{source_id}.txt"
    if record_path.exists() and normalized_path.exists():
        record = _read_object(record_path)
        if record.get("catalog_entry_sha256") != _canonical_sha256(source):
            raise CorpusBuildError(
                f"Existing source differs from catalog: {source_id}."
            )
        if _file_sha256(normalized_path) != record.get("normalized_content_sha256"):
            raise CorpusBuildError(
                f"Existing normalized source hash mismatch: {source_id}."
            )
        record["normalized_path"] = str(normalized_path)
        return record

    if source["kind"] == "github_archive":
        documents, acquisition = _acquire_github_documents(source)
    elif source["kind"] == "ecfr_xml":
        documents, acquisition = _acquire_ecfr_documents(source, client)
    else:
        raise CorpusBuildError(f"Unsupported natural source kind: {source['kind']}.")
    return _write_source_record(
        source=source,
        documents=documents,
        acquisition=acquisition,
        record_path=record_path,
        normalized_path=normalized_path,
        conditions=["current", "canonical"],
    )


def _acquire_pair(
    pair: Mapping[str, Any], source_root: Path, client: httpx.Client
) -> dict[str, Any]:
    pair_id = str(pair["pair_id"])
    if pair.get("repository"):
        old_entry = {
            "source_id": f"{pair_id}_old",
            "source_family": pair_id,
            "domain_group": "temporal_source_condition",
            "domain_id": pair["domain_id"],
            "kind": "github_archive",
            "repository": pair["repository"],
            "revision": pair["old_revision"],
            "content_root": pair["content_root"],
            "license_id": pair["license_id"],
            "publication_window": "archived_pre_2026",
        }
        current_entry = {
            **old_entry,
            "source_id": f"{pair_id}_current",
            "revision": pair["current_revision"],
            "publication_window": "current_2026",
        }
        old = _acquire_temporal_source(
            old_entry, source_root, client, ["archived", "superseded"]
        )
        current = _acquire_temporal_source(
            current_entry, source_root, client, ["current", "canonical"]
        )
    elif pair.get("kind") == "ecfr_pair":
        common = {
            "source_family": pair_id,
            "domain_group": "temporal_source_condition",
            "domain_id": pair["domain_id"],
            "kind": "ecfr_xml",
            "title": pair["title"],
            "part": pair["part"],
            "license_id": "US-Government-Work",
        }
        old = _acquire_temporal_source(
            {
                **common,
                "source_id": f"{pair_id}_old",
                "revision": pair["old_revision"],
                "publication_window": "archived_2020",
            },
            source_root,
            client,
            ["archived", "superseded"],
        )
        current = _acquire_temporal_source(
            {
                **common,
                "source_id": f"{pair_id}_current",
                "revision": pair["current_revision"],
                "publication_window": "current_2026",
            },
            source_root,
            client,
            ["current", "canonical"],
        )
    elif pair.get("kind") == "authority_web_pair":
        common = {
            "source_family": pair_id,
            "domain_group": "temporal_source_condition",
            "domain_id": pair["domain_id"],
            "kind": "web_page",
            "license_id": "source_specific_public_web",
            "publication_window": "current_2026",
        }
        old = _acquire_temporal_source(
            {
                **common,
                "source_id": f"{pair_id}_low_authority",
                "url": pair["low_authority_url"],
            },
            source_root,
            client,
            ["current", "noncanonical", "low_authority"],
        )
        current = _acquire_temporal_source(
            {
                **common,
                "source_id": f"{pair_id}_authoritative",
                "url": pair["authoritative_url"],
            },
            source_root,
            client,
            ["current", "canonical", "high_authority"],
        )
    else:
        raise CorpusBuildError(f"Unsupported temporal pair: {pair_id}.")
    return {
        "pair_id": pair_id,
        "condition_type": pair["condition_type"],
        "domain_id": pair["domain_id"],
        "sources": [old, current],
    }


def _acquire_temporal_source(
    source: Mapping[str, Any],
    source_root: Path,
    client: httpx.Client,
    conditions: list[str],
) -> dict[str, Any]:
    source_id = str(source["source_id"])
    record_path = source_root / f"{source_id}.json"
    normalized_path = source_root / f"{source_id}.txt"
    if record_path.exists() and normalized_path.exists():
        record = _read_object(record_path)
        if record.get("catalog_entry_sha256") != _canonical_sha256(source):
            raise CorpusBuildError(
                f"Existing source differs from catalog: {source_id}."
            )
        if _file_sha256(normalized_path) != record.get("normalized_content_sha256"):
            raise CorpusBuildError(
                f"Existing normalized source hash mismatch: {source_id}."
            )
        record["normalized_path"] = str(normalized_path)
        return record
    if source["kind"] == "github_archive":
        documents, acquisition = _acquire_github_documents(source)
    elif source["kind"] == "ecfr_xml":
        documents, acquisition = _acquire_ecfr_documents(source, client)
    elif source["kind"] == "web_page":
        documents, acquisition = _acquire_web_document(source, client)
    else:  # pragma: no cover
        raise CorpusBuildError(f"Unsupported temporal source kind: {source['kind']}.")
    return _write_source_record(
        source=source,
        documents=documents,
        acquisition=acquisition,
        record_path=record_path,
        normalized_path=normalized_path,
        conditions=conditions,
    )


def _acquire_github_documents(
    source: Mapping[str, Any],
) -> tuple[list[Document], dict[str, Any]]:
    repository = str(source["repository"])
    revision = str(source["revision"])
    content_root = str(source["content_root"]).strip("/")
    with tempfile.TemporaryDirectory(prefix="contexttrace-unseen-v2-") as temporary:
        checkout = Path(temporary) / "repo"
        _run(["git", "init", "--quiet", str(checkout)])
        _run(
            [
                "git",
                "-C",
                str(checkout),
                "remote",
                "add",
                "origin",
                f"https://github.com/{repository}.git",
            ]
        )
        _run(["git", "-C", str(checkout), "sparse-checkout", "init", "--cone"])
        _run(["git", "-C", str(checkout), "sparse-checkout", "set", content_root])
        _run(
            [
                "git",
                "-C",
                str(checkout),
                "fetch",
                "--quiet",
                "--depth",
                "1",
                "origin",
                revision,
            ]
        )
        _run(
            [
                "git",
                "-C",
                str(checkout),
                "checkout",
                "--quiet",
                "--detach",
                "FETCH_HEAD",
            ]
        )
        resolved = _run(["git", "-C", str(checkout), "rev-parse", "HEAD"]).strip()
        if resolved != revision:
            raise CorpusBuildError(f"GitHub revision mismatch for {repository}.")
        root = checkout / content_root
        documents = _documents_from_directory(root, source_id=str(source["source_id"]))
        return documents, {
            "method": "git_sparse_checkout",
            "repository": repository,
            "revision": resolved,
            "content_root": content_root,
            "canonical_url": f"https://github.com/{repository}/tree/{revision}/{content_root}",
        }


def _acquire_ecfr_documents(
    source: Mapping[str, Any], client: httpx.Client
) -> tuple[list[Document], dict[str, Any]]:
    title = int(source["title"])
    part = int(source["part"])
    revision = str(source["revision"])
    url = f"https://www.ecfr.gov/api/versioner/v1/full/{revision}/title-{title}.xml?part={part}"
    response = client.get(url)
    response.raise_for_status()
    raw = response.content
    if not raw.lstrip().startswith(b"<"):
        raise CorpusBuildError(f"eCFR response is not XML: {url}.")
    text = " ".join(
        piece.strip() for piece in ET.fromstring(raw).itertext() if piece.strip()
    )
    if len(text) < 2000:
        raise CorpusBuildError(f"eCFR source is unexpectedly short: {url}.")
    return [Document(path=f"title-{title}-part-{part}.xml", text=text)], {
        "method": "ecfr_versioner_api",
        "url": url,
        "response_sha256": hashlib.sha256(raw).hexdigest(),
        "response_bytes": len(raw),
        "canonical_url": f"https://www.ecfr.gov/current/title-{title}/part-{part}",
    }


def _acquire_web_document(
    source: Mapping[str, Any], client: httpx.Client
) -> tuple[list[Document], dict[str, Any]]:
    url = str(source["url"])
    response = client.get(url)
    response.raise_for_status()
    raw = response.content
    parser = _HTMLText()
    parser.feed(response.text)
    text = _normalize_text(" ".join(parser.parts))
    if len(text) < 1500:
        raise CorpusBuildError(f"Web source is unexpectedly short: {url}.")
    return [Document(path=url, text=text)], {
        "method": "https_snapshot",
        "url": str(response.url),
        "response_sha256": hashlib.sha256(raw).hexdigest(),
        "response_bytes": len(raw),
        "canonical_url": url,
    }


def _documents_from_directory(root: Path, *, source_id: str) -> list[Document]:
    if not root.is_dir():
        raise CorpusBuildError(f"Cataloged content root is absent: {root}.")
    candidates = [
        path
        for path in root.rglob("*")
        if path.is_file()
        and path.suffix.casefold() in SUPPORTED_SUFFIXES
        and not any(part.startswith(".") for part in path.relative_to(root).parts)
    ]
    candidates.sort(
        key=lambda path: hashlib.sha256(
            f"{source_id}:{path.relative_to(root)}".encode()
        ).hexdigest()
    )
    documents: list[Document] = []
    total = 0
    for path in candidates:
        try:
            raw = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            raw = path.read_text(encoding="utf-8", errors="replace")
        text = _normalize_source_file(raw, suffix=path.suffix.casefold())
        if len(text) < 200:
            continue
        remaining = MAX_SOURCE_CHARS - total
        if remaining <= 0:
            break
        text = text[:remaining]
        documents.append(Document(path=str(path.relative_to(root)), text=text))
        total += len(text)
    if total < 20_000 or len(documents) < 3:
        raise CorpusBuildError(f"Cataloged documentation is too small: {root}.")
    return sorted(documents, key=lambda document: document.path)


def _write_source_record(
    *,
    source: Mapping[str, Any],
    documents: list[Document],
    acquisition: Mapping[str, Any],
    record_path: Path,
    normalized_path: Path,
    conditions: list[str],
) -> dict[str, Any]:
    combined = "\n\n".join(
        f"===== FILE: {document.path} =====\n{document.text}" for document in documents
    )
    normalized_path.write_text(combined + "\n", encoding="utf-8")
    file_rows = [
        {
            "path": document.path,
            "chars": len(document.text),
            "sha256": hashlib.sha256(document.text.encode()).hexdigest(),
        }
        for document in documents
    ]
    record: dict[str, Any] = {
        **dict(source),
        "catalog_entry_sha256": _canonical_sha256(source),
        "acquired_at": _utc_now(),
        "acquisition": dict(acquisition),
        "source_conditions": conditions,
        "document_count": len(documents),
        "selected_file_manifest_sha256": _canonical_sha256(file_rows),
        "selected_files": file_rows,
        "normalized_content_sha256": _file_sha256(normalized_path),
        "normalized_chars": len(combined),
    }
    record_path.write_text(
        json.dumps(record, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    record["normalized_path"] = str(normalized_path)
    return record


def _load_or_generate_questions(
    *,
    output_root: Path,
    key: str,
    documents: Sequence[Document],
    count: int,
    model: str,
    seed: int,
    temporal: bool,
) -> list[str]:
    question_root = output_root / "questions"
    question_root.mkdir(exist_ok=True)
    path = question_root / f"{key}.json"
    if path.exists():
        value = _read_object(path)
        questions = value.get("questions")
        if isinstance(questions, list) and len(questions) == count:
            return [str(question) for question in questions]
        raise CorpusBuildError(f"Existing question artifact is invalid: {key}.")
    excerpts = _select_excerpts(documents, count=count, seed=seed)
    excerpt_text = "\n\n".join(
        f"Excerpt {index + 1}:\n{excerpt[:900]}"
        for index, excerpt in enumerate(excerpts)
    )
    instruction = (
        "Write exactly five questions that require deciding which source is current or authoritative. "
        "Questions must be answerable from the excerpts and should test changed rules, replacements, or source authority."
        if temporal
        else f"Write exactly {count} diverse factual questions answerable from the documentation excerpts. Include configuration, numeric, procedural, and direct-fact questions."
    )
    output_contract = (
        f"Return exactly {count} questions as a JSON array of strings. "
        "Every string must end with a question mark. Do not answer, summarize, "
        "explain, number, or wrap the JSON in Markdown."
    )
    prompt = (
        f"TASK: {instruction}\n{output_contract}\n\n"
        f"SOURCE EXCERPTS:\n{excerpt_text}\n\nOUTPUT CONTRACT: {output_contract}"
    )
    response_schema = _question_response_schema(count)
    attempt_root = output_root / "question-attempts"
    attempt_root.mkdir(exist_ok=True)
    for attempt in range(3):
        result = _ollama_chat(
            model=model,
            prompt=prompt,
            seed=seed + attempt,
            max_tokens=700,
            format_schema=response_schema,
        )
        questions = _parse_questions(result["text"], count=count)
        attempt_record = {
            "schema_version": "1.0",
            "key": key,
            "attempt": attempt + 1,
            "model": model,
            "seed": seed + attempt,
            "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
            "response_format_sha256": _canonical_sha256(response_schema),
            "raw_response": result["text"],
            "raw_response_sha256": hashlib.sha256(result["text"].encode()).hexdigest(),
            "parsed_question_count": len(questions),
            "generation": result["metadata"],
        }
        attempt_path = attempt_root / f"{key}-{attempt + 1:02d}.json"
        attempt_path.write_text(
            json.dumps(attempt_record, indent=2, ensure_ascii=False, sort_keys=True)
            + "\n",
            encoding="utf-8",
        )
        if len(questions) == count:
            record = {
                "schema_version": "1.0",
                "key": key,
                "model": model,
                "seed": seed + attempt,
                "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
                "response_format_sha256": _canonical_sha256(response_schema),
                "questions": questions,
                "raw_response_sha256": hashlib.sha256(
                    result["text"].encode()
                ).hexdigest(),
                "successful_attempt_path": f"question-attempts/{attempt_path.name}",
            }
            path.write_text(
                json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )
            return questions
    raise CorpusBuildError(f"Question generation failed after three attempts: {key}.")


def _question_response_schema(count: int) -> dict[str, Any]:
    return {
        "type": "array",
        "minItems": count,
        "maxItems": count,
        "items": {
            "type": "string",
            "minLength": 20,
            "maxLength": 300,
            "pattern": r"^.*\?$",
        },
    }


def _generate_case(
    *,
    case_id: str,
    track: str,
    question: str,
    source_records: list[Mapping[str, Any]],
    index: int,
    encoder: _DenseEncoder,
    trace_root: Path,
    pair: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    chunk_size = 384 if (index // 2) % 2 == 0 else 768
    overlap = 64 if chunk_size == 384 else 128
    retrieval_family = ("bm25", "vector", "hybrid")[index % 3]
    reranking = bool((index // 3) % 2)
    model = GENERATOR_MODELS[index % len(GENERATOR_MODELS)]
    chunks = [
        chunk
        for source in source_records
        for chunk in _chunk_documents(
            _documents_from_record(source),
            source_id=str(source["source_id"]),
            size=chunk_size,
            overlap=overlap,
        )
    ]
    ranking = _retrieve(
        question,
        chunks,
        family=retrieval_family,
        encoder=encoder,
        top_k=20,
    )
    if reranking:
        ranking = _rerank(question, ranking, chunks)
    selected = [chunks[position] for position in ranking[:3]]
    contexts = "\n\n".join(f"[{chunk.id}]\n{chunk.text}" for chunk in selected)
    prompt = (
        "Answer the question using only the supplied retrieved contexts. Cite supporting context IDs in square brackets. "
        "If the contexts do not support an answer, say that the answer is not available from the retrieved evidence.\n\n"
        f"Question: {question}\n\nRetrieved contexts:\n{contexts}"
    )
    generation = _ollama_chat(
        model=model,
        prompt=prompt,
        seed=_seed(case_id),
        max_tokens=320,
    )
    trace = {
        "schema_version": TRACE_SCHEMA_VERSION,
        "case_id": case_id,
        "track": track,
        "query": question,
        "answer": generation["text"],
        "retrieved_chunks": [
            {
                "id": chunk.id,
                "source_id": chunk.source_id,
                "document_path": chunk.document_path,
                "chunk_index": chunk.index,
                "text": chunk.text,
            }
            for chunk in [chunks[position] for position in ranking]
        ],
        "selected_context_ids": [chunk.id for chunk in selected],
        "retrieval": {"family": retrieval_family, "top_k": 20},
        "chunking": {"size": chunk_size, "overlap": overlap, "unit": "tokens"},
        "reranking": {
            "enabled": reranking,
            "implementation": "deterministic_bm25_v1" if reranking else None,
        },
        "generator": {
            "provider": "Ollama-local",
            "model": model,
            "seed": _seed(case_id),
            "temperature": 0.2,
            "max_output_tokens": 320,
        },
        "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
        "generation": generation["metadata"],
        "verifier_history": [],
    }
    if _contains_label_key(trace):
        raise CorpusBuildError(f"Generated trace contains a label field: {case_id}.")
    trace_path = trace_root / f"{case_id}.json"
    trace_path.write_text(
        json.dumps(trace, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    primary = source_records[-1]
    return {
        "case_id": case_id,
        "track": track,
        "source_family": str(pair["pair_id"] if pair else primary["source_family"]),
        "source_document_id": str(primary["source_id"]),
        "source_ids": [str(source["source_id"]) for source in source_records],
        "domain_group": str(primary["domain_group"]),
        "domain_id": str(primary["domain_id"]),
        "publication_window": str(primary["publication_window"]),
        "condition_type": pair.get("condition_type") if pair else None,
        "retrieval": trace["retrieval"],
        "chunking": trace["chunking"],
        "reranking": trace["reranking"],
        "generator": trace["generator"],
        "prompt_sha256": trace["prompt_sha256"],
        "trace_artifact_path": f"traces/{trace_path.name}",
        "trace_sha256": _file_sha256(trace_path),
        "answer_length_chars": len(generation["text"]),
        "context_count": len(selected),
        "labels_accessible_at_generation": False,
        "verifier_history": [],
    }


class _DenseEncoder:
    def __init__(self, model_path: Path) -> None:
        if not model_path.is_dir():
            raise CorpusBuildError("Embedding model must be a local directory.")
        from sentence_transformers import SentenceTransformer

        self.model = SentenceTransformer(str(model_path))
        self._chunk_cache: dict[str, np.ndarray] = {}
        self.lock = {
            "id": "sentence-transformers/all-MiniLM-L6-v2",
            "local_path_name": model_path.name,
            "artifact_manifest_sha256": _directory_manifest_sha256(model_path),
            "dimensions": int(self.model.get_embedding_dimension()),
        }

    def encode(self, texts: Sequence[str]) -> np.ndarray:
        return np.asarray(
            self.model.encode(
                list(texts),
                batch_size=32,
                convert_to_numpy=True,
                normalize_embeddings=True,
                show_progress_bar=False,
            ),
            dtype=np.float32,
        )

    def encode_chunks(self, chunks: Sequence[Chunk]) -> np.ndarray:
        cache_key = _canonical_sha256(
            [
                [chunk.id, hashlib.sha256(chunk.text.encode()).hexdigest()]
                for chunk in chunks
            ]
        )
        if cache_key not in self._chunk_cache:
            self._chunk_cache[cache_key] = self.encode([chunk.text for chunk in chunks])
        return self._chunk_cache[cache_key]


def _retrieve(
    query: str,
    chunks: Sequence[Chunk],
    *,
    family: str,
    encoder: _DenseEncoder,
    top_k: int,
) -> list[int]:
    limit = min(max(top_k, 50), len(chunks))
    lexical = _stable_top(_bm25_scores(query, chunks), chunks, limit)
    if family == "bm25":
        return lexical[:top_k]
    embeddings = encoder.encode_chunks(chunks)
    query_vector = encoder.encode([query])[0]
    vector = _stable_top(embeddings @ query_vector, chunks, limit)
    if family == "vector":
        return vector[:top_k]
    if family != "hybrid":
        raise CorpusBuildError(f"Unknown retrieval family: {family}.")
    scores: dict[int, float] = Counter()
    for ranking in (lexical, vector):
        for rank, position in enumerate(ranking, start=1):
            scores[position] = scores.get(position, 0.0) + 1.0 / (60 + rank)
    return sorted(
        scores, key=lambda position: (-scores[position], chunks[position].id)
    )[:top_k]


def _rerank(query: str, ranking: list[int], chunks: Sequence[Chunk]) -> list[int]:
    candidates = [chunks[position] for position in ranking]
    scores = _bm25_scores(query, candidates)
    return [
        ranking[position]
        for position in _stable_top(scores, candidates, len(candidates))
    ]


def _bm25_scores(query: str, chunks: Sequence[Chunk]) -> np.ndarray:
    tokenized = [_lexical_tokens(chunk.text) for chunk in chunks]
    query_terms = sorted(set(_lexical_tokens(query)))
    lengths = np.asarray([len(tokens) for tokens in tokenized], dtype=np.float64)
    average = float(lengths.mean()) if len(lengths) else 0.0
    scores = np.zeros(len(chunks), dtype=np.float64)
    if not query_terms or not average:
        return scores
    frequencies = [Counter(tokens) for tokens in tokenized]
    for term in query_terms:
        document_frequency = sum(term in frequency for frequency in frequencies)
        if not document_frequency:
            continue
        inverse = math.log(
            1.0 + (len(chunks) - document_frequency + 0.5) / (document_frequency + 0.5)
        )
        for index, frequency in enumerate(frequencies):
            count = frequency.get(term, 0)
            if count:
                denominator = count + 1.5 * (0.25 + 0.75 * lengths[index] / average)
                scores[index] += inverse * count * 2.5 / denominator
    return scores


def _stable_top(
    scores: Sequence[float], chunks: Sequence[Chunk], limit: int
) -> list[int]:
    return sorted(
        range(len(chunks)), key=lambda index: (-float(scores[index]), chunks[index].id)
    )[:limit]


def _chunk_documents(
    documents: Sequence[Document], *, source_id: str, size: int, overlap: int
) -> list[Chunk]:
    chunks: list[Chunk] = []
    stride = size - overlap
    ordinal = 0
    for document in documents:
        matches = list(TOKEN_RE.finditer(document.text))
        for start in range(0, len(matches), stride):
            window = matches[start : start + size]
            if not window:
                continue
            chunks.append(
                Chunk(
                    id=f"{source_id}/chunk-{ordinal:06d}",
                    source_id=source_id,
                    document_path=document.path,
                    index=ordinal,
                    text=document.text[window[0].start() : window[-1].end()],
                )
            )
            ordinal += 1
            if start + size >= len(matches):
                break
    if not chunks:
        raise CorpusBuildError(f"Chunking produced no chunks: {source_id}.")
    return chunks


def _select_excerpts(
    documents: Sequence[Document], *, count: int, seed: int
) -> list[str]:
    candidates: list[tuple[str, str]] = []
    for document in documents:
        matches = list(TOKEN_RE.finditer(document.text))
        for start in range(0, len(matches), 480):
            window = matches[start : start + 480]
            if len(window) < 180:
                continue
            excerpt = document.text[window[0].start() : window[-1].end()]
            order = hashlib.sha256(
                f"{seed}:{document.path}:{start}".encode()
            ).hexdigest()
            candidates.append((order, excerpt))
    if len(candidates) < count:
        raise CorpusBuildError("Source has too few question-authoring excerpts.")
    return [excerpt for _, excerpt in sorted(candidates)[:count]]


def _ollama_chat(
    *,
    model: str,
    prompt: str,
    seed: int,
    max_tokens: int,
    format_schema: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    started = time.perf_counter()
    request: dict[str, Any] = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "think": False,
        "options": {
            "temperature": 0.2,
            "seed": seed,
            "num_predict": max_tokens,
        },
    }
    if format_schema is not None:
        request["format"] = dict(format_schema)
    response = httpx.post(
        OLLAMA_URL,
        json=request,
        timeout=300.0,
    )
    response.raise_for_status()
    payload = response.json()
    text = str((payload.get("message") or {}).get("content") or "").strip()
    if not text:
        raise CorpusBuildError(f"Ollama returned an empty response from {model}.")
    return {
        "text": text,
        "metadata": {
            "completed_at": _utc_now(),
            "elapsed_ms": round((time.perf_counter() - started) * 1000, 3),
            "eval_count": payload.get("eval_count"),
            "prompt_eval_count": payload.get("prompt_eval_count"),
            "done_reason": payload.get("done_reason"),
        },
    }


def _parse_questions(text: str, *, count: int) -> list[str]:
    cleaned = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
    candidates: list[Any] = []
    try:
        value = json.loads(cleaned.strip("` \n"))
        if isinstance(value, list):
            candidates = value
    except json.JSONDecodeError:
        match = re.search(r"\[[\s\S]*\]", cleaned)
        if match:
            try:
                value = json.loads(match.group(0))
                if isinstance(value, list):
                    candidates = value
            except json.JSONDecodeError:
                pass
    if not candidates:
        candidates = QUESTION_LINE_RE.findall(cleaned)
    questions: list[str] = []
    for candidate in candidates:
        question = " ".join(str(candidate).split()).strip(' "')
        if (
            20 <= len(question) <= 300
            and question.endswith("?")
            and question not in questions
        ):
            questions.append(question)
    return questions[:count] if len(questions) >= count else []


def _validate_boundaries(
    catalog: Mapping[str, Any],
    candidate_freeze: Mapping[str, Any],
    development: Mapping[str, Any],
) -> None:
    candidate_identity = dict(candidate_freeze)
    candidate_expected = str(candidate_identity.pop("freeze_payload_sha256", ""))
    if (
        not candidate_expected
        or _canonical_sha256(candidate_identity) != candidate_expected
    ):
        raise CorpusBuildError("Candidate freeze payload hash is absent or invalid.")
    development_identity = dict(development)
    development_seal = development_identity.pop("seal", None)
    development_expected = (
        str(development_seal.get("payload_sha256") or "")
        if isinstance(development_seal, Mapping)
        else ""
    )
    if (
        not development_expected
        or _canonical_sha256(development_identity) != development_expected
    ):
        raise CorpusBuildError(
            "Development manifest payload hash is absent or invalid."
        )
    if (
        candidate_freeze.get("status")
        != "candidate_frozen_before_unseen_v2_acquisition"
    ):
        raise CorpusBuildError("Candidate freeze is absent or invalid.")
    boundaries = candidate_freeze.get("boundaries") or {}
    if boundaries.get("labels_created") or boundaries.get(
        "candidate_executed_on_unseen_v2"
    ):
        raise CorpusBuildError("Candidate freeze boundary is already contaminated.")
    natural = catalog.get("natural_sources")
    pairs = catalog.get("temporal_pairs")
    if not isinstance(natural, list) or len(natural) != 30:
        raise CorpusBuildError("The catalog must contain exactly 30 natural sources.")
    if not isinstance(pairs, list) or len(pairs) != 20:
        raise CorpusBuildError("The catalog must contain exactly 20 temporal pairs.")
    natural_ids = [str(source["source_id"]) for source in natural]
    natural_families = [str(source["source_family"]) for source in natural]
    natural_domains = [str(source["domain_id"]) for source in natural]
    pair_ids = [str(pair["pair_id"]) for pair in pairs]
    pair_domains = [str(pair["domain_id"]) for pair in pairs]
    for values, label in (
        (natural_ids, "natural source IDs"),
        (natural_families, "natural source families"),
        (natural_domains, "natural domain IDs"),
        (pair_ids, "temporal pair IDs"),
        (pair_domains, "temporal domain IDs"),
    ):
        if len(values) != len(set(values)):
            raise CorpusBuildError(f"Catalog {label} must be unique.")
    natural_groups = Counter(str(source["domain_group"]) for source in natural)
    if natural_groups != Counter(
        {
            "software_product": 10,
            "support_operational": 10,
            "policy_regulatory": 10,
        }
    ):
        raise CorpusBuildError("Natural source domains must be balanced 10/10/10.")
    pair_kinds = Counter(
        "github_pair" if pair.get("repository") else str(pair.get("kind"))
        for pair in pairs
    )
    if pair_kinds != Counter(
        {"github_pair": 10, "ecfr_pair": 5, "authority_web_pair": 5}
    ):
        raise CorpusBuildError("Temporal pairs must be balanced 10/5/5 by source type.")
    old_families = {
        str(source["source_family"])
        for source in development.get("sources") or []
        if isinstance(source, Mapping) and source.get("source_family")
    }
    old_domains = {
        str(case["domain_id"])
        for case in development.get("cases") or []
        if isinstance(case, Mapping) and case.get("domain_id")
    }
    new_families = set(natural_families)
    new_domains = {
        *(str(source["domain_id"]) for source in natural),
        *(str(pair["domain_id"]) for pair in pairs),
    }
    if old_families & new_families:
        raise CorpusBuildError("Source-family overlap with development corpus.")
    if old_domains & new_domains:
        raise CorpusBuildError("Domain-ID overlap with development corpus.")
    if {str(source["publication_window"]) for source in natural} != {"2026-H2"}:
        raise CorpusBuildError("Natural sources must use the new 2026-H2 window.")


def _validate_acquired_sources(
    sources: Sequence[Mapping[str, Any]], development: Mapping[str, Any]
) -> None:
    source_ids = [str(source["source_id"]) for source in sources]
    fingerprints = [str(source["normalized_content_sha256"]) for source in sources]
    if len(source_ids) != len(set(source_ids)):
        raise CorpusBuildError("Acquired source IDs are not unique.")
    if len(fingerprints) != len(set(fingerprints)):
        raise CorpusBuildError("Acquired sources contain normalized duplicates.")
    old_hashes = {
        str(source["normalized_content_sha256"])
        for source in development.get("sources") or []
        if isinstance(source, Mapping) and source.get("normalized_content_sha256")
    }
    if old_hashes & set(fingerprints):
        raise CorpusBuildError("Normalized source collision with development corpus.")


def _artifact_manifest(
    output_root: Path,
    rows: Sequence[Mapping[str, Any]],
    sources: Sequence[Mapping[str, Any]],
) -> dict[str, str]:
    artifacts: dict[str, str] = {}
    for row in rows:
        relative = str(row["trace_artifact_path"])
        artifacts[relative] = _file_sha256(output_root / relative)
    for source in sources:
        path = Path(str(source["normalized_path"]))
        relative = str(path.relative_to(output_root))
        artifacts[relative] = _file_sha256(path)
    return {key: artifacts[key] for key in sorted(artifacts)}


def _public_source_record(source: Mapping[str, Any]) -> dict[str, Any]:
    excluded = {"normalized_path", "selected_files"}
    return {key: value for key, value in source.items() if key not in excluded}


def _documents_from_record(source: Mapping[str, Any]) -> list[Document]:
    path = Path(str(source["normalized_path"]))
    text = path.read_text(encoding="utf-8")
    markers = list(re.finditer(r"^===== FILE: (.+?) =====\n", text, re.MULTILINE))
    documents: list[Document] = []
    for index, marker in enumerate(markers):
        start = marker.end()
        end = markers[index + 1].start() if index + 1 < len(markers) else len(text)
        documents.append(Document(path=marker.group(1), text=text[start:end].strip()))
    if not documents:
        documents.append(Document(path="normalized-source", text=text))
    return documents


def _normalize_source_file(raw: str, *, suffix: str) -> str:
    if suffix in {".html", ".htm"}:
        parser = _HTMLText()
        parser.feed(raw)
        raw = " ".join(parser.parts)
    elif suffix in {".xml", ".sgml"}:
        try:
            raw = " ".join(piece.strip() for piece in ET.fromstring(raw).itertext())
        except ET.ParseError:
            raw = re.sub(r"<[^>]+>", " ", raw)
    raw = re.sub(r"\{[%{].*?[}%]\}", " ", raw, flags=re.DOTALL)
    raw = re.sub(r"!\[[^]]*\]\([^)]+\)", " ", raw)
    raw = re.sub(r"\[([^]]+)\]\([^)]+\)", r"\1", raw)
    return _normalize_text(html.unescape(raw))


def _normalize_text(value: str) -> str:
    value = value.replace("\x00", " ").replace("\r\n", "\n")
    value = re.sub(r"[ \t]+", " ", value)
    value = re.sub(r"\n{3,}", "\n\n", value)
    return value.strip()


def _ollama_lock() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for model in GENERATOR_MODELS:
        output = _run(["ollama", "show", model, "--modelfile"])
        match = re.search(r"^FROM\s+(.+)$", output, flags=re.MULTILINE)
        if not match:
            raise CorpusBuildError(f"Could not resolve Ollama model: {model}.")
        weight_path = Path(match.group(1).strip())
        if not weight_path.is_file():
            raise CorpusBuildError(f"Ollama weight is absent: {model}.")
        rows.append(
            {
                "provider": "Ollama-local",
                "model": model,
                "weight_sha256": _file_sha256(weight_path),
                "weight_bytes": weight_path.stat().st_size,
                "modelfile_sha256": hashlib.sha256(output.encode()).hexdigest(),
            }
        )
    return rows


def _directory_manifest_sha256(root: Path) -> str:
    rows = [
        {
            "path": str(path.relative_to(root)),
            "bytes": path.stat().st_size,
            "sha256": _file_sha256(path),
        }
        for path in sorted(root.rglob("*"))
        if path.is_file() and ".cache" not in path.relative_to(root).parts
    ]
    if not rows:
        raise CorpusBuildError(f"Artifact directory contains no files: {root}.")
    return _canonical_sha256(rows)


def _read_journal(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), 1
    ):
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise CorpusBuildError(f"Invalid journal line {line_number}.") from exc
        if not isinstance(value, dict) or not value.get("case_id"):
            raise CorpusBuildError(f"Invalid journal row {line_number}.")
        rows.append(value)
    return rows


def _validate_completed_case(
    row: Mapping[str, Any],
    *,
    case_id: str,
    track: str,
    source_ids: list[str],
    trace_root: Path,
) -> None:
    expected_relative = f"traces/{case_id}.json"
    if (
        row.get("case_id") != case_id
        or row.get("track") != track
        or row.get("trace_artifact_path") != expected_relative
        or row.get("source_ids") != source_ids
    ):
        raise CorpusBuildError(f"Resumed journal metadata mismatch: {case_id}.")
    trace_path = trace_root / f"{case_id}.json"
    if not trace_path.is_file() or _file_sha256(trace_path) != row.get("trace_sha256"):
        raise CorpusBuildError(f"Resumed trace hash mismatch: {case_id}.")
    trace = _read_object(trace_path)
    if (
        trace.get("case_id") != case_id
        or trace.get("track") != track
        or trace.get("verifier_history") != []
        or _contains_label_key(trace)
    ):
        raise CorpusBuildError(f"Resumed trace boundary mismatch: {case_id}.")


def _contains_label_key(value: Any, *, allow_null_labels: bool = False) -> bool:
    if isinstance(value, Mapping):
        for key, item in value.items():
            normalized = str(key).casefold()
            if normalized in LABEL_KEYS and not (
                allow_null_labels and normalized == "labels" and item is None
            ):
                return True
            if _contains_label_key(item, allow_null_labels=allow_null_labels):
                return True
    elif isinstance(value, list):
        return any(
            _contains_label_key(item, allow_null_labels=allow_null_labels)
            for item in value
        )
    return False


def _acquire_lock(path: Path) -> int:
    try:
        return os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise CorpusBuildError("Another corpus process holds the output lock.") from exc


def _run(command: list[str]) -> str:
    return subprocess.run(command, check=True, capture_output=True, text=True).stdout


def _read_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"Expected a JSON object: {path}.")
    return value


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _canonical_sha256(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def _seed(value: str) -> int:
    return int(hashlib.sha256(value.encode()).hexdigest()[:8], 16)


def _lexical_tokens(value: str) -> list[str]:
    return [match.group(0).casefold() for match in LEXICAL_RE.finditer(value)]


def _counter(values: Iterable[Any]) -> dict[str, int]:
    counts = Counter(
        str(value).lower() if isinstance(value, bool) else str(value)
        for value in values
    )
    return {key: counts[key] for key in sorted(counts)}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


if __name__ == "__main__":
    raise SystemExit(main())
