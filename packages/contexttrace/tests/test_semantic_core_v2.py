from __future__ import annotations

import json
from importlib import resources

import jsonschema

from contexttrace.contracts import (
    CLAIM_VERIFICATION_SCHEMA_VERSION,
    VERIFIER_VERSION as V1_VERIFIER_VERSION,
)
from contexttrace.verify.judges import JudgeVerdict
from contexttrace.verify.schema import RAGTrace, TraceCitation, TraceContext
from contexttrace.verify.semantic_core_v2 import (
    DETERMINISTIC_ONLY_V2_PROFILE,
    NO_SOURCE_CONDITION_V2_PROFILE,
    SELECTIVE_V2_PROFILE,
    verify_trace_v2,
)
from contexttrace.verify.semantic_core_v2.claims import unitize_claims


class FakeNLI:
    provider = "local_nli"
    model = "frozen-unit-nli"

    def __init__(self, label: str, confidence: float = 0.95) -> None:
        self.label = label
        self.confidence = confidence
        self.calls = 0

    def verify_claim(self, *, query, claim, contexts):
        del query, claim
        self.calls += 1
        assert contexts
        verdict = {
            "entailment": "supported",
            "contradiction": "contradicted",
            "neutral": "unsupported",
        }[self.label]
        return JudgeVerdict(
            verdict=verdict,
            confidence=self.confidence,
            reason="frozen synthetic NLI result",
            provider=self.provider,
            model=self.model,
            raw={
                "nli_label": self.label,
                "nli_scores": {self.label: self.confidence},
                "backend": "synthetic",
                "context_id": contexts[0].id,
            },
        )


def _trace(
    *,
    answer: str = "Customers may request a refund within 30 days.",
    context: str = "Customers may request a refund within 30 days.",
    context_metadata: dict | None = None,
    trace_metadata: dict | None = None,
    citations: list[TraceCitation] | None = None,
) -> RAGTrace:
    return RAGTrace(
        query="What is the refund period?",
        answer=answer,
        contexts=[
            TraceContext(
                id="policy/chunk-1",
                text=context,
                metadata=context_metadata or {"canonical": True, "current": True},
            )
        ],
        citations=citations or [],
        metadata=trace_metadata or {"case_id": "unit-case"},
    )


def test_v1_contract_identity_remains_unchanged() -> None:
    assert V1_VERIFIER_VERSION == "semantic_v1_calibrated"
    assert CLAIM_VERIFICATION_SCHEMA_VERSION == "1.0"


def test_claim_unitizer_preserves_exact_answer_offsets() -> None:
    answer = "First fact [policy/chunk-1]. Second fact; third fact."
    claims, limited = unitize_claims(answer)
    assert not limited
    assert len(claims) == 3
    for claim in claims:
        assert answer[claim.start_char : claim.end_char] == claim.text
    assert "[policy/chunk-1]" not in claims[0].verification_text


def test_strong_canonical_support_can_be_green_without_nli() -> None:
    result = verify_trace_v2(_trace())
    claim = result["claims"][0]
    assert claim["claim_verdict"] == "supported"
    assert claim["truth_status"] == "not_assessed"
    assert claim["source_condition"] == "current_canonical"
    assert claim["failure_label"] == "none"
    assert claim["primary_root_cause"] == "none"
    assert claim["route"] == "deterministic"
    assert claim["green"] is True
    assert result["summary"]["nli_invocations"] == 0


def test_weak_overlap_without_nli_abstains_instead_of_turning_green() -> None:
    result = verify_trace_v2(
        _trace(
            answer="The policy guarantees premium replacement shipping.",
            context="This policy discusses replacement products and shipping addresses.",
        ),
        profile=DETERMINISTIC_ONLY_V2_PROFILE,
    )
    claim = result["claims"][0]
    assert claim["claim_verdict"] == "unverifiable"
    assert claim["diagnostic_abstention"] is True
    assert claim["green"] is False
    assert claim["route"] in {"deterministic", "unresolved"}


