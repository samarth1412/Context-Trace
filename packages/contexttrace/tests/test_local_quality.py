from __future__ import annotations

import socket

import pytest

from contexttrace.verify.judges import JudgeVerdict
from contexttrace.verify.local_quality import (
    LocalQualityError,
    LocalQualityJudge,
    LocalQualityProfile,
    decompose_material_claim,
    verify_trace_local_quality,
)
from contexttrace.verify.schema import RAGTrace, TraceContext


class FakeNLI:
    provider = "local_nli"
    model = "fake-local-nli"

    def verify_claim(self, *, query, claim, contexts):
        del query
        premise = contexts[0].text.casefold()
        hypothesis = claim.casefold()
        if "finance director" in hypothesis:
            label, confidence = "neutral", 0.98
        elif "free shipping" in hypothesis:
            label, confidence = "neutral", 0.97
        elif "not enabled" in premise and "enabled" in hypothesis:
            label, confidence = "contradiction", 0.96
        else:
            label, confidence = "entailment", 0.95
        verdict = {
            "entailment": "supported",
            "contradiction": "contradicted",
            "neutral": "unsupported",
        }[label]
        return JudgeVerdict(
            verdict=verdict,
            confidence=confidence,
            reason="fake local result",
            provider=self.provider,
            model=self.model,
            raw={
                "nli_label": label,
                "nli_scores": {label: confidence},
                "backend": "fake_local",
            },
        )


def _judge(claim: str, evidence: str, *, nli=None):
    return LocalQualityJudge(nli=nli).verify_claim(
        query="What does the evidence establish?",
        claim=claim,
        contexts=[TraceContext(id="c1", text=evidence)],
    )


def test_compound_claim_decomposition_preserves_material_additions() -> None:
    assert decompose_material_claim(
        "Customers may request a refund within 30 days and receive free shipping."
    ) == [
        "Customers may request a refund within 30 days.",
        "Customers may receive free shipping.",
    ]
    assert decompose_material_claim(
        "Travel reimbursement requires itemized receipts and approval from both a manager and the finance director."
    ) == [
        "Travel reimbursement requires itemized receipts.",
        "Travel reimbursement requires approval from a manager.",
        "Travel reimbursement requires approval from the finance director.",
    ]


def test_nli_atom_aggregation_recovers_partial_support() -> None:
    verdict = _judge(
        "Customers may request a refund within 30 days and receive free shipping.",
        "Customers may request a refund within 30 days. Return-shipping charges are not described.",
        nli=FakeNLI(),
    )
    assert verdict.verdict == "partially_supported"
    assert len(verdict.raw["atomic_claims"]) == 2
    assert verdict.raw["automatic_supported"] is False


def test_number_words_are_compared_without_hard_coding_a_case() -> None:
    verdict = _judge(
        "Employees may work remotely three days per week.",
        "Employees may work remotely up to two days per week.",
    )
    assert verdict.verdict == "contradicted"
    assert verdict.raw["reason_code"] == "one_or_more_atomic_claims_contradicted"


def test_unrelated_numbers_do_not_create_a_numeric_contradiction() -> None:
    verdict = _judge(
        "The archive retains reports for three years.",
        "The dashboard has two panels. Reports are available in the archive.",
    )
    assert verdict.verdict != "contradicted"


def test_relation_numbers_without_trailing_units_are_compared() -> None:
    verdict = _judge(
        "The airport train departs from platform 4.",
        "The airport train departs from platform 7.",
    )
    assert verdict.verdict == "contradicted"


def test_explicit_absence_is_unsupported_not_contradicted() -> None:
    verdict = _judge(
        "Customer data is backed up every six hours.",
        "Customer data is encrypted. The overview does not specify a backup schedule.",
    )
    assert verdict.verdict == "unsupported"
    assert verdict.raw["atomic_claims"][0]["reason_code"] == "evidence_explicitly_omits_asserted_detail"


