import type { EvalSummary, TraceDetail, TraceSummary } from "@/lib/types";

export const mockTraces: TraceDetail[] = [
  {
    id: "trace_refund_supported",
    project_id: "project_support",
    project: "support-rag",
    query: "What is the refund policy?",
    metadata: { latency_ms: 842 },
    status: "evaluated",
    chunks: [
      {
        id: "chunk_db_12",
        chunk_id: "chunk_12",
        content: "Customers can request refunds within 30 days of purchase.",
        source: "refund-policy.md",
        metadata: {},
        relevance_score: 0.91,
        position: 0,
        selected: true
      },
      {
        id: "chunk_db_13",
        chunk_id: "chunk_13",
        content: "Shipping time depends on the destination and carrier.",
        source: "shipping.md",
        metadata: {},
        relevance_score: 0.42,
        position: 1,
        selected: false
      }
    ],
    answer: {
      id: "answer_1",
      answer: "Refunds are available within 30 days.",
      model: "gpt-4.1-mini",
      usage: {
        prompt_tokens: 1000,
        completion_tokens: 200,
        total_tokens: 1200
      },
      metadata: {}
    },
    citation_checks: [
      {
        id: "check_1",
        claim: "Refunds are available within 30 days.",
        source_chunk_id: "chunk_12",
        support_status: "directly_supported",
        support_score: 0.98,
        rationale: "The source explicitly states the 30-day refund window."
      }
    ],
    evaluation: {
      citation_checks: [
        {
          claim: "Refunds are available within 30 days.",
          source_chunk_id: "chunk_12",
          verdict: "directly_supported",
          support_score: 0.98,
          reason: "The source explicitly states the 30-day refund window."
        }
      ],
      failure: {
        failure_type: "no_failure_detected",
        severity: "none",
        root_cause: "All cited claims are supported by selected context.",
        suggested_fix: "No fix required."
      }
    },
    created_at: "2026-05-31T12:00:00Z",
    updated_at: "2026-05-31T12:00:01Z"
  },
  {
    id: "trace_refund_mismatch",
    project_id: "project_support",
    project: "support-rag",
    query: "How fast are refunds processed?",
    metadata: { latency_ms: 1320 },
    status: "evaluated",
    chunks: [
      {
        id: "chunk_db_22",
        chunk_id: "chunk_22",
        content: "Customers can request refunds within 30 days. Processing times vary by bank.",
        source: "refund-policy.md",
        metadata: {},
        relevance_score: 0.87,
        position: 0,
        selected: true
      }
    ],
    answer: {
      id: "answer_2",
      answer: "Refunds are available within 30 days and are processed in two days.",
      model: "gpt-4.1-mini",
      usage: {
        prompt_tokens: 860,
        completion_tokens: 180,
        total_tokens: 1040
      },
      metadata: {}
    },
    citation_checks: [
      {
        id: "check_2",
        claim: "Refunds are processed in two days.",
        source_chunk_id: "chunk_22",
        support_status: "unsupported",
        support_score: 0.1,
        rationale: "The cited source does not state a two-day processing time."
      }
    ],
    evaluation: {
      citation_checks: [
        {
          claim: "Refunds are processed in two days.",
          source_chunk_id: "chunk_22",
          verdict: "unsupported",
          support_score: 0.1,
          reason: "The cited source does not state a two-day processing time."
        }
      ],
      failure: {
        failure_type: "citation_mismatch",
        severity: "medium",
        root_cause: "The answer cites refund policy evidence for a processing-time claim that is not supported.",
        suggested_fix: "Require sentence-level citation checks for timing claims before returning the answer."
      }
    },
    created_at: "2026-05-31T12:04:00Z",
    updated_at: "2026-05-31T12:04:01Z"
  },
  {
    id: "trace_policy_unsupported",
    project_id: "project_support",
    project: "support-rag",
    query: "Can final-sale items be refunded?",
    metadata: { latency_ms: 990 },
    status: "evaluated",
    chunks: [
      {
        id: "chunk_db_31",
        chunk_id: "chunk_31",
        content: "Final sale items are not refundable.",
        source: "refund-policy.md",
        metadata: {},
        relevance_score: 0.96,
        position: 0,
        selected: true
      }
    ],
    answer: {
      id: "answer_3",
      answer: "Final-sale items can be refunded within 30 days.",
      model: "gpt-4.1-mini",
      usage: {
        prompt_tokens: 720,
        completion_tokens: 140,
        total_tokens: 860
      },
      metadata: {}
    },
    citation_checks: [
      {
        id: "check_3",
        claim: "Final-sale items can be refunded within 30 days.",
        source_chunk_id: "chunk_31",
        support_status: "contradicted",
        support_score: 0,
        rationale: "The cited source says final sale items are not refundable."
      }
    ],
    evaluation: {
      citation_checks: [
        {
          claim: "Final-sale items can be refunded within 30 days.",
          source_chunk_id: "chunk_31",
          verdict: "contradicted",
          support_score: 0,
          reason: "The cited source says final sale items are not refundable."
        }
      ],
      failure: {
        failure_type: "contradicted_answer",
        severity: "high",
        root_cause: "The generated answer contradicts the selected policy chunk.",
        suggested_fix: "Add contradiction checks and force abstention when selected evidence conflicts with the answer."
      }
    },
    created_at: "2026-05-31T12:10:00Z",
    updated_at: "2026-05-31T12:10:01Z"
  }
];

export const mockTraceSummaries: TraceSummary[] = mockTraces.map((trace) => ({
  id: trace.id,
  query: trace.query,
  status: trace.status,
  failure_type: trace.evaluation?.failure.failure_type ?? "unknown",
  severity: trace.evaluation?.failure.severity ?? "medium",
  citation_support:
    trace.evaluation?.citation_checks.reduce((sum, check) => sum + (check.support_score ?? 0), 0) /
      Math.max(trace.evaluation?.citation_checks.length ?? 1, 1) || 0,
  unsupported_claim_rate:
    (trace.evaluation?.citation_checks.filter((check) =>
      ["unsupported", "contradicted", "not_enough_info"].includes(check.verdict ?? "pending")
    ).length ?? 0) / Math.max(trace.evaluation?.citation_checks.length ?? 1, 1),
  updated_at: trace.updated_at
}));

export const mockEvalSummary: EvalSummary = {
  eval_set_id: "eval_refund_policy",
  name: "refund-policy-regression",
  total_questions: 3,
  linked_trace_count: 3,
  evaluated_trace_count: 3,
  unevaluated_trace_count: 0,
  avg_citation_support: 0.36,
  unsupported_claim_rate: 0.67,
  failure_type_distribution: {
    no_failure_detected: 1,
    citation_mismatch: 1,
    contradicted_answer: 1
  },
  worst_traces: [
    {
      trace_id: "trace_policy_unsupported",
      question_id: "q_3",
      question: "Can final-sale items be refunded?",
      failure_type: "contradicted_answer",
      severity: "high",
      citation_support: 0,
      unsupported_claim_rate: 1,
      root_cause: "The generated answer contradicts the selected policy chunk."
    },
    {
      trace_id: "trace_refund_mismatch",
      question_id: "q_2",
      question: "How fast are refunds processed?",
      failure_type: "citation_mismatch",
      severity: "medium",
      citation_support: 0.1,
      unsupported_claim_rate: 1,
      root_cause: "The cited source does not support the processing-time claim."
    }
  ]
};
