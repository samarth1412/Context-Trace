"""Acquire and validate the authorized temporal/source-condition snapshots.

This module has no generator, verifier, annotation, evaluation, or publishing
integration. Network access is limited to the exact public identities in the
approved catalog and to commit-pinned repository license files.
"""

from __future__ import annotations

import argparse
import datetime as dt
import difflib
import gzip
import hashlib
import html
import io
import json
import os
import re
import ssl
import sys
import tarfile
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Mapping, Sequence

import certifi
from jsonschema import Draft202012Validator, FormatChecker  # type: ignore[import-untyped]

from benchmarks.contexttrace_unseen_v1.build_temporal_pre_acquisition_catalog import (
    validate_catalog,
)


EXPECTED_CATALOG_SHA256 = (
    "a3781a725ad5100a610e8a6e2bec1b7458903333622ce0461d095c88c8bd6678"
)
AUTHORIZATION_ID = "11A"
EXTRACTION_VERSION = "contexttrace-unseen-temporal-text-v1"
MAX_DOWNLOAD_BYTES = 256 * 1024 * 1024
MAX_MEMBER_BYTES = 32 * 1024 * 1024
MAX_ZIP_UNCOMPRESSED_BYTES = 512 * 1024 * 1024
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
POSITIVE_LAW_TITLES = {1, 3, 4, 5, 9, 10, 11, 13, 14, 17, 18, 23, 28, 31, 35, 36, 44, 46, 49, 51, 52, 54}
GOVERNMENT_XML_EXCLUDED_TAGS = {
    "form",
    "gph",
    "graphic",
    "img",
    "math",
    "script",
    "style",
    "svg",
}
USLM_EDITORIAL_EXCLUDED_TAGS = {
    "footnote",
    "notes",
    "sourcecredit",
    "statutorynote",
}
LEGAL_NAME_RE = re.compile(
    r"^(?:copying|copyright|license|licence|notice)(?:[._-].*)?$", re.IGNORECASE
)
GITHUB_IDENTIFIER_RE = re.compile(
    r"^github:(?P<repository>[^@]+)@(?P<commit>[a-f0-9]{40})$"
)
WIKIMEDIA_IDENTIFIER_RE = re.compile(
    r"^(?P<project>wikipedia|wikisource):page-(?P<page>\d+):revision-(?P<revision>\d+)$"
)
PAIR_ANCHORS = {
    "ctu1_pair_api_sklearn_feature_names": (
        ("get_feature_names",),
        ("get_feature_names_out",),
    ),
    "ctu1_pair_api_matplotlib_hist_density": (
        ("normed", "density"),
        ("density",),
    ),
    "ctu1_pair_api_scipy_imageio_imread": (
        ("imread", "imageio"),
        ("imread",),
    ),
    "ctu1_pair_api_pytest_yield_fixture": (
        ("yield_fixture",),
        ("fixture",),
    ),
    "ctu1_pair_api_pillow_resampling_lanczos": (
        ("antialias",),
        ("lanczos",),
    ),
}


class TemporalAcquisitionError(RuntimeError):
    """The authorized temporal acquisition cannot safely continue."""


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TemporalAcquisitionError(f"Expected an object in {path}.")
    return value


def write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def safe_relative(path: Path, root: Path) -> str:
    relative = path.resolve().relative_to(root.resolve()).as_posix()
    if PurePosixPath(relative).is_absolute() or ".." in PurePosixPath(relative).parts:
        raise TemporalAcquisitionError(f"Unsafe artifact path: {relative}")
    return relative


def prepare_private_workspace(path: Path) -> None:
    resolved = path.resolve()
    if path.name in {"", ".", ".."} or not path.name.startswith(
        ".tmp-contexttrace-unseen-v1-temporal"
    ):
        raise TemporalAcquisitionError(
            "Workspace must be a dedicated .tmp-contexttrace-unseen-v1-temporal* directory."
        )
    if resolved == Path("/") or resolved == Path.home().resolve():
        raise TemporalAcquisitionError("Refusing an unsafe workspace.")
    path.mkdir(parents=True, exist_ok=True)
    os.chmod(path, 0o700)


def validate_authorization(
    *,
    catalog_path: Path,
    catalog: Mapping[str, Any],
    authorization: Mapping[str, Any],
    calibration: Mapping[str, Any],
    natural: Mapping[str, Any],
) -> None:
    actual_hash = sha256_file(catalog_path)
    if actual_hash != EXPECTED_CATALOG_SHA256:
        raise TemporalAcquisitionError(
            f"Catalog hash mismatch: expected {EXPECTED_CATALOG_SHA256}, got {actual_hash}."
        )
    validate_catalog(
        catalog,
        calibration_registry=calibration,
        natural_source_manifest=natural,
    )
    if (
        authorization.get("authorization_id") != AUTHORIZATION_ID
        or authorization.get("authorized_catalog_sha256") != actual_hash
        or authorization.get("external_exposure_attestation")
        != "none_of_the_20_exact_temporal_source_pairs_influenced_contexttrace_or_groundlm_development"
    ):
        raise TemporalAcquisitionError("Exact-hash exposure authorization is absent.")
    scope = authorization.get("scope")
    if not isinstance(scope, Mapping):
        raise TemporalAcquisitionError("Authorization scope is absent.")
    required_true = {
        "source_acquisition_authorized",
        "local_normalization_authorized",
    }
    required_false = {
        "source_substitution_authorized",
        "paid_endpoints_authorized",
        "trace_generation_authorized",
        "model_calls_authorized",
        "verifier_calls_authorized",
        "annotation_authorized",
        "evaluation_authorized",
        "external_publication_authorized",
    }
    if any(scope.get(field) is not True for field in required_true) or any(
        scope.get(field) is not False for field in required_false
    ):
        raise TemporalAcquisitionError("Authorization scope was broadened or weakened.")
    if catalog.get("acquisition_budget_usd") != {
        "hard_limit": 0.0,
        "normal_operating_limit": 0.0,
        "paid_endpoints": 0,
    }:
        raise TemporalAcquisitionError("Acquisition is not locked to zero cost.")


