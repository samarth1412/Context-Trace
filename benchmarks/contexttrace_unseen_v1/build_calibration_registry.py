"""Build a conservative registry of every source exposure visible in the repo.

This utility inventories prior evidence; it never downloads external content.
It scans structured benchmark artifacts as text so very large JSON/JSONL files
do not need to be loaded into memory. The output is a schema-valid calibration
registry plus small provenance artifacts. It is intentionally conservative:
host aliases and dataset-level exposures are retained even when the legacy
artifact lacks a complete source snapshot.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import unicodedata
from collections import defaultdict
from pathlib import Path
from typing import Iterable
from urllib.parse import urlsplit, urlunsplit


CREATED_AT = "2026-07-24T00:00:00Z"
URL_KEY_PATTERN = re.compile(
    r'"(?:source_url|document_url|canonical_url)"\s*:\s*("(?:[^"\\]|\\.)*")'
)
FAMILY_KEY_PATTERN = re.compile(
    r'"source_family"\s*:\s*("(?:[^"\\]|\\.)*")'
)
SOURCE_KEY_PATTERN = re.compile(
    r'"source"\s*:\s*("(?:[^"\\]|\\.)*")'
)
URL_PATTERN = re.compile(r"^https?://", re.IGNORECASE)
DOMAIN_LIKE_PATTERN = re.compile(
    r"^(?:[a-z0-9-]+\.)+[a-z]{2,}(?:/|$)", re.IGNORECASE
)
NON_DOMAIN_SUFFIXES = {
    "adoc",
    "json",
    "md",
    "pdf",
    "py",
    "rst",
    "tex",
    "txt",
    "yaml",
    "yml",
}

DEFAULT_SCAN_ROOTS = (
    "benchmarks/contexttrace_bench",
    "benchmarks/real_world_rag",
    "benchmarks/results",
    "benchmarks/datasets",
    "datasets",
    "examples",
    "validation",
    "packages/contexttrace/contexttrace/verify",
)

HOST_ALIASES = {
    "arize.com": "arize_phoenix",
    "www.arize.com": "arize_phoenix",
    "deepeval.com": "deepeval",
    "www.deepeval.com": "deepeval",
    "developers.llamaindex.ai": "llamaindex",
    "developers.openai.com": "openai",
    "openai.com": "openai",
    "www.openai.com": "openai",
    "platform.openai.com": "openai",
    "docs.haystack.deepset.ai": "haystack",
    "docs.lancedb.com": "lancedb",
    "docs.langchain.com": "langchain",
    "reference.langchain.com": "langchain",
    "docs.opensearch.org": "opensearch",
    "docs.pinecone.io": "pinecone",
    "docs.pydantic.dev": "pydantic",
    "docs.python.org": "python",
    "docs.ragas.io": "ragas",
    "docs.sqlalchemy.org": "sqlalchemy",
    "docs.trychroma.com": "chroma",
    "docs.vespa.ai": "vespa",
    "docs.weaviate.io": "weaviate",
    "dspy.ai": "dspy",
    "elastic.co": "elastic",
    "www.elastic.co": "elastic",
    "guardrailsai.com": "guardrails",
    "kubernetes.io": "kubernetes",
    "learn.microsoft.com": "microsoft",
    "milvus.io": "milvus",
    "mongodb.com": "mongodb",
    "www.mongodb.com": "mongodb",
    "opentelemetry.io": "opentelemetry",
    "qdrant.tech": "qdrant",
    "redis.io": "redis",
    "www.trulens.org": "trulens",
}

FAMILY_ALIASES = {
    "arize.com": "arize_phoenix",
    "aws": "aws",
    "deepeval.com": "deepeval",
    "developers.llamaindex.ai": "llamaindex",
    "developers.openai.com": "openai",
    "django": "django",
    "docker": "docker",
    "docs.haystack.deepset.ai": "haystack",
    "docs.lancedb.com": "lancedb",
    "docs.langchain.com": "langchain",
    "docs.opensearch.org": "opensearch",
    "docs.pinecone.io": "pinecone",
    "docs.ragas.io": "ragas",
    "docs.trychroma.com": "chroma",
    "docs.vespa.ai": "vespa",
    "docs.weaviate.io": "weaviate",
    "dspy.ai": "dspy",
    "elastic.co": "elastic",
    "fastapi": "fastapi",
    "github actions": "github_actions",
    "github.com": "github_public_repositories",
    "google cloud": "google_cloud",
    "guardrailsai.com": "guardrails",
    "kubernetes": "kubernetes",
    "langchain": "langchain",
    "learn.microsoft.com": "microsoft",
    "llamaindex": "llamaindex",
    "microsoft azure": "microsoft_azure",
    "milvus.io": "milvus",
    "mongodb.com": "mongodb",
    "openai": "openai",
    "opentelemetry.io": "opentelemetry",
    "postgresql": "postgresql",
    "pydantic": "pydantic",
    "python": "python",
    "qdrant.tech": "qdrant",
    "redis.io": "redis",
    "sqlalchemy": "sqlalchemy",
    "trulens.org": "trulens",
    "www.trulens.org": "trulens",
}

GITHUB_ORG_ALIASES = {
    "chroma-core": "chroma",
    "guardrails-ai": "guardrails",
    "pgvector": "pgvector",
    "samarth1412": "contexttrace",
    "stanfordnlp": "dspy",
}


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _slug(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).casefold()
    value = re.sub(r"[^a-z0-9]+", "_", value).strip("_")
    return value[:120] or "unknown"


def _decode_json_string(raw: str) -> str:
    value = json.loads(raw)
    if not isinstance(value, str):
        raise TypeError("expected a JSON string")
    return value.strip()


def canonical_url(value: str) -> str:
    """Return a stable URL form without fragments or superficial slashes."""

    value = value.strip()
    if not URL_PATTERN.match(value):
        if DOMAIN_LIKE_PATTERN.match(value):
            hostname_candidate = value.split("/", 1)[0]
            if hostname_candidate.rsplit(".", 1)[-1].casefold() in NON_DOMAIN_SUFFIXES:
                raise ValueError(f"not a public URL: {value!r}")
            value = f"https://{value}"
        else:
            raise ValueError(f"not a public URL: {value!r}")
    parts = urlsplit(value)
    scheme = parts.scheme.casefold()
    host = (parts.hostname or "").casefold()
    if not host:
        raise ValueError(f"URL has no host: {value!r}")
    port = parts.port
    netloc = host
    if port and not (
        (scheme == "http" and port == 80) or (scheme == "https" and port == 443)
    ):
        netloc = f"{host}:{port}"
    path = re.sub(r"/+", "/", parts.path or "/")
    if path != "/":
        path = path.rstrip("/")
    return urlunsplit((scheme, netloc, path, parts.query, ""))


def family_for_url(value: str) -> str:
    parts = urlsplit(value)
    host = (parts.hostname or "").casefold()
    if host == "github.com":
        segments = [segment for segment in parts.path.split("/") if segment]
        if segments:
            return GITHUB_ORG_ALIASES.get(
                segments[0].casefold(), f"github_{_slug(segments[0])}"
            )
        return "github_public_repositories"
    return HOST_ALIASES.get(host, _slug(host.removeprefix("www.")))


def canonical_family(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold().strip()
    return FAMILY_ALIASES.get(normalized, _slug(normalized))


def _structured_files(repo_root: Path) -> Iterable[Path]:
    for relative_root in DEFAULT_SCAN_ROOTS:
        root = repo_root / relative_root
        if not root.exists():
            continue
        for path in sorted(root.rglob("*")):
            if (
                path.is_file()
                and path.suffix.casefold() in {".json", ".jsonl"}
                and "contexttrace_unseen_v1" not in path.parts
            ):
                yield path


def collect_exposures(repo_root: Path) -> dict[str, object]:
    """Collect URL/family provenance without loading entire benchmark files."""

    urls: dict[str, set[str]] = defaultdict(set)
    families: dict[str, set[str]] = defaultdict(set)
    source_strings: dict[str, set[str]] = defaultdict(set)
    scanned_files: list[dict[str, object]] = []
    read_errors: list[dict[str, str]] = []

    for path in _structured_files(repo_root):
        relative = path.relative_to(repo_root).as_posix()
        hasher = hashlib.sha256()
        matched = False
        try:
            with path.open("rb") as handle:
                for raw_line in handle:
                    hasher.update(raw_line)
                    line = raw_line.decode("utf-8", errors="replace")
                    for match in URL_KEY_PATTERN.finditer(line):
                        raw_value = _decode_json_string(match.group(1))
                        try:
                            value = canonical_url(raw_value)
                        except ValueError:
                            continue
                        urls[value].add(relative)
                        matched = True
                    for match in FAMILY_KEY_PATTERN.finditer(line):
                        raw_value = _decode_json_string(match.group(1))
                        if raw_value:
                            families[canonical_family(raw_value)].add(relative)
                            matched = True
                    for match in SOURCE_KEY_PATTERN.finditer(line):
                        raw_value = _decode_json_string(match.group(1))
                        if not raw_value:
                            continue
                        try:
                            value = canonical_url(raw_value)
                        except ValueError:
                            if DOMAIN_LIKE_PATTERN.match(raw_value):
                                source_strings[raw_value].add(relative)
                            continue
                        urls[value].add(relative)
                        matched = True
        except OSError as exc:
            read_errors.append({"path": relative, "error": str(exc)})
            continue
        scanned_files.append(
            {
                "path": relative,
                "sha256": hasher.hexdigest(),
                "bytes": path.stat().st_size,
                "contained_source_metadata": matched,
            }
        )

    inventory_path = repo_root / "research/cain2027/evidence_inventory.json"
    dataset_exposures: dict[str, set[str]] = defaultdict(set)
    if inventory_path.exists():
        inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
        for dataset in inventory.get("datasets", []):
            classifications = {
                str(value).casefold()
                for value in dataset.get("classification", [])
            }
            if not classifications & {
                "calibration",
                "development",
                "previously_inspected_holdout",
                "unusable_for_independent_evaluation",
            }:
                continue
            dataset_id = str(dataset.get("id") or "").strip()
            if not dataset_id:
                continue
            family = f"dataset_{_slug(dataset_id)}"
            for path_value in dataset.get("paths", []):
                dataset_exposures[family].add(str(path_value))

    return {
        "urls": {key: sorted(value) for key, value in sorted(urls.items())},
        "families": {
            key: sorted(value) for key, value in sorted(families.items())
        },
        "source_strings": {
            key: sorted(value) for key, value in sorted(source_strings.items())
        },
        "dataset_exposures": {
            key: sorted(value) for key, value in sorted(dataset_exposures.items())
        },
        "scanned_files": scanned_files,
        "read_errors": read_errors,
    }


def normalized_text_sha256(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text)
    normalized = " ".join(normalized.split()).casefold()
    return _sha256(normalized.encode("utf-8"))


def _source_record(
    *,
    key: str,
    family: str,
    canonical_identifier: str,
    provenance: list[str],
    artifact_relative_path: str,
    artifact_bytes: bytes,
    source_url: str,
) -> dict[str, object]:
    key_hash = _sha256(key.encode("utf-8"))
    artifact_text = artifact_bytes.decode("utf-8")
    return {
        "source_id": f"calib_{key_hash[:24]}",
        "source_document_id": f"calib_doc_{key_hash[:24]}",
        "document_lineage_id": f"calib_lineage_{_slug(family)}",
        "source_family": family,
        "domain_group": "software_product_documentation",
        "domain_id": f"calibration_{_slug(family)}",
        "publication_window": "pre_2026-07-24_or_unknown",
        "source_url": source_url,
        "canonical_identifier": canonical_identifier,
        "snapshot_path": artifact_relative_path,
        "snapshot_sha256": _sha256(artifact_bytes),
        "normalized_text_path": artifact_relative_path,
        "normalized_content_sha256": normalized_text_sha256(artifact_text),
        "near_duplicate_cluster_id": (
            f"calib_cluster_{normalized_text_sha256(artifact_text)[:24]}"
        ),
        "collected_at": CREATED_AT,
        "published_at": None,
        "language": "en",
        "content_type": "text/plain; profile=legacy-exposure-record",
        "source_conditions": ["unknown"],
        "authority_basis": None,
        "license": {
            "license_id": "UNKNOWN_LEGACY_EXPOSURE",
            "terms_url": None,
            "redistribution": "metadata_only",
            "attribution_required": False,
            "review_status": "pending",
            "notes": (
                "Calibration-only exposure record; not approved for reuse or "
                "candidate collection."
            ),
        },
        "access": {
            "access_class": "public",
            "authentication_required": False,
            "collection_permitted": False,
            "restrictions": ["calibration_only", "legacy_snapshot_incomplete"],
        },
        "privacy_classification": "public",
        "metadata": {
            "exposure_provenance_paths": provenance,
            "legacy_snapshot_scope": "repository-visible identifier/metadata only",
        },
    }


def build_registry(
    repo_root: Path,
    output_directory: Path,
) -> tuple[dict[str, object], dict[str, object]]:
    inventory = collect_exposures(repo_root)
    artifact_directory = output_directory / "artifacts"
    artifact_directory.mkdir(parents=True, exist_ok=True)
    for stale_artifact in artifact_directory.glob("*.txt"):
        stale_artifact.unlink()

    sources: list[dict[str, object]] = []
    represented_families: set[str] = set()
    artifact_root_relative = output_directory.relative_to(repo_root)

    for value, provenance_value in inventory["urls"].items():
        provenance = list(provenance_value)
        family = family_for_url(value)
        represented_families.add(family)
        key = f"url:{value}"
        key_hash = _sha256(key.encode("utf-8"))
        artifact_path = artifact_directory / f"url_{key_hash[:24]}.txt"
        artifact_text = (
            "ContextTrace legacy calibration exposure record\n"
            f"canonical_url: {value}\n"
            f"source_family: {family}\n"
            "provenance:\n"
            + "".join(f"- {item}\n" for item in provenance)
        )
        artifact_path.write_text(artifact_text, encoding="utf-8")
        relative_artifact = (
            artifact_root_relative / "artifacts" / artifact_path.name
        ).as_posix()
        sources.append(
            _source_record(
                key=key,
                family=family,
                canonical_identifier=value,
                provenance=provenance,
                artifact_relative_path=relative_artifact,
                artifact_bytes=artifact_text.encode("utf-8"),
                source_url=value,
            )
        )

    family_provenance: dict[str, set[str]] = defaultdict(set)
    for key in ("families", "dataset_exposures"):
        for family, provenance_value in inventory[key].items():
            family_provenance[family].update(provenance_value)

    for family, provenance_set in sorted(family_provenance.items()):
        if family in represented_families:
            continue
        provenance = sorted(provenance_set)
        key = f"family:{family}"
        key_hash = _sha256(key.encode("utf-8"))
        artifact_path = artifact_directory / f"family_{key_hash[:24]}.txt"
        artifact_text = (
            "ContextTrace legacy calibration family exposure record\n"
            f"source_family: {family}\n"
            "provenance:\n"
            + "".join(f"- {item}\n" for item in provenance)
        )
        artifact_path.write_text(artifact_text, encoding="utf-8")
        relative_artifact = (
            artifact_root_relative / "artifacts" / artifact_path.name
        ).as_posix()
        sources.append(
            _source_record(
                key=key,
                family=family,
                canonical_identifier=f"urn:contexttrace:calibration:{family}",
                provenance=provenance,
                artifact_relative_path=relative_artifact,
                artifact_bytes=artifact_text.encode("utf-8"),
                source_url=f"urn:contexttrace:calibration:{family}",
            )
        )

    sources.sort(key=lambda item: str(item["source_id"]))
    registry = {
        "schema_version": "1.0",
        "manifest_kind": "contexttrace_calibration_registry",
        "created_at": CREATED_AT,
        "domain_ontology_version": "contexttrace-unseen-v1-domain-ontology-0.1",
        "disjoint_dimensions": [
            "source_id",
            "source_document_id",
            "source_family",
            "domain_id",
            "publication_window",
            "snapshot_sha256",
            "normalized_content_sha256",
            "near_duplicate_cluster_id",
        ],
        "sources": sources,
    }

    inventory_document = {
        "schema_version": "1.0",
        "inventory_kind": "contexttrace_repository_calibration_exposure",
        "created_at": CREATED_AT,
        "scope": {
            "scan_roots": list(DEFAULT_SCAN_ROOTS),
            "structured_extensions": [".json", ".jsonl"],
            "excludes": ["benchmarks/contexttrace_unseen_v1"],
            "external_or_unrecorded_human_exposure_discoverable": False,
        },
        "counts": {
            "source_urls": len(inventory["urls"]),
            "explicit_source_families": len(inventory["families"]),
            "dataset_exposure_families": len(inventory["dataset_exposures"]),
            "registry_sources": len(sources),
            "scanned_files": len(inventory["scanned_files"]),
            "read_errors": len(inventory["read_errors"]),
        },
        **inventory,
    }
    return registry, inventory_document


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--output-directory",
        type=Path,
        default=Path("benchmarks/contexttrace_unseen_v1/calibration"),
    )
    args = parser.parse_args()
    repo_root = args.repo_root.resolve()
    output_directory = args.output_directory
    if not output_directory.is_absolute():
        output_directory = repo_root / output_directory
    output_directory.mkdir(parents=True, exist_ok=True)

    registry, inventory = build_registry(repo_root, output_directory)
    (output_directory / "registry.json").write_text(
        json.dumps(registry, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output_directory / "exposure_inventory.json").write_text(
        json.dumps(inventory, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if inventory["read_errors"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
