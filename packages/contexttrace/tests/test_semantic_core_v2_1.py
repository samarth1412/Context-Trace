from __future__ import annotations

import json
from dataclasses import replace
from importlib import resources

import jsonschema

from contexttrace.verify.judges import JudgeVerdict
from contexttrace.verify.schema import RAGTrace, TraceContext
from contexttrace.verify.semantic_core_v2 import verify_trace_v2
from contexttrace.verify.semantic_core_v2_1 import (
    SELECTIVE_V2_1_PROFILE,
    verify_trace_v2_1,
    verify_traces_v2_1,
)


class EntailingNLI:
    def __init__(self) -> None:
        self.contexts = []

    def verify_claim(self, *, query, claim, contexts):
        del query, claim
        self.contexts.append(contexts)
        return JudgeVerdict(
            verdict="supported",
            confidence=0.95,
            reason="synthetic entailment",
            provider="test",
            model="test-nli",
            raw={
                "nli_label": "entailment",
                "nli_scores": {"entailment": 0.95},
                "context_id": contexts[0].id,
            },
        )


def _ambiguous_trace() -> RAGTrace:
    return RAGTrace(
        query="What replacements qualify?",
        answer="Defective items qualify for a replacement.",
        contexts=[
            TraceContext(
                id="returns",
                text="The returns policy covers defective products and available remedies.",
                metadata={"canonical": True, "current": True},
            )
        ],
    )


def _strong_trace() -> RAGTrace:
    return RAGTrace(
        query="What is the refund window?",
        answer="The refund window is 14 days.",
        contexts=[
            TraceContext(
                id="refunds",
                text="The refund window is 14 days.",
                metadata={"canonical": True, "current": True},
            )
        ],
    )


def _version_conflict_trace() -> RAGTrace:
    return RAGTrace(
        query="Which schema version is current?",
        answer="The schema version is v2.1.",
        contexts=[
            TraceContext(
                id="schema",
                text="The schema version is v1.8.",
                metadata={"canonical": True, "current": True},
            )
        ],
    )


def test_ambiguous_nli_only_support_still_cannot_become_green() -> None:
    legacy = verify_trace_v2(_ambiguous_trace(), nli=EntailingNLI())
    guarded = verify_trace_v2_1(_ambiguous_trace(), nli=EntailingNLI())

    assert legacy["claims"][0]["green"] is True
    claim = guarded["claims"][0]
    assert claim["claim_verdict"] == "supported"
    assert claim["route"] == "nli"
    assert claim["green"] is False
    assert claim["qualification_required"] is True
    assert claim["flags"]["nli_only_green_promotion_blocked"] is True
    assert claim["nli"]["nli_label"] == "entailment"
    assert claim["nli"]["learned_support_risk"]["eligible_for_intervention"] is False
    assert guarded["summary"]["green_claims"] == 0
    assert guarded["summary"]["overall_status"] == "warning"


def test_strong_deterministic_support_remains_green() -> None:
    result = verify_trace_v2_1(_strong_trace())

    assert result["claims"][0]["route"] == "deterministic"
    assert result["claims"][0]["green"] is True
    assert result["summary"]["overall_status"] == "green"
    span = result["claims"][0]["evidence_spans"][0]
    context = _strong_trace().contexts[0]
    assert span["role"] == "supporting"
    assert context.text[span["start_char"] : span["end_char"]] == span["text"]


def test_learned_intervention_is_preserved_in_output_provenance() -> None:
    result = verify_trace_v2_1(_version_conflict_trace(), nli=EntailingNLI())

    nli = result["claims"][0]["nli"]
    assert result["claims"][0]["claim_verdict"] == "unsupported"
    assert nli["provider"] == "contexttrace_learned_support_risk_gate"
    assert nli["learned_support_risk"]["intervened"] is True


def test_conflict_fallback_intervention_is_preserved_in_output_provenance() -> None:
    fallback_only = replace(
        SELECTIVE_V2_1_PROFILE,
        learned_support_risk_gate=False,
    )
    result = verify_trace_v2_1(
        _version_conflict_trace(),
        profile=fallback_only,
        nli=EntailingNLI(),
    )

    nli = result["claims"][0]["nli"]
    assert result["claims"][0]["claim_verdict"] == "contradicted"
    assert nli["provider"] == "contexttrace_observable_conflict_guard"
    assert nli["observable_conflict_guard"]["version"]


def test_guarded_profile_is_hash_identified_and_v2_schema_compatible() -> None:
    result = verify_trace_v2_1(_strong_trace())
    schema = json.loads(
        resources.files("contexttrace.schemas")
        .joinpath("claim-verification-v2.schema.json")
        .read_text(encoding="utf-8")
    )

    assert result["profile_id"] == "selective_v2_1_safety"
    assert result["profile_sha256"] == SELECTIVE_V2_1_PROFILE.sha256
    assert result["verification_profile"]["prevent_nli_only_green_promotion"] is True
    assert result["verification_profile"]["compose_same_source_nli_spans"] is True
    assert result["verification_profile"]["learned_support_risk_gate"] is True
    jsonschema.Draft202012Validator(schema).validate(result)


def test_nli_receives_query_cue_and_composed_same_source_spans() -> None:
    nli = EntailingNLI()
    trace = RAGTrace(
        query="What can Qdrant filters target?",
        answer=(
            "Qdrant filters can impose conditions on payload and point IDs during "
            "search or retrieval."
        ),
        contexts=[
            TraceContext(
                id="qdrant",
                text=(
                    "With Qdrant, you can set conditions when searching or retrieving "
                    "points. For example, you can impose conditions on both the payload "
                    "and the id of the point."
                ),
                metadata={"canonical": True, "current": True},
            )
        ],
    )

    result = verify_trace_v2_1(trace, nli=nli)

    assert result["claims"][0]["route"] == "nli"
    assert len(nli.contexts) == 1
    assert len(nli.contexts[0]) == 1
    premise = nli.contexts[0][0].text
    assert premise.startswith("Question: What can Qdrant filters target?\nEvidence: ")
    assert "searching or retrieving points" in premise
    assert "payload and the id of the point" in premise


def test_guarded_batch_preserves_input_order() -> None:
    results = verify_traces_v2_1(
        [_strong_trace(), _ambiguous_trace()],
        nli=EntailingNLI(),
        max_workers=2,
    )

    assert [result["input_identity"]["answer_sha256"] for result in results] == [
        verify_trace_v2_1(_strong_trace())["input_identity"]["answer_sha256"],
        verify_trace_v2_1(_ambiguous_trace(), nli=EntailingNLI())["input_identity"][
            "answer_sha256"
        ],
    ]
