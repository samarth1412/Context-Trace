"""Acquire and deterministically normalize the authorized Unseen-v1 sources.

This module deliberately contains no generator, verifier, annotation, or
evaluation integration. It accepts only the exact immutable snapshots recorded
in the reviewed pre-acquisition catalog.
"""

from __future__ import annotations

import argparse
import copy
import datetime as dt
import gzip
import hashlib
import html
import json
import os
import ssl
import subprocess
import sys
import tarfile
import time
import unicodedata
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path, PurePosixPath
from typing import Any, Mapping, Sequence

import certifi
from jsonschema import (  # type: ignore[import-untyped]
    Draft202012Validator,
    FormatChecker,
)

from benchmarks.contexttrace_unseen_v1.validate_pre_acquisition import (
    validate_catalog,
)


EXTRACTION_VERSION = "contexttrace-unseen-text-v1"
AUTHORIZATION_DECISION = "9A"
MAX_TEXT_FILE_BYTES = 5 * 1024 * 1024
TEXT_SUFFIXES = {
    ".adoc",
    ".asciidoc",
    ".htm",
    ".html",
    ".md",
    ".mdx",
    ".rdoc",
    ".rst",
    ".text",
    ".txt",
    ".xml",
}
TEXT_BASENAMES = {"readme", "readme.md", "readme.rst", "readme.txt"}
EXCLUDED_DIRECTORY_NAMES = {
    ".git",
    "_build",
    "assets",
    "build",
    "dist",
    "generated",
    "images",
    "img",
    "node_modules",
    "static",
    "target",
    "third-party",
    "third_party",
    "vendor",
    "vendors",
}
ROOT_LEGAL_PATTERNS = (
    "LICENSE",
    "LICENSE.*",
    "NOTICE",
    "NOTICE.*",
    "COPYING",
    "COPYING.*",
    "COPYRIGHT",
    "COPYRIGHT.*",
)
XML_EXCLUDED_TAGS = {
    "FORM",
    "GPH",
    "GRAPHIC",
    "IMG",
    "MATH",
    "SCRIPT",
    "STYLE",
    "SVG",
}
DISJOINT_DIMENSIONS = [
    "source_id",
    "source_document_id",
    "source_family",
    "domain_id",
    "publication_window",
    "snapshot_sha256",
    "normalized_content_sha256",
    "near_duplicate_cluster_id",
]


class AcquisitionError(RuntimeError):
    """The authorized source acquisition cannot safely continue."""


def _utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _sha512_file(path: Path) -> str:
    digest = hashlib.sha512()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _canonical_text_hash(text: str) -> str:
    canonical = " ".join(unicodedata.normalize("NFKC", text).casefold().split())
    return _sha256_bytes(canonical.encode("utf-8"))


def _publication_window(timestamp: str) -> str:
    parsed = dt.datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    half = 1 if parsed.month <= 6 else 2
    return f"{parsed.year}-H{half}"


def _safe_relative_path(path: Path, root: Path) -> str:
    relative = path.relative_to(root).as_posix()
    if relative.startswith("/") or ".." in PurePosixPath(relative).parts:
        raise AcquisitionError(f"Unsafe relative path: {relative}")
    return relative


def _validate_authorization(catalog: Mapping[str, Any]) -> None:
    authorization = catalog.get("acquisition_authorization")
    if not isinstance(authorization, Mapping):
        raise AcquisitionError("The catalog lacks acquisition authorization.")
    if authorization.get("decision") != AUTHORIZATION_DECISION:
        raise AcquisitionError("Decision 9A is required for source acquisition.")
    expected_false = (
        "model_calls_authorized",
        "trace_generation_authorized",
        "annotation_authorized",
        "evaluation_authorized",
        "external_publication_authorized",
    )
    if any(authorization.get(field) is not False for field in expected_false):
        raise AcquisitionError("Decision 9A must not authorize downstream work.")
    if catalog.get("status") != "reviewed_and_authorized_for_local_acquisition":
        raise AcquisitionError("Catalog status does not permit acquisition.")
    amendment = catalog.get("content_yield_amendment")
    if not isinstance(amendment, Mapping) or amendment.get("decision") != "10A":
        raise AcquisitionError("Decision 10A is required for the content amendment.")
    if (
        amendment.get("source_family_substitution_authorized") is not False
        or amendment.get("model_calls_authorized") is not False
    ):
        raise AcquisitionError(
            "Decision 10A must not broaden source families or calls."
        )