def test_nli_can_resolve_ambiguous_deterministic_evidence() -> None:
    nli = FakeNLI("entailment")
    result = verify_trace_v2(
        _trace(
            answer="Defective items qualify for a replacement.",
            context="The returns policy covers defective products and available remedies.",
        ),
        nli=nli,
    )
    claim = result["claims"][0]
    assert nli.calls == 1
    assert claim["claim_verdict"] == "supported"
    assert claim["route"] == "nli"
    assert claim["diagnostic_abstention"] is False


def test_nli_disagreement_is_unverifiable_and_abstained() -> None:
    nli = FakeNLI("contradiction")
    result = verify_trace_v2(
        _trace(
            answer="The policy guarantees premium replacement shipping.",
            context="This policy discusses replacement products and shipping addresses.",
        ),
        nli=nli,
    )
    claim = result["claims"][0]
    assert claim["claim_verdict"] == "unverifiable"
    assert claim["route"] == "deterministic_nli_disagreement"
    assert claim["diagnostic_abstention"] is True
    assert claim["green"] is False


def test_supported_stale_source_is_not_hidden_inside_positive_verdict() -> None:
    result = verify_trace_v2(
        _trace(context_metadata={"canonical": True, "stale": True})
    )
    claim = result["claims"][0]
    assert claim["claim_verdict"] == "supported"
    assert claim["source_condition"] == "stale"
    assert claim["failure_label"] == "source_condition_failure"
    assert claim["primary_root_cause"] == "stale_or_superseded_source"
    assert claim["green"] is False


def test_supported_noncanonical_source_is_an_explicit_source_failure() -> None:
    result = verify_trace_v2(
        _trace(context_metadata={"canonical": False, "current": True})
    )
    claim = result["claims"][0]
    assert claim["source_condition"] == "current_noncanonical"
    assert claim["failure_label"] == "source_condition_failure"
    assert claim["primary_root_cause"] == "noncanonical_or_low_authority_source"


def test_source_condition_ablation_masks_source_features() -> None:
    result = verify_trace_v2(
        _trace(context_metadata={"canonical": True, "stale": True}),
        profile=NO_SOURCE_CONDITION_V2_PROFILE,
    )
    assert result["claims"][0]["source_condition"] == "unknown"


def test_citation_state_is_independent_from_support() -> None:
    answer = "Customers may request a refund within 30 days."
    result = verify_trace_v2(
        _trace(
            answer=answer,
            trace_metadata={"case_id": "citation", "citation_required": True},
        )
    )
    claim = result["claims"][0]
    assert claim["claim_verdict"] == "supported"
    assert claim["citation_state"] == "missing"
    assert claim["failure_label"] == "citation_mismatch"
    assert claim["green"] is False

    cited = verify_trace_v2(
        _trace(
            answer=answer,
            trace_metadata={"case_id": "citation", "citation_required": True},
            citations=[TraceCitation(claim=answer, source_id="policy/chunk-1")],
        )
    )
    assert cited["claims"][0]["citation_state"] == "correct"


def test_observable_retrieval_metadata_controls_root_attribution() -> None:
    result = verify_trace_v2(
        _trace(
            answer="The plan includes international concierge support.",
            context="Account owners can change their billing address.",
            trace_metadata={
                "case_id": "retrieval",
                "eligible_evidence_in_corpus": True,
            },
        ),
        profile=DETERMINISTIC_ONLY_V2_PROFILE,
    )
    assert result["claims"][0]["primary_root_cause"] == "retrieval_miss"


def test_prediction_validates_against_frozen_v2_schema() -> None:
    result = verify_trace_v2(_trace())
    schema = json.loads(
        resources.files("contexttrace.schemas")
        .joinpath("claim-verification-v2.schema.json")
        .read_text(encoding="utf-8")
    )
    jsonschema.Draft202012Validator(schema).validate(result)


def test_default_profile_identity_is_frozen() -> None:
    assert SELECTIVE_V2_PROFILE.id == "selective_v2"
    assert len(SELECTIVE_V2_PROFILE.sha256) == 64