def test_qualified_evidence_for_universal_claim_requires_review() -> None:
    verdict = _judge(
        "Every enterprise plan includes priority support.",
        "Priority support may be available for some enterprise plans, subject to contract.",
    )
    assert verdict.verdict == "unverifiable"
    assert verdict.raw["review_required"] is True


def test_approximate_evidence_does_not_support_an_exact_claim() -> None:
    verdict = _judge(
        "The workshop capacity is exactly 100 attendees.",
        "The workshop is planned for approximately 100 attendees; the room is pending.",
    )
    assert verdict.verdict == "unverifiable"
    assert verdict.raw["review_required"] is True


def test_explicit_not_all_is_a_real_universal_contradiction() -> None:
    verdict = _judge(
        "All paid accounts include audit export.",
        "Not all paid accounts include audit export; only regulated plans do.",
    )
    assert verdict.verdict == "contradicted"


def test_conflicting_selected_sources_fail_closed() -> None:
    judge = LocalQualityJudge()
    verdict = judge.verify_claim(
        query="Is remote access enabled?",
        claim="Remote access is enabled.",
        contexts=[
            TraceContext(id="old", text="Remote access is enabled."),
            TraceContext(id="new", text="Remote access is not enabled."),
        ],
    )
    assert verdict.verdict == "unverifiable"
    assert verdict.raw["review_required"] is True
    assert verdict.raw["automatic_supported"] is False


def test_absence_statement_is_not_treated_as_a_conflicting_source() -> None:
    verdict = _judge(
        "A completed inspection requires a photograph and a supervisor signature.",
        "A completed inspection requires a photograph. "
        "The manual does not mention a supervisor signature.",
    )
    assert verdict.verdict == "partially_supported"


def test_no_later_than_is_a_bound_not_a_negation() -> None:
    verdict = _judge(
        "Domestic transfers settle within one business day.",
        "A domestic transfer settles no later than one business day after submission.",
        nli=FakeNLI(),
    )
    assert verdict.verdict == "supported"


def test_required_nli_never_silently_falls_back() -> None:
    with pytest.raises(LocalQualityError, match="will not download"):
        LocalQualityJudge(profile=LocalQualityProfile(require_nli=True))


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"max_evidence_spans": 0}, "max_evidence_spans"),
        ({"review_threshold": 1.01}, "review_threshold"),
        ({"nli_entailment_threshold": -0.01}, "nli_entailment_threshold"),
    ],
)
def test_profile_rejects_invalid_limits(kwargs, message) -> None:
    with pytest.raises(ValueError, match=message):
        LocalQualityProfile(**kwargs)


def test_trace_report_preserves_backend_evidence_and_separate_truth_status() -> None:
    result = verify_trace_local_quality(
        RAGTrace(
            query="What is enabled?",
            answer="Remote access is enabled.",
            contexts=[
                TraceContext(
                    id="policy",
                    text="Remote access is enabled.",
                    metadata={"canonical": True, "current": True},
                )
            ],
        )
    )
    claim = result["claims"][0]
    assert result["experimental"] is True
    assert result["local_only"] is True
    assert claim["backend"]["remote_inference"] is False
    assert claim["truth_status"] == "not_assessed"
    assert claim["evidence_spans"][0]["context_id"] == "policy"
    assert claim["source_condition"]["condition"] == "current_canonical"


def test_deterministic_local_path_makes_no_network_connection(monkeypatch) -> None:
    def blocked(*args, **kwargs):
        raise AssertionError("network access attempted")

    monkeypatch.setattr(socket.socket, "connect", blocked)
    verdict = _judge("The service is enabled.", "The service is enabled.")
    assert verdict.verdict == "supported"


def test_errors_and_uncertainty_never_become_automatic_support() -> None:
    verdict = _judge(
        "Every account receives expedited support.",
        "Expedited support may be available for eligible accounts.",
    )
    assert verdict.verdict == "unverifiable"
    assert verdict.raw["automatic_supported"] is False
