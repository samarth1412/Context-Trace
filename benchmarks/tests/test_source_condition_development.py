from __future__ import annotations

import json

from benchmarks.product_safety.build_source_condition_corpus import (
    DEFAULT_OUTPUT,
    build_corpus,
)
from benchmarks.product_safety.run_source_condition_benchmark import run


def test_source_condition_corpus_is_current_and_split_disjoint() -> None:
    stored = json.loads(DEFAULT_OUTPUT.read_text(encoding="utf-8"))

    assert stored == build_corpus()
    assert stored["counts"] == {"development": 36, "heldout_development": 18}
    families = {
        split: {
            case["source_family"] for case in stored["cases"] if case["split"] == split
        }
        for split in ("development", "heldout_development")
    }
    assert not families["development"] & families["heldout_development"]


def test_each_source_condition_category_occurs_in_both_splits() -> None:
    cases = build_corpus()["cases"]
    expected = {case["category"] for case in cases}

    for split in ("development", "heldout_development"):
        assert {
            case["category"] for case in cases if case["split"] == split
        } == expected


def test_source_condition_benchmark_candidate_passes_development_gate() -> None:
    report = run()
    heldout = report["heldout_development"]

    assert heldout["candidate_v2_1"]["macro_f1"] >= 0.9
    assert heldout["candidate_v2_1"]["dangerous_false_green_rate"] == 0.0
    assert heldout["candidate_v2_1"]["macro_f1"] > heldout["frozen_v2"]["macro_f1"]
