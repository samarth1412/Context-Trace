from contexttrace.verify.runner import FULL_VERIFICATION_PROFILE, VerificationProfile
from contexttrace.verify.runner import verify_trace
from contexttrace.verify.schema import RAGTrace, TraceCitation, TraceContext


def _supported_trace() -> RAGTrace:
    return RAGTrace(
        query="What is the refund policy?",
        answer="Refunds are allowed within 30 days.",
        contexts=[
            TraceContext(
                id="policy",
                text="Customers may request refunds within 30 days of purchase.",
                metadata={"source_timestamp": "2026-06-01"},
            )
        ],
        citations=[
            TraceCitation(
                claim="Refunds are allowed within 30 days.",
                source_id="policy",
            )
        ],
    )


def test_default_profile_matches_explicit_full_profile():
    trace = _supported_trace()

    assert verify_trace(trace, mode="semantic") == verify_trace(
        trace,
        mode="semantic",
        profile=FULL_VERIFICATION_PROFILE,
    )


def test_disabled_modules_do_not_emit_ablation_outputs():
    profile = VerificationProfile(
        citation_alignment=False,
        abstention_logic=False,
        source_assessment=False,
        root_cause_inference=False,
        evidence_span_localization=False,
    )

    result = verify_trace(_supported_trace(), mode="semantic", profile=profile)
    claim = result["claims"][0]

    assert claim["verdict"] == "supported"
    assert claim["evidence_span"] is None
    assert claim["supporting_spans"] == []
    assert claim["citation_status"] == "claim_has_no_citation"
    assert claim["source_status"] == "freshness_unknown"
    assert claim["source_assessment"] == {}
    assert "root_cause" not in claim
    assert result["abstention"]["should_abstain"] is False
    assert result["summary"]["root_causes"] == {}
    assert result["summary"]["primary_root_cause"] == ""
    assert result["verification_profile"] == profile.to_dict()
