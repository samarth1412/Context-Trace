from __future__ import annotations

import json

from contexttrace.verify.semantic_core_v2_1 import observable_conflicts

from benchmarks.product_safety.build_hard_negatives import (
    DEFAULT_OUTPUT,
    build_corpus,
)


def test_hard_negative_corpus_is_current_and_balanced() -> None:
    generated = build_corpus()
    stored = json.loads(DEFAULT_OUTPUT.read_text(encoding="utf-8"))

    assert stored == generated
    assert generated["case_count"] == 24
    assert sum(case["expected"] == "supported" for case in generated["cases"]) == 12
    assert sum(case["expected"] == "not_supported" for case in generated["cases"]) == 12


def test_every_generated_negative_has_an_observable_guard_signal() -> None:
    negatives = [
        case for case in build_corpus()["cases"] if case["expected"] == "not_supported"
    ]

    for case in negatives:
        conflicts = observable_conflicts(case["claim"], case["premise"])
        assert conflicts, case["id"]
        assert case["category"] in {conflict.category for conflict in conflicts}


def test_positive_controls_do_not_trigger_the_guard() -> None:
    positives = [
        case for case in build_corpus()["cases"] if case["expected"] == "supported"
    ]

    for case in positives:
        assert not observable_conflicts(case["claim"], case["premise"]), case["id"]
