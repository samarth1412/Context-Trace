"""Public identities for the experimental hybrid_v2 verifier."""

SCHEMA_VERSION = "2.0"
TAXONOMY_VERSION = "contexttrace-hybrid-v2.0"
VERIFIER_VERSION = "hybrid_v2"
PROFILE_ID = "hybrid_v2"
DIAGNOSTIC_REASONER_VERSION = "evidence_chain_v2"

CAPABILITIES = {
    "metadata_free_source_chronology": True,
    "content_lifecycle_relations": True,
    "unresolved_source_conflicts": True,
    "query_temporal_scope": True,
    "query_conditioned_evidence_gaps": True,
    "local_nli_mode": True,
    "independent_truth_certification": False,
}

LIMITATIONS = (
    "Experimental API: labels and thresholds may change before hybrid_v2 is frozen.",
    "Support and source relations are assessed only from supplied evidence and metadata.",
    "Freshness remains unknown when neither metadata nor source text exposes chronology or lifecycle evidence.",
    "The default semantic mode is deterministic; entailment requires explicit mode='nli' and a local frozen model.",
)
