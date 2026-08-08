from __future__ import annotations

from dataclasses import replace

from contexttrace.verify.judges import JudgeVerdict
from contexttrace.verify.schema import RAGTrace, TraceContext
from contexttrace.verify.semantic_core_v2_1 import (
    SELECTIVE_V2_1_PROFILE,
    verify_trace_v2_1,
    verify_traces_v2_1,
)


class RecordingNLI:
    def __init__(self, verdict: str = "supported") -> None:
        self.verdict = verdict
        self.calls: list[str] = []

    def verify_claim(self, *, query, claim, contexts):
        del query
        self.calls.append(claim)
        label = "entailment" if self.verdict == "supported" else "neutral"
        return JudgeVerdict(
            verdict=self.verdict,
            confidence=0.97,
            reason="synthetic grouped verdict",
            provider="test",
            model="test-nli",
            raw={
                "nli_label": label,
                "nli_scores": {label: 0.97},
                "context_id": contexts[0].id,
            },
        )


class FailingNLI:
    def __init__(self) -> None:
        self.calls = 0

    def verify_claim(self, *, query, claim, contexts):
        del query, claim, contexts
        self.calls += 1
        raise RuntimeError("synthetic provider failure")


class SelectiveNLI(RecordingNLI):
    def verify_claim(self, *, query, claim, contexts):
        if "30-day processing time" not in claim or "clinic" in claim:
            return super().verify_claim(
                query=query,
                claim=claim,
                contexts=contexts,
            )
        self.calls.append(claim)
        return JudgeVerdict(
            verdict="unsupported",
            confidence=0.98,
            reason="synthetic missing-fact rejection",
            provider="test",
            model="test-nli",
            raw={
                "nli_label": "neutral",
                "nli_scores": {"neutral": 0.98},
                "context_id": contexts[0].id,
            },
        )


def _two_ambiguous_claims() -> RAGTrace:
    return RAGTrace(
        query="What happened at the two workplaces?",
        answer=(
            "The clinic where Lindsey worked has fired her. "
            "The office where Morgan worked has dismissed him."
        ),
        contexts=[
            TraceContext(
                id="workplaces",
                text=(
                    "The clinic fired Lindsey, covered her name on its marquee "
                    "with tape, and publicly distanced itself from her actions. "
                    "Callers contacted the animal clinic, where Lindsey worked. "
                    "The office dismissed Morgan, removed his badge from its "
                    "directory, and publicly distanced itself from his actions. "
                    "Employees contacted the regional office, where Morgan worked."
                ),
            )
        ],
    )


def test_grouped_entailment_resolves_two_claims_with_one_invocation() -> None:
    nli = RecordingNLI()

    result = verify_trace_v2_1(_two_ambiguous_claims(), nli=nli)

    assert len(result["claims"]) == 2
    assert len(nli.calls) == 1
    assert "clinic where Lindsey worked" in nli.calls[0]
    assert "office where Morgan worked" in nli.calls[0]
    assert {claim["claim_verdict"] for claim in result["claims"]} == {"supported"}
    groups = {
        claim["nli"]["grouped_claim_nli"]["group_id"]
        for claim in result["claims"]
    }
    assert len(groups) == 1
    assert result["summary"]["nli_invocations"] == 1
    assert result["summary"]["nli_invocation_rate"] == 0.5


def test_non_entailing_group_abstains_without_forced_claim_attribution() -> None:
    nli = RecordingNLI(verdict="unsupported")

    result = verify_trace_v2_1(_two_ambiguous_claims(), nli=nli)

    assert len(nli.calls) == 1
    assert {claim["claim_verdict"] for claim in result["claims"]} == {
        "unverifiable"
    }
    assert all(claim["diagnostic_abstention"] for claim in result["claims"])
    assert {
        claim["nli"]["grouped_claim_nli"]["resolution"]
        for claim in result["claims"]
    } == {"unresolved"}
    assert result["summary"]["nli_invocations"] == 1


def test_profile_can_disable_grouped_claim_routing() -> None:
    nli = RecordingNLI()
    profile = replace(
        SELECTIVE_V2_1_PROFILE,
        id="ungrouped-test",
        grouped_claim_nli=False,
    )

    result = verify_trace_v2_1(_two_ambiguous_claims(), nli=nli, profile=profile)

    assert len(nli.calls) == 2
    assert all("grouped_claim_nli" not in claim["nli"] for claim in result["claims"])
    assert result["summary"]["nli_invocations"] == 2


def test_deterministic_claim_does_not_split_same_source_group() -> None:
    nli = RecordingNLI()
    base = _two_ambiguous_claims()
    trace = replace(
        base,
        answer=(
            "The clinic where Lindsey worked has fired her. "
            "Access is enabled. "
            "The office where Morgan worked has dismissed him."
        ),
        contexts=[
            replace(
                base.contexts[0],
                text=base.contexts[0].text + " Access is enabled.",
            )
        ],
    )

    result = verify_trace_v2_1(trace, nli=nli)

    assert len(result["claims"]) == 3
    assert len(nli.calls) == 1
    assert result["claims"][1]["route"] == "deterministic"
    assert result["summary"]["nli_invocations"] == 1


def test_group_state_is_isolated_across_concurrent_traces() -> None:
    nli = RecordingNLI()

    results = verify_traces_v2_1(
        [_two_ambiguous_claims(), _two_ambiguous_claims()],
        nli=nli,
        max_workers=2,
    )

    assert len(nli.calls) == 2
    assert [result["summary"]["nli_invocations"] for result in results] == [1, 1]
    assert all(
        len(
            {
                claim["nli"]["grouped_claim_nli"]["group_id"]
                for claim in result["claims"]
            }
        )
        == 1
        for result in results
    )


def test_group_provider_failure_abstains_once_and_does_not_retry_members() -> None:
    nli = FailingNLI()

    result = verify_trace_v2_1(_two_ambiguous_claims(), nli=nli)

    assert nli.calls == 1
    assert result["summary"]["nli_invocations"] == 1
    assert {claim["claim_verdict"] for claim in result["claims"]} == {
        "unverifiable"
    }


def test_claim_with_missing_material_fact_is_excluded_from_group() -> None:
    nli = SelectiveNLI()
    base = _two_ambiguous_claims()
    trace = replace(
        base,
        answer=(
            base.answer
            + " Funding is needed to reduce the current 30-day processing time."
        ),
        contexts=[
            replace(
                base.contexts[0],
                text=(
                    base.contexts[0].text
                    + " Congress should provide funding to process more applications."
                    + " The agency is committed to a 30-day completion window."
                ),
            )
        ],
    )

    result = verify_trace_v2_1(trace, nli=nli)

    assert len(nli.calls) == 2
    grouped = [
        claim
        for claim in result["claims"]
        if (claim.get("nli") or {}).get("grouped_claim_nli")
    ]
    assert len(grouped) == 2
    assert all(
        claim["nli"]["grouped_claim_nli"]["group_size"] == 2
        for claim in grouped
    )
    missing = result["claims"][2]
    assert missing["deterministic"]["signals"]["missing_facts"]
    assert "grouped_claim_nli" not in missing["nli"]
    assert missing["claim_verdict"] == "unsupported"