def download(url: str, *, accept: str = "*/*", attempts: int = 3) -> bytes:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": accept,
            "User-Agent": (
                "ContextTrace-Unseen-v1-temporal-research-collector/1.0 "
                "(https://github.com/samarth1412/Context-Trace)"
            ),
        },
    )
    context = ssl.create_default_context(cafile=certifi.where())
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            with urllib.request.urlopen(
                request, timeout=180, context=context
            ) as response:
                if response.status != 200:
                    raise TemporalAcquisitionError(
                        f"Unexpected HTTP {response.status} for {url}."
                    )
                content_length = response.headers.get("Content-Length")
                if content_length and int(content_length) > MAX_DOWNLOAD_BYTES:
                    raise TemporalAcquisitionError(f"Download exceeds limit: {url}")
                payload = response.read(MAX_DOWNLOAD_BYTES + 1)
                if len(payload) > MAX_DOWNLOAD_BYTES:
                    raise TemporalAcquisitionError(f"Download exceeds limit: {url}")
                return payload
        except urllib.error.HTTPError as exc:
            last_error = exc
            if attempt < attempts:
                retry_after = exc.headers.get("Retry-After")
                delay = int(retry_after) if retry_after and retry_after.isdigit() else (
                    30 if exc.code == 429 else 5 * attempt
                )
                time.sleep(min(delay, 60))
        except (OSError, urllib.error.URLError, TemporalAcquisitionError) as exc:
            last_error = exc
            if attempt < attempts:
                time.sleep(2 ** (attempt - 1))
    raise TemporalAcquisitionError(
        f"Download failed after {attempts} attempts: {url}"
    ) from last_error


