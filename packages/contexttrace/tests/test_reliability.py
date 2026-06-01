from contexttrace.reliability import ReliabilityScorer


def test_reliability_scorer_returns_explainable_score():
    result = ReliabilityScorer().score(
        citation_support=0.9,
        unsupported_claim_rate=0.05,
        failure_rate=0.0,
        retrieval_quality=0.85,
        token_efficiency=0.9,
    )

    assert result.score >= 90
    assert result.grade == "A"
    assert result.components["unsupported_claim_rate"] == 95
    assert result.strengths
    assert result.recommendations


def test_reliability_scorer_scores_trace_from_evaluation_payload():
    trace = {
        "chunks": [{"chunk_id": "chunk_1", "relevance_score": 0.4, "selected": True}],
        "answer": {"usage": {"total_tokens": 13000}},
        "evaluation": {
            "scores": {"citation_support": 0.2, "unsupported_claim_rate": 1.0},
            "failure": {"failure_type": "unsupported_answer"},
            "citation_checks": [],
        },
    }

    result = ReliabilityScorer().score_trace(trace)

    assert result.score < 45
    assert result.grade == "F"
    assert "retrieval_quality" in result.components
    assert any("Token usage is high" in item for item in result.weaknesses)
