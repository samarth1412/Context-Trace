from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = REPO_ROOT / "out" / "anonymous-contexttrace-artifact.zip"
DEFAULT_RAGTRUTH_PACK = (
    REPO_ROOT
    / "benchmarks"
    / "contexttrace_bench"
    / "out"
    / "ragtruth_release_bundle"
    / "ragtruth_reviewed_case_pack.json"
)
DEFAULT_RAGTRUTH_CANDIDATE = (
    REPO_ROOT
    / "benchmarks"
    / "contexttrace_bench"
    / "out"
    / "ragtruth_release_bundle"
    / "candidates"
    / "ragas_predictions.json"
)
ARCHIVE_TIMESTAMP = (2026, 1, 1, 0, 0, 0)
ROOT_FILES = {
    "LICENSE",
    "pytest.ini",
    "REPRODUCIBILITY.md",
    "benchmarks/__init__.py",
}
ALLOWED_PREFIXES = (
    "packages/contexttrace/",
    "benchmarks/contexttrace_bench/",
    "benchmarks/tests/",
)
EXCLUDED_PATHS = {
    "benchmarks/contexttrace_bench/SOTA_STATUS.json",
    "benchmarks/contexttrace_bench/SOTA_STATUS.md",
    "benchmarks/tests/test_benchmark_metrics.py",
}
EXCLUDED_PREFIXES = ("benchmarks/contexttrace_bench/out/",)
EXTRA_WORKTREE_FILES = {
    "ANONYMOUS_ARTIFACT.md",
    "scripts/build_anonymous_artifact.py",
    "benchmarks/contexttrace_bench/artifact_runtime.py",
    "benchmarks/tests/test_anonymous_artifact.py",
}
ARTIFACT_README_SOURCE = "ANONYMOUS_ARTIFACT.md"
ARTIFACT_README_PATH = "README.md"
RAGTRUTH_PACK_PATH = "benchmarks/contexttrace_bench/out/ragtruth_release_bundle/ragtruth_reviewed_case_pack.json"
RAGTRUTH_CANDIDATE_PATH = "benchmarks/contexttrace_bench/out/ragtruth_release_bundle/candidates/ragas_predictions.json"
RAGTRUTH_LICENSE_PATH = "THIRD_PARTY_LICENSES/RAGTruth-LICENSE.txt"
RAGTRUTH_README_PATH = "THIRD_PARTY_LICENSES/README.md"
MANIFEST_PATH = "ARTIFACT_MANIFEST.json"
ZIP_ROOT = "contexttrace-arr-artifact"

RAGTRUTH_LICENSE = """MIT License

Copyright (c) 2023 Particle Media

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

RAGTRUTH_README = """# Third-Party Data

This artifact includes a 200-case evaluation pack derived from RAGTruth and a
matching RAGAS prediction file. RAGTruth is distributed by Particle Media under
the MIT license included in this directory. Upstream source:
https://github.com/ParticleMedia/RAGTruth