def persist_exact(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != payload:
            raise TemporalAcquisitionError(
                f"Existing artifact differs from acquired bytes: {path}"
            )
        return
    path.write_bytes(payload)


def normalized_lines(parts: Iterable[str]) -> str:
    lines: list[str] = []
    blank = False
    for part in parts:
        for raw_line in html.unescape(part).replace("\r", "\n").splitlines():
            line = " ".join(raw_line.split())
            if line:
                lines.append(line)
                blank = False
            elif lines and not blank:
                lines.append("")
                blank = True
    while lines and not lines[-1]:
        lines.pop()
    return "\n".join(lines) + "\n"


def xml_visible_text(
    payload: bytes, *, excluded_tags: set[str] | None = None
) -> str:
    excluded = GOVERNMENT_XML_EXCLUDED_TAGS | (excluded_tags or set())
    try:
        root = ET.fromstring(payload)
    except ET.ParseError as exc:
        raise TemporalAcquisitionError(f"Invalid XML: {exc}") from exc
    parts: list[str] = []

    def visit(node: ET.Element) -> None:
        tag = node.tag.rsplit("}", 1)[-1].casefold()
        if tag in excluded:
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
    return normalized_lines(parts)


class BytesReader:
    def __init__(self, payload: bytes) -> None:
        self.payload = payload
        self.position = 0

    def read(self, size: int = -1) -> bytes:
        if size < 0:
            size = len(self.payload) - self.position
        start = self.position
        end = min(len(self.payload), start + size)
        self.position = end
        return self.payload[start:end]


def deterministic_tar(members: Sequence[tuple[str, bytes]]) -> bytes:
    output = io.BytesIO()
    with gzip.GzipFile(filename="", mode="wb", fileobj=output, mtime=0) as gz:
        with tarfile.open(fileobj=gz, mode="w") as archive:
            for name, payload in sorted(members):
                pure = PurePosixPath(name)
                if pure.is_absolute() or ".." in pure.parts:
                    raise TemporalAcquisitionError(f"Unsafe archive member: {name}")
                info = tarfile.TarInfo(name)
                info.size = len(payload)
                info.mtime = 0
                info.uid = info.gid = 0
                info.uname = info.gname = ""
                info.mode = 0o444
                archive.addfile(info, BytesReader(payload))
    return output.getvalue()


def extract_ecfr(
    source: Mapping[str, Any], payload: bytes
) -> tuple[bytes, str, dict[str, Any]]:
    revision = source["immutable_revision"]
    if len(payload) != int(revision["expected_bytes"]):
        raise TemporalAcquisitionError(f"{source['source_id']} byte count changed.")
    if sha256_bytes(payload) != revision["expected_sha256"]:
        raise TemporalAcquisitionError(f"{source['source_id']} hash changed.")
    text = xml_visible_text(payload)
    if len(text) < 1000:
        raise TemporalAcquisitionError(f"{source['source_id']} has insufficient text.")
    return payload, text, {
        "effective_date": revision["value"],
        "upstream_bytes": len(payload),
        "upstream_sha256": sha256_bytes(payload),
        "included_document_files": 1,
        "retained_legal_files": 0,
    }


def acquire_ecfr(source: Mapping[str, Any]) -> tuple[bytes, str, dict[str, Any]]:
    payload = download(str(source["source_url"]), accept="application/xml")
    return extract_ecfr(source, payload)


def github_root_entries(repository: str, commit: str) -> list[Mapping[str, Any]]:
    url = (
        f"https://api.github.com/repos/{repository}/contents?"
        + urllib.parse.urlencode({"ref": commit})
    )
    value = json.loads(download(url, accept="application/vnd.github+json"))
    if not isinstance(value, list):
        raise TemporalAcquisitionError(f"Unexpected GitHub root listing for {repository}.")
    return [item for item in value if isinstance(item, Mapping)]


def github_legal_paths(repository: str, commit: str) -> list[str]:
    entries = github_root_entries(repository, commit)
    paths: list[str] = []
    for entry in entries:
        name = str(entry.get("name") or "")
        if not LEGAL_NAME_RE.fullmatch(name):
            continue
        if entry.get("type") == "file":
            paths.append(str(entry["path"]))
        elif entry.get("type") == "dir":
            url = (
                f"https://api.github.com/repos/{repository}/contents/"
                f"{urllib.parse.quote(str(entry['path']))}?"
                + urllib.parse.urlencode({"ref": commit})
            )
            children = json.loads(download(url, accept="application/vnd.github+json"))
            if not isinstance(children, list):
                raise TemporalAcquisitionError(
                    f"Unexpected legal directory listing for {repository}."
                )
            for child in children:
                if (
                    isinstance(child, Mapping)
                    and child.get("type") == "file"
                    and int(child.get("size") or 0) <= MAX_MEMBER_BYTES
                ):
                    paths.append(str(child["path"]))
    if not paths:
        raise TemporalAcquisitionError(
            f"No commit-pinned repository license found for {repository}@{commit}."
        )
    return sorted(set(paths))


def safe_allowlisted_path(value: str) -> str:
    pure = PurePosixPath(value)
    if pure.is_absolute() or ".." in pure.parts or not pure.parts:
        raise TemporalAcquisitionError(f"Unsafe allowlisted path: {value}")
    return pure.as_posix()


def raw_github_url(repository: str, commit: str, path: str) -> str:
    quoted = "/".join(urllib.parse.quote(part) for part in PurePosixPath(path).parts)
    return f"https://raw.githubusercontent.com/{repository}/{commit}/{quoted}"


def acquire_github(source: Mapping[str, Any]) -> tuple[bytes, str, dict[str, Any]]:
    match = GITHUB_IDENTIFIER_RE.fullmatch(str(source["canonical_identifier"]))
    if match is None:
        raise TemporalAcquisitionError(
            f"Invalid GitHub identity for {source['source_id']}."
        )
    repository = match.group("repository")
    commit = match.group("commit")
    if commit != source["immutable_revision"]["value"]:
        raise TemporalAcquisitionError(f"{source['source_id']} commit changed.")
    content_paths = sorted(
        safe_allowlisted_path(str(value))
        for value in source["extraction"]["allowlisted_paths"]
    )
    license_paths = github_legal_paths(repository, commit)
    members: list[tuple[str, bytes]] = []
    content_parts: list[str] = []
    member_hashes: dict[str, str] = {}
    for kind, paths in (("content", content_paths), ("legal", license_paths)):
        for path in paths:
            payload = download(raw_github_url(repository, commit, path))
            if len(payload) > MAX_MEMBER_BYTES or b"\x00" in payload:
                raise TemporalAcquisitionError(
                    f"Ineligible repository member: {repository}/{path}"
                )
            try:
                decoded = payload.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise TemporalAcquisitionError(
                    f"Non-UTF-8 repository member: {repository}/{path}"
                ) from exc
            archive_name = f"{kind}/{path}"
            members.append((archive_name, payload))
            member_hashes[archive_name] = sha256_bytes(payload)
            if kind == "content":
                content_parts.append(f"===== FILE: {path} =====\n{decoded}")
    text = normalized_lines(content_parts)
    if len(text) < 500:
        raise TemporalAcquisitionError(f"{source['source_id']} has insufficient text.")
    return deterministic_tar(members), text, {
        "repository": repository,
        "commit": commit,
        "release_ref": source["immutable_revision"]["release_ref"],
        "allowlisted_paths": content_paths,
        "retained_license_paths": license_paths,
        "member_sha256": dict(sorted(member_hashes.items())),
        "included_document_files": len(content_paths),
        "retained_legal_files": len(license_paths),
    }


def expand_section_selector(selector: str) -> list[str]:
    match = re.fullmatch(
        r"\d+ USC ([0-9a-z]+)(?:-([0-9a-z]+(?:-[0-9]+)?))?", selector
    )
    if match is None:
        raise TemporalAcquisitionError(f"Unsupported U.S. Code selector: {selector}")
    start, end = match.groups()
    if end is None:
        return [start]
    if start.isdigit() and end.isdigit():
        return [str(value) for value in range(int(start), int(end) + 1)]
    if end.startswith(f"{start}-") and end.removeprefix(f"{start}-").isdigit():
        last = int(end.removeprefix(f"{start}-"))
        return [start, *(f"{start}-{value}" for value in range(1, last + 1))]
    if end.isdigit() and "-" not in start:
        return [start, *(f"{start}-{value}" for value in range(1, int(end) + 1))]
    raise TemporalAcquisitionError(f"Unsupported U.S. Code range: {selector}")


def safe_zip_members(payload: bytes) -> tuple[zipfile.ZipFile, list[zipfile.ZipInfo]]:
    try:
        archive = zipfile.ZipFile(io.BytesIO(payload))
    except zipfile.BadZipFile as exc:
        raise TemporalAcquisitionError(f"Invalid OLRC ZIP: {exc}") from exc
    members = archive.infolist()
    total = 0
    for member in members:
        pure = PurePosixPath(member.filename)
        if (
            pure.is_absolute()
            or ".." in pure.parts
            or member.flag_bits & 0x1
            or member.file_size > MAX_ZIP_UNCOMPRESSED_BYTES
        ):
            archive.close()
            raise TemporalAcquisitionError(f"Unsafe OLRC ZIP member: {member.filename}")
        total += member.file_size
    if total > MAX_ZIP_UNCOMPRESSED_BYTES:
        archive.close()
        raise TemporalAcquisitionError("OLRC ZIP exceeds uncompressed size limit.")
    return archive, members


def extract_olrc(
    source: Mapping[str, Any], payload: bytes
) -> tuple[bytes, str, dict[str, Any]]:
    revision = source["immutable_revision"]
    if len(payload) != int(revision["expected_bytes"]):
        raise TemporalAcquisitionError(f"{source['source_id']} byte count changed.")
    if sha256_bytes(payload) != revision["expected_sha256"]:
        raise TemporalAcquisitionError(f"{source['source_id']} hash changed.")
    selectors = list(source["extraction"]["section_selectors"])
    wanted = {
        section for selector in selectors for section in expand_section_selector(selector)
    }
    found: dict[str, str] = {}
    archive, members = safe_zip_members(payload)
    try:
        xml_members = [
            member
            for member in members
            if not member.is_dir() and member.filename.casefold().endswith(".xml")
        ]
        if not xml_members:
            raise TemporalAcquisitionError("OLRC ZIP has no XML member.")
        for member in xml_members:
            with archive.open(member) as handle:
                for _, element in ET.iterparse(handle, events=("end",)):
                    if element.tag.rsplit("}", 1)[-1].casefold() != "section":
                        continue
                    identifier = next(
                        (
                            str(value)
                            for key, value in element.attrib.items()
                            if key.rsplit("}", 1)[-1].casefold() == "identifier"
                        ),
                        "",
                    )
                    match = re.search(r"/s([^/]+)$", identifier)
                    section = (
                        match.group(1).replace("_", "-").replace("–", "-")
                        if match
                        else ""
                    )
                    if section in wanted and section not in found:
                        section_payload = ET.tostring(element, encoding="utf-8")
                        found[section] = xml_visible_text(
                            section_payload,
                            excluded_tags=USLM_EDITORIAL_EXCLUDED_TAGS,
                        )
                    element.clear()
    finally:
        archive.close()
    missing = sorted(wanted - set(found))
    if missing:
        raise TemporalAcquisitionError(
            f"{source['source_id']} is missing U.S. Code sections: {missing}"
        )
    text = normalized_lines(
        f"===== SECTION: {section} =====\n{found[section]}"
        for section in sorted(found, key=lambda value: (len(value), value))
    )
    if len(text) < 150:
        raise TemporalAcquisitionError(f"{source['source_id']} has insufficient text.")
    title_match = re.search(r"title(\d+)", str(source["source_id"]))
    if title_match is None:
        raise TemporalAcquisitionError("Cannot determine OLRC title identity.")
    title = int(title_match.group(1))
    return payload, text, {
        "release_point": revision["value"],
        "release_date": revision["release_date"],
        "upstream_bytes": len(payload),
        "upstream_sha256": sha256_bytes(payload),
        "selected_sections": sorted(found, key=lambda value: (len(value), value)),
        "positive_law_title": title in POSITIVE_LAW_TITLES,
        "ultimate_legal_effect_outside_scope": True,
        "included_document_files": len(found),
        "retained_legal_files": 0,
    }


def acquire_olrc(source: Mapping[str, Any]) -> tuple[bytes, str, dict[str, Any]]:
    payload = download(str(source["source_url"]), accept="application/zip")
    return extract_olrc(source, payload)


def strip_balanced_templates(text: str) -> str:
    output: list[str] = []
    index = 0
    depth = 0
    while index < len(text):
        pair = text[index : index + 2]
        if pair == "{{":
            depth += 1
            index += 2
            continue
        if pair == "}}" and depth:
            depth -= 1
            index += 2
            continue
        if depth == 0:
            output.append(text[index])
        index += 1
    return "".join(output)


def normalize_wikitext(text: str) -> str:
    text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)
    text = re.sub(r"<ref\b[^>/]*>.*?</ref\s*>", "", text, flags=re.I | re.S)
    text = re.sub(r"<ref\b[^>]*/\s*>", "", text, flags=re.I)
    text = re.sub(
        r"(?ims)^[ \t]*==+\s*(?:references|external links|further reading|see also|notes|bibliography)\s*==+.*$",
        "",
        text,
    )
    text = re.sub(r"(?is)<gallery\b.*?</gallery\s*>", "", text)
    text = re.sub(r"(?is)\[\[(?:file|image):.*?\]\]", "", text)
    text = strip_balanced_templates(text)
    text = re.sub(r"\[\[[^|\]]+\|([^\]]+)\]\]", r"\1", text)
    text = re.sub(r"\[\[([^\]]+)\]\]", r"\1", text)
    text = re.sub(r"\[(?:https?|ftp)://[^\s\]]+\s+([^\]]+)\]", r"\1", text)
    text = re.sub(r"\[(?:https?|ftp)://[^\]]+\]", "", text)
    text = re.sub(r"(?m)^\{\|.*?^\|\}", "", text, flags=re.S)
    text = re.sub(r"</?[^>]+>", "", text)
    text = re.sub(r"'{2,5}", "", text)
    text = re.sub(r"(?m)^={2,}\s*(.*?)\s*={2,}$", r"\1", text)
    return normalized_lines([text])


