"""Versioned safety policy layered over the frozen semantic_core_v2 candidate."""

from __future__ import annotations

from dataclasses import dataclass

from contexttrace.verify.semantic_core_v2.profile import V2Profile


@dataclass(frozen=True)
class V21Profile(V2Profile):
    """A schema-compatible profile whose hash includes the promotion policy."""

    id: str = "selective_v2_1_safety"
    prevent_nli_only_green_promotion: bool = True
    compose_same_source_nli_spans: bool = True
    include_query_cue_for_nli: bool = True
    atomic_claim_unitization: bool = True
    observable_conflict_guard: bool = True
    learned_support_risk_gate: bool = True
    relational_source_condition_reasoning: bool = True
    hierarchical_evidence_attribution: bool = True
    grouped_claim_nli: bool = True
    evidence_span_min_score: float = 0.18
    max_attribution_spans: int = 3
    max_composed_nli_chars: int = 2400
    max_nli_query_chars: int = 512
    max_grouped_nli_claims: int = 3
    max_grouped_nli_spans_per_claim: int = 2
    grouped_nli_entailment_confidence: float = 0.95

    def __post_init__(self) -> None:
        super().__post_init__()
        if not 256 <= self.max_composed_nli_chars <= 8192:
            raise ValueError("max_composed_nli_chars must be between 256 and 8192.")
        if not 0 <= self.max_nli_query_chars <= 1024:
            raise ValueError("max_nli_query_chars must be between 0 and 1024.")
        if not 0.0 <= self.evidence_span_min_score <= 1.0:
            raise ValueError("evidence_span_min_score must be between zero and one.")
        if not 1 <= self.max_attribution_spans <= 3:
            raise ValueError("max_attribution_spans must be between 1 and 3.")
        if not 2 <= self.max_grouped_nli_claims <= 4:
            raise ValueError("max_grouped_nli_claims must be between 2 and 4.")
        if not 1 <= self.max_grouped_nli_spans_per_claim <= 3:
            raise ValueError(
                "max_grouped_nli_spans_per_claim must be between 1 and 3."
            )
        if not 0.0 <= self.grouped_nli_entailment_confidence <= 1.0:
            raise ValueError(
                "grouped_nli_entailment_confidence must be between zero and one."
            )


SELECTIVE_V2_1_PROFILE = V21Profile()
DETERMINISTIC_ONLY_V2_1_PROFILE = V21Profile(
    id="deterministic_only_v2_1_safety",
    enable_nli=False,
)
