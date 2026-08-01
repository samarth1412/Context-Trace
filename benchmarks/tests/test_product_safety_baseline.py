from benchmarks.product_safety.run_baseline import run_baseline


def test_deterministic_product_safety_baseline_is_repeatable() -> None:
    result = run_baseline()

    assert result["evidence_class"] == (
        "development_only_not_independent_research_evidence"
    )
    assert result["runtime_id"] == "semantic_core_v2_deterministic"
    assert result["model_lock"] is None
    assert result["controlled"]["cases"] == 14
    assert result["controlled"]["exact_match_rate"] == 1.0
    assert result["public_holdout"]["cases"] == 150
    assert result["public_holdout"]["runtime_failures"] == 0
    assert "dangerous_safe_classification_rate" in result["public_holdout"]
