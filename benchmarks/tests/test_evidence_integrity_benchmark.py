from __future__ import annotations

import json
from pathlib import Path

import pytest

from benchmarks.evidence_integrity.run import (
    IntegrityBenchmarkError,
    assert_disjoint,
    load_cases,
    run_cases,
    sha256_file,
    verify_manifest,
)


ROOT = Path(__file__).resolve().parents[2]
BENCHMARK = ROOT / "benchmarks" / "evidence_integrity"


def test_frozen_development_and_heldout_sets_are_disjoint_and_pass() -> None:
    development_path = BENCHMARK / "development_cases.json"
    heldout_path = BENCHMARK / "heldout_cases.json"
    development = load_cases(development_path, expected_split="development")
    heldout = load_cases(heldout_path, expected_split="heldout")
    assert_disjoint(development, heldout)

    for split, path, cases in (
        ("development", development_path, development),
        ("heldout", heldout_path, heldout),
    ):
        report = run_cases(cases, split=split, dataset_sha256=sha256_file(path))
        assert report["acceptance"]["passed"] is True
        assert report["summary"]["dangerous_false_green_count"] == 0
        assert report["summary"]["network_calls"] == 0
        assert report["summary"]["model_calls"] == 0
        if split == "heldout":
            recorded = json.loads(
                (BENCHMARK / "results" / "heldout_report.json").read_text(encoding="utf-8")
            )
            assert recorded == report


def test_manifest_locks_both_case_files() -> None:
    manifest = verify_manifest(BENCHMARK / "manifest.json")
    assert set(manifest["files"]) == {"development_cases.json", "heldout_cases.json"}


def test_labels_inside_trace_are_rejected(tmp_path: Path) -> None:
    path = tmp_path / "leaky.json"
    path.write_text(
        json.dumps(
            {
                "split": "development",
                "cases": [
                    {
                        "id": "leak",
                        "trace": {
                            "query": "q",
                            "answer": "a",
                            "contexts": [{"id": "c", "text": "t", "metadata": {"label": "x"}}],
                        },
                        "expected": {
                            "status": "complete",
                            "issue_types": [],
                            "unknown_contexts": 0,
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(IntegrityBenchmarkError, match="evaluation label"):
        load_cases(path, expected_split="development")