def acquire_wikimedia(source: Mapping[str, Any]) -> tuple[bytes, str, dict[str, Any]]:
    match = WIKIMEDIA_IDENTIFIER_RE.fullmatch(str(source["canonical_identifier"]))
    if match is None:
        raise TemporalAcquisitionError(
            f"Invalid Wikimedia identity for {source['source_id']}."
        )
    project = match.group("project")
    page_id = int(match.group("page"))
    revision_id = int(match.group("revision"))
    if revision_id != source["immutable_revision"]["value"]:
        raise TemporalAcquisitionError(f"{source['source_id']} revision changed.")
    host = "en.wikipedia.org" if project == "wikipedia" else "en.wikisource.org"
    params = {
        "action": "query",
        "format": "json",
        "formatversion": "2",
        "prop": "revisions",
        "revids": str(revision_id),
        "rvprop": "ids|timestamp|size|sha1|content",
        "rvslots": "main",
    }
    url = f"https://{host}/w/api.php?{urllib.parse.urlencode(params)}"
    response = json.loads(download(url, accept="application/json"))
    pages = response.get("query", {}).get("pages", [])
    if not isinstance(pages, list) or len(pages) != 1:
        raise TemporalAcquisitionError(f"Unexpected MediaWiki response for {revision_id}.")
    page = pages[0]
    revisions = page.get("revisions", [])
    if (
        int(page.get("pageid") or 0) != page_id
        or not isinstance(revisions, list)
        or len(revisions) != 1
    ):
        raise TemporalAcquisitionError(f"MediaWiki page identity changed for {revision_id}.")
    revision = revisions[0]
    slot = revision.get("slots", {}).get("main", {})
    content = slot.get("content")
    if not isinstance(content, str):
        raise TemporalAcquisitionError(f"MediaWiki content is absent for {revision_id}.")
    expected = source["immutable_revision"]
    content_bytes = content.encode("utf-8")
    computed_sha1 = hashlib.sha1(content_bytes).hexdigest()
    identity_mismatch = (
        int(revision.get("revid") or 0) != revision_id
        or revision.get("timestamp") != expected["revision_timestamp"]
        or int(revision.get("size") or -1) != int(expected["reviewed_wikitext_bytes"])
        or len(content_bytes) != int(expected["reviewed_wikitext_bytes"])
        or revision.get("sha1") != computed_sha1
    )
    if identity_mismatch:
        raise TemporalAcquisitionError(
            "MediaWiki immutable metadata changed for "
            f"{revision_id}: revid={revision.get('revid')}, "
            f"timestamp={revision.get('timestamp')}, size={revision.get('size')}, "
            f"utf8_bytes={len(content_bytes)}, sha1={revision.get('sha1')}, "
            f"computed_sha1={computed_sha1}."
        )
    retained = {
        "page_id": page_id,
        "title": page.get("title"),
        "revision_id": revision_id,
        "parent_id": revision.get("parentid"),
        "timestamp": revision.get("timestamp"),
        "size": revision.get("size"),
        "sha1": revision.get("sha1"),
        "content_model": slot.get("contentmodel"),
        "content_format": slot.get("contentformat"),
        "content": content,
    }
    raw = canonical_json_bytes(retained)
    text = normalize_wikitext(content)
    if len(text) < 300:
        raise TemporalAcquisitionError(f"{source['source_id']} has insufficient text.")
    return raw, text, {
        "project": project,
        "page_id": page_id,
        "revision_id": revision_id,
        "revision_timestamp": revision["timestamp"],
        "upstream_wikitext_bytes": len(content_bytes),
        "upstream_content_sha1": revision["sha1"],
        "author_history_url": (
            f"https://{host}/w/index.php?title="
            f"{urllib.parse.quote(str(page.get('title') or '').replace(' ', '_'))}"
            "&action=history"
        ),
        "user_metadata_retained": False,
        "included_document_files": 1,
        "retained_legal_files": 0,
    }


def retained_wikimedia(
    source: Mapping[str, Any], raw: bytes
) -> tuple[bytes, str, dict[str, Any]]:
    retained = json.loads(raw)
    if not isinstance(retained, Mapping):
        raise TemporalAcquisitionError(
            f"{source['source_id']} retained Wikimedia payload is invalid."
        )
    revision = source["immutable_revision"]
    if (
        retained.get("revision_id") != revision["value"]
        or retained.get("page_id") != revision["page_id"]
        or retained.get("timestamp") != revision["revision_timestamp"]
        or retained.get("size") != revision["reviewed_wikitext_bytes"]
    ):
        raise TemporalAcquisitionError(
            f"{source['source_id']} retained Wikimedia identity changed."
        )
    content = retained.get("content")
    if not isinstance(content, str) or len(content.encode("utf-8")) != int(
        revision["reviewed_wikitext_bytes"]
    ):
        raise TemporalAcquisitionError(
            f"{source['source_id']} retained Wikimedia content changed."
        )
    project_match = WIKIMEDIA_IDENTIFIER_RE.fullmatch(
        str(source["canonical_identifier"])
    )
    if project_match is None:
        raise TemporalAcquisitionError(
            f"{source['source_id']} Wikimedia identity is invalid."
        )
    project = project_match.group("project")
    host = "en.wikipedia.org" if project == "wikipedia" else "en.wikisource.org"
    text = normalize_wikitext(content)
    return raw, text, {
        "project": project,
        "page_id": retained["page_id"],
        "revision_id": retained["revision_id"],
        "revision_timestamp": retained["timestamp"],
        "upstream_wikitext_bytes": retained["size"],
        "upstream_content_sha1": retained["sha1"],
        "author_history_url": (
            f"https://{host}/w/index.php?title="
            f"{urllib.parse.quote(str(retained.get('title') or '').replace(' ', '_'))}"
            "&action=history"
        ),
        "user_metadata_retained": False,
        "included_document_files": 1,
        "retained_legal_files": 0,
    }


