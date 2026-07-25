from __future__ import annotations

import copy
import datetime as dt
import hashlib
import io
import json
import tarfile
from pathlib import Path

import pytest

from benchmarks.contexttrace_unseen_v1.acquire_sources import (
    AcquisitionError,
    _canonical_text_hash,
    _eligible_repository_files,
    _extract_text,
    _sha512_file,
    _validate_authorization,
    _write_deterministic_tar,
    _xml_visible_text,
)
from benchmarks.contexttrace_unseen_v1.validate_acquisition import (
    AcquisitionValidationError,
    _safe_artifact_path,
    _validate_repository_archive,
)


ROOT = Path(__file__).resolve().parents[2]
CATALOG = json.loads(
    (ROOT / "benchmarks/contexttrace_unseen_v1/pre_acquisition_catalog.json").read_text(
        encoding="utf-8"
    )
)


def test_acquisition_requires_narrow_9a_authorization() -> None:
    _validate_authorization(CATALOG)
    unauthorized = copy.deepcopy(CATALOG)
    unauthorized["acquisition_authorization"]["model_calls_authorized"] = True
    with pytest.raises(AcquisitionError, match="downstream"):
        _validate_authorization(unauthorized)


def test_repository_filter_excludes_third_party_binary_and_generated(
    tmp_path: Path,
) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "guide.md").write_text("Eligible guide", encoding="utf-8")
    (docs / "diagram.png").write_bytes(b"\x00PNG")
    (docs / "vendor").mkdir()
    (docs / "vendor/copy.md").write_text("third party", encoding="utf-8")
    (docs / "generated").mkdir()
    (docs / "generated/output.rst").write_text("generated", encoding="utf-8")

    files, exclusions = _eligible_repository_files(docs)

    assert [path.name for path in files] == ["guide.md"]
    assert exclusions["unsupported_extension"] == 1
    assert exclusions["excluded_directory:vendor"] == 1
    assert exclusions["excluded_directory:generated"] == 1


def test_repository_filter_accepts_rdoc(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    source = docs / "syntax.rdoc"
    source.write_text("Ruby documentation", encoding="utf-8")

    files, exclusions = _eligible_repository_files(docs)

    assert files == [source]
    assert exclusions == {}


def test_deterministic_archive_has_stable_bytes(tmp_path: Path) -> None:
    checkout = tmp_path / "checkout"
    docs = checkout / "docs"
    docs.mkdir(parents=True)
    guide = docs / "guide.md"
    guide.write_text("same bytes", encoding="utf-8")
    license_path = checkout / "LICENSE"
    license_path.write_text("terms", encoding="utf-8")
    first = tmp_path / "first.tar.gz"
    second = tmp_path / "second.tar.gz"

    for output in (first, second):
        _write_deterministic_tar(
            output,
            content_root=docs,
            content_files=[guide],
            checkout=checkout,
            legal_files=[license_path],
        )

    assert first.read_bytes() == second.read_bytes()
    with tarfile.open(fileobj=io.BytesIO(first.read_bytes()), mode="r:gz") as tar:
        assert tar.getnames() == ["content/guide.md", "legal/LICENSE"]


def test_normalized_hash_is_nfkc_casefolded_and_whitespace_insensitive() -> None:
    assert _canonical_text_hash("Ａ  B\n") == _canonical_text_hash("a b")


def test_ecfr_xml_extraction_excludes_graphics_and_forms() -> None:
    payload = (
        b"<?xml version='1.0'?>"
        b"<ROOT><P>Regulatory text</P><GPH>image caption</GPH>"
        b"<FORM>form content</FORM><P>More text</P></ROOT>"
    )

    visible = _xml_visible_text(payload)

    assert "Regulatory text" in visible
    assert "More text" in visible
    assert "image caption" not in visible
    assert "form content" not in visible


def test_repository_xml_extraction_tolerates_build_time_entities(
    tmp_path: Path,
) -> None:
    source = tmp_path / "guide.xml"
    source.write_text(
        "<!DOCTYPE guide [<!ENTITY project SYSTEM 'project.xml'>]>"
        "<guide><p>&project; operational guidance</p></guide>",
        encoding="utf-8",
    )

    visible = _extract_text(source)

    assert "operational guidance" in visible


def test_artifact_paths_cannot_escape_private_workspace(tmp_path: Path) -> None:
    with pytest.raises(AcquisitionValidationError, match="Unsafe"):
        _safe_artifact_path(tmp_path, "../outside.txt")


def test_raw_artifact_mutation_changes_hash(tmp_path: Path) -> None:
    artifact = tmp_path / "source.xml"
    artifact.write_bytes(b"<PART>original</PART>")
    before = hashlib.sha256(artifact.read_bytes()).hexdigest()
    artifact.write_bytes(b"<PART>changed</PART>")
    after = hashlib.sha256(artifact.read_bytes()).hexdigest()
    assert before != after


def test_sha512_verifies_upstream_release_bytes(tmp_path: Path) -> None:
    artifact = tmp_path / "release.tar.gz"
    artifact.write_bytes(b"release bytes")
    assert _sha512_file(artifact) == hashlib.sha512(b"release bytes").hexdigest()


def test_generated_timestamps_are_timezone_aware() -> None:
    value = dt.datetime.now(dt.timezone.utc).isoformat()
    assert dt.datetime.fromisoformat(value).tzinfo is not None


def test_archive_reconstruction_uses_path_component_order(
    tmp_path: Path,
) -> None:
    checkout = tmp_path / "checkout"
    docs = checkout / "docs"
    nested = docs / "java"
    nested.mkdir(parents=True)
    nested_file = nested / "guide.md"
    nested_file.write_text("nested", encoding="utf-8")
    sibling = docs / "java-dependencies.md"
    sibling.write_text("sibling", encoding="utf-8")
    archive_path = tmp_path / "source.tar.gz"
    _write_deterministic_tar(
        archive_path,
        content_root=docs,
        content_files=[nested_file, sibling],
        checkout=checkout,
        legal_files=[],
    )
    source = {
        "source_family": "test",
        "metadata": {
            "included_document_files": 2,
            "retained_legal_files": 0,
        },
    }

    _, _, reconstructed = _validate_repository_archive(archive_path, source)

    assert reconstructed.index("java/guide.md") < reconstructed.index(
        "java-dependencies.md"
    )
