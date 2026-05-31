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
    WRONG_TOOL_USED = "wrong_tool_used"
    TOOL_ERROR = "tool_error"
    STALE_MEMORY_USED = "stale_memory_used"
    MISSING_MEMORY = "missing_memory"
    EXCESSIVE_TOOL_CALLS = "excessive_tool_calls"
    AGENT_LOOP_DETECTED = "agent_loop_detected"
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


class AgentEventType(str, Enum):
    PLANNER_STEP = "planner_step"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    RETRIEVAL = "retrieval"
    MEMORY_READ = "memory_read"
    MEMORY_WRITE = "memory_write"
    HUMAN_APPROVAL = "human_approval"
    FINAL_ANSWER = "final_answer"
    ERROR = "error"