def acquire_source(
    source: Mapping[str, Any],
) -> tuple[bytes, str, str, dict[str, Any]]:
    method = str(source["acquisition_method"])
    if method == "ecfr_versioner_api":
        raw, text, metadata = acquire_ecfr(source)
        content_type = "application/xml"
    elif method == "github_raw_allowlist":
        raw, text, metadata = acquire_github(source)
        content_type = "application/gzip"
    elif method == "olrc_release_point_zip":
        raw, text, metadata = acquire_olrc(source)
        content_type = "application/zip"
    elif method == "mediawiki_revision_api":
        raw, text, metadata = acquire_wikimedia(source)
        content_type = "application/json"
    else:
        raise TemporalAcquisitionError(f"Unsupported acquisition method: {method}")
    return raw, text, content_type, metadata


def retained_source(
    source: Mapping[str, Any], raw_path: Path, normalized_path: Path
) -> tuple[bytes, str, str, dict[str, Any]]:
    if not raw_path.is_file() and normalized_path.is_file():
        raise TemporalAcquisitionError(
            f"{source['source_id']} has an incomplete retained artifact pair."
        )
    if not raw_path.is_file():
        raise TemporalAcquisitionError(
            f"{source['source_id']} retained raw artifact is absent."
        )
    raw = raw_path.read_bytes()
    method = str(source["acquisition_method"])
    if method == "ecfr_versioner_api":
        _, text, metadata = extract_ecfr(source, raw)
        content_type = "application/xml"
    elif method == "github_raw_allowlist":
        text, member_hashes = reconstruct_github(raw)
        match = GITHUB_IDENTIFIER_RE.fullmatch(str(source["canonical_identifier"]))
        if match is None:
            raise TemporalAcquisitionError(
                f"Invalid retained GitHub identity for {source['source_id']}."
            )
        content_paths = [
            name.removeprefix("content/")
            for name in member_hashes
            if name.startswith("content/")
        ]
        legal_paths = [
            name.removeprefix("legal/")
            for name in member_hashes
            if name.startswith("legal/")
        ]
        expected_content = sorted(
            safe_allowlisted_path(str(value))
            for value in source["extraction"]["allowlisted_paths"]
        )
        if sorted(content_paths) != expected_content or not legal_paths:
            raise TemporalAcquisitionError(
                f"{source['source_id']} retained path allowlist changed."
            )
        metadata = {
            "repository": match.group("repository"),
            "commit": match.group("commit"),
            "release_ref": source["immutable_revision"]["release_ref"],
            "allowlisted_paths": content_paths,
            "retained_license_paths": legal_paths,
            "member_sha256": member_hashes,
            "included_document_files": len(content_paths),
            "retained_legal_files": len(legal_paths),
        }
        content_type = "application/gzip"
    elif method == "olrc_release_point_zip":
        _, text, metadata = extract_olrc(source, raw)
        content_type = "application/zip"
    elif method == "mediawiki_revision_api":
        _, text, metadata = retained_wikimedia(source, raw)
        content_type = "application/json"
    else:
        raise TemporalAcquisitionError(f"Unsupported retained method: {method}")
    if normalized_path.is_file() and normalized_path.read_bytes() != text.encode("utf-8"):
        raise TemporalAcquisitionError(
            f"{source['source_id']} retained normalization is irreproducible."
        )
    return raw, text, content_type, metadata


def raw_suffix(method: str) -> str:
    return {
        "ecfr_versioner_api": ".xml",
        "github_raw_allowlist": ".tar.gz",
        "olrc_release_point_zip": ".zip",
        "mediawiki_revision_api": ".json",
    }[method]


def published_at(source: Mapping[str, Any]) -> str:
    revision = source["immutable_revision"]
    kind = revision["kind"]
    if kind == "git_commit":
        return str(revision["commit_timestamp"])
    if kind == "mediawiki_revision":
        return str(revision["revision_timestamp"])
    if kind == "effective_date":
        return f"{revision['value']}T00:00:00Z"
    if kind == "release_point":
        return f"{revision['release_date']}T00:00:00Z"
    raise TemporalAcquisitionError(f"Unsupported publication identity: {kind}")


def schema_conditions(condition: str) -> list[str]:
    return {
        "archived": ["archived", "stale"],
        "current": ["current", "canonical"],
        "deprecated_api": ["archived", "superseded"],
        "replacement_api": ["current", "canonical"],
        "noncanonical": ["noncanonical"],
        "low_authority": ["low_authority"],
        "authoritative": ["current", "canonical"],
    }[condition]


def source_record(
    *,
    source: Mapping[str, Any],
    workspace: Path,
    raw_path: Path,
    normalized_path: Path,
    content_type: str,
    metadata: Mapping[str, Any],
    collected_at: str,
) -> dict[str, Any]:
    license_record = source["license"]
    access_record = source["access"]
    return {
        "source_id": source["source_id"],
        "source_document_id": source["source_id"],
        "document_lineage_id": source["source_family"],
        "source_family": source["source_family"],
        "domain_group": source["domain_group"],
        "domain_id": source["domain_id"],
        "publication_window": source["publication_window"],
        "source_url": source["source_url"],
        "canonical_identifier": source["canonical_identifier"],
        "snapshot_path": safe_relative(raw_path, workspace),
        "snapshot_sha256": sha256_file(raw_path),
        "normalized_text_path": safe_relative(normalized_path, workspace),
        "normalized_content_sha256": sha256_file(normalized_path),
        "near_duplicate_cluster_id": f"{source['source_family']}_cluster",
        "collected_at": collected_at,
        "published_at": published_at(source),
        "language": "en",
        "content_type": content_type,
        "source_conditions": schema_conditions(str(source["condition"])),
        "authority_basis": (
            f"Frozen condition={source['condition']}; publisher={source['publisher']}; "
            f"immutable identity={source['immutable_revision']['kind']}."
        ),
        "license": {
            "license_id": license_record["license_id"],
            "terms_url": license_record["terms_url"],
            "redistribution": license_record["redistribution"],
            "attribution_required": license_record["attribution_required"],
            "review_status": "approved",
            "reviewed_by": "project owner; Codex-assisted review",
            "reviewed_at": "2026-07-26T00:00:00Z",
            "notes": "; ".join(license_record["restrictions"]),
        },
        "access": {
            "access_class": access_record["access_class"],
            "authentication_required": access_record["authentication_required"],
            "collection_permitted": access_record["collection_permitted"],
            "restrictions": list(license_record["restrictions"]),
        },
        "privacy_classification": access_record["privacy_classification"],
        "metadata": {
            **metadata,
            "catalog_condition": source["condition"],
            "acquisition_method": source["acquisition_method"],
            "extraction_version": EXTRACTION_VERSION,
            "immutable_revision": source["immutable_revision"],
        },
    }


