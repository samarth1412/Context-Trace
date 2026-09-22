from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from pathlib import Path

import pytest

from benchmarks.local_verification_quality.run import _metrics, _trace, load_cases


REPO = Path(__file__).resolve().parents[2]
BENCHMARK = REPO / "benchmarks" / "local_verification_quality"


def _load(name: str) -> dict:
    return json.loads((BENCHMARK / name).read_text(encoding="utf-8"))


def test_development_and_heldout_scenario_families_are_disjoint() -> None:
    development = _load("development_cases.json")
    heldout = _load("heldout_cases.json")

    assert set(development["scenario_families"]).isdisjoint(heldout["scenario_families"])
    assert development["provenance"] == "synthetic_author_labeled"
    assert heldout["provenance"] == "synthetic_author_labeled"


def test_frozen_case_files_match_manifest() -> None:
    manifest = _load("freeze_manifest.json")
    for filename, field in (
        ("development_cases.json", "development_cases_sha256"),
        ("heldout_cases.json", "heldout_cases_sha256"),
    ):
        digest = hashlib.sha256((BENCHMARK / filename).read_bytes()).hexdigest()
        assert digest == manifest[field]
    assert manifest["frozen_before_scoring"] is True


def test_loader_rejects_wrong_split() -> None:
    with pytest.raises(ValueError, match="Expected split heldout"):
        load_cases(BENCHMARK / "development_cases.json", expected_split="heldout")


def test_trace_adapter_does_not_send_evaluation_labels_or_tags() -> None:
    case = _load("development_cases.json")["cases"][0]
    trace = _trace(case)
    text = json.dumps(asdict(trace), sort_keys=True)

    assert case["expected_verdict"] not in text
    assert "expected_verdict" not in text
    assert "expected_evidence_context_ids" not in text
    assert "tags" not in text


def test_metrics_use_explicit_false_green_and_false_alarm_denominators() -> None:
    def row(case_id: str, expected: str, predicted: str) -> dict:
        return {
            "case_id": case_id,
            "expected_verdict": expected,
            "expected_evidence_context_ids": [case_id],
            "predictions": {
                "candidate": {
                    "verdict": predicted,
                    "review_required": False,
                    "evidence_context_ids": [case_id],
                    "latency_ms": 1.0,
                }
            },
        }

    rows = [
        row("good", "supported", "supported"),
        row("alarm", "supported", "unsupported"),
        row("green", "contradicted", "supported"),
        row("caught", "unsupported", "unsupported"),
    ]
    metrics = _metrics(rows, "candidate")

    assert metrics["incorrect_supported"] == {
        "count": 1,
        "denominator_non_supported": 2,
        "rate": 0.5,
        "case_ids": ["green"],
    }
    assert metrics["false_alarms_on_supported"] == {
        "count": 1,
        "denominator_supported": 2,
        "rate": 0.5,
        "case_ids": ["alarm"],
    }
