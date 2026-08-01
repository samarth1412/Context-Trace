from __future__ import annotations

import json

from benchmarks.product_safety.build_evidence_attribution_corpus import (
    DEFAULT_OUTPUT,
    build_corpus,
)
from benchmarks.product_safety.run_evidence_attribution_benchmark import run


def test_evidence_attribution_corpus_is_current_and_split_disjoint() -> None:
    stored = json.loads(DEFAULT_OUTPUT.read_text(encoding="utf-8"))

    assert stored == build_corpus()
    assert stored["counts"] == {"development": 24, "heldout_development": 18}
    families = {
        split: {
            case["source_family"] for case in stored["cases"] if case["split"] == split
        }
        for split in ("development", "heldout_development")
    }
    assert not families["development"] & families["heldout_development"]


def test_every_attribution_category_occurs_in_both_splits() -> None:
    cases = build_corpus()["cases"]
    expected = {case["category"] for case in cases}

    for split in ("development", "heldout_development"):
        assert {
            case["category"] for case in cases if case["split"] == split
        } == expected


def test_candidate_clears_attribution_development_gates() -> None:
    heldout = run()["heldout_development"]
    candidate = heldout["candidate_v2_1"]
    frozen = heldout["frozen_v2"]

    assert candidate["span_exact_f1"] >= 0.95
    assert candidate["character_iou"] >= 0.95
    assert candidate["source_offset_integrity"] == 1.0
    assert candidate["over_attribution_rate"] <= 0.05
    assert candidate["span_exact_f1"] > frozen["span_exact_f1"]