def _run_git(args: Sequence[str], *, cwd: Path | None = None) -> str:
    command = ["git", *args]
    completed = subprocess.run(
        command,
        cwd=cwd,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=600,
    )
    if completed.returncode:
        stderr = completed.stderr.strip()
        raise AcquisitionError(f"Git command failed ({' '.join(command)}): {stderr}")
    return completed.stdout.strip()


def _prepare_sparse_checkout(entry: Mapping[str, Any], checkout: Path) -> None:
    expected_commit = str(entry["commit_sha1"])
    patterns = [f"/{str(entry['content_root']).strip('/')}/"]
    patterns.extend(f"/{pattern}" for pattern in ROOT_LEGAL_PATTERNS)
    if (checkout / ".git").is_dir():
        actual = _run_git(["rev-parse", "HEAD"], cwd=checkout)
        if actual == expected_commit:
            sparse_file = checkout / ".git/info/sparse-checkout"
            sparse_file.write_text("\n".join(patterns) + "\n", encoding="utf-8")
            _run_git(["sparse-checkout", "reapply"], cwd=checkout)
            return
        raise AcquisitionError(
            f"{entry['family_id']} checkout exists at unexpected commit {actual}."
        )

    checkout.mkdir(parents=True, exist_ok=False)
    _run_git(["init", "--quiet"], cwd=checkout)
    _run_git(["remote", "add", "origin", str(entry["repository_url"])], cwd=checkout)
    _run_git(["sparse-checkout", "init", "--no-cone"], cwd=checkout)
    sparse_file = checkout / ".git/info/sparse-checkout"
    sparse_file.write_text("\n".join(patterns) + "\n", encoding="utf-8")
    _run_git(
        [
            "-c",
            "protocol.version=2",
            "fetch",
            "--quiet",
            "--depth=1",
            "--filter=blob:none",
            "origin",
            expected_commit,
        ],
        cwd=checkout,
    )
    _run_git(["checkout", "--quiet", "--detach", "FETCH_HEAD"], cwd=checkout)
    actual = _run_git(["rev-parse", "HEAD"], cwd=checkout)
    if actual != expected_commit:
        raise AcquisitionError(
            f"{entry['family_id']} resolved to {actual}, expected {expected_commit}."
        )


def _is_excluded_path(relative: PurePosixPath) -> str | None:
    for part in relative.parts[:-1]:
        if part.casefold() in EXCLUDED_DIRECTORY_NAMES:
            return f"excluded_directory:{part.casefold()}"
    name = relative.name.casefold()
    suffix = relative.suffix.casefold()
    if name not in TEXT_BASENAMES and suffix not in TEXT_SUFFIXES:
        return "unsupported_extension"
    return None


def _eligible_repository_files(
    content_root: Path,
) -> tuple[list[Path], Counter[str]]:
    if not content_root.is_dir():
        raise AcquisitionError(f"Documentation root is absent: {content_root}")
    included: list[Path] = []
    exclusions: Counter[str] = Counter()
    for path in sorted(content_root.rglob("*")):
        if path.is_symlink():
            exclusions["symlink"] += 1
            continue
        if not path.is_file():
            continue
        relative = PurePosixPath(path.relative_to(content_root).as_posix())
        reason = _is_excluded_path(relative)
        if reason:
            exclusions[reason] += 1
            continue
        size = path.stat().st_size
        if size > MAX_TEXT_FILE_BYTES:
            exclusions["oversized_text_file"] += 1
            continue
        payload = path.read_bytes()
        if b"\x00" in payload:
            exclusions["binary_content"] += 1
            continue
        try:
            payload.decode("utf-8")
        except UnicodeDecodeError:
            exclusions["non_utf8"] += 1
            continue
        included.append(path)
    if not included:
        raise AcquisitionError(f"No eligible text files found under {content_root}.")
    return included, exclusions


def _root_legal_files(checkout: Path) -> list[Path]:
    legal: set[Path] = set()
    for pattern in ROOT_LEGAL_PATTERNS:
        for path in checkout.glob(pattern):
            if path.is_file() and not path.is_symlink():
                legal.add(path)
    return sorted(legal)


