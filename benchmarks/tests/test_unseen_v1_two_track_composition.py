from __future__ import annotations

import copy
from pathlib import Path

import pytest

from benchmarks.contexttrace_unseen_v1.compose_two_track_freeze import (
    CompositionError,
    _combined_case_manifest,
    _combined_source_manifest,
    _uniform_leakage_audit,
    _validate_input_sets,
)
from benchmarks.contexttrace_unseen_v1.freeze_manifest import (
    BYTE_NORMALIZED_HASH,
    SEMANTIC_NORMALIZED_HASH,
)


def _source(index: int, *, temporal: bool) -> dict:
    prefix = "temporal" if temporal else "natural"
    return {
        "source_id": f"{prefix}-source-{index}",
        "normalized_text_path": f"normalized/{prefix}-{index}.txt",
        "metadata": {},
    }


def _case(index: int, *, temporal: bool) -> dict:
    return {
        "case_id": (
            f"temporal-case-{index}" if temporal else f"natural-case-{index}"
        ),
        "track": (
            "temporal_source_condition" if temporal else "natural_ood"
        ),
        "verifier_history": [],
    }


def _case_manifest(cases: list[dict]) -> dict:
    return {
        "label_access": {
            "labels_created": False,
            "labels_accessible": False,
            "first_accessed_at": None,
        },
        "cases": cases,
    }


def _source_manifest(sources: list[dict]) -> dict:
    return {
        "disjoint_dimensions": ["source_id"],
        "sources": sources,
    }


def _valid_sets() -> tuple[dict, dict, dict, dict]:
    natural_sources = _source_manifest(
        [_source(index, temporal=False) for index in range(36)]
    )
    temporal_sources = _source_manifest(
        [_source(index, temporal=True) for index in range(37)]
    )
    natural_cases = _case_manifest(
        [_case(index, temporal=False) for index in range(393)]
    )
    temporal_cases = _case_manifest(
        [_case(index, temporal=True) for index in range(100)]
    )
    return natural_sources, temporal_sources, natural_cases, temporal_cases


def test_composition_preserves_counts_and_adds_hash_provenance() -> None:
    natural_sources, temporal_sources, natural_cases, temporal_cases = (
        _valid_sets()
    )
    _validate_input_sets(
        natural_sources, temporal_sources, natural_cases, temporal_cases
    )
    sources = _combined_source_manifest(
        natural_sources,
        temporal_sources,
        composed_at="2026-07-26T00:00:00Z",
    )
    cases = _combined_case_manifest(
        natural_cases,
        temporal_cases,
        composed_at="2026-07-26T00:00:00Z",
    )
    assert len(sources["sources"]) == 73
    assert len(cases["cases"]) == 493
    kinds = {
        source["metadata"]["composite_origin_track"]: source["metadata"][
            "normalized_content_hash_kind"
        ]
        for source in sources["sources"]
    }
    assert kinds == {
        "natural_ood": SEMANTIC_NORMALIZED_HASH,
        "temporal_source_condition": BYTE_NORMALIZED_HASH,
    }
    assert cases["label_access"]["labels_accessible"] is False


def test_composition_rejects_cross_track_case_id_overlap() -> None:
    natural_sources, temporal_sources, natural_cases, temporal_cases = (
        _valid_sets()
    )
    temporal_cases["cases"][0]["case_id"] = natural_cases["cases"][0]["case_id"]
    with pytest.raises(CompositionError, match="Case IDs overlap"):
        _validate_input_sets(
            natural_sources, temporal_sources, natural_cases, temporal_cases
        )


def test_uniform_leakage_audit_uses_one_semantic_method(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    natural_root = tmp_path / "natural"
    temporal_root = tmp_path / "temporal"
    for root, path, text in (
        (natural_root, "normalized/natural.txt", "Alpha   SOURCE"),
        (temporal_root, "normalized/temporal.txt", "Beta source"),
        (project, "normalized/calibration.txt", "Gamma source"),
    ):
        target = root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    result = _uniform_leakage_audit(
        project_root=project,
        natural_sources=_source_manifest(
            [
                {
                    "source_id": "natural",
                    "normalized_text_path": "normalized/natural.txt",
                }
            ]
        ),
        temporal_sources=_source_manifest(
            [
                {
                    "source_id": "temporal",
                    "normalized_text_path": "normalized/temporal.txt",
                }
            ]
        ),
        calibration=_source_manifest(
            [
                {
                    "source_id": "calibration",
                    "normalized_text_path": "normalized/calibration.txt",
                }
            ]
        ),
        natural_acquisition_root=natural_root,
        temporal_acquisition_root=temporal_root,
    )
    assert result["unique_candidate_fingerprints"] == 2
    assert result["candidate_calibration_collisions"] == 0

    duplicate = copy.deepcopy(
        {
            "disjoint_dimensions": ["source_id"],
            "sources": [
                {
                    "source_id": "temporal",
                    "normalized_text_path": "normalized/temporal.txt",
                }
            ],
        }
    )
    (temporal_root / "normalized/temporal.txt").write_text(
        " alpha source ", encoding="utf-8"
    )
    with pytest.raises(CompositionError, match="leakage"):
        _uniform_leakage_audit(
            project_root=project,
            natural_sources=_source_manifest(
                [
                    {
                        "source_id": "natural",
                        "normalized_text_path": "normalized/natural.txt",
                    }
                ]
            ),
            temporal_sources=duplicate,
            calibration=_source_manifest(
                [
                    {
                        "source_id": "calibration",
                        "normalized_text_path": "normalized/calibration.txt",
                    }
                ]
            ),
            natural_acquisition_root=natural_root,
            temporal_acquisition_root=temporal_root,
        )
