from __future__ import annotations

import json
import zipfile
from pathlib import Path

from scripts.build_anonymous_artifact import (
    ARCHIVE_TIMESTAMP,
    ZIP_ROOT,
    build_anonymous_artifact,
    _git_tracked_paths,
    sanitize_text,
    validate_anonymous_artifact,
)
from benchmarks.contexttrace_bench.artifact_runtime import ANONYMOUS_REVISION, repository_revision


def test_sanitize_text_removes_project_identity_and_local_paths():
    owner = "sam" + "arth" + "1412"
    owner_alias = "sam" + "arth" + "vinayaka"
    given_name = "sam" + "arth"
    username = "ma" + "nnv"
    source = (
        "https://github.com/%s/Context-Trace/issues " % owner
        + "https://" + "pypi" + ".org/project/contexttrace/ "
        + "%s %s author@%s " % (owner_alias, given_name, "uf" + "l.edu")
        + "C:\\Users\\%s\\project\\results.json" % username
    )

    sanitized, count = sanitize_text(source)

    assert count >= 6
    assert owner not in sanitized
    assert owner_alias not in sanitized
    assert given_name not in sanitized.lower()
    assert "pypi.org" not in sanitized
    assert "uf" + "l.edu" not in sanitized
    assert username not in sanitized
    assert "<ANONYMIZED_LOCAL_PATH>" in sanitized


def test_anonymous_artifact_is_deterministic_and_valid_without_external_data(tmp_path):
    first = build_anonymous_artifact(
        output_path=tmp_path / "first.zip",
        include_external_data=False,
    )
    second = build_anonymous_artifact(
        output_path=tmp_path / "second.zip",
        include_external_data=False,
        output_directory=tmp_path / "materialized",
    )

    assert first["sha256"] == second["sha256"]
    assert first["external_ragtruth_data_included"] is False
    assert validate_anonymous_artifact(first["archive"])["status"] == "passed"
    assert (Path(second["materialized_directory"]) / "ARTIFACT_MANIFEST.json").is_file()
    with zipfile.ZipFile(first["archive"], "r") as archive:
        names = archive.namelist()
        assert names == sorted(names)
        assert all(info.date_time == ARCHIVE_TIMESTAMP for info in archive.infolist())
        assert "%s/README.md" % ZIP_ROOT in names
        assert "%s/packages/contexttrace/contexttrace/repair.py" % ZIP_ROOT in names
        assert "%s/packages/contexttrace/tests/test_repair.py" % ZIP_ROOT in names
        assert "%s/examples/diagnose_agent_trace.json" % ZIP_ROOT in names
        assert not any(".git" in Path(name).parts for name in names)
        manifest = json.loads(archive.read("%s/ARTIFACT_MANIFEST.json" % ZIP_ROOT))
        assert manifest["paper_reproduction_ready"] is False


def test_anonymous_artifact_validator_rejects_identity_and_secret(tmp_path):
    owner = "sam" + "arth" + "1412"
    fake_key = "sk-" + "abcdefghijklmnopqrstuvwxyz"
    path = tmp_path / "bad.zip"
    with zipfile.ZipFile(path, "w") as archive:
        info = zipfile.ZipInfo("%s/README.md" % ZIP_ROOT, date_time=ARCHIVE_TIMESTAMP)
        archive.writestr(info, "github.com/%s/Context-Trace %s" % (owner, fake_key))

    validation = validate_anonymous_artifact(path)

    assert validation["status"] == "failed"
    assert {error["name"] for error in validation["errors"]}.issuperset(
        {"repository_owner", "public_repository", "openai_key", "required_files"}
    )


def test_anonymous_artifact_validator_rejects_path_traversal(tmp_path):
    path = tmp_path / "traversal.zip"
    with zipfile.ZipFile(path, "w") as archive:
        info = zipfile.ZipInfo("%s/../secret.txt" % ZIP_ROOT, date_time=ARCHIVE_TIMESTAMP)
        archive.writestr(info, "secret")

    validation = validate_anonymous_artifact(path)

    assert validation["status"] == "failed"
    assert any(error["name"] == "archive_path" for error in validation["errors"])


def test_git_source_discovery_requires_exact_repository_root(monkeypatch, tmp_path):
    from scripts import build_anonymous_artifact as module

    nested = tmp_path / "nested"
    nested.mkdir()
    monkeypatch.setattr(module, "REPO_ROOT", nested)

    assert _git_tracked_paths() is None


def test_anonymous_runtime_revision_does_not_use_parent_checkout(tmp_path):
    nested = tmp_path / "artifact"
    nested.mkdir()

    assert repository_revision(nested) == ANONYMOUS_REVISION
