from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pytest

from benchmarks.jev_claim_verification.experiment import (
    LABELS,
    ExperimentalJevJudge,
    JevExperimentError,
    build_jev_state,
    enforce_remote_policy,
    load_cases,
    run_experiment,
    summarize,
)
from contexttrace.verify.schema import TraceContext


ROOT = Path(__file__).resolve().parents[2]
CASES = ROOT / "benchmarks" / "jev_claim_verification"


@dataclass
class FakeAnswer:
    choice: str
    confidence: float
    probabilities: dict[str, float]


@dataclass
class FakeUsage:
    input_tokens: int = 123
    output_tokens: int = 17


@dataclass
class FakeResponse:
    answers: dict[str, FakeAnswer]
    model: str = "jev-1.13.0"
    usage: FakeUsage = field(default_factory=FakeUsage)


class FakeClient:
    def __init__(self, verdict: str = "supported") -> None:
        self.verdict = verdict
        self.calls: list[dict[str, object]] = []

    def system_one(self, *, state: object, questions: object, model: str) -> FakeResponse:
        self.calls.append({"state": state, "questions": questions, "model": model})
        probabilities = {label: 0.025 for label in LABELS}
        probabilities[self.verdict] = 0.9
        return FakeResponse(
            answers={
                "verdict": FakeAnswer(
                    choice=self.verdict,
                    confidence=0.875,
                    probabilities=probabilities,
                )
            }
        )


def fake_choice(**kwargs: object) -> dict[str, object]:
    return dict(kwargs)


def test_jev_state_contains_only_selected_claim_evidence_fields() -> None:
    state = build_jev_state(
        query="question",
        claim="claim",
        contexts=[TraceContext(id="selected:1", text="minimum evidence", metadata={"secret": "x"})],
    )

    assert set(state) == {"query", "claim", "selected_evidence"}
    assert state["selected_evidence"] == [{"id": "selected:1", "text": "minimum evidence"}]
    serialized = repr(state)
    assert "expected_verdict" not in serialized
    assert "secret" not in serialized


def test_experiment_records_documented_jev_outputs_without_inventing_details() -> None:
    case = load_cases(CASES / "development_cases.json")[0]
    client = FakeClient(verdict="supported")
    judge = ExperimentalJevJudge(
        client=client,
        choice_factory=fake_choice,
        model="jev-latest",
    )

    result = run_experiment([case], judge=judge)

    row = result["rows"][0]
    jev = row["jev"]
    assert jev["verdict"] == "supported"
    assert set(jev["probabilities"]) == set(LABELS)
    assert jev["confidence"] == 0.875
    assert jev["requested_model"] == "jev-latest"
    assert jev["resolved_model"] == "jev-1.13.0"
    assert jev["usage"] == {"input_tokens": 123, "output_tokens": 17, "total_tokens": 140}
    assert jev["latency_ms"] >= 0.0
    assert jev["reason"] is None
    assert jev["matched_facts"] == []
    assert jev["missing_facts"] == []
    assert jev["conflicting_facts"] == []
    assert row["input_audit"]["evaluation_label_sent"] is False
    sent_state = client.calls[0]["state"]
    assert "expected_verdict" not in sent_state
    assert "split" not in sent_state
    assert "category" not in sent_state


def test_remote_policy_preserves_local_only_and_requires_explicit_opt_in() -> None:
    with pytest.raises(JevExperimentError, match="local_only"):
        enforce_remote_policy(local_only=True, allow_remote=True)
    with pytest.raises(JevExperimentError, match="--allow-remote"):
        enforce_remote_policy(local_only=False, allow_remote=False)
    enforce_remote_policy(local_only=False, allow_remote=True)


def test_development_and_heldout_files_cannot_be_mixed() -> None:
    development = load_cases(CASES / "development_cases.json", expected_split="development")
    heldout = load_cases(CASES / "heldout_cases.json", expected_split="heldout")

    assert {case.case_id for case in development}.isdisjoint(case.case_id for case in heldout)
    assert {case.expected_verdict for case in development} == set(LABELS)
    assert {case.expected_verdict for case in heldout} == set(LABELS)
    with pytest.raises(JevExperimentError, match="Expected heldout split"):
        load_cases(CASES / "development_cases.json", expected_split="heldout")


def test_summary_highlights_unsupported_false_supported_errors() -> None:
    rows = [
        {
            "case_id": "unsafe",
            "expected_verdict": "unsupported",
            "baseline": {"verdict": "unsupported"},
            "jev": {
                "verdict": "supported",
                "latency_ms": 10.0,
                "usage": {"input_tokens": 20, "output_tokens": 3},
            },
        }
    ]

    result = summarize(rows)

    assert result["unsupported_false_supported_case_ids"] == ["unsafe"]
    assert result["dangerous_false_supported_case_ids"] == ["unsafe"]
    assert result["baseline_jev_disagreements"] == [
        {
            "case_id": "unsafe",
            "expected": "unsupported",
            "baseline": "unsupported",
            "jev": "supported",
        }
    ]
