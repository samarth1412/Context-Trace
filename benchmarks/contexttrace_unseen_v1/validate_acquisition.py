"""Offline, fail-closed validation of acquired Unseen-v1 source snapshots."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import sys
import tarfile
import unicodedata
import xml.etree.ElementTree as ET
from pathlib import Path, PurePosixPath
from typing import Any, Mapping

from benchmarks.contexttrace_unseen_v1.acquire_sources import (
    AcquisitionError,
    _canonical_identifier,
    _extract_payload,
    _is_excluded_path,
    _load_json,
    _sha256_file,
    _validate_authorization,
    _validate_source_manifest,
    _xml_visible_text,
)
from benchmarks.contexttrace_unseen_v1.validate_pre_acquisition import (
    validate_catalog,
)


class AcquisitionValidationError(ValueError):
    """Acquired source bytes or metadata violate the frozen contract."""


MINIMUM_DOCUMENT_FILES_PER_DOCUMENTATION_SNAPSHOT = 5


def _safe_artifact_path(workspace: Path, relative: str) -> Path:
    pure = PurePosixPath(relative)
    if pure.is_absolute() or ".." in pure.parts:
        raise AcquisitionValidationError(f"Unsafe artifact path: {relative}")
    resolved_workspace = workspace.resolve()
    resolved = (workspace / Path(*pure.parts)).resolve()
    if resolved != resolved_workspace and resolved_workspace not in resolved.parents:
        raise AcquisitionValidationError(f"Artifact escapes workspace: {relative}")
    return resolved


def _canonical_hash(text: str) -> str:
    canonical = " ".join(unicodedata.normalize("NFKC", text).casefold().split())
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _parse_time(value: str) -> dt.datetime:
    parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise AcquisitionValidationError(f"Timestamp lacks a timezone: {value}")
    return parsed


def _validate_repository_archive(
    path: Path, source: Mapping[str, Any]
) -> tuple[int, int, str]:
    extracted_content: list[tuple[PurePosixPath, str]] = []
    content_count = 0
    legal_count = 0
    seen: set[str] = set()
    try:
        archive = tarfile.open(path, mode="r:gz")
    except (OSError, tarfile.TarError) as exc:
        raise AcquisitionValidationError(f"Invalid archive {path}: {exc}") from exc
    with archive:
        for member in archive.getmembers():
            pure = PurePosixPath(member.name)
            if (
                pure.is_absolute()
                or ".." in pure.parts
                or member.name in seen
                or not member.isfile()
            ):
                raise AcquisitionValidationError(
                    f"Unsafe or duplicate archive member: {member.name}"
                )
            seen.add(member.name)
            if (
                member.mtime != 0
                or member.uid != 0
                or member.gid != 0
                or member.mode != 0o444
            ):
                raise AcquisitionValidationError(
                    f"Nondeterministic archive metadata: {member.name}"
                )
            handle = archive.extractfile(member)
            if handle is None:
                raise AcquisitionValidationError(
                    f"Archive member is unreadable: {member.name}"
                )
            payload = handle.read()
            if member.name.startswith("content/"):
                relative = PurePosixPath(member.name.removeprefix("content/"))
                if _is_excluded_path(relative) is not None:
                    raise AcquisitionValidationError(
                        f"Excluded path entered snapshot: {relative}"
                    )
                if b"\x00" in payload:
                    raise AcquisitionValidationError(
                        f"Binary payload entered snapshot: {relative}"
                    )
                try:
                    payload.decode("utf-8")
                except UnicodeDecodeError as exc:
                    raise AcquisitionValidationError(
                        f"Non-UTF-8 payload entered snapshot: {relative}"
                    ) from exc
                text = _extract_payload(payload, relative.suffix)
                if text:
                    extracted_content.append((relative, text))
                content_count += 1
            elif member.name.startswith("legal/"):
                legal_count += 1
            else:
                raise AcquisitionValidationError(
                    f"Unexpected archive member root: {member.name}"
                )
    sections = [
        f"===== FILE: {relative.as_posix()} =====\n{text}"
        for relative, text in sorted(extracted_content, key=lambda item: item[0].parts)
    ]
    reconstructed = "\n\n".join(sections) + "\n"
    metadata = source["metadata"]
    if content_count != int(metadata["included_document_files"]):
        raise AcquisitionValidationError(
            f"{source['source_family']} document count does not match metadata."
        )
    if legal_count != int(metadata["retained_legal_files"]):
        raise AcquisitionValidationError(
            f"{source['source_family']} legal-file count does not match metadata."
        )
    return content_count, legal_count, reconstructed


def _validate_ecfr_snapshot(path: Path, catalog_entry: Mapping[str, Any]) -> str:
    payload = path.read_bytes()
    try:
        root = ET.fromstring(payload)
    except ET.ParseError as exc:
        raise AcquisitionValidationError(
            f"Invalid eCFR XML for {catalog_entry['family_id']}: {exc}"
        ) from exc
    if root.attrib.get("N") != str(catalog_entry["part"]):
        raise AcquisitionValidationError(
            f"{catalog_entry['family_id']} XML part identity does not match catalog."
        )
    return _xml_visible_text(payload).strip() + "\n"


def validate_acquisition(
    *,
    catalog: Mapping[str, Any],
    calibration: Mapping[str, Any],
    manifest: Mapping[str, Any],
    ledger: Mapping[str, Any],
    workspace: Path,
    source_schema: Path,
) -> dict[str, Any]:
    _validate_authorization(catalog)
    validate_catalog(catalog, calibration, require_attestation=True)
    _validate_source_manifest(manifest, source_schema)
    if ledger.get("status") != "complete":
        raise AcquisitionValidationError("Acquisition ledger is not complete.")
    if (
        ledger.get("model_calls") != 0
        or ledger.get("verifier_calls") != 0
        or ledger.get("trace_count") != 0
    ):
        raise AcquisitionValidationError("Downstream work occurred during acquisition.")

    catalog_entries = {entry["family_id"]: entry for entry in catalog["entries"]}
    sources = {source["source_family"]: source for source in manifest["sources"]}
    ledger_sources = {
        source["family_id"]: source for source in ledger.get("sources", [])
    }
    expected_families = set(catalog_entries)
    if set(sources) != expected_families or set(ledger_sources) != expected_families:
        raise AcquisitionValidationError(
            "Catalog, source manifest, and ledger family sets differ."
        )
    if ledger.get("source_count") != 36:
        raise AcquisitionValidationError("Ledger source count is not 36.")

    manifest_created = _parse_time(str(manifest["created_at"]))
    raw_paths: set[str] = set()
    normalized_paths: set[str] = set()
    raw_hashes: set[str] = set()
    normalized_hashes: set[str] = set()
    total_raw_bytes = 0
    total_normalized_bytes = 0
    repository_files = 0
    legal_files = 0

    for family_id in sorted(expected_families):
        entry = catalog_entries[family_id]
        source = sources[family_id]
        ledger_source = ledger_sources[family_id]
        if source["source_url"] != entry["canonical_url"]:
            raise AcquisitionValidationError(
                f"{family_id} canonical source URL changed."
            )
        if source["canonical_identifier"] != _canonical_identifier(entry):
            raise AcquisitionValidationError(
                f"{family_id} canonical identifier changed."
            )
        if source["domain_id"] != entry["domain_id"]:
            raise AcquisitionValidationError(f"{family_id} domain ID changed.")
        if source["domain_group"] != entry["domain_group"]:
            raise AcquisitionValidationError(f"{family_id} domain group changed.")
        if _parse_time(source["collected_at"]) > manifest_created:
            raise AcquisitionValidationError(
                f"{family_id} was collected after manifest creation."
            )

        raw_relative = str(source["snapshot_path"])
        normalized_relative = str(source["normalized_text_path"])
        if raw_relative in raw_paths or normalized_relative in normalized_paths:
            raise AcquisitionValidationError("Artifact paths are not unique.")
        raw_paths.add(raw_relative)
        normalized_paths.add(normalized_relative)
        raw_path = _safe_artifact_path(workspace, raw_relative)
        normalized_path = _safe_artifact_path(workspace, normalized_relative)
        if not raw_path.is_file() or not normalized_path.is_file():
            raise AcquisitionValidationError(
                f"{family_id} retained artifact is missing."
            )

        raw_sha256 = _sha256_file(raw_path)
        if (
            raw_sha256 != source["snapshot_sha256"]
            or raw_sha256 != ledger_source["snapshot_sha256"]
        ):
            raise AcquisitionValidationError(f"{family_id} raw hash mismatch.")
        try:
            normalized_text = normalized_path.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            raise AcquisitionValidationError(
                f"{family_id} normalized artifact is not UTF-8."
            ) from exc
        normalized_sha256 = _canonical_hash(normalized_text)
        if (
            normalized_sha256 != source["normalized_content_sha256"]
            or normalized_sha256 != ledger_source["normalized_content_sha256"]
        ):
            raise AcquisitionValidationError(f"{family_id} normalized hash mismatch.")
        if raw_sha256 in raw_hashes or normalized_sha256 in normalized_hashes:
            raise AcquisitionValidationError("Acquired source hashes collide.")
        raw_hashes.add(raw_sha256)
        normalized_hashes.add(normalized_sha256)

        if entry["access_profile"] in {
            "github_commit_archive",
            "gitlab_commit_archive",
        }:
            if (
                source["metadata"]["commit_sha1"] != entry["commit_sha1"]
                or ledger_source["resolved_commit_sha1"] != entry["commit_sha1"]
            ):
                raise AcquisitionValidationError(
                    f"{family_id} commit identity changed."
                )
            docs, legal, reconstructed = _validate_repository_archive(raw_path, source)
            repository_files += docs
            legal_files += legal
        elif entry["access_profile"] == "apache_release_archive":
            if (
                source["metadata"]["upstream_archive_sha512"] != entry["archive_sha512"]
                or source["metadata"]["selected_archive_members"]
                != entry["archive_member_paths"]
                or source["metadata"]["selected_legal_members"]
                != entry["archive_legal_member_paths"]
            ):
                raise AcquisitionValidationError(
                    f"{family_id} Apache release selection changed."
                )
            docs, legal, reconstructed = _validate_repository_archive(raw_path, source)
            repository_files += docs
            legal_files += legal
        else:
            reconstructed = _validate_ecfr_snapshot(raw_path, entry)
            docs = 0
        if (
            entry["access_profile"] != "ecfr_versioner_api"
            and docs < MINIMUM_DOCUMENT_FILES_PER_DOCUMENTATION_SNAPSHOT
        ):
            raise AcquisitionValidationError(
                f"{family_id} has insufficient reviewed documentation yield: {docs}."
            )
        if reconstructed != normalized_text:
            raise AcquisitionValidationError(
                f"{family_id} normalized artifact is not reproducible."
            )

        total_raw_bytes += raw_path.stat().st_size
        total_normalized_bytes += normalized_path.stat().st_size
        if ledger_source["snapshot_bytes"] != raw_path.stat().st_size:
            raise AcquisitionValidationError(f"{family_id} raw byte count mismatch.")
        if ledger_source["normalized_text_bytes"] != normalized_path.stat().st_size:
            raise AcquisitionValidationError(
                f"{family_id} normalized byte count mismatch."
            )

    calibration_normalized_hashes = {
        str(source.get("normalized_content_sha256") or "")
        for source in calibration["sources"]
    }
    collisions = sorted(normalized_hashes & calibration_normalized_hashes)
    if collisions:
        raise AcquisitionValidationError(
            f"Calibration normalized-content overlap detected: {collisions}"
        )
    return {
        "status": "valid",
        "source_count": len(sources),
        "domain_group_counts": dict(
            sorted(
                {
                    group: sum(
                        source["domain_group"] == group for source in sources.values()
                    )
                    for group in {source["domain_group"] for source in sources.values()}
                }.items()
            )
        ),
        "repository_document_files": repository_files,
        "retained_legal_files": legal_files,
        "raw_bytes": total_raw_bytes,
        "normalized_text_bytes": total_normalized_bytes,
        "calibration_hash_collisions": collisions,
        "model_calls": 0,
        "verifier_calls": 0,
        "trace_count": 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--catalog",
        type=Path,
        default=Path("benchmarks/contexttrace_unseen_v1/pre_acquisition_catalog.json"),
    )
    parser.add_argument(
        "--calibration-registry",
        type=Path,
        default=Path("benchmarks/contexttrace_unseen_v1/calibration/registry.json"),
    )
    parser.add_argument(
        "--source-manifest",
        type=Path,
        default=Path(
            "benchmarks/contexttrace_unseen_v1/candidate_source_manifest.json"
        ),
    )
    parser.add_argument(
        "--ledger",
        type=Path,
        default=Path("benchmarks/contexttrace_unseen_v1/acquisition_ledger.json"),
    )
    parser.add_argument(
        "--workspace",
        type=Path,
        default=Path(".tmp-contexttrace-unseen-v1-acquisition"),
    )
    parser.add_argument(
        "--source-schema",
        type=Path,
        default=Path("benchmarks/contexttrace_unseen_v1/source_manifest.schema.json"),
    )
    args = parser.parse_args()
    try:
        result = validate_acquisition(
            catalog=_load_json(args.catalog),
            calibration=_load_json(args.calibration_registry),
            manifest=_load_json(args.source_manifest),
            ledger=_load_json(args.ledger),
            workspace=args.workspace,
            source_schema=args.source_schema,
        )
    except (AcquisitionError, AcquisitionValidationError, OSError, ValueError) as exc:
        print(f"acquisition validation failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
