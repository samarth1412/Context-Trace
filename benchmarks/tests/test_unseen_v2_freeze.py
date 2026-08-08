import hashlib
import json
from pathlib import Path

from benchmarks.contexttrace_unseen_v2.freeze_candidate import (
    MAX_IDENTIFIER_SCOPE_TERMS,
    MAX_SCOPE_SEPARATORS,
    METRICS,
    TAXONOMY_VERSION,
    _canonical_sha256,
    _source_rows,
)

FREEZE_ROOT = Path(__file__).resolve().parents[1] / "contexttrace_unseen_v2"
PUBLIC_MANIFEST = FREEZE_ROOT / "contexttrace_unseen_v2_frozen_unlabeled.json"


def test_unseen_v2_metrics_are_strict_and_clustered() -> None:
    metrics = json.loads(METRICS.read_text(encoding="utf-8"))

    assert metrics["statistics"]["bootstrap"]["cluster_key"] == "source_family"
    assert metrics["statistics"]["bootstrap"]["replicates"] == 10000
    assert metrics["statistics"]["paired_randomization"]["replicates"] == 100000
    assert (
        metrics["sota_candidate_gates"]["dangerous_false_green_rate"]["value"] == 0.01
    )
    assert (
        metrics["sota_candidate_gates"]["physical_nli_invocation_rate"]["value"] == 0.4
    )


def test_candidate_source_manifest_is_sorted_and_hashable() -> None:
    rows = _source_rows()
    paths = {row["path"] for row in rows}

    assert rows == sorted(rows, key=lambda row: row["path"])
    assert all(row["bytes"] > 0 for row in rows)
    assert len(_canonical_sha256(rows)) == 64
    assert "packages/contexttrace/contexttrace/verify/facts.py" in paths
    assert "packages/contexttrace/contexttrace/verify/claims.py" in paths
    assert "packages/contexttrace/contexttrace/verify/judges.py" in paths
    assert "benchmarks/contexttrace_unseen_v2/METRICS.json" in paths


def test_freeze_uses_semantic_v2_taxonomy() -> None:
    assert TAXONOMY_VERSION == "contexttrace-diagnosis-v2.0"
    assert MAX_IDENTIFIER_SCOPE_TERMS == 8
    assert MAX_SCOPE_SEPARATORS == 12


def test_public_unseen_v2_manifest_is_sealed_and_unlabeled() -> None:
    manifest = json.loads(PUBLIC_MANIFEST.read_text(encoding="utf-8"))
    identity = dict(manifest)
    seal = identity.pop("seal")
    file_sha256 = hashlib.sha256(PUBLIC_MANIFEST.read_bytes()).hexdigest()
    sidecar = PUBLIC_MANIFEST.with_suffix(".json.sha256").read_text(
        encoding="utf-8"
    )
    freeze_record = json.loads(
        (FREEZE_ROOT / "freeze-record.json").read_text(encoding="utf-8")
    )

    assert _canonical_sha256(identity) == seal["payload_sha256"]
    assert sidecar.split() == [file_sha256, PUBLIC_MANIFEST.name]
    assert manifest["case_count"] == 400
    assert manifest["source_count"] == 70
    assert manifest["composition"]["natural_ood"] == 300
    assert manifest["composition"]["temporal_source_condition"] == 100
    assert manifest["composition"]["domain_groups"] == {
        "policy_regulatory": 100,
        "software_product": 100,
        "support_operational": 100,
    }
    assert manifest["integrity"] == {
        "competitor_calls": 0,
        "domain_id_overlap_with_development": 0,
        "labels_present": False,
        "nli_calls": 0,
        "normalized_content_overlap_with_development": 0,
        "paid_api_calls": 0,
        "source_family_overlap_with_development": 0,
        "verifier_calls": 0,
    }
    assert len({case["case_id"] for case in manifest["cases"]}) == 400
    assert freeze_record["manifest_file_sha256"] == file_sha256
    assert freeze_record["manifest_payload_sha256"] == seal["payload_sha256"]
    assert freeze_record["candidate_executed"] is False
    assert freeze_record["labels_created"] is False
    assert freeze_record["evaluation_authorized"] is False
