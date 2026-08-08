from __future__ import annotations

import json

from benchmarks.product_safety.build_checker_development_corpus import (
    DEFAULT_OUTPUT,
    build_corpus,
)


def test_checker_development_corpus_is_current() -> None:
    stored = json.loads(DEFAULT_OUTPUT.read_text(encoding="utf-8"))

    assert stored == build_corpus()
    assert stored["counts"] == {"train": 96, "validation": 24, "test": 24}


def test_checker_source_families_are_split_disjoint() -> None:
    cases = build_corpus()["cases"]
    families = {
        split: {case["source_family"] for case in cases if case["split"] == split}
        for split in ("train", "validation", "test")
    }

    assert not families["train"] & families["validation"]
    assert not families["train"] & families["test"]
    assert not families["validation"] & families["test"]


def test_every_category_occurs_in_each_split() -> None:
    cases = build_corpus()["cases"]
    expected = {case["category"] for case in cases}

    for split in ("train", "validation", "test"):
        assert {
            case["category"] for case in cases if case["split"] == split
        } == expected
