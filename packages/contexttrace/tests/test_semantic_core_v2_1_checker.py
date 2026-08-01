from __future__ import annotations

import pytest

from contexttrace.verify.judges import JudgeVerdict
from contexttrace.verify.schema import TraceContext
from contexttrace.verify.semantic_core_v2_1 import (
    OBSERVABLE_CONFLICT_GUARD_VERSION,
    ObservableConflictGuard,
    observable_conflicts,
)


class AlwaysEntails:
    provider = "synthetic_nli"
    model = "synthetic-model"

    def verify_claim(self, *, query, claim, contexts):
        del query, claim
        return JudgeVerdict(
            verdict="supported",
            confidence=0.96,
            reason="synthetic entailment",
            provider=self.provider,
            model=self.model,
            raw={
                "nli_label": "entailment",
                "context_id": contexts[0].id,
            },
        )


@pytest.mark.parametrize(
    ("claim", "evidence", "category"),
    [
        (
            "The retention period is 90 days.",
            "The retention period is 30 days.",
            "numeric",
        ),
        (
            "The policy takes effect on October 1, 2026.",
            "The policy takes effect on July 1, 2026.",
            "date",
        ),
        (
            "Clients must use API v3.0.",
            "Clients must use API v2.4.",
            "version",
        ),
        (
            "Audit logging is not enabled by default.",
            "Audit logging is enabled by default.",
            "negation",
        ),
        (
            "Service B calls Service A.",
            "Service A calls Service B.",
            "reversed_relation",
        ),
        (
            "The SDK supports YAML.",
            "The SDK supports JSON.",
            "identifier_substitution",
        ),
        (
            "The replacement endpoint is /v1/search.",
            "The replacement endpoint is /v2/search.",
            "path_substitution",
        ),
        (
            "The endpoint is deprecated.",
            "The endpoint is active.",
            "status",
        ),
        (
            "Refunds are available within 30 days.",
            "Refunds are available within 30 days if the item is unopened.",
            "condition_omission",
        ),
        (
            "Encryption is optional.",
            "Encryption is optional for local development.",
            "scope_omission",
        ),
        (
            "Requests of 10 MB are accepted.",
            "Requests under 10 MB are accepted.",
            "numeric_boundary",
        ),
        (
            "The endpoint was deprecated in v2.",
            "The endpoint was deprecated after v2.",
            "temporal_boundary",
        ),
    ],
)
def test_observable_conflicts_cover_hard_negative_categories(
    claim: str,
    evidence: str,
    category: str,
) -> None:
    conflicts = observable_conflicts(claim, evidence)

    assert category in {conflict.category for conflict in conflicts}


def test_guard_blocks_false_entailment_and_preserves_base_provenance() -> None:
    guard = ObservableConflictGuard(AlwaysEntails())

    result = guard.verify_claim(
        query="How long is retention?",
        claim="The retention period is 90 days.",
        contexts=[TraceContext(id="policy", text="The retention period is 30 days.")],
    )

    assert result.verdict == "contradicted"
    assert result.confidence == 0.96
    assert result.provider == "contexttrace_observable_conflict_guard"
    assert result.model == "synthetic-model"
    assert result.raw["base_provider"] == "synthetic_nli"
    assert result.raw["nli_label"] == "contradiction"
    assert (
        result.raw["observable_conflict_guard"]["version"]
        == OBSERVABLE_CONFLICT_GUARD_VERSION
    )


def test_guard_reads_only_evidence_from_query_augmented_premise() -> None:
    guard = ObservableConflictGuard(AlwaysEntails())

    result = guard.verify_claim(
        query="Does the question mention 90 days?",
        claim="The retention period is 90 days.",
        contexts=[
            TraceContext(
                id="policy",
                text=(
                    "Question: Does the question mention 90 days?\n"
                    "Evidence: The retention period is 30 days."
                ),
            )
        ],
    )

    assert result.verdict == "contradicted"


def test_guard_preserves_supported_verdict_when_evidence_has_no_conflict() -> None:
    guard = ObservableConflictGuard(AlwaysEntails())

    result = guard.verify_claim(
        query="How long is retention?",
        claim="The retention period is 30 days.",
        contexts=[TraceContext(id="policy", text="The retention period is 30 days.")],
    )

    assert result.verdict == "supported"
    assert result.provider == "synthetic_nli"


def test_guard_does_not_guess_selected_evidence_with_multiple_contexts() -> None:
    class EntailsWithoutContextId(AlwaysEntails):
        def verify_claim(self, *, query, claim, contexts):
            verdict = super().verify_claim(
                query=query,
                claim=claim,
                contexts=contexts,
            )
            return JudgeVerdict(
                verdict=verdict.verdict,
                confidence=verdict.confidence,
                reason=verdict.reason,
                provider=verdict.provider,
                model=verdict.model,
                raw={"nli_label": "entailment"},
            )

    result = ObservableConflictGuard(EntailsWithoutContextId()).verify_claim(
        query="How long is retention?",
        claim="The retention period is 90 days.",
        contexts=[
            TraceContext(id="a", text="The retention period is 30 days."),
            TraceContext(id="b", text="A different policy applies."),
        ],
    )

    assert result.verdict == "supported"
