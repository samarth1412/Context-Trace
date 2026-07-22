from contexttrace.verify.semantic_normalization import extract_normalized_dates, normalize_semantic_text


def test_normalizes_entities_numbers_comparatives_and_negation():
    normalized = normalize_semantic_text("The U.S. can't admit fewer than five entities.")

    assert "united states" in normalized
    assert "not" in normalized
    assert "less than 5" in normalized


def test_normalizes_written_date_without_changing_invalid_date():
    assert extract_normalized_dates("Released June 3, 2024") == {"2024-06-03"}
    assert extract_normalized_dates("Released February 31, 2024") == set()
