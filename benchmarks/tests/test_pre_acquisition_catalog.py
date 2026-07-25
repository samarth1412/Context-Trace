from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from benchmarks.contexttrace_unseen_v1.validate_pre_acquisition import (
    CatalogError,
    validate_catalog,
)


ROOT = Path(__file__).resolve().parents[2]
CATALOG = json.loads(
    (
        ROOT
        / "benchmarks/contexttrace_unseen_v1/pre_acquisition_catalog.json"
    ).read_text(encoding="utf-8")
)
CALIBRATION = json.loads(
    (
        ROOT / "benchmarks/contexttrace_unseen_v1/calibration/registry.json"
    ).read_text(encoding="utf-8")
)


def test_reviewed_catalog_is_balanced_and_disjoint() -> None:
    result = validate_catalog(CATALOG, CALIBRATION)
    assert result["entry_count"] == 36
    assert result["target_cases"] == 396
    assert result["overlaps"] == {}
    assert result["external_human_exposure_attested"] is False


def test_acquisition_gate_requires_external_exposure_attestation() -> None:
    with pytest.raises(CatalogError, match="attestation"):
        validate_catalog(CATALOG, CALIBRATION, require_attestation=True)


def test_calibration_family_overlap_fails_closed() -> None:
    catalog = copy.deepcopy(CATALOG)
    catalog["entries"][0]["source_family"] = CALIBRATION["sources"][0][
        "source_family"
    ]
    catalog["entries"][0]["family_id"] = catalog["entries"][0]["source_family"]
    with pytest.raises(CatalogError, match="Calibration overlap"):
        validate_catalog(catalog, CALIBRATION)


def test_mutable_repository_reference_fails_closed() -> None:
    catalog = copy.deepcopy(CATALOG)
    catalog["entries"][0]["commit_sha1"] = "main"
    with pytest.raises(CatalogError, match="immutable commit"):
        validate_catalog(catalog, CALIBRATION)
