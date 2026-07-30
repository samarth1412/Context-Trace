from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from contexttrace.verify.semantic_core_v2.constants import (
    NLI_ARTIFACT_MANIFEST_SHA256,
    NLI_MODEL_ID,
    NLI_MODEL_REVISION,
)
from contexttrace.verify.semantic_core_v2.profile import PROFILES


REPO_ROOT = Path(__file__).resolve().parents[3]
RESEARCH_ROOT = REPO_ROOT / "research" / "cain2027"


def _load(name: str) -> dict:
    return json.loads((RESEARCH_ROOT / name).read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    "name",
    [
        "IMPLEMENTATION_LOCK.json",
        "DEPENDENCY_LOCK.json",
        "EVALUATION_CONFIG.json",
        "ABLATION_CONFIG.json",
    ],
)
def test_gate_e_lock_payload_hashes_are_valid(name: str) -> None:
    record = _load(name)
    expected = record.pop("payload_sha256")
    canonical = json.dumps(
        record,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    assert hashlib.sha256(canonical).hexdigest() == expected


def test_implementation_source_manifest_is_frozen() -> None:
    lock = _load("IMPLEMENTATION_LOCK.json")
    rows = lock["source_manifest"]
    for row in rows:
        path = REPO_ROOT / row["path"]
        assert path.stat().st_size == row["bytes"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == row["sha256"]
    canonical = json.dumps(
        rows,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    assert (
        hashlib.sha256(canonical).hexdigest()
        == lock["implementation"]["source_manifest_sha256"]
    )


def test_private_source_archive_matches_when_retained() -> None:
    lock = _load("IMPLEMENTATION_LOCK.json")
    archive = lock["implementation"]["source_archive"]
    path = REPO_ROOT / archive["private_path"]
    if not path.is_file():
        pytest.skip("The private source archive is intentionally not stored in Git.")
    assert path.stat().st_size == archive["bytes"]
    assert hashlib.sha256(path.read_bytes()).hexdigest() == archive["sha256"]


def test_frozen_v1_boundary_still_matches_implementation_lock() -> None:
    lock = _load("IMPLEMENTATION_LOCK.json")
    facts = (
        REPO_ROOT / "packages" / "contexttrace" / "contexttrace" / "verify" / "facts.py"
    )
    assert (
        hashlib.sha256(facts.read_bytes()).hexdigest()
        == lock["frozen_boundaries"]["semantic_v1_calibrated_facts_sha256"]
    )


def test_profile_hashes_match_evaluation_and_ablation_locks() -> None:
    evaluation = _load("EVALUATION_CONFIG.json")
    ablations = _load("ABLATION_CONFIG.json")
    assert (
        PROFILES[evaluation["candidate_system"]["profile_id"]].sha256
        == evaluation["candidate_system"]["profile_sha256"]
    )
    for ablation in ablations["ablations"]:
        assert PROFILES[ablation["profile_id"]].sha256 == ablation["profile_sha256"]


def test_nli_identity_matches_dependency_lock() -> None:
    dependency = _load("DEPENDENCY_LOCK.json")
    nli = dependency["nli"]
    assert nli["model_id"] == NLI_MODEL_ID
    assert nli["model_revision"] == NLI_MODEL_REVISION
    assert nli["artifact_manifest_sha256"] == NLI_ARTIFACT_MANIFEST_SHA256
    assert nli["automatic_download_permitted"] is False
    assert nli["remote_inference_permitted"] is False


def test_evaluation_config_remains_unexecuted_and_label_free() -> None:
    evaluation = _load("EVALUATION_CONFIG.json")
    assert evaluation["status"] == "configured_not_authorized_not_executed"
    assert evaluation["execution"]["gold_labels_permitted_as_system_input"] is False
    assert evaluation["execution"]["implementation_team_gold_access_permitted"] is False
    assert evaluation["execution"]["manual_prediction_edits_permitted"] is False
