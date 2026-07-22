from contexttrace.verify.claims import extract_claims


def test_extracts_numbered_list_as_atomic_claims():
    claims = extract_claims("1. Alpha launched in 2024. 2. Beta launched in 2025.")

    assert [claim.text for claim in claims] == [
        "Alpha launched in 2024.",
        "Beta launched in 2025.",
    ]


def test_splits_independent_semicolon_clauses_without_splitting_entity_list():
    claims = extract_claims("Alpha is current; Beta is deprecated.")

    assert [claim.text for claim in claims] == ["Alpha is current.", "Beta is deprecated."]
    assert len(extract_claims("The supported regions are France, Spain, and Italy.")) == 1
