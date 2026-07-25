from __future__ import annotations

import json
from pathlib import Path

import pytest

from benchmarks.contexttrace_unseen_v1 import build_calibration_registry as builder


def test_canonical_url_removes_fragments_and_trailing_slashes() -> None:
    assert (
        builder.canonical_url(
            "HTTPS://Docs.Python.org:443/3/library/urllib.request.html/#top"
        )
        == "https://docs.python.org/3/library/urllib.request.html"
    )


def test_known_host_and_github_org_aliases() -> None:
    assert builder.family_for_url("https://docs.python.org/3/") == "python"
    assert (
        builder.family_for_url("https://github.com/chroma-core/chroma/issues/1")
        == "chroma"
    )
    assert builder.canonical_family("developers.openai.com") == "openai"


def test_local_filename_is_not_treated_as_domain() -> None:
    with pytest.raises(ValueError, match="not a public URL"):
        builder.canonical_url("callbacks.md")


def test_builder_emits_schema_shaped_registry_and_provenance(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    source_dir = repo / "benchmarks/contexttrace_bench"
    source_dir.mkdir(parents=True)
    (repo / "research/cain2027").mkdir(parents=True)
    (repo / "research/cain2027/evidence_inventory.json").write_text(
        json.dumps(
            {
                "datasets": [
                    {
                        "id": "legacy_set",
                        "paths": ["benchmarks/legacy"],
                        "classification": ["calibration"],
                    },
                    {
                        "id": "future_set",
                        "paths": ["benchmarks/future"],
                        "classification": [],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    (source_dir / "cases.jsonl").write_text(
        json.dumps(
            {
                "source_family": "Python",
                "contexts": [
                    {
                        "source_url": "https://docs.python.org/3/library/json.html",
                        "text": "Previously inspected text.",
                    }
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )

    output = repo / "benchmarks/contexttrace_unseen_v1/calibration"
    registry, inventory = builder.build_registry(repo, output)

    assert registry["manifest_kind"] == "contexttrace_calibration_registry"
    assert inventory["counts"]["source_urls"] == 1
    assert not inventory["read_errors"]
    assert "dataset_future_set" not in inventory["dataset_exposures"]
    assert any(
        source["source_family"] == "python" for source in registry["sources"]
    )
    for source in registry["sources"]:
        artifact = repo / source["snapshot_path"]
        assert artifact.is_file()
        assert builder._sha256(artifact.read_bytes()) == source["snapshot_sha256"]
