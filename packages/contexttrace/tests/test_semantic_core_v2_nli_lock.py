from __future__ import annotations

from pathlib import Path

import pytest

from contexttrace.verify.semantic_core_v2.nli import (
    NLI_ARTIFACT_FILES,
    V2NLIArtifactError,
    verify_nli_artifact,
)


REPO_ROOT = Path(__file__).resolve().parents[3]
LOCAL_MODEL = (
    REPO_ROOT
    / ".tmp-contexttrace-models"
    / "cross-encoder--nli-deberta-v3-small--fa280487"
)


def test_missing_nli_artifact_fails_closed(tmp_path: Path) -> None:
    with pytest.raises(V2NLIArtifactError, match="missing"):
        verify_nli_artifact(tmp_path)


def test_changed_nli_artifact_fails_closed(tmp_path: Path) -> None:
    for relative in NLI_ARTIFACT_FILES:
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"changed")
    with pytest.raises(V2NLIArtifactError, match="hash mismatch"):
        verify_nli_artifact(tmp_path)


def test_downloaded_pinned_nli_artifact_matches_lock() -> None:
    if not LOCAL_MODEL.is_dir():
        pytest.skip("Pinned local NLI artifact is intentionally not stored in Git.")
    record = verify_nli_artifact(LOCAL_MODEL)
    assert record["model_revision"] == "fa2804872c3b4bd748f38c0185cc85775361e735"
    assert (
        record["artifact_manifest_sha256"]
        == "330f0fd77aad129877e1a1a90d4a77e6f093ee238b97d535202816a116b9c9f3"
    )
