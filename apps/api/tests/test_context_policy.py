from app.playground.policy import (
    POLICY_ABSTAIN_LOW_CONFIDENCE,
    POLICY_COMPRESSED_CONTEXT,
    POLICY_DENSE_TOP_K,
    POLICY_HYBRID,
    POLICY_HYBRID_RERANK,
    QUERY_AMBIGUOUS,
    QUERY_BROAD_SUMMARY,
    QUERY_FACT_SPECIFIC,
    QUERY_MULTI_HOP,
    QUERY_UNANSWERABLE_RISK,
    PolicySelector,
    QueryClassification,
    QueryClassifier,
)


def test_query_classifier_labels_core_query_shapes():
    classifier = QueryClassifier()

    assert classifier.classify("What is the refund window?").query_class == QUERY_FACT_SPECIFIC
    assert classifier.classify("Summarize the refund policy").query_class == QUERY_BROAD_SUMMARY
    assert (
        classifier.classify("Compare refunds and exchanges for final-sale items").query_class
        == QUERY_MULTI_HOP
    )
    assert classifier.classify("This policy?").query_class == QUERY_AMBIGUOUS
    assert classifier.classify("What is the current refund rate today?").query_class == QUERY_UNANSWERABLE_RISK


def test_policy_selector_uses_dense_for_specific_high_confidence():
    decision = PolicySelector().select(
        classification=_classification(QUERY_FACT_SPECIFIC),
        retrieval_confidence=0.8,
    )

    assert decision.selected_policy == POLICY_DENSE_TOP_K


def test_policy_selector_uses_hybrid_for_specific_moderate_confidence():
    decision = PolicySelector().select(
        classification=_classification(QUERY_FACT_SPECIFIC),
        retrieval_confidence=0.3,
    )

    assert decision.selected_policy == POLICY_HYBRID


def test_policy_selector_uses_rerank_for_multi_hop():
    decision = PolicySelector().select(
        classification=_classification(QUERY_MULTI_HOP),
        retrieval_confidence=0.4,
    )

    assert decision.selected_policy == POLICY_HYBRID_RERANK


def test_policy_selector_uses_compressed_context_for_broad_summary():
    decision = PolicySelector().select(
        classification=_classification(QUERY_BROAD_SUMMARY),
        retrieval_confidence=0.4,
    )

    assert decision.selected_policy == POLICY_COMPRESSED_CONTEXT
    assert decision.token_budget > 0


def test_policy_selector_abstains_for_ambiguous_low_confidence():
    decision = PolicySelector().select(
        classification=_classification(QUERY_AMBIGUOUS),
        retrieval_confidence=0.25,
    )

    assert decision.selected_policy == POLICY_ABSTAIN_LOW_CONFIDENCE
    assert decision.retrieval_strategy is None


def test_policy_selector_abstains_for_unanswerable_low_confidence():
    decision = PolicySelector().select(
        classification=_classification(QUERY_UNANSWERABLE_RISK),
        retrieval_confidence=0.5,
    )

    assert decision.selected_policy == POLICY_ABSTAIN_LOW_CONFIDENCE


def _classification(query_class):
    return QueryClassification(query_class=query_class, reason="test")
