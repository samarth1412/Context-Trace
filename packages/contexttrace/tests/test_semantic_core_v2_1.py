from __future__ import annotations

import json
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
    def verify_claim(self, *, query, claim, contexts):
        del query, claim
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


def test_nli_only_support_cannot_be_promoted_to_green() -> None:
    legacy = verify_trace_v2(_ambiguous_trace(), nli=EntailingNLI())
    guarded = verify_trace_v2_1(_ambiguous_trace(), nli=EntailingNLI())

    assert legacy["claims"][0]["green"] is True
    claim = guarded["claims"][0]
    assert claim["claim_verdict"] == "supported"
    assert claim["route"] == "nli"
    assert claim["green"] is False
    assert claim["qualification_required"] is True
    assert claim["flags"]["nli_only_green_promotion_blocked"] is True
    assert guarded["summary"]["green_claims"] == 0
    assert guarded["summary"]["overall_status"] == "warning"


def test_strong_deterministic_support_remains_green() -> None:
    result = verify_trace_v2_1(_strong_trace())

    assert result["claims"][0]["route"] == "deterministic"
    assert result["claims"][0]["green"] is True
    assert result["summary"]["overall_status"] == "green"


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
    jsonschema.Draft202012Validator(schema).validate(result)


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