def validate_source_schema(manifest: Mapping[str, Any], schema_path: Path) -> None:
    schema = load_json(schema_path)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(manifest), key=lambda item: list(item.path))
    if errors:
        detail = "; ".join(
            f"{'/'.join(map(str, error.path)) or '<root>'}: {error.message}"
            for error in errors[:10]
        )
        raise TemporalAcquisitionError(f"Temporal source manifest is invalid: {detail}")


def text_line_diff(left: str, right: str) -> dict[str, Any]:
    left_lines = [line for line in left.splitlines() if line.strip()]
    right_lines = [line for line in right.splitlines() if line.strip()]
    matcher = difflib.SequenceMatcher(a=left_lines, b=right_lines, autojunk=False)
    changed_left = changed_right = 0
    for operation, left_start, left_end, right_start, right_end in matcher.get_opcodes():
        if operation != "equal":
            changed_left += left_end - left_start
            changed_right += right_end - right_start
    return {
        "left_nonempty_lines": len(left_lines),
        "right_nonempty_lines": len(right_lines),
        "changed_left_lines": changed_left,
        "changed_right_lines": changed_right,
        "sequence_ratio": round(matcher.ratio(), 8),
    }


def validate_pair_yield(
    pair: Mapping[str, Any],
    source_records: Mapping[str, Mapping[str, Any]],
    workspace: Path,
) -> dict[str, Any]:
    left_record = source_records[str(pair["left_source_id"])]
    right_record = source_records[str(pair["right_source_id"])]
    left = (workspace / left_record["normalized_text_path"]).read_text(encoding="utf-8")
    right = (workspace / right_record["normalized_text_path"]).read_text(encoding="utf-8")
    if sha256_bytes(left.encode()) == sha256_bytes(right.encode()):
        raise TemporalAcquisitionError(f"{pair['pair_id']} normalized texts are identical.")
    metrics = text_line_diff(left, right)
    if min(len(left), len(right)) < 150:
        raise TemporalAcquisitionError(f"{pair['pair_id']} has insufficient paired text.")
    pair_type = str(pair["pair_type"])
    anchors: dict[str, list[str]] = {}
    if pair_type == "old_api_to_replacement_api":
        left_anchors, right_anchors = PAIR_ANCHORS[str(pair["pair_id"])]
        left_folded, right_folded = left.casefold(), right.casefold()
        if any(anchor not in left_folded for anchor in left_anchors) or any(
            anchor not in right_folded for anchor in right_anchors
        ):
            raise TemporalAcquisitionError(
                f"{pair['pair_id']} lacks its frozen API relationship anchors."
            )
        anchors = {"left": list(left_anchors), "right": list(right_anchors)}
    elif pair_type == "archived_policy_to_current_policy":
        if (
            metrics["changed_left_lines"] < 5
            or metrics["changed_right_lines"] < 5
        ):
            raise TemporalAcquisitionError(
                f"{pair['pair_id']} lacks material point-in-time change yield."
            )
    else:
        right_sections = set(right_record["metadata"].get("selected_sections", []))
        if not right_sections:
            raise TemporalAcquisitionError(
                f"{pair['pair_id']} lacks authoritative section selection."
            )
        anchors = {"right_sections": sorted(right_sections)}
    return {
        "pair_id": pair["pair_id"],
        "pair_type": pair_type,
        "left_source_id": pair["left_source_id"],
        "right_source_id": pair["right_source_id"],
        "status": "eligible",
        "metrics": metrics,
        "anchors": anchors,
        "model_calls": 0,
        "verifier_calls": 0,
    }


def reconstruct_github(raw: bytes) -> tuple[str, dict[str, str]]:
    content: list[tuple[str, str]] = []
    hashes: dict[str, str] = {}
    try:
        archive = tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz")
    except tarfile.TarError as exc:
        raise TemporalAcquisitionError(f"Invalid repository archive: {exc}") from exc
    with archive:
        for member in archive.getmembers():
            pure = PurePosixPath(member.name)
            if (
                pure.is_absolute()
                or ".." in pure.parts
                or not member.isfile()
                or member.mtime != 0
                or member.uid != 0
                or member.gid != 0
                or member.mode != 0o444
            ):
                raise TemporalAcquisitionError(
                    f"Unsafe repository archive member: {member.name}"
                )
            handle = archive.extractfile(member)
            if handle is None:
                raise TemporalAcquisitionError(f"Unreadable member: {member.name}")
            payload = handle.read()
            hashes[member.name] = sha256_bytes(payload)
            if member.name.startswith("content/"):
                path = member.name.removeprefix("content/")
                content.append((path, payload.decode("utf-8")))
            elif not member.name.startswith("legal/"):
                raise TemporalAcquisitionError(
                    f"Unexpected repository archive root: {member.name}"
                )
    return normalized_lines(
        f"===== FILE: {path} =====\n{text}" for path, text in sorted(content)
    ), dict(sorted(hashes.items()))


def reconstruct_source(
    source: Mapping[str, Any],
    raw: bytes,
    metadata: Mapping[str, Any],
) -> str:
    method = str(source["acquisition_method"])
    if method == "ecfr_versioner_api":
        return xml_visible_text(raw)
    if method == "github_raw_allowlist":
        text, member_hashes = reconstruct_github(raw)
        if member_hashes != metadata["member_sha256"]:
            raise TemporalAcquisitionError(
                f"{source['source_id']} member hashes changed."
            )
        return text
    if method == "olrc_release_point_zip":
        _, text, rebuilt = extract_olrc(source, raw)
        if rebuilt["selected_sections"] != metadata["selected_sections"]:
            raise TemporalAcquisitionError(
                f"{source['source_id']} section selection changed."
            )
        return text
    if method == "mediawiki_revision_api":
        retained = json.loads(raw)
        if (
            retained["revision_id"] != source["immutable_revision"]["value"]
            or retained["page_id"] != source["immutable_revision"]["page_id"]
        ):
            raise TemporalAcquisitionError(
                f"{source['source_id']} retained revision identity changed."
            )
        return normalize_wikitext(str(retained["content"]))
    raise TemporalAcquisitionError(f"Unsupported reconstruction method: {method}")