class _VisibleHTMLText(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._excluded_depth = 0
        self._parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        del attrs
        folded = tag.casefold()
        if folded == "img":
            return
        if folded in {"script", "style", "svg", "form"}:
            self._excluded_depth += 1
        elif not self._excluded_depth and folded in {
            "br",
            "div",
            "h1",
            "h2",
            "h3",
            "h4",
            "h5",
            "h6",
            "li",
            "p",
            "pre",
            "section",
            "table",
            "td",
            "th",
            "tr",
        }:
            self._parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag.casefold() in {"script", "style", "svg", "form"}:
            self._excluded_depth = max(0, self._excluded_depth - 1)
        elif not self._excluded_depth:
            self._parts.append("\n")

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        del tag, attrs

    def handle_data(self, data: str) -> None:
        if not self._excluded_depth:
            self._parts.append(data)

    def text(self) -> str:
        return "".join(self._parts)


def _xml_visible_text(payload: bytes) -> str:
    try:
        root = ET.fromstring(payload)
    except ET.ParseError as exc:
        raise AcquisitionError(f"Invalid XML snapshot: {exc}") from exc

    parts: list[str] = []

    def visit(node: ET.Element) -> None:
        tag = node.tag.rsplit("}", 1)[-1].casefold().upper()
        if tag in XML_EXCLUDED_TAGS:
            if node.tail:
                parts.append(node.tail)
            return
        if node.text:
            parts.append(node.text)
        for child in node:
            visit(child)
        if node.tail:
            parts.append(node.tail)

    visit(root)
    return "\n".join(part.strip() for part in parts if part.strip())


def _extract_payload(payload: bytes, suffix: str) -> str:
    suffix = suffix.casefold()
    if suffix in {".html", ".htm", ".xml"}:
        parser = _VisibleHTMLText()
        parser.feed(payload.decode("utf-8"))
        text = parser.text()
    else:
        text = payload.decode("utf-8")
    text = html.unescape(text)
    return text.replace("\r\n", "\n").replace("\r", "\n").strip()


def _extract_text(path: Path) -> str:
    return _extract_payload(path.read_bytes(), path.suffix)


def _write_deterministic_tar(
    output: Path,
    *,
    content_root: Path,
    content_files: Sequence[Path],
    checkout: Path,
    legal_files: Sequence[Path],
) -> None:
    members: list[tuple[str, bytes]] = [
        (
            f"content/{_safe_relative_path(path, content_root)}",
            path.read_bytes(),
        )
        for path in content_files
    ]
    members.extend(
        (
            f"legal/{_safe_relative_path(path, checkout)}",
            path.read_bytes(),
        )
        for path in legal_files
    )
    _write_deterministic_payload_tar(output, members)


def _write_deterministic_payload_tar(
    output: Path, members: Sequence[tuple[str, bytes]]
) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("wb") as raw_handle:
        with gzip.GzipFile(
            filename="", mode="wb", fileobj=raw_handle, mtime=0
        ) as gzip_handle:
            with tarfile.open(fileobj=gzip_handle, mode="w") as archive:
                for archive_name, payload in sorted(members):
                    info = tarfile.TarInfo(name=archive_name)
                    info.size = len(payload)
                    info.mtime = 0
                    info.uid = 0
                    info.gid = 0
                    info.uname = ""
                    info.gname = ""
                    info.mode = 0o444
                    archive.addfile(info, fileobj=_BytesReader(payload))


class _BytesReader:
    def __init__(self, payload: bytes) -> None:
        self._payload = payload
        self._position = 0

    def read(self, size: int = -1) -> bytes:
        if size < 0:
            size = len(self._payload) - self._position
        start = self._position
        end = min(len(self._payload), start + size)
        self._position = end
        return self._payload[start:end]


def _write_normalized_repository_text(
    output: Path, content_root: Path, files: Sequence[Path]
) -> None:
    sections: list[str] = []
    for path in files:
        relative = _safe_relative_path(path, content_root)
        extracted = _extract_text(path)
        if extracted:
            sections.append(f"===== FILE: {relative} =====\n{extracted}")
    if not sections:
        raise AcquisitionError(f"No visible text extracted from {content_root}.")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n\n".join(sections) + "\n", encoding="utf-8")


def _download(url: str, *, attempts: int = 3) -> tuple[bytes, Mapping[str, str]]:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/xml,text/xml;q=0.9,*/*;q=0.1",
            "User-Agent": "ContextTrace-Unseen-v1-research-collector/1.0",
        },
    )
    tls_context = ssl.create_default_context(cafile=certifi.where())
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            with urllib.request.urlopen(
                request, timeout=120, context=tls_context
            ) as response:
                payload = response.read()
                headers = dict(response.headers.items())
                if response.status != 200:
                    raise AcquisitionError(
                        f"Unexpected HTTP status {response.status} for {url}."
                    )
                return payload, headers
        except (OSError, urllib.error.URLError, AcquisitionError) as exc:
            last_error = exc
            if attempt < attempts:
                time.sleep(2 ** (attempt - 1))
    raise AcquisitionError(f"Download failed after {attempts} attempts: {url}") from (
        last_error
    )


def _download_archive(url: str, destination: Path, *, expected_sha512: str) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.is_file():
        actual = _sha512_file(destination)
        if actual == expected_sha512:
            return
        raise AcquisitionError(
            f"Existing archive checksum mismatch: expected {expected_sha512}, "
            f"got {actual}."
        )
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "ContextTrace-Unseen-v1-research-collector/1.0"},
    )
    tls_context = ssl.create_default_context(cafile=certifi.where())
    partial = destination.with_name(f"{destination.name}.partial")
    try:
        with urllib.request.urlopen(
            request, timeout=120, context=tls_context
        ) as response:
            if response.status != 200:
                raise AcquisitionError(
                    f"Unexpected HTTP status {response.status} for {url}."
                )
            with partial.open("wb") as handle:
                for block in iter(lambda: response.read(1024 * 1024), b""):
                    handle.write(block)
        actual = _sha512_file(partial)
        if actual != expected_sha512:
            raise AcquisitionError(
                f"Downloaded archive checksum mismatch: expected {expected_sha512}, "
                f"got {actual}."
            )
        partial.replace(destination)
    except (OSError, urllib.error.URLError) as exc:
        raise AcquisitionError(f"Archive download failed: {url}") from exc


def _source_record(
    *,
    entry: Mapping[str, Any],
    catalog: Mapping[str, Any],
    collected_at: str,
    published_at: str,
    snapshot_path: str,
    snapshot_sha256: str,
    normalized_path: str,
    normalized_sha256: str,
    content_type: str,
    metadata: Mapping[str, Any],
) -> dict[str, Any]:
    family_id = str(entry["family_id"])
    license_profile = catalog["license_profiles"][entry["license_profile"]]
    access_profile = catalog["access_profiles"][entry["access_profile"]]
    license_ids = license_profile["license_ids"]
    restrictions = list(dict.fromkeys(license_profile["required_actions"]))
    restrictions.append(str(access_profile["collection_method"]))
    return {
        "source_id": f"{family_id}_snapshot",
        "source_document_id": f"{family_id}_snapshot",
        "document_lineage_id": f"{family_id}_lineage",
        "source_family": family_id,
        "domain_group": entry["domain_group"],
        "domain_id": entry["domain_id"],
        "publication_window": _publication_window(published_at),
        "source_url": entry["canonical_url"],
        "canonical_identifier": _canonical_identifier(entry),
        "snapshot_path": snapshot_path,
        "snapshot_sha256": snapshot_sha256,
        "normalized_text_path": normalized_path,
        "normalized_content_sha256": normalized_sha256,
        "near_duplicate_cluster_id": f"{family_id}_cluster",
        "collected_at": collected_at,
        "published_at": published_at,
        "language": "en",
        "content_type": content_type,
        "source_conditions": ["current", "canonical"],
        "authority_basis": (
            "Official publisher repository, official release archive, or official "
            "eCFR Versioner API at the immutable cataloged snapshot."
        ),
        "license": {
            "license_id": " OR ".join(license_ids),
            "terms_url": license_profile["terms_url"],
            "redistribution": "permitted",
            "attribution_required": bool(license_profile["attribution_required"]),
            "review_status": "approved",
            "reviewed_by": "project owner; Codex-assisted terms review",
            "reviewed_at": "2026-07-24T00:00:00Z",
            "notes": "; ".join(license_profile["required_actions"]),
        },
        "access": {
            "access_class": "public",
            "authentication_required": False,
            "collection_permitted": True,
            "restrictions": restrictions,
        },
        "privacy_classification": "public",
        "metadata": dict(metadata),
    }


def _canonical_identifier(entry: Mapping[str, Any]) -> str:
    if entry["access_profile"] == "ecfr_versioner_api":
        return (
            f"ecfr:title-{entry['title']}:part-{entry['part']}:{entry['snapshot_date']}"
        )
    if entry["access_profile"] == "apache_release_archive":
        return f"{entry['archive_url']}#sha512={entry['archive_sha512']}"
    return (
        f"{entry['repository_url']}@{entry['commit_sha1']}:"
        f"{str(entry['content_root']).strip('/')}"
    )


def _acquire_repository(
    entry: Mapping[str, Any],
    *,
    catalog: Mapping[str, Any],
    workspace: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    family_id = str(entry["family_id"])
    checkout = workspace / "checkouts" / family_id
    _prepare_sparse_checkout(entry, checkout)
    content_root = checkout / str(entry["content_root"])
    files, exclusions = _eligible_repository_files(content_root)
    legal_files = _root_legal_files(checkout)

    raw_path = workspace / "artifacts/raw" / f"{family_id}.tar.gz"
    normalized_path = workspace / "artifacts/normalized" / f"{family_id}.txt"
    _write_deterministic_tar(
        raw_path,
        content_root=content_root,
        content_files=files,
        checkout=checkout,
        legal_files=legal_files,
    )
    _write_normalized_repository_text(normalized_path, content_root, files)
    collected_at = _utc_now()
    published_at = _run_git(
        ["show", "-s", "--format=%cI", str(entry["commit_sha1"])], cwd=checkout
    )
    if not published_at:
        raise AcquisitionError(f"{family_id} lacks a commit timestamp.")
    published_at = (
        dt.datetime.fromisoformat(published_at)
        .astimezone(dt.timezone.utc)
        .isoformat()
        .replace("+00:00", "Z")
    )

    raw_relative = _safe_relative_path(raw_path, workspace)
    normalized_relative = _safe_relative_path(normalized_path, workspace)
    raw_sha256 = _sha256_file(raw_path)
    normalized_text = normalized_path.read_text(encoding="utf-8")
    normalized_sha256 = _canonical_text_hash(normalized_text)
    metadata = {
        "publisher": entry["publisher"],
        "release_ref": entry["release_ref"],
        "commit_sha1": entry["commit_sha1"],
        "content_root": entry["content_root"],
        "acquisition_method": entry["access_profile"],
        "extraction_version": EXTRACTION_VERSION,
        "included_document_files": len(files),
        "retained_legal_files": len(legal_files),
        "excluded_files_by_reason": dict(sorted(exclusions.items())),
    }
    record = _source_record(
        entry=entry,
        catalog=catalog,
        collected_at=collected_at,
        published_at=published_at,
        snapshot_path=raw_relative,
        snapshot_sha256=raw_sha256,
        normalized_path=normalized_relative,
        normalized_sha256=normalized_sha256,
        content_type="application/gzip",
        metadata=metadata,
    )
    ledger = {
        "family_id": family_id,
        "status": "acquired_and_normalized",
        "collected_at": collected_at,
        "expected_commit_sha1": entry["commit_sha1"],
        "resolved_commit_sha1": _run_git(["rev-parse", "HEAD"], cwd=checkout),
        "snapshot_path": raw_relative,
        "snapshot_bytes": raw_path.stat().st_size,
        "snapshot_sha256": raw_sha256,
        "normalized_text_path": normalized_relative,
        "normalized_text_bytes": normalized_path.stat().st_size,
        "normalized_content_sha256": normalized_sha256,
        **metadata,
    }
    return record, ledger


def _acquire_apache_release(
    entry: Mapping[str, Any],
    *,
    catalog: Mapping[str, Any],
    workspace: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    family_id = str(entry["family_id"])
    upstream_path = workspace / "downloads" / Path(str(entry["archive_url"])).name
    _download_archive(
        str(entry["archive_url"]),
        upstream_path,
        expected_sha512=str(entry["archive_sha512"]),
    )
    requested_content = list(entry["archive_member_paths"])
    requested_legal = list(entry["archive_legal_member_paths"])
    requested = set(requested_content) | set(requested_legal)
    payloads: dict[str, bytes] = {}
    try:
        with tarfile.open(upstream_path, mode="r:gz") as archive:
            for member in archive.getmembers():
                if member.name not in requested:
                    continue
                if not member.isfile():
                    raise AcquisitionError(
                        f"Reviewed archive member is not a file: {member.name}"
                    )
                handle = archive.extractfile(member)
                if handle is None:
                    raise AcquisitionError(
                        f"Reviewed archive member is unreadable: {member.name}"
                    )
                payloads[member.name] = handle.read()
    except (OSError, tarfile.TarError) as exc:
        raise AcquisitionError(f"Invalid Apache release archive: {exc}") from exc
    missing = sorted(requested - payloads.keys())
    if missing:
        raise AcquisitionError(f"Reviewed Apache archive members are absent: {missing}")

    content_members: list[tuple[str, bytes]] = []
    normalized_sections: list[str] = []
    for member_name in requested_content:
        payload = payloads[member_name]
        relative = PurePosixPath(member_name).name
        if len(payload) > MAX_TEXT_FILE_BYTES or b"\x00" in payload:
            raise AcquisitionError(
                f"Reviewed Apache documentation is ineligible: {member_name}"
            )
        extracted = _extract_payload(payload, PurePosixPath(member_name).suffix)
        if not extracted:
            raise AcquisitionError(
                f"Reviewed Apache documentation has no visible text: {member_name}"
            )
        content_members.append((f"content/{relative}", payload))
        normalized_sections.append(f"===== FILE: {relative} =====\n{extracted}")
    legal_members = [
        (f"legal/{PurePosixPath(name).name}", payloads[name])
        for name in requested_legal
    ]

    raw_path = workspace / "artifacts/raw" / f"{family_id}.tar.gz"
    normalized_path = workspace / "artifacts/normalized" / f"{family_id}.txt"
    _write_deterministic_payload_tar(raw_path, [*content_members, *legal_members])
    normalized_path.parent.mkdir(parents=True, exist_ok=True)
    normalized_path.write_text(
        "\n\n".join(normalized_sections) + "\n", encoding="utf-8"
    )
    collected_at = _utc_now()
    raw_relative = _safe_relative_path(raw_path, workspace)
    normalized_relative = _safe_relative_path(normalized_path, workspace)
    raw_sha256 = _sha256_file(raw_path)
    normalized_sha256 = _canonical_text_hash(
        normalized_path.read_text(encoding="utf-8")
    )
    metadata = {
        "publisher": entry["publisher"],
        "release_ref": entry["release_ref"],
        "upstream_archive_url": entry["archive_url"],
        "upstream_archive_sha512": entry["archive_sha512"],
        "upstream_archive_bytes": upstream_path.stat().st_size,
        "selected_archive_members": requested_content,
        "selected_legal_members": requested_legal,
        "acquisition_method": entry["access_profile"],
        "extraction_version": EXTRACTION_VERSION,
        "included_document_files": len(content_members),
        "retained_legal_files": len(legal_members),
        "excluded_files_by_reason": {
            "not_in_reviewed_archive_member_allowlist": "all other members"
        },
    }
    record = _source_record(
        entry=entry,
        catalog=catalog,
        collected_at=collected_at,
        published_at=str(entry["published_at"]),
        snapshot_path=raw_relative,
        snapshot_sha256=raw_sha256,
        normalized_path=normalized_relative,
        normalized_sha256=normalized_sha256,
        content_type="application/gzip",
        metadata=metadata,
    )
    ledger = {
        "family_id": family_id,
        "status": "acquired_and_normalized",
        "collected_at": collected_at,
        "snapshot_path": raw_relative,
        "snapshot_bytes": raw_path.stat().st_size,
        "snapshot_sha256": raw_sha256,
        "normalized_text_path": normalized_relative,
        "normalized_text_bytes": normalized_path.stat().st_size,
        "normalized_content_sha256": normalized_sha256,
        **metadata,
    }
    return record, ledger


def _acquire_ecfr(
    entry: Mapping[str, Any],
    *,
    catalog: Mapping[str, Any],
    workspace: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    family_id = str(entry["family_id"])
    payload, response_headers = _download(str(entry["canonical_url"]))
    if not payload.lstrip().startswith(b"<"):
        raise AcquisitionError(f"{family_id} response is not an XML document.")
    visible_text = _xml_visible_text(payload)
    if not visible_text.strip():
        raise AcquisitionError(f"{family_id} XML contains no eligible text.")

    raw_path = workspace / "artifacts/raw" / f"{family_id}.xml"
    normalized_path = workspace / "artifacts/normalized" / f"{family_id}.txt"
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    normalized_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_bytes(payload)
    normalized_path.write_text(visible_text.strip() + "\n", encoding="utf-8")
    collected_at = _utc_now()
    published_at = f"{entry['snapshot_date']}T00:00:00Z"
    raw_relative = _safe_relative_path(raw_path, workspace)
    normalized_relative = _safe_relative_path(normalized_path, workspace)
    raw_sha256 = _sha256_file(raw_path)
    normalized_sha256 = _canonical_text_hash(
        normalized_path.read_text(encoding="utf-8")
    )
    metadata = {
        "publisher": entry["publisher"],
        "snapshot_date": entry["snapshot_date"],
        "title": entry["title"],
        "part": entry["part"],
        "acquisition_method": entry["access_profile"],
        "extraction_version": EXTRACTION_VERSION,
        "excluded_element_types": sorted(XML_EXCLUDED_TAGS),
        "response_content_type": response_headers.get("Content-Type"),
        "response_last_modified": response_headers.get("Last-Modified"),
    }
    record = _source_record(
        entry=entry,
        catalog=catalog,
        collected_at=collected_at,
        published_at=published_at,
        snapshot_path=raw_relative,
        snapshot_sha256=raw_sha256,
        normalized_path=normalized_relative,
        normalized_sha256=normalized_sha256,
        content_type="application/xml",
        metadata=metadata,
    )
    ledger = {
        "family_id": family_id,
        "status": "acquired_and_normalized",
        "collected_at": collected_at,
        "snapshot_date": entry["snapshot_date"],
        "title": entry["title"],
        "part": entry["part"],
        "snapshot_path": raw_relative,
        "snapshot_bytes": raw_path.stat().st_size,
        "snapshot_sha256": raw_sha256,
        "normalized_text_path": normalized_relative,
        "normalized_text_bytes": normalized_path.stat().st_size,
        "normalized_content_sha256": normalized_sha256,
        **metadata,
    }
    return record, ledger


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise AcquisitionError(f"Expected a JSON object in {path}.")
    return value


def _validate_source_manifest(manifest: Mapping[str, Any], schema: Path) -> None:
    validator = Draft202012Validator(_load_json(schema), format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(manifest), key=lambda item: list(item.path))
    if errors:
        rendered = "; ".join(
            f"{'/'.join(str(part) for part in error.path) or '<root>'}: {error.message}"
            for error in errors[:10]
        )
        raise AcquisitionError(f"Candidate source manifest is invalid: {rendered}")
    sources = manifest["sources"]
    if len(sources) != 36:
        raise AcquisitionError("Candidate source manifest requires 36 sources.")
    if len({source["source_family"] for source in sources}) != 36:
        raise AcquisitionError("Candidate source families are not unique.")
    normalized_hashes = [source["normalized_content_sha256"] for source in sources]
    if len(set(normalized_hashes)) != len(normalized_hashes):
        raise AcquisitionError("Candidate normalized source snapshots collide.")


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def acquire(
    *,
    catalog_path: Path,
    calibration_path: Path,
    schema_path: Path,
    workspace: Path,
    output_manifest: Path,
    output_ledger: Path,
    family_ids: set[str] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    catalog = _load_json(catalog_path)
    calibration = _load_json(calibration_path)
    _validate_authorization(catalog)
    validate_catalog(catalog, calibration, require_attestation=True)
    workspace.mkdir(parents=True, exist_ok=True)
    os.chmod(workspace, 0o700)

    selected_entries = [
        entry
        for entry in catalog["entries"]
        if family_ids is None or entry["family_id"] in family_ids
    ]
    if family_ids is not None:
        found = {entry["family_id"] for entry in selected_entries}
        missing = sorted(family_ids - found)
        if missing:
            raise AcquisitionError(f"Unknown requested families: {missing}")

    prior_records: dict[str, dict[str, Any]] = {}
    prior_ledger: dict[str, dict[str, Any]] = {}
    if output_manifest.exists():
        prior = _load_json(output_manifest)
        prior_records = {
            source["source_family"]: source for source in prior.get("sources", [])
        }
    if output_ledger.exists():
        prior = _load_json(output_ledger)
        prior_ledger = {item["family_id"]: item for item in prior.get("sources", [])}

    records = copy.deepcopy(prior_records)
    ledger_items = copy.deepcopy(prior_ledger)
    for index, entry in enumerate(selected_entries, start=1):
        family_id = str(entry["family_id"])
        print(
            f"[{index}/{len(selected_entries)}] acquiring {family_id}",
            flush=True,
        )
        if entry["access_profile"] in {
            "github_commit_archive",
            "gitlab_commit_archive",
        }:
            record, ledger = _acquire_repository(
                entry, catalog=catalog, workspace=workspace
            )
        elif entry["access_profile"] == "apache_release_archive":
            record, ledger = _acquire_apache_release(
                entry, catalog=catalog, workspace=workspace
            )
        elif entry["access_profile"] == "ecfr_versioner_api":
            record, ledger = _acquire_ecfr(entry, catalog=catalog, workspace=workspace)
        else:
            raise AcquisitionError(
                f"Unsupported access profile for {family_id}: {entry['access_profile']}"
            )
        records[family_id] = record
        ledger_items[family_id] = ledger
        partial_manifest = {
            "schema_version": "1.0",
            "manifest_kind": "contexttrace_unseen_v1_sources",
            "created_at": _utc_now(),
            "domain_ontology_version": "cain2027-v1",
            "disjoint_dimensions": DISJOINT_DIMENSIONS,
            "sources": [records[key] for key in sorted(records)],
        }
        partial_ledger = {
            "schema_version": "1.0",
            "record_kind": "contexttrace_unseen_v1_acquisition",
            "status": "in_progress",
            "recorded_at": _utc_now(),
            "authorization_decision": AUTHORIZATION_DECISION,
            "catalog_sha256": _sha256_file(catalog_path),
            "workspace_artifact_root": "private working directory; not published",
            "extraction_version": EXTRACTION_VERSION,
            "model_calls": 0,
            "verifier_calls": 0,
            "trace_count": 0,
            "sources": [ledger_items[key] for key in sorted(ledger_items)],
        }
        _write_json(output_manifest, partial_manifest)
        _write_json(output_ledger, partial_ledger)

    manifest = {
        "schema_version": "1.0",
        "manifest_kind": "contexttrace_unseen_v1_sources",
        "created_at": _utc_now(),
        "domain_ontology_version": "cain2027-v1",
        "disjoint_dimensions": DISJOINT_DIMENSIONS,
        "sources": [records[key] for key in sorted(records)],
    }
    complete = len(records) == 36
    if complete:
        _validate_source_manifest(manifest, schema_path)
    ledger = {
        "schema_version": "1.0",
        "record_kind": "contexttrace_unseen_v1_acquisition",
        "status": "complete" if complete else "in_progress",
        "recorded_at": _utc_now(),
        "authorization_decision": AUTHORIZATION_DECISION,
        "catalog_sha256": _sha256_file(catalog_path),
        "source_manifest_sha256": _sha256_bytes(
            (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode("utf-8")
        ),
        "workspace_artifact_root": "private working directory; not published",
        "extraction_version": EXTRACTION_VERSION,
        "source_count": len(records),
        "model_calls": 0,
        "verifier_calls": 0,
        "trace_count": 0,
        "sources": [ledger_items[key] for key in sorted(ledger_items)],
    }
    _write_json(output_manifest, manifest)
    _write_json(output_ledger, ledger)
    return manifest, ledger


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
        "--source-schema",
        type=Path,
        default=Path("benchmarks/contexttrace_unseen_v1/source_manifest.schema.json"),
    )
    parser.add_argument(
        "--workspace",
        type=Path,
        default=Path(".tmp-contexttrace-unseen-v1-acquisition"),
    )
    parser.add_argument(
        "--output-manifest",
        type=Path,
        default=Path(
            "benchmarks/contexttrace_unseen_v1/candidate_source_manifest.json"
        ),
    )
    parser.add_argument(
        "--output-ledger",
        type=Path,
        default=Path("benchmarks/contexttrace_unseen_v1/acquisition_ledger.json"),
    )
    parser.add_argument("--family", action="append", dest="families")
    args = parser.parse_args()
    try:
        manifest, ledger = acquire(
            catalog_path=args.catalog,
            calibration_path=args.calibration_registry,
            schema_path=args.source_schema,
            workspace=args.workspace,
            output_manifest=args.output_manifest,
            output_ledger=args.output_ledger,
            family_ids=set(args.families) if args.families else None,
        )
    except (AcquisitionError, OSError, ValueError) as exc:
        print(f"acquisition failed: {exc}", file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "status": ledger["status"],
                "source_count": len(manifest["sources"]),
                "model_calls": ledger["model_calls"],
                "verifier_calls": ledger["verifier_calls"],
                "trace_count": ledger["trace_count"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
