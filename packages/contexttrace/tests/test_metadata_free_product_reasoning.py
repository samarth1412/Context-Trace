from contexttrace.verify.hybrid_v2 import verify_trace_hybrid_v2 as verify_trace
from contexttrace.verify.schema import RAGTrace, TraceCitation, TraceContext


def _verify(query: str, answer: str, *contexts: str):
    return verify_trace(
        RAGTrace(
            query=query,
            answer=answer,
            contexts=[
                TraceContext(id="document-%s" % index, text=text)
                for index, text in enumerate(contexts, start=1)
            ],
        ),
        mode="semantic",
    )


def test_content_versions_identify_metadata_free_supersession():
    result = _verify(
        "Which API should integrations use?",
        "Integrations should use LegacyClient.",
        "Integration guide version 1. Integrations should use LegacyClient.",
        "Integration guide version 2. LegacyClient was retired; integrations should use ModernClient instead.",
    )

    claim = result["claims"][0]
    assessment = claim["source_assessment"]
    assert claim["verdict"] == "supported"
    assert claim["source_status"] == "grounded_but_stale"
    assert result["abstention"]["should_abstain"] is True
    assert assessment["query_requires_current_source"] is True
    assert assessment["newer_related_sources"][0]["context_id"] == "document-2"
    assert assessment["best_source"]["version_origin"] == "content"
    assert assessment["newer_related_sources"][0]["version_origin"] == "content"
    assert "content:version" in assessment["newer_related_sources"][0]["relation_basis"]
    assert "context_text" not in assessment["best_source"]
    assert "timestamp_sort" not in assessment["best_source"]
    assert "version_sort" not in assessment["best_source"]
    assert "claim_conflict" not in assessment["best_source"]


def test_lifecycle_language_identifies_supersession_without_dates_or_versions():
    result = _verify(
        "How should applications create a client?",
        "Applications should construct ClassicClient.",
        "Applications should construct ClassicClient.",
        "ClassicClient is deprecated and replaced by NextClient. Applications should construct NextClient instead.",
    )

    claim = result["claims"][0]
    newer = claim["source_assessment"]["newer_related_sources"][0]
    assert claim["source_status"] == "grounded_but_stale"
    assert newer["lifecycle_signal"] == "replacement"
    assert "content:lifecycle_replacement" in newer["relation_basis"]
    assert result["abstention"]["should_abstain"] is True


def test_replacement_guidance_does_not_penalize_claim_using_replacement():
    result = _verify(
        "Which client should applications use?",
        "Applications should construct NextClient.",
        "ClassicClient is deprecated and replaced by NextClient. Applications should construct NextClient instead.",
    )

    claim = result["claims"][0]
    assert claim["verdict"] == "supported"
    assert claim["source_status"] == "freshness_unknown"
    assert claim["source_assessment"]["has_conflict"] is False
    assert result["abstention"]["should_abstain"] is False


def test_explicit_historical_version_is_not_treated_as_unsafe_current_guidance():
    result = _verify(
        "What did integration guide version 1 recommend?",
        "Integrations should use LegacyClient.",
        "Integration guide version 1. Integrations should use LegacyClient.",
        "Integration guide version 2. LegacyClient was retired; integrations should use ModernClient instead.",
    )

    claim = result["claims"][0]
    assert claim["source_status"] == "historical_source"
    assert claim["source_assessment"]["query_temporal_scope"] == "historical"
    assert result["abstention"]["should_abstain"] is False


def test_metadata_free_disagreement_without_chronology_stays_conflicted():
    result = _verify(
        "Does Atlas enable remote access by default?",
        "Atlas enables remote access by default.",
        "Atlas enables remote access by default.",
        "Atlas disables remote access by default.",
    )

    claim = result["claims"][0]
    assert claim["source_status"] == "grounded_but_conflicted"
    assert claim["source_assessment"]["has_conflict"] is True
    assert claim["source_assessment"]["has_newer_related_source"] is False
    assert result["abstention"]["should_abstain"] is True


def test_unrelated_higher_version_does_not_make_supporting_source_stale():
    result = _verify(
        "What does Widget export?",
        "Widget exports telemetry.",
        "Widget exports telemetry.",
        "Billing handbook version 9. Invoices are retained for seven years.",
    )

    claim = result["claims"][0]
    assert claim["verdict"] == "supported"
    assert claim["source_status"] == "freshness_unknown"
    assert claim["source_assessment"]["newer_related_sources"] == []


def test_content_dates_identify_newer_conflicting_guidance():
    result = _verify(
        "What retention period should operators configure?",
        "Operators should configure 30 days of retention.",
        "Published 2024-01-10. Operators should configure 30 days of retention.",
        "Updated 2026-05-20. Operators should configure 14 days of retention.",
    )

    claim = result["claims"][0]
    newer = claim["source_assessment"]["newer_related_sources"][0]
    assert claim["source_status"] == "grounded_but_stale"
    assert newer["timestamp_origin"] == "content"
    assert "content:timestamp" in newer["relation_basis"]


def test_query_relevant_missing_fact_is_unverifiable_without_metadata():
    result = _verify(
        "What delivery guarantee does Widget export provide?",
        "Widget export guarantees delivery within five seconds.",
        "Widget export sends telemetry to configured consumers.",
    )

    claim = result["claims"][0]
    assert claim["verdict"] == "unverifiable"
    assert claim["evidence_relevance"]["basis"] == "query_context_overlap"
    assert claim["evidence_relevance"]["context_id"] == "document-1"
    assert claim["root_cause"]["label"] == "insufficient_context"


def test_irrelevant_context_remains_unsupported_without_metadata():
    result = _verify(
        "What delivery guarantee does Widget export provide?",
        "Widget export guarantees delivery within five seconds.",
        "The staff cafeteria serves lunch on weekdays.",
    )

    claim = result["claims"][0]
    assert claim["verdict"] == "unsupported"
    assert claim["evidence_relevance"]["basis"] == "none"


def test_query_relevant_context_does_not_turn_answer_overreach_into_unverifiable():
    result = _verify(
        "What does Nimbus postfiltering do?",
        "It encrypts every vector in an external service.",
        "Nimbus postfiltering applies metadata filters after vector search.",
    )

    claim = result["claims"][0]
    assert claim["verdict"] == "unsupported"


def test_elliptical_answer_to_relevant_query_is_unverifiable():
    result = _verify(
        "Which database does the service use for sessions?",
        "It uses Redis.",
        "The service session guide describes expiry and rotation but does not name a storage engine.",
    )

    claim = result["claims"][0]
    assert claim["verdict"] == "unverifiable"
    assert claim["evidence_relevance"]["basis"] == "query_context_overlap"


def test_unrelated_answer_to_relevant_query_remains_unsupported():
    result = _verify(
        "Which database does the service use for sessions?",
        "Paris is the capital of France.",
        "The service session guide describes expiry and rotation but does not name a storage engine.",
    )

    assert result["claims"][0]["verdict"] == "unsupported"


def test_non_supporting_citation_to_query_relevant_source_is_unverifiable():
    result = verify_trace(
        RAGTrace(
            query="What is the documented service-level agreement?",
            answer="Availability is 99.99%.",
            contexts=[
                TraceContext(
                    id="service-guide",
                    text="The service guide lists support contacts but does not publish a service-level agreement.",
                )
            ],
            citations=[
                TraceCitation(claim="Availability is 99.99%.", source_id="service-guide")
            ],
        ),
        mode="semantic",
    )

    claim = result["claims"][0]
    assert claim["verdict"] == "unverifiable"
    assert claim["citation_status"] == "cited_source_does_not_support_claim"
