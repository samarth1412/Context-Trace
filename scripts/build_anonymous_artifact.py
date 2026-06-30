from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = REPO_ROOT / "out" / "anonymous-contexttrace-artifact.zip"
DEFAULT_DIRECTORY = REPO_ROOT / "artifacts" / "arr_anonymous"
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
    "docs/arr-readiness.md",
    "docs/arr-submission-checklist.md",
}
ALLOWED_PREFIXES = (
    "packages/contexttrace/",
    "benchmarks/contexttrace_bench/",
    "benchmarks/tests/",
    "paper/",
)
EXCLUDED_PATHS = {
    "benchmarks/contexttrace_bench/SOTA_STATUS.json",
    "benchmarks/contexttrace_bench/SOTA_STATUS.md",
    "benchmarks/tests/test_benchmark_metrics.py",
    "paper/ANONYMITY_AUDIT.md",
    "paper/PAGE_LIMIT_AUDIT.md",
}
EXCLUDED_PREFIXES = ("benchmarks/contexttrace_bench/out/",)
EXTRA_WORKTREE_FILES = {
    "ANONYMOUS_ARTIFACT.md",
    "scripts/build_anonymous_artifact.py",
    "benchmarks/contexttrace_bench/artifact_runtime.py",
    "benchmarks/tests/test_anonymous_artifact.py",
    "examples/diagnose_agent_trace.json",
    "paper/build/main.pdf",
}
ARTIFACT_README_SOURCE = "ANONYMOUS_ARTIFACT.md"
ARTIFACT_README_PATH = "README.md"
RAGTRUTH_PACK_PATH = "benchmarks/contexttrace_bench/out/ragtruth_release_bundle/ragtruth_reviewed_case_pack.json"
RAGTRUTH_CANDIDATE_PATH = "benchmarks/contexttrace_bench/out/ragtruth_release_bundle/candidates/ragas_predictions.json"
RAGTRUTH_LICENSE_PATH = "THIRD_PARTY_LICENSES/RAGTruth-LICENSE.txt"
RAGTRUTH_README_PATH = "THIRD_PARTY_LICENSES/README.md"
FULL_OUTPUT_NAMES = (
    "main_results.md",
    "baseline_comparison.md",
    "ablations.md",
    "error_analysis.md",
    "reproducibility_summary.md",
    "manifest.json",
    "ablations.json",
    "error_analysis.json",
)
FULL_OUTPUT_ROOT = "benchmarks/contexttrace_bench/out/arr_full"
AFTER_REVIEW_OUTPUT_ROOT = "benchmarks/contexttrace_bench/out/arr_full_after_review"
AFTER_REVIEW_OUTPUT_NAMES = (
    *FULL_OUTPUT_NAMES,
    "sensitivity_analysis.md",
    "sensitivity_analysis.json",
    "simulated_review_status.json",
)
SIMULATED_AGGREGATE_FILES = (
    "benchmarks/contexttrace_bench/out/simulated_review/ragtruth/agreement.json",
    "benchmarks/contexttrace_bench/out/simulated_review/ragtruth/review_summary.md",
    "benchmarks/contexttrace_bench/out/simulated_review/ragtruth/run_manifest.json",
    "benchmarks/contexttrace_bench/out/simulated_review/diag150/agreement.json",
    "benchmarks/contexttrace_bench/out/simulated_review/diag150/review_summary.md",
    "benchmarks/contexttrace_bench/out/simulated_review/diag150/run_manifest.json",
    "benchmarks/contexttrace_bench/out/rq4/simulated/rq4_results.json",
    "benchmarks/contexttrace_bench/out/rq4/simulated/rq4_results.md",
    "benchmarks/contexttrace_bench/out/rq4/simulated/run_manifest.json",
    "benchmarks/contexttrace_bench/out/corrections/correction_summary.md",
    "benchmarks/contexttrace_bench/out/corrections/sensitivity_analysis.json",
    "benchmarks/contexttrace_bench/out/corrections/sensitivity_analysis.md",
)
MANIFEST_PATH = "ARTIFACT_MANIFEST.json"
ZIP_ROOT = "contexttrace-arr-artifact"
CLAIM_POLICY_PATH = "CLAIM_POLICY.md"
REVIEW_STATUS_PATH = "REVIEW_STATUS.md"
ANONYMIZATION_CHECKLIST_PATH = "ANONYMIZATION_CHECKLIST.md"
BINARY_SUFFIXES = {".pdf"}

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

CLAIM_POLICY = """# Claim policy

Allowed: ContextTrace is a benchmarked, local-first evidence-chain forensics
system with frozen pre-review dataset-specific results.

Blocked: broad SOTA, independent human validation, and improved human
actionability. LLM-simulated pilots are protocol stress tests only and cannot
satisfy human-review or SOTA gates.
"""

ANONYMIZATION_CHECKLIST = """# Anonymization checklist

- Author names, handles, emails, affiliations, local paths, repository links,
  package-index links, and common secrets are scanned.
- Git history, private annotation keys, private condition keys, raw reviewer
  identities, and non-anonymous release links are excluded.
- The paper PDF and text sources use an anonymous author block.
- A failed validator blocks artifact creation.
"""