def validate_offline(
    *,
    catalog: Mapping[str, Any],
    manifest: Mapping[str, Any],
    ledger: Mapping[str, Any],
    workspace: Path,
    schema_path: Path,
    calibration: Mapping[str, Any],
    natural: Mapping[str, Any],
) -> dict[str, Any]:
    validate_source_schema(manifest, schema_path)
    if (
        ledger.get("status") != "complete"
        or ledger.get("source_count") != 37
        or ledger.get("pair_count") != 20
        or any(ledger.get(field) != 0 for field in ("model_calls", "verifier_calls", "trace_count", "paid_endpoint_calls"))
    ):
        raise TemporalAcquisitionError("Temporal acquisition ledger is incomplete.")
    catalog_sources = {str(item["source_id"]): item for item in catalog["sources"]}
    manifest_sources = {str(item["source_id"]): item for item in manifest["sources"]}
    ledger_sources = {
        str(item["source_id"]): item for item in ledger.get("sources", [])
    }
    if set(catalog_sources) != set(manifest_sources) or set(catalog_sources) != set(
        ledger_sources
    ):
        raise TemporalAcquisitionError("Catalog, manifest, and ledger source sets differ.")
    raw_hashes: set[str] = set()
    normalized_hashes: set[str] = set()
    total_raw = total_normalized = 0
    method_counts: Counter[str] = Counter()
    retained_legal_files = 0
    selected_statutory_sections = 0
    wikimedia_user_metadata_records = 0
    for source_id in sorted(catalog_sources):
        source = catalog_sources[source_id]
        record = manifest_sources[source_id]
        ledger_item = ledger_sources[source_id]
        if (
            record["canonical_identifier"] != source["canonical_identifier"]
            or record["source_url"] != source["source_url"]
            or record["metadata"]["catalog_condition"] != source["condition"]
        ):
            raise TemporalAcquisitionError(f"{source_id} identity changed.")
        raw_path = workspace / record["snapshot_path"]
        normalized_path = workspace / record["normalized_text_path"]
        if not raw_path.is_file() or not normalized_path.is_file():
            raise TemporalAcquisitionError(f"{source_id} retained artifact is absent.")
        raw_hash = sha256_file(raw_path)
        normalized_hash = sha256_file(normalized_path)
        if (
            raw_hash != record["snapshot_sha256"]
            or raw_hash != ledger_item["snapshot_sha256"]
            or normalized_hash != record["normalized_content_sha256"]
            or normalized_hash != ledger_item["normalized_content_sha256"]
        ):
            raise TemporalAcquisitionError(f"{source_id} retained hash mismatch.")
        reconstructed = reconstruct_source(
            source, raw_path.read_bytes(), record["metadata"]
        )
        if reconstructed.encode("utf-8") != normalized_path.read_bytes():
            raise TemporalAcquisitionError(f"{source_id} normalization is irreproducible.")
        if raw_hash in raw_hashes or normalized_hash in normalized_hashes:
            raise TemporalAcquisitionError("Temporal source artifact hashes collide.")
        raw_hashes.add(raw_hash)
        normalized_hashes.add(normalized_hash)
        total_raw += raw_path.stat().st_size
        total_normalized += normalized_path.stat().st_size
        method_counts[str(source["acquisition_method"])] += 1
        retained_legal_files += int(
            record["metadata"].get("retained_legal_files", 0)
        )
        selected_statutory_sections += len(
            record["metadata"].get("selected_sections", [])
        )
        wikimedia_user_metadata_records += int(
            bool(record["metadata"].get("user_metadata_retained", False))
        )

    prior_normalized = {
        str(item.get("normalized_content_sha256") or "")
        for prior in (calibration, natural)
        for item in prior.get("sources", [])
    }
    collisions = sorted(normalized_hashes & prior_normalized)
    if collisions:
        raise TemporalAcquisitionError(
            f"Normalized content overlaps prior corpora: {collisions}"
        )
    pair_records = {
        str(item["pair_id"]): item for item in ledger.get("pairs", [])
    }
    if set(pair_records) != {str(item["pair_id"]) for item in catalog["pairs"]}:
        raise TemporalAcquisitionError("Pair-yield record set is incomplete.")
    if any(item.get("status") != "eligible" for item in pair_records.values()):
        raise TemporalAcquisitionError("An acquired temporal pair is ineligible.")
    for pair in catalog["pairs"]:
        rebuilt = validate_pair_yield(pair, manifest_sources, workspace)
        if rebuilt != pair_records[str(pair["pair_id"])]:
            raise TemporalAcquisitionError(
                f"{pair['pair_id']} pair-yield record is irreproducible."
            )
    return {
        "status": "valid",
        "source_count": 37,
        "pair_count": 20,
        "planned_case_count": 100,
        "method_counts": dict(sorted(method_counts.items())),
        "raw_bytes": total_raw,
        "normalized_text_bytes": total_normalized,
        "retained_repository_legal_files": retained_legal_files,
        "selected_statutory_sections": selected_statutory_sections,
        "wikimedia_user_metadata_records": wikimedia_user_metadata_records,
        "prior_normalized_hash_collisions": collisions,
        "model_calls": 0,
        "verifier_calls": 0,
        "trace_count": 0,
        "paid_endpoint_calls": 0,
    }


def validation_record(
    *,
    result: Mapping[str, Any],
    catalog_path: Path,
    authorization_path: Path,
    manifest_path: Path,
    ledger_path: Path,
) -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "record_kind": "contexttrace_unseen_v1_temporal_acquisition_validation",
        "validated_at": utc_now(),
        "status": result["status"],
        "inputs": {
            "catalog_sha256": sha256_file(catalog_path),
            "authorization_sha256": sha256_file(authorization_path),
            "source_manifest_sha256": sha256_file(manifest_path),
            "acquisition_ledger_sha256": sha256_file(ledger_path),
            "acquisition_and_validator_sha256": sha256_file(Path(__file__)),
        },
        "result": dict(result),
    }


