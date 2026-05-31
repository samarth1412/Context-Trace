from enum import Enum


class FailureType(str, Enum):
    NO_FAILURE_DETECTED = "no_failure_detected"
    RETRIEVAL_MISS = "retrieval_miss"
    LOW_RELEVANCE_CONTEXT = "low_relevance_context"
    CITATION_MISMATCH = "citation_mismatch"
    UNSUPPORTED_ANSWER = "unsupported_answer"
    CONTRADICTED_ANSWER = "contradicted_answer"
    CONFLICTING_SOURCES = "conflicting_sources"
    BAD_CHUNKING = "bad_chunking"
    OVER_COMPRESSION = "over_compression"
    SHOULD_HAVE_ABSTAINED = "should_have_abstained"
    QUERY_NEEDS_DECOMPOSITION = "query_needs_decomposition"
    UNKNOWN = "unknown"


class Severity(str, Enum):
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class CitationVerdict(str, Enum):
    DIRECTLY_SUPPORTED = "directly_supported"
    PARTIALLY_SUPPORTED = "partially_supported"
    UNSUPPORTED = "unsupported"
    CONTRADICTED = "contradicted"
    NOT_ENOUGH_INFO = "not_enough_info"


class SupportStatus(str, Enum):
    PENDING = "pending"
    DIRECTLY_SUPPORTED = "directly_supported"
    PARTIALLY_SUPPORTED = "partially_supported"
    UNSUPPORTED = "unsupported"
    CONTRADICTED = "contradicted"
    NOT_ENOUGH_INFO = "not_enough_info"
