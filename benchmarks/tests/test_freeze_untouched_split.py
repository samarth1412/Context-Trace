import pytest

from benchmarks.contexttrace_bench.freeze_untouched_split import freeze_split


def _case(case_id, *, source_family="family-a", document="doc-a", domain="software", window="2026-Q2"):
    return {
        "id": case_id,
        "track": "natural_ood",
        "source_family": source_family,
        "source_document_id": document,
        "domain": domain,
        "publication_window": window,
    }


def test_freeze_split_is_sorted_and_hash_is_deterministic():
    candidate = {
        "cases": [
            _case("b", source_family="family-b", document="doc-b", domain="support"),
            _case("a"),
        ]
    }
    calibration = {
        "cases": [
            _case(
                "cal",
                source_family="calibration-family",
                document="calibration-doc",
                domain="finance",
                window="2025-Q4",
            )
        ]
    }

    first = freeze_split(candidate, calibration)
    second = freeze_split(candidate, calibration)

    assert first["status"] == "frozen_unscored"
    assert [case["id"] for case in first["cases"]] == ["a", "b"]
    assert first["manifest_sha256"] == second["manifest_sha256"]
    assert len(first["manifest_sha256"]) == 64


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("source_family", "calibration-family"),
        ("source_document_id", "calibration-doc"),
        ("domain", "finance"),
        ("publication_window", "2025-Q4"),
    ],
)
def test_freeze_split_rejects_each_calibration_overlap_dimension(field, value):
    candidate_case = _case(
        "candidate",
        source_family="new-family",
        document="new-doc",
        domain="support",
        window="2026-Q3",
    )
    candidate_case["track"] = "temporal_source_condition"
    candidate_case[field] = value
    calibration_case = _case(
        "calibration",
        source_family="calibration-family",
        document="calibration-doc",
        domain="finance",
        window="2025-Q4",
    )

    with pytest.raises(ValueError, match="overlaps calibration"):
        freeze_split({"cases": [candidate_case]}, {"cases": [calibration_case]})


def test_freeze_split_requires_all_separation_fields():
    candidate = _case("candidate")
    del candidate["publication_window"]

    with pytest.raises(ValueError, match="publication_window"):
        freeze_split({"cases": [candidate]}, {"cases": []})
