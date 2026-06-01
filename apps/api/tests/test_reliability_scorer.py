from app.services.reliability_scorer import ReliabilityScorer


def test_reliability_scorer_rewards_supported_low_failure_trace():
    result = ReliabilityScorer().score(
        citation_support=0.95,
        unsupported_claim_rate=0.0,
        failure_rate=0.0,
        retrieval_quality=0.9,
        token_efficiency=1.0,
    )

    assert result.score >= 90
    assert result.grade == "A"
    assert result.components["citation_support"] == 95
    assert result.strengths
    assert result.recommendations


def test_reliability_scorer_explains_unsupported_failures():
    result = ReliabilityScorer().score(
        citation_support=0.2,
        unsupported_claim_rate=0.8,
        failure_rate=1.0,
    )

    assert result.score < 45
    assert result.grade == "F"
    assert any("Unsupported claims" in item for item in result.weaknesses)
    assert any("Constrain generation" in item for item in result.recommendations)


def test_reliability_scorer_skips_unavailable_optional_components():
    result = ReliabilityScorer().score(
        citation_support=0.8,
        unsupported_claim_rate=0.2,
        failure_rate=0.0,
    )

    assert "retrieval_quality" not in result.components
    assert 75 <= result.score < 90
    assert result.grade == "B"