The ContextTrace review metadata in the derived pack is assisted calibration
metadata, not independent human validation. Consult the artifact's frozen study
protocol before making empirical claims.
"""

PROJECT_OWNER = "samarth" + "1412"
LOCAL_USERNAME = "ma" + "nnv"
PROJECT_REPOSITORY_URL = "https://github.com/" + PROJECT_OWNER + "/Context-Trace"
PACKAGE_INDEX_URL = "https://" + "pypi" + ".org/project/contexttrace"

TEXT_REPLACEMENTS = (
    (re.compile(re.escape(PROJECT_REPOSITORY_URL), re.IGNORECASE), "https://example.invalid/anonymous-artifact"),
    (re.compile(re.escape(PACKAGE_INDEX_URL) + r"/?", re.IGNORECASE), "https://example.invalid/anonymous-package"),
    (re.compile(re.escape(PROJECT_OWNER), re.IGNORECASE), "anonymous"),
    (re.compile(re.escape(LOCAL_USERNAME), re.IGNORECASE), "anonymous"),
)
IDENTITY_PATTERNS = (
    ("repository_owner", re.compile(re.escape(PROJECT_OWNER), re.IGNORECASE)),
    ("local_username", re.compile(re.escape(LOCAL_USERNAME), re.IGNORECASE)),
    ("public_repository", re.compile(re.escape(PROJECT_REPOSITORY_URL.split("://", 1)[1]), re.IGNORECASE)),
    ("package_index", re.compile(re.escape(PACKAGE_INDEX_URL.split("://", 1)[1]), re.IGNORECASE)),
    ("email_address", re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)),
    ("windows_user_path", re.compile(r"[A-Z]:\\Users\\[^\\]+\\", re.IGNORECASE)),
    ("posix_user_path", re.compile(r"/(?:Users|home)/[^/]+/", re.IGNORECASE)),
)
SECRET_PATTERNS = (
    ("openai_key", re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b")),
    ("github_token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b")),
    ("private_key", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
)
FORBIDDEN_ARCHIVE_PARTS = {
    ".git",
    ".env",
    "__pycache__",
    ".pytest_cache",
    "condition_key.private.json",
    "annotation_key.private.json",
}
REQUIRED_FILES = {
    "README.md",
    "LICENSE",
    "REPRODUCIBILITY.md",
    "packages/contexttrace/pyproject.toml",
    "benchmarks/contexttrace_bench/ARR_EXPERIMENTS.json",
    "benchmarks/contexttrace_bench/reproduce_arr_tables.py",
    "scripts/build_anonymous_artifact.py",
    MANIFEST_PATH,
}


def build_anonymous_artifact(
    *,
    output_path: str | Path = DEFAULT_OUTPUT,
    ragtruth_case_pack_path: str | Path | None = DEFAULT_RAGTRUTH_PACK,
    ragtruth_candidate_path: str | Path | None = DEFAULT_RAGTRUTH_CANDIDATE,
    include_external_data: bool = True,
) -> dict[str, Any]:
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, bytes] = {}
    redaction_count = 0

    for relative_path in _source_paths():
        source = REPO_ROOT / relative_path
        archive_path = (
            ARTIFACT_README_PATH
            if relative_path in {ARTIFACT_README_SOURCE, ARTIFACT_README_PATH}
            else relative_path
        )
        text = source.read_text(encoding="utf-8")
        sanitized, replacements = sanitize_text(text)
        redaction_count += replacements
        payload[archive_path] = sanitized.encode("utf-8")

    external_data = False
    if include_external_data:
        case_pack = Path(ragtruth_case_pack_path) if ragtruth_case_pack_path else None
        candidate = Path(ragtruth_candidate_path) if ragtruth_candidate_path else None
        if case_pack is None or not case_pack.is_file():
            raise FileNotFoundError("RAGTruth case pack is required for the complete anonymous artifact.")
        if candidate is None or not candidate.is_file():
            raise FileNotFoundError("RAGTruth candidate predictions are required for the complete anonymous artifact.")
        for source, archive_path in (
            (case_pack, RAGTRUTH_PACK_PATH),
            (candidate, RAGTRUTH_CANDIDATE_PATH),
        ):
            sanitized, replacements = sanitize_text(source.read_text(encoding="utf-8-sig"))
            redaction_count += replacements
            payload[archive_path] = sanitized.encode("utf-8")
        payload[RAGTRUTH_LICENSE_PATH] = RAGTRUTH_LICENSE.encode("utf-8")
        payload[RAGTRUTH_README_PATH] = RAGTRUTH_README.encode("utf-8")
        external_data = True

    manifest = {
        "schema_version": 1,
        "artifact": "anonymous ContextTrace ARR artifact",
        "archive_root": ZIP_ROOT,
        "deterministic_timestamp": "2026-01-01T00:00:00Z",
        "external_ragtruth_data_included": external_data,
        "paper_reproduction_ready": external_data,
        "redactions_applied": redaction_count,
        "files": [
            {
                "path": path,
                "bytes": len(content),
                "sha256": _sha256_bytes(content),
            }
            for path, content in sorted(payload.items())
        ],
    }
    payload[MANIFEST_PATH] = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode("utf-8")
    _write_deterministic_zip(destination, payload)

    validation = validate_anonymous_artifact(destination)
    if validation["status"] != "passed":
        destination.unlink(missing_ok=True)
        raise ValueError("Anonymous artifact validation failed: %s" % validation["errors"])
    archive_sha = _sha256_file(destination)
    checksum_path = destination.with_suffix(destination.suffix + ".sha256")
    validation_path = destination.with_suffix(destination.suffix + ".validation.json")
    checksum_path.write_text("%s  %s\n" % (archive_sha, destination.name), encoding="ascii")
    validation_path.write_text(json.dumps(validation, indent=2, sort_keys=True), encoding="utf-8")
    return {
        "archive": str(destination),
        "sha256": archive_sha,
        "checksum": str(checksum_path),
        "validation": str(validation_path),
        "file_count": validation["file_count"],
        "bytes": destination.stat().st_size,
        "external_ragtruth_data_included": external_data,
    }


def validate_anonymous_artifact(path: str | Path) -> dict[str, Any]:
    archive_path = Path(path)
    errors: list[dict[str, Any]] = []
    names: list[str] = []
    payload: dict[str, bytes] = {}
    try:
        with zipfile.ZipFile(archive_path, "r") as archive:
            infos = archive.infolist()
            names = [info.filename for info in infos]
            if names != sorted(names):
                errors.append({"name": "archive_order", "message": "ZIP entries are not sorted."})
            if len(names) != len(set(names)):
                errors.append({"name": "duplicate_paths", "message": "ZIP contains duplicate paths."})
            for info in infos:
                relative = _relative_archive_path(info.filename)
                if relative is None:
                    errors.append({"name": "archive_path", "path": info.filename})
                    continue
                if info.date_time != ARCHIVE_TIMESTAMP:
                    errors.append({"name": "timestamp", "path": relative})
                if _forbidden_path(relative):
                    errors.append({"name": "forbidden_path", "path": relative})
                payload[relative] = archive.read(info)
    except (OSError, zipfile.BadZipFile) as exc:
        return {"status": "failed", "file_count": 0, "errors": [{"name": "archive", "message": str(exc)}]}

    missing = sorted(REQUIRED_FILES - set(payload))
    if missing:
        errors.append({"name": "required_files", "missing": missing})
    for relative, content in payload.items():
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError:
            errors.append({"name": "encoding", "path": relative})
            continue
        for marker, pattern in (*IDENTITY_PATTERNS, *SECRET_PATTERNS):
            if pattern.search(text):
                errors.append({"name": marker, "path": relative})

    _validate_manifest(payload, errors)
    return {
        "status": "passed" if not errors else "failed",
        "file_count": len(payload),
        "archive_sha256": _sha256_file(archive_path) if archive_path.is_file() else None,
        "errors": errors,
    }


def sanitize_text(text: str) -> tuple[str, int]:
    sanitized = text
    total = 0
    for pattern, replacement in TEXT_REPLACEMENTS:
        sanitized, count = pattern.subn(replacement, sanitized)
        total += count
    sanitized, windows_count = re.subn(
        r"[A-Z]:\\Users\\[^\\]+\\[^\r\n\"']+",
        "<ANONYMIZED_LOCAL_PATH>",
        sanitized,
        flags=re.IGNORECASE,
    )
    sanitized, posix_count = re.subn(
        r"/(?:Users|home)/[^/]+/[^\s\"']+",
        "<ANONYMIZED_LOCAL_PATH>",
        sanitized,
        flags=re.IGNORECASE,
    )
    return sanitized, total + windows_count + posix_count


def _source_paths() -> list[str]:
    tracked = _git_tracked_paths()
    if tracked is None:
        tracked = _manifest_source_paths()
    candidates = tracked.union(path for path in EXTRA_WORKTREE_FILES if (REPO_ROOT / path).is_file())
    selected = []
    for path in candidates:
        normalized = PurePosixPath(path).as_posix()
        if normalized in EXCLUDED_PATHS or normalized.startswith(EXCLUDED_PREFIXES):
            continue
        if (
            normalized in ROOT_FILES
            or normalized == ARTIFACT_README_PATH
            or normalized in EXTRA_WORKTREE_FILES
            or normalized.startswith(ALLOWED_PREFIXES)
        ):
            source = (REPO_ROOT / normalized).resolve()
            try:
                source.relative_to(REPO_ROOT)
            except ValueError as exc:
                raise ValueError("Artifact source escapes repository root: %s" % normalized) from exc
            if source.is_file():
                selected.append(normalized)
    if ARTIFACT_README_SOURCE not in selected and ARTIFACT_README_PATH not in selected:
        raise FileNotFoundError("Anonymous artifact README is missing.")
    return sorted(selected)


def _git_tracked_paths() -> set[str] | None:
    try:
        root = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        if Path(root).resolve() != REPO_ROOT.resolve():
            return None
        completed = subprocess.run(
            ["git", "ls-files", "-z"],
            cwd=REPO_ROOT,
            capture_output=True,
            check=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return None
    return {
        item.decode("utf-8")
        for item in completed.stdout.split(b"\0")
        if item
    }


def _manifest_source_paths() -> set[str]:
    manifest_path = REPO_ROOT / MANIFEST_PATH
    if not manifest_path.is_file():
        raise RuntimeError("Artifact building requires either its exact git checkout or ARTIFACT_MANIFEST.json.")
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    return {
        str(row.get("path") or "")
        for row in payload.get("files") or []
        if isinstance(row, dict) and row.get("path")
    }


def _write_deterministic_zip(path: Path, payload: dict[str, bytes]) -> None:
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for relative, content in sorted(payload.items()):
            info = zipfile.ZipInfo("%s/%s" % (ZIP_ROOT, relative), date_time=ARCHIVE_TIMESTAMP)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            archive.writestr(info, content, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)


def _relative_archive_path(name: str) -> str | None:
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts or not path.parts or path.parts[0] != ZIP_ROOT:
        return None
    if len(path.parts) < 2:
        return None
    return PurePosixPath(*path.parts[1:]).as_posix()


def _forbidden_path(path: str) -> bool:
    lowered_parts = {part.lower() for part in PurePosixPath(path).parts}
    return any(part.lower() in lowered_parts for part in FORBIDDEN_ARCHIVE_PARTS)


def _validate_manifest(payload: dict[str, bytes], errors: list[dict[str, Any]]) -> None:
    raw = payload.get(MANIFEST_PATH)
    if raw is None:
        return
    try:
        manifest = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        errors.append({"name": "manifest_json", "message": str(exc)})
        return
    declared = {str(row.get("path")): row for row in manifest.get("files") or [] if isinstance(row, dict)}
    actual = {path: content for path, content in payload.items() if path != MANIFEST_PATH}
    if set(declared) != set(actual):
        errors.append({"name": "manifest_paths", "message": "Manifest paths do not match payload."})
        return
    for path, content in actual.items():
        row = declared[path]
        if int(row.get("bytes") or -1) != len(content) or str(row.get("sha256") or "") != _sha256_bytes(content):
            errors.append({"name": "manifest_integrity", "path": path})


def _sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build or validate the anonymous ContextTrace ARR artifact.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--ragtruth-case-pack", default=str(DEFAULT_RAGTRUTH_PACK))
    parser.add_argument("--ragtruth-candidate", default=str(DEFAULT_RAGTRUTH_CANDIDATE))
    parser.add_argument("--no-external-data", action="store_true")
    parser.add_argument("--validate-only", default=None)
    args = parser.parse_args(argv)
    if args.validate_only:
        validation = validate_anonymous_artifact(args.validate_only)
        print(json.dumps(validation, indent=2, sort_keys=True))
        return 0 if validation["status"] == "passed" else 1
    result = build_anonymous_artifact(
        output_path=args.output,
        ragtruth_case_pack_path=args.ragtruth_case_pack,
        ragtruth_candidate_path=args.ragtruth_candidate,
        include_external_data=not args.no_external_data,
    )
    print("Archive: %s" % result["archive"])
    print("SHA256: %s" % result["sha256"])
    print("Files: %s" % result["file_count"])
    print("External RAGTruth data: %s" % result["external_ragtruth_data_included"])
    print("Validation: %s" % result["validation"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
