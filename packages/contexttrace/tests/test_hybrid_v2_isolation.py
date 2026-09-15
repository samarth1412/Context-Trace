from jsonschema import Draft202012Validator

from contexttrace import load_json_schema
from contexttrace.verify import verify_trace, verify_trace_hybrid_v2
from contexttrace.verify.schema import RAGTrace, TraceContext


def _metadata_free_trace() -> RAGTrace:
    return RAGTrace(
        query="Which API should integrations use?",
        answer="Integrations should use LegacyClient.",
        contexts=[
            TraceContext(
                id="old",
                text="Integration guide version 1. Integrations should use LegacyClient.",
            ),
            TraceContext(
                id="new",
                text=(
                    "Integration guide version 2. LegacyClient was retired; "
                    "integrations should use ModernClient instead."
                ),
            ),
        ],
    )


def test_default_verifier_preserves_frozen_v1_behavior_and_identity():
    result = verify_trace(_metadata_free_trace(), mode="semantic")
    claim = result["claims"][0]

    assert result["schema_version"] == "1.0"
    assert result["taxonomy_version"] == "1.0"
    assert result["verifier_version"] == "semantic_v1_calibrated"
    assert "diagnostic_reasoner_version" not in result
    assert "evidence_relevance" not in claim
    assert "query_requires_current_source" not in claim["source_assessment"]
    assert claim["source_status"] == "freshness_unknown"
    assert result["abstention"]["should_abstain"] is False


def test_hybrid_v2_is_opt_in_and_schema_valid():
    result = verify_trace_hybrid_v2(_metadata_free_trace())
    claim = result["claims"][0]
    schema = load_json_schema("ClaimVerificationHybridV2")

    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(result)
    assert result["schema_version"] == "2.0"
    assert result["taxonomy_version"] == "contexttrace-hybrid-v2.0"
    assert result["verifier_version"] == "hybrid_v2"
    assert result["diagnostic_reasoner_version"] == "evidence_chain_v2"
    assert result["experimental"] is True
    assert claim["source_status"] == "grounded_but_stale"
    assert claim["source_assessment"]["query_requires_current_source"] is True
    assert result["abstention"]["should_abstain"] is True