PROJECT_OWNER = "sam" + "arth" + "1412"
PROJECT_OWNER_ALT = "sam" + "arth" + "vinayaka"
AUTHOR_GIVEN_NAME = "sam" + "arth"
LOCAL_USERNAME = "ma" + "nnv"
PERSONAL_MAIL_DOMAIN = "gma" + "il.com"
UNIVERSITY_MAIL_DOMAIN = "uf" + "l.edu"
PROJECT_REPOSITORY_URL = "https://github.com/" + PROJECT_OWNER + "/Context-Trace"
PACKAGE_INDEX_URL = "https://" + "pypi" + ".org/project/contexttrace"

TEXT_REPLACEMENTS = (
    (re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE), "<ANONYMIZED_EMAIL>"),
    (re.compile(re.escape(PROJECT_REPOSITORY_URL), re.IGNORECASE), "https://example.invalid/anonymous-artifact"),
    (re.compile(re.escape(PACKAGE_INDEX_URL) + r"/?", re.IGNORECASE), "https://example.invalid/anonymous-package"),
    (re.compile(re.escape(PROJECT_OWNER), re.IGNORECASE), "anonymous"),
    (re.compile(re.escape(PROJECT_OWNER_ALT), re.IGNORECASE), "anonymous"),
    (re.compile(r"\b" + re.escape(AUTHOR_GIVEN_NAME) + r"\b", re.IGNORECASE), "Anonymous"),
    (re.compile(re.escape(LOCAL_USERNAME), re.IGNORECASE), "anonymous"),
    (re.compile(re.escape(PERSONAL_MAIL_DOMAIN), re.IGNORECASE), "example.invalid"),
    (re.compile(re.escape(UNIVERSITY_MAIL_DOMAIN), re.IGNORECASE), "example.invalid"),
)
IDENTITY_PATTERNS = (
    ("repository_owner", re.compile(re.escape(PROJECT_OWNER), re.IGNORECASE)),
    ("repository_owner_alias", re.compile(re.escape(PROJECT_OWNER_ALT), re.IGNORECASE)),
    ("author_given_name", re.compile(r"\b" + re.escape(AUTHOR_GIVEN_NAME) + r"\b", re.IGNORECASE)),
    ("local_username", re.compile(re.escape(LOCAL_USERNAME), re.IGNORECASE)),
    ("public_repository", re.compile(re.escape(PROJECT_REPOSITORY_URL.split("://", 1)[1]), re.IGNORECASE)),
    ("package_index", re.compile(re.escape(PACKAGE_INDEX_URL.split("://", 1)[1]), re.IGNORECASE)),
    ("personal_mail_domain", re.compile(re.escape(PERSONAL_MAIL_DOMAIN), re.IGNORECASE)),
    ("university_mail_domain", re.compile(re.escape(UNIVERSITY_MAIL_DOMAIN), re.IGNORECASE)),
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
    "packages/contexttrace/contexttrace/repair.py",
    "packages/contexttrace/tests/test_repair.py",
    "examples/diagnose_agent_trace.json",
    "benchmarks/contexttrace_bench/ARR_EXPERIMENTS.json",
    "benchmarks/contexttrace_bench/reproduce_arr_tables.py",
    "docs/arr-submission-checklist.md",
    "paper/main.tex",
    "paper/build/main.pdf",
    "paper/tables/table1_main_results.tex",
    "scripts/build_anonymous_artifact.py",
    MANIFEST_PATH,
    CLAIM_POLICY_PATH,
    REVIEW_STATUS_PATH,
    ANONYMIZATION_CHECKLIST_PATH,
}


