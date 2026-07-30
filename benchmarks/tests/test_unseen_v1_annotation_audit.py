from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from benchmarks.contexttrace_unseen_v1.build_annotation_audit_packets import (
    select_annotation_audit_cases,
)


ROOT = Path(__file__).resolve().parents[2]
MANIFEST = (
    ROOT
    / ".tmp-contexttrace-unseen-v1-two-track-freeze"
    / "contexttrace_unseen_v1_frozen_unlabeled.json"
)


def _cases() -> list[dict]:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))["cases"]


def test_annotation_audit_selection_is_deterministic_and_disjoint():
    first = select_annotation_audit_cases(_cases())
    second = select_annotation_audit_cases(_cases())

    assert [case["case_id"] for case in first["production"]] == [
        case["case_id"] for case in second["production"]
    ]
    assert len(first["production"]) == 60
    assert len(first["practice"]) == 6
    assert not (
        {case["case_id"] for case in first["production"]}
        & {case["case_id"] for case in first["practice"]}
    )


def test_annotation_audit_selection_has_frozen_balance():
    selection = select_annotation_audit_cases(_cases())
    production = selection["production"]
    tracks = Counter(case["track"] for case in production)
    natural_domains = Counter(
        case["domain_group"] for case in production if case["track"] == "natural_ood"
    )
    pair_types = Counter(
        case["source_condition_pair"]["pair_type"]
        for case in production
        if case["track"] == "temporal_source_condition"
    )

    assert tracks == {"natural_ood": 45, "temporal_source_condition": 15}
    assert natural_domains == {
        "policy_regulatory": 15,
        "software_product_documentation": 15,
        "support_operational": 15,
    }
    assert sorted(pair_types.values()) == [3, 4, 4, 4]
    assert len({case["source_family"] for case in production}) >= 12
