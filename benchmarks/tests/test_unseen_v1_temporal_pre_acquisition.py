from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest

from benchmarks.contexttrace_unseen_v1.build_temporal_pre_acquisition_catalog import (
    TemporalCatalogError,
    build_catalog,
    build_command,
    validate_catalog,
)


ROOT = Path(__file__).resolve().parents[2]
CALIBRATION_PATH = (
    ROOT / "benchmarks/contexttrace_unseen_v1/calibration/registry.json"
)
NATURAL_PATH = (
    ROOT / "benchmarks/contexttrace_unseen_v1/candidate_source_manifest.json"
)
CATALOG_PATH = (
    ROOT / "benchmarks/contexttrace_unseen_v1/temporal_pre_acquisition_catalog.json"
)


def _prior_manifests() -> tuple[dict, dict]:
    calibration = json.loads(CALIBRATION_PATH.read_text(encoding="utf-8"))
    natural = json.loads(NATURAL_PATH.read_text(encoding="utf-8"))
    return calibration, natural


def _validate(catalog: dict) -> dict:
    calibration, natural = _prior_manifests()
    return validate_catalog(
        catalog,
        calibration_registry=calibration,
        natural_source_manifest=natural,
    )


def test_catalog_is_deterministic_balanced_and_disjoint() -> None:
    first = build_catalog()
    second = build_catalog()
    assert first == second
    assert first == json.loads(CATALOG_PATH.read_text(encoding="utf-8"))

    result = _validate(first)
    assert result == {
        "status": "valid_pending_owner_authorization",
        "source_count": 37,
        "pair_count": 20,
        "case_count": 100,
        "pair_type_counts": {
            "archived_policy_to_current_policy": 5,
            "low_authority_to_authoritative": 5,
            "noncanonical_to_canonical": 5,
            "old_api_to_replacement_api": 5,
        },
        "case_pair_type_counts": {
            "archived_policy_to_current_policy": 25,
            "low_authority_to_authoritative": 25,
            "noncanonical_to_canonical": 25,
            "old_api_to_replacement_api": 25,
        },
        "retrieval_counts": {"bm25": 34, "hybrid": 33, "vector": 33},
        "context_mode_counts": {
            "left_only": 40,
            "mixed_left_first": 20,
            "mixed_right_first": 20,
            "right_only": 20,
        },
        "generator_route_counts": {"hosted": 50, "local": 50},
        "acquisition_hard_limit_usd": 0.0,
        "proposed_generation_hard_limit_usd": 3.0,
        "model_calls_authorized": False,
        "verifier_calls_authorized": False,
        "labels_accessible": False,
    }


def test_committed_catalog_hash_matches_sidecar() -> None:
    digest = hashlib.sha256(CATALOG_PATH.read_bytes()).hexdigest()
    sidecar = CATALOG_PATH.with_suffix(".json.sha256").read_text(encoding="utf-8")
    assert sidecar == f"{digest}  {CATALOG_PATH.name}\n"
    assert digest == "a3781a725ad5100a610e8a6e2bec1b7458903333622ce0461d095c88c8bd6678"


def test_catalog_cannot_authorize_acquisition_or_downstream_work() -> None:
    catalog = build_catalog()
    assert set(catalog["authorization"].values()) >= {False}
    assert catalog["acquisition_budget_usd"]["hard_limit"] == 0.0
    assert catalog["proposed_generation_budget_usd"]["generation_not_yet_authorized"]

    catalog["authorization"]["source_acquisition_authorized"] = True
    with pytest.raises(TemporalCatalogError, match="cannot grant authorization"):
        _validate(catalog)


def test_catalog_rejects_changed_pair_condition() -> None:
    catalog = build_catalog()
    catalog["pairs"][0]["right_condition"] = "authoritative"
    with pytest.raises(TemporalCatalogError, match="Pair conditions changed"):
        _validate(catalog)


def test_catalog_rejects_missing_preverified_snapshot_hash() -> None:
    catalog = build_catalog()
    source = next(
        item
        for item in catalog["sources"]
        if item["immutable_revision"]["kind"] == "effective_date"
    )
    source["immutable_revision"]["expected_sha256"] = ""
    with pytest.raises(TemporalCatalogError, match="Missing expected hash"):
        _validate(catalog)


def test_catalog_rejects_case_allocation_mutation() -> None:
    catalog = build_catalog()
    case = catalog["case_plan"][0]
    case["pair_id"] = next(
        pair["pair_id"]
        for pair in catalog["pairs"]
        if pair["pair_type"] != case["pair_type"]
    )
    with pytest.raises(TemporalCatalogError, match="Case pair mapping changed"):
        _validate(catalog)


def test_catalog_rejects_prior_corpus_identity_overlap() -> None:
    catalog = build_catalog()
    calibration, natural = _prior_manifests()
    overlap = copy.deepcopy(calibration)
    overlap["sources"][0]["source_family"] = catalog["sources"][0]["source_family"]
    with pytest.raises(TemporalCatalogError, match="overlap prior corpora"):
        validate_catalog(
            catalog,
            calibration_registry=overlap,
            natural_source_manifest=natural,
        )


def test_build_refuses_to_overwrite_a_different_lock(tmp_path: Path) -> None:
    output = tmp_path / "catalog.json"
    build_command(output)
    changed = json.loads(output.read_text(encoding="utf-8"))
    changed["status"] = "changed"
    output.write_text(json.dumps(changed), encoding="utf-8")
    with pytest.raises(TemporalCatalogError, match="Refusing to overwrite"):
        build_command(output)