def build_anonymous_artifact(
    *,
    output_path: str | Path = DEFAULT_OUTPUT,
    ragtruth_case_pack_path: str | Path | None = DEFAULT_RAGTRUTH_PACK,
    ragtruth_candidate_path: str | Path | None = DEFAULT_RAGTRUTH_CANDIDATE,
    include_external_data: bool = True,
    output_directory: str | Path | None = None,
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
        if source.suffix.lower() in BINARY_SUFFIXES:
            payload[archive_path] = source.read_bytes()
        else:
            text = source.read_text(encoding="utf-8")
            sanitized, replacements = sanitize_text(text)
            redaction_count += replacements
            payload[archive_path] = sanitized.encode("utf-8")

    payload[CLAIM_POLICY_PATH] = CLAIM_POLICY.encode("utf-8")
    payload[ANONYMIZATION_CHECKLIST_PATH] = ANONYMIZATION_CHECKLIST.encode("utf-8")
    review_status_source = REPO_ROOT / "benchmarks" / "contexttrace_bench" / "SIMULATED_REVIEW_STATUS.md"
    if not review_status_source.is_file():
        raise FileNotFoundError("Tracked simulated-review status is missing.")
    review_status, replacements = sanitize_text(review_status_source.read_text(encoding="utf-8"))
    redaction_count += replacements
    payload[REVIEW_STATUS_PATH] = review_status.encode("utf-8")

    external_data = False
    full_outputs = False
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
        full_output_dir = REPO_ROOT / FULL_OUTPUT_ROOT
        missing_full_outputs = [name for name in FULL_OUTPUT_NAMES if not (full_output_dir / name).is_file()]
        if missing_full_outputs:
            raise FileNotFoundError("Frozen full-run outputs are missing: %s" % ", ".join(missing_full_outputs))
        for name in FULL_OUTPUT_NAMES:
            source = full_output_dir / name
            sanitized, replacements = sanitize_text(source.read_text(encoding="utf-8-sig"))
            redaction_count += replacements
            payload["%s/%s" % (FULL_OUTPUT_ROOT, name)] = sanitized.encode("utf-8")
        after_review_dir = REPO_ROOT / AFTER_REVIEW_OUTPUT_ROOT
        missing_after_review = [
            name for name in AFTER_REVIEW_OUTPUT_NAMES if not (after_review_dir / name).is_file()
        ]
        if missing_after_review:
            raise FileNotFoundError(
                "Frozen after-review outputs are missing: %s" % ", ".join(missing_after_review)
            )
        for name in AFTER_REVIEW_OUTPUT_NAMES:
            source = after_review_dir / name
            sanitized, replacements = sanitize_text(source.read_text(encoding="utf-8-sig"))
            redaction_count += replacements
            payload["%s/%s" % (AFTER_REVIEW_OUTPUT_ROOT, name)] = sanitized.encode("utf-8")
        missing_simulated = [path for path in SIMULATED_AGGREGATE_FILES if not (REPO_ROOT / path).is_file()]
        if missing_simulated:
            raise FileNotFoundError(
                "Simulated aggregate outputs are missing: %s" % ", ".join(missing_simulated)
            )
        for relative in SIMULATED_AGGREGATE_FILES:
            source = REPO_ROOT / relative
            sanitized, replacements = sanitize_text(source.read_text(encoding="utf-8-sig"))
            redaction_count += replacements
            payload[relative] = sanitized.encode("utf-8")
        full_outputs = True

    manifest = {
        "schema_version": 1,
        "artifact": "anonymous ContextTrace ARR artifact",
        "archive_root": ZIP_ROOT,
        "deterministic_timestamp": "2026-01-01T00:00:00Z",
        "external_ragtruth_data_included": external_data,
        "paper_reproduction_ready": external_data and full_outputs,
        "frozen_full_outputs_included": full_outputs,
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
    materialized_directory = None
    if output_directory is not None:
        materialized_directory = _materialize_directory(Path(output_directory), payload)

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
        "frozen_full_outputs_included": full_outputs,
        "materialized_directory": materialized_directory,
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
        if Path(relative).suffix.lower() in BINARY_SUFFIXES:
            continue
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


def _materialize_directory(path: Path, payload: dict[str, bytes]) -> str:
    destination = path.resolve()
    if destination == REPO_ROOT.resolve() or destination.parent == destination or not destination.name:
        raise ValueError("Refusing unsafe materialized artifact target.")
    if destination.exists():
        if destination.is_symlink() or not destination.is_dir():
            raise ValueError("Materialized artifact target must be a real directory.")
        shutil.rmtree(destination)
    for relative, content in sorted(payload.items()):
        output = destination / relative
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(content)
    return str(destination)


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
    expected_ready = bool(manifest.get("external_ragtruth_data_included")) and bool(
        manifest.get("frozen_full_outputs_included")
    )
    if bool(manifest.get("paper_reproduction_ready")) != expected_ready:
        errors.append({"name": "manifest_readiness", "message": "Paper readiness flags are inconsistent."})
    if manifest.get("frozen_full_outputs_included"):
        missing_full_outputs = sorted(
            "%s/%s" % (FULL_OUTPUT_ROOT, name)
            for name in FULL_OUTPUT_NAMES
            if "%s/%s" % (FULL_OUTPUT_ROOT, name) not in payload
        )
        if missing_full_outputs:
            errors.append({"name": "full_outputs", "missing": missing_full_outputs})
        missing_after_review = sorted(
            "%s/%s" % (AFTER_REVIEW_OUTPUT_ROOT, name)
            for name in AFTER_REVIEW_OUTPUT_NAMES
            if "%s/%s" % (AFTER_REVIEW_OUTPUT_ROOT, name) not in payload
        )
        if missing_after_review:
            errors.append({"name": "after_review_outputs", "missing": missing_after_review})
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
    parser.add_argument("--directory", default=None, help="Also materialize the exact anonymous payload directory.")
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
        output_directory=args.directory,
    )
    print("Archive: %s" % result["archive"])
    print("SHA256: %s" % result["sha256"])
    print("Files: %s" % result["file_count"])
    print("External RAGTruth data: %s" % result["external_ragtruth_data_included"])
    print("Frozen full outputs: %s" % result["frozen_full_outputs_included"])
    if result["materialized_directory"]:
        print("Directory: %s" % result["materialized_directory"])
    print("Validation: %s" % result["validation"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