def acquire(
    *,
    catalog_path: Path,
    authorization_path: Path,
    calibration_path: Path,
    natural_path: Path,
    schema_path: Path,
    workspace: Path,
    output_manifest: Path,
    output_ledger: Path,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    catalog = load_json(catalog_path)
    authorization = load_json(authorization_path)
    calibration = load_json(calibration_path)
    natural = load_json(natural_path)
    validate_authorization(
        catalog_path=catalog_path,
        catalog=catalog,
        authorization=authorization,
        calibration=calibration,
        natural=natural,
    )
    prepare_private_workspace(workspace)
    records: list[dict[str, Any]] = []
    ledger_sources: list[dict[str, Any]] = []
    collected_at = utc_now()
    failures: list[str] = []
    for source in sorted(catalog["sources"], key=lambda item: str(item["source_id"])):
        source_id = str(source["source_id"])
        raw_path = (
            workspace
            / "artifacts/raw"
            / f"{source_id}{raw_suffix(str(source['acquisition_method']))}"
        )
        normalized_path = workspace / "artifacts/normalized" / f"{source_id}.txt"
        try:
            if raw_path.is_file() or normalized_path.is_file():
                raw, text, content_type, metadata = retained_source(
                    source, raw_path, normalized_path
                )
            else:
                raw, text, content_type, metadata = acquire_source(source)
        except TemporalAcquisitionError as exc:
            failures.append(f"{source_id}: {exc}")
            continue
        persist_exact(raw_path, raw)
        persist_exact(normalized_path, text.encode("utf-8"))
        record = source_record(
            source=source,
            workspace=workspace,
            raw_path=raw_path,
            normalized_path=normalized_path,
            content_type=content_type,
            metadata=metadata,
            collected_at=collected_at,
        )
        records.append(record)
        ledger_sources.append(
            {
                "source_id": source_id,
                "status": "acquired_and_normalized",
                "acquisition_method": source["acquisition_method"],
                "collected_at": collected_at,
                "snapshot_path": record["snapshot_path"],
                "snapshot_sha256": record["snapshot_sha256"],
                "snapshot_bytes": raw_path.stat().st_size,
                "normalized_text_path": record["normalized_text_path"],
                "normalized_content_sha256": record["normalized_content_sha256"],
                "normalized_text_bytes": normalized_path.stat().st_size,
                "immutable_revision": source["immutable_revision"],
            }
        )
    if failures:
        raise TemporalAcquisitionError(
            "Exact source acquisition incomplete: " + " | ".join(failures)
        )
    manifest = {
        "schema_version": "1.0",
        "manifest_kind": "contexttrace_unseen_v1_sources",
        "created_at": utc_now(),
        "domain_ontology_version": "contexttrace-unseen-v1-domain-ontology-0.1",
        "disjoint_dimensions": DISJOINT_DIMENSIONS,
        "sources": records,
    }
    validate_source_schema(manifest, schema_path)
    source_index = {str(item["source_id"]): item for item in records}
    pair_records = [
        validate_pair_yield(pair, source_index, workspace)
        for pair in sorted(catalog["pairs"], key=lambda item: str(item["pair_id"]))
    ]
    ledger = {
        "schema_version": "1.0",
        "record_kind": "contexttrace_unseen_v1_temporal_acquisition",
        "recorded_at": utc_now(),
        "status": "complete",
        "authorization_id": AUTHORIZATION_ID,
        "catalog_sha256": EXPECTED_CATALOG_SHA256,
        "authorization_sha256": sha256_file(authorization_path),
        "extraction_version": EXTRACTION_VERSION,
        "source_count": len(records),
        "pair_count": len(pair_records),
        "planned_case_count": len(catalog["case_plan"]),
        "source_manifest_sha256": sha256_bytes(
            (json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True) + "\n").encode()
        ),
        "workspace_artifact_root": "private working directory; not published",
        "model_calls": 0,
        "verifier_calls": 0,
        "trace_count": 0,
        "paid_endpoint_calls": 0,
        "sources": ledger_sources,
        "pairs": pair_records,
    }
    result = validate_offline(
        catalog=catalog,
        manifest=manifest,
        ledger=ledger,
        workspace=workspace,
        schema_path=schema_path,
        calibration=calibration,
        natural=natural,
    )
    write_json(output_manifest, manifest)
    write_json(output_ledger, ledger)
    return manifest, ledger, result


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "command", choices=("acquire", "validate"), nargs="?", default="acquire"
    )
    parser.add_argument(
        "--catalog",
        type=Path,
        default=Path(
            "benchmarks/contexttrace_unseen_v1/temporal_pre_acquisition_catalog.json"
        ),
    )
    parser.add_argument(
        "--authorization",
        type=Path,
        default=Path(
            "benchmarks/contexttrace_unseen_v1/temporal_acquisition_authorization.json"
        ),
    )
    parser.add_argument(
        "--calibration-registry",
        type=Path,
        default=Path("benchmarks/contexttrace_unseen_v1/calibration/registry.json"),
    )
    parser.add_argument(
        "--natural-source-manifest",
        type=Path,
        default=Path("benchmarks/contexttrace_unseen_v1/candidate_source_manifest.json"),
    )
    parser.add_argument(
        "--source-schema",
        type=Path,
        default=Path("benchmarks/contexttrace_unseen_v1/source_manifest.schema.json"),
    )
    parser.add_argument(
        "--workspace",
        type=Path,
        default=Path(".tmp-contexttrace-unseen-v1-temporal-acquisition"),
    )
    parser.add_argument(
        "--output-manifest",
        type=Path,
        default=Path(
            "benchmarks/contexttrace_unseen_v1/temporal_source_manifest.json"
        ),
    )
    parser.add_argument(
        "--output-ledger",
        type=Path,
        default=Path(
            "benchmarks/contexttrace_unseen_v1/temporal_acquisition_ledger.json"
        ),
    )
    parser.add_argument(
        "--output-validation",
        type=Path,
        default=Path(
            "benchmarks/contexttrace_unseen_v1/"
            "temporal_acquisition_validation.json"
        ),
    )
    args = parser.parse_args(argv)
    try:
        catalog = load_json(args.catalog)
        authorization = load_json(args.authorization)
        calibration = load_json(args.calibration_registry)
        natural = load_json(args.natural_source_manifest)
        validate_authorization(
            catalog_path=args.catalog,
            catalog=catalog,
            authorization=authorization,
            calibration=calibration,
            natural=natural,
        )
        if args.command == "acquire":
            _, _, result = acquire(
                catalog_path=args.catalog,
                authorization_path=args.authorization,
                calibration_path=args.calibration_registry,
                natural_path=args.natural_source_manifest,
                schema_path=args.source_schema,
                workspace=args.workspace,
                output_manifest=args.output_manifest,
                output_ledger=args.output_ledger,
            )
        else:
            result = validate_offline(
                catalog=catalog,
                manifest=load_json(args.output_manifest),
                ledger=load_json(args.output_ledger),
                workspace=args.workspace,
                schema_path=args.source_schema,
                calibration=calibration,
                natural=natural,
            )
        write_json(
            args.output_validation,
            validation_record(
                result=result,
                catalog_path=args.catalog,
                authorization_path=args.authorization,
                manifest_path=args.output_manifest,
                ledger_path=args.output_ledger,
            ),
        )
    except (OSError, ValueError, TemporalAcquisitionError) as exc:
        print(f"temporal acquisition failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
