from contexttrace.verify.facts import compare_facts
from contexttrace.verify.verdicts import is_contradicted


def test_date_mismatch_is_a_structured_conflict():
    result = compare_facts(
        "The release occurred on June 3, 2024.",
        "The release occurred on June 4, 2024.",
        mode="semantic",
    )

    assert any(fact.type == "date" for fact in result.conflicting_fact_details)


def test_numeric_and_negation_conflicts_are_detected():
    assert is_contradicted("The limit is 30 days.", "The limit is 14 days.", 0.9, mode="semantic")
    assert is_contradicted("The feature is enabled.", "The feature is not enabled.", 0.9, mode="semantic")


def test_explicit_opposed_predicates_are_detected():
    assert is_contradicted(
        "Atlas enables public access by default.",
        "Atlas disables public access by default.",
        0.77,
        mode="semantic",
    )
    assert not is_contradicted(
        "Atlas enables public access by default.",
        "Borealis disables guest checkout.",
        0.77,
        mode="semantic",
    )


def test_multi_passage_attribution_requires_support_from_every_named_passage():
    result = compare_facts(
        "Constipation is a symptom (passage 2 & 3).",
        "passage 2: The cause is unknown. passage 3: Symptoms include constipation.",
        mode="semantic",
    )

    assert any(fact.type == "attribution" for fact in result.conflicting_fact_details)


def test_explicit_denial_of_existence_rejects_lifecycle_false_premise():
    assert is_contradicted(
        "Orion discontinued its public token because adoption fell.",
        "Orion has never offered a public token.",
        0.36,
        mode="semantic",
    )


def test_low_overlap_negation_without_lifecycle_entailment_is_not_a_conflict():
    assert not is_contradicted(
        "Orion publishes an annual security report.",
        "Orion has never offered a public token.",
        0.36,
        mode="semantic",
    )
