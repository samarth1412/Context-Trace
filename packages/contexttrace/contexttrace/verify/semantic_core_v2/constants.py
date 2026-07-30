"""Frozen semantic_core_v2 identities and taxonomies."""

from __future__ import annotations


VERIFIER_VERSION = "semantic_core_v2"
SCHEMA_VERSION = "2.0"
TAXONOMY_VERSION = "contexttrace-diagnosis-v2.0"
PROFILE_VERSION = "selective-v2.0.0"
GENERIC_RULEPACK_VERSION = "generic-v2.0.0"
SOURCE_RULEPACK_VERSION = "source-condition-v2.0.0"
CLAIM_UNITIZER_VERSION = "claim-unitizer-v2.0.0"

CLAIM_VERDICTS = (
    "supported",
    "partially_supported",
    "contradicted",
    "unsupported",
    "unverifiable",
)
FAILURE_LABELS = (
    "none",
    "retrieval_miss",
    "context_selection_error",
    "citation_mismatch",
    "answer_overreach",
    "contradiction",
    "insufficient_evidence",
    "should_have_abstained",
    "source_condition_failure",
)
ROOT_CAUSES = (
    "none",
    "retrieval_miss",
    "reranking_failure",
    "chunking_issue",
    "corpus_gap",
    "stale_or_superseded_source",
    "noncanonical_or_low_authority_source",
    "citation_mismatch",
    "answer_overreach",
    "insufficient_selected_context",
    "conflicting_contexts",
    "failure_to_abstain",
    "not_observable",
)
CITATION_STATES = (
    "not_applicable",
    "correct",
    "partial",
    "wrong_source",
    "missing",
    "malformed",
)
SOURCE_CONDITIONS = (
    "current_canonical",
    "current_noncanonical",
    "stale",
    "superseded",
    "low_authority",
    "conflicting_authorities",
    "unknown",
)
ABSTENTION_REQUIREMENTS = (
    "must_answer",
    "may_answer_with_qualification",
    "must_abstain",
)
ROUTES = (
    "deterministic",
    "nli",
    "deterministic_nli_agreement",
    "deterministic_nli_disagreement",
    "unresolved",
)

NLI_MODEL_ID = "cross-encoder/nli-deberta-v3-small"
NLI_MODEL_REVISION = "fa2804872c3b4bd748f38c0185cc85775361e735"
NLI_ARTIFACT_MANIFEST_SHA256 = (
    "330f0fd77aad129877e1a1a90d4a77e6f093ee238b97d535202816a116b9c9f3"
)
NLI_NUMERICAL_PRECISION = "float32"
NLI_MAX_LENGTH = 512

CAPABILITIES = {
    "claim_unitization": True,
    "claim_verdict": True,
    "failure_label": True,
    "primary_observable_root_cause": True,
    "citation_state": True,
    "source_condition": True,
    "abstention": True,
    "evidence_span_localization": True,
    "selective_nli": True,
    "bounded_batch_concurrency": True,
    "independent_truth_certification": False,
}

LIMITATIONS = (
    "Support is assessed against supplied evidence; independent real-world truth is not certified.",
    "Source-condition diagnoses require explicit source metadata or observable conflicting sources.",
    "Retrieval, reranking, chunking, and corpus causes are emitted only when trace metadata exposes the required stage evidence.",
    "The local NLI model is an English-language auxiliary signal and may fail on domain-specific, multilingual, or long-range reasoning.",
    "Low-confidence or route-disagreement cases abstain instead of receiving a forced positive diagnosis.",
)
