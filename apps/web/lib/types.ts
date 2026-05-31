export type FailureType =
  | "no_failure_detected"
  | "retrieval_miss"
  | "low_relevance_context"
  | "citation_mismatch"
  | "unsupported_answer"
  | "contradicted_answer"
  | "conflicting_sources"
  | "bad_chunking"
  | "over_compression"
  | "should_have_abstained"
  | "query_needs_decomposition"
  | "wrong_tool_used"
  | "tool_error"
  | "stale_memory_used"
  | "missing_memory"
  | "excessive_tool_calls"
  | "agent_loop_detected"
  | "unknown";

export type Severity = "none" | "low" | "medium" | "high";

export type CitationVerdict =
  | "pending"
  | "directly_supported"
  | "partially_supported"
  | "unsupported"
  | "contradicted"
  | "not_enough_info";

export type TraceChunk = {
  id: string;
  chunk_id: string;
  content: string;
  source?: string | null;
  metadata?: Record<string, unknown>;
  relevance_score?: number | null;
  position: number;
  selected: boolean;
};

export type TraceAnswer = {
  id: string;
  answer: string;
  model?: string | null;
  usage?: Record<string, number>;
  metadata?: Record<string, unknown>;
};

export type CitationCheck = {
  id?: string;
  claim: string;
  source_chunk_id: string;
  support_status?: CitationVerdict;
  verdict?: CitationVerdict;
  support_score?: number | null;
  rationale?: string | null;
  reason?: string | null;
};

export type FailurePayload = {
  failure_type: FailureType;
  severity: Severity;
  root_cause: string;
  suggested_fix: string;
};

export type TraceEvaluation = {
  citation_checks: CitationCheck[];
  failure: FailurePayload;
};

export type ContextPolicyMetadata = {
  query_class?: string;
  query_class_reason?: string;
  selected_policy?: string;
  reason?: string;
  retrieval_confidence?: number;
  retrieval_strategy?: string;
  token_budget?: number;
  selected_chunk_ids?: string[];
  dropped_chunk_ids?: string[];
};

export type AgentEventType =
  | "planner_step"
  | "tool_call"
  | "tool_result"
  | "retrieval"
  | "memory_read"
  | "memory_write"
  | "human_approval"
  | "final_answer"
  | "error";

export type AgentEvent = {
  id: string;
  trace_id: string;
  event_type: AgentEventType;
  name?: string | null;
  input_json?: unknown;
  output_json?: unknown;
  metadata_json?: Record<string, unknown>;
  latency_ms?: number | null;
  error_message?: string | null;
  created_at: string;
};

export type TraceDetail = {
  id: string;
  project_id: string;
  project: string;
  query: string;
  metadata?: Record<string, unknown>;
  status: string;
  chunks: TraceChunk[];
  answer?: TraceAnswer | null;
  citation_checks: CitationCheck[];
  agent_events?: AgentEvent[];
  evaluation?: TraceEvaluation | null;
  created_at: string;
  updated_at: string;
};

export type TraceSummary = {
  id: string;
  query: string;
  status: string;
  failure_type: FailureType;
  severity: Severity;
  citation_support: number;
  unsupported_claim_rate: number;
  updated_at: string;
};

export type EvalSummary = {
  eval_set_id: string;
  name: string;
  total_questions: number;
  linked_trace_count: number;
  evaluated_trace_count: number;
  unevaluated_trace_count: number;
  avg_citation_support: number;
  unsupported_claim_rate: number;
  failure_type_distribution: Record<string, number>;
  worst_traces: Array<{
    trace_id: string;
    question_id: string;
    question: string;
    failure_type: FailureType;
    severity: Severity;
    citation_support: number;
    unsupported_claim_rate: number;
    root_cause: string;
  }>;
};

export type DataSource = "backend" | "mock";

export type PlaygroundChunk = {
  chunk_id: string;
  content: string;
  source?: string | null;
  score: number;
  metadata?: Record<string, unknown>;
};

export type PlaygroundQueryResponse = {
  answer: string;
  trace_id: string;
  retrieved_chunks: PlaygroundChunk[];
  citations: Array<{
    claim: string;
    source_chunk_id: string;
  }>;
  evaluation: TraceEvaluation;
};

export type PlaygroundDocumentUploadResponse = {
  document_id: string;
  filename: string;
  chunk_count: number;
};

export type RetrievalStrategyName = "dense_top_k" | "bm25_top_k" | "hybrid" | "hybrid_rerank";

export type PlaygroundComparisonMetrics = {
  citation_support: number;
  unsupported_claim_rate: number;
  failure_type: FailureType;
  token_usage: Record<string, unknown>;
  latency_ms: number;
};

export type PlaygroundComparisonResult = {
  strategy: RetrievalStrategyName;
  trace_id: string;
  answer: string;
  retrieved_chunks: PlaygroundChunk[];
  citations: Array<{
    claim: string;
    source_chunk_id: string;
  }>;
  metrics: PlaygroundComparisonMetrics;
  evaluation: TraceEvaluation;
};

export type PlaygroundCompareResponse = {
  query: string;
  results: PlaygroundComparisonResult[];
};

export type ExternalEndpointResponse = {
  id: string;
  project_id: string;
  name: string;
  url: string;
  method: "GET" | "POST";
  headers: Record<string, string>;
  body_template: Record<string, unknown>;
  response_mapping: Record<string, string>;
  created_at: string;
};

export type ExternalEndpointTestResponse = {
  endpoint_id: string;
  trace_id: string;
  mapped: {
    raw_response: Record<string, unknown>;
    answer: string;
    retrieved_chunks: Array<{
      chunk_id?: string | null;
      content: string;
      source?: string | null;
      metadata?: Record<string, unknown>;
      relevance_score?: number | null;
    }>;
    citations: Array<{
      claim: string;
      source_chunk_id: string;
      metadata?: Record<string, unknown>;
    }>;
    usage: Record<string, unknown>;
    model?: string | null;
  };
};
