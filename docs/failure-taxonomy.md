# Failure Taxonomy

ContextTrace classifies failures into actionable categories. The goal is to
identify what broke in the evidence path, not to hide it behind a generic
quality score.

## RAG Labels

- `no_failure_detected`: the answer and citations are supported.
- `retrieval_miss`: the needed source was not retrieved.
- `low_relevance_context`: retrieved chunks are weakly related to the query.
- `citation_mismatch`: a citation does not support its specific claim.
- `unsupported_answer`: selected context does not support one or more claims.
- `contradicted_answer`: selected evidence contradicts the answer.
- `conflicting_sources`: retrieved sources disagree.
- `bad_chunking`: chunk boundaries removed or obscured required evidence.
- `over_compression`: context compression removed required evidence.
- `should_have_abstained`: the system answered without sufficient evidence.
- `query_needs_decomposition`: the query requires multiple retrieval steps.

## Agent Labels

- `wrong_tool_used`: the selected tool was inappropriate for the task.
- `tool_error`: a tool call failed or returned unusable output.
- `stale_memory_used`: the agent relied on outdated memory.
- `missing_memory`: required prior state was unavailable.
- `excessive_tool_calls`: the agent used more calls than necessary.
- `agent_loop_detected`: planning or tool calls repeated without progress.
- `unknown`: the failure could not be classified confidently.

Each classification includes severity, evidence, explanation, and suggested
remediation. Typical fixes include retriever tuning, reranking, chunking
changes, evidence-constrained generation, abstention, tool-policy checks, and
memory freshness controls.

## Severity

Severity is one of `none`, `low`, `medium`, or `high`. Use it for triage; a
high-severity contradicted answer is normally release-blocking, while a
low-severity relevance issue may remain a tuning task.

## Scoring Fields

- `citation_support`: average support score across evaluated citations.
- `unsupported_claim_rate`: share of unsupported, contradicted, or unknown claims.
- `failure_type`: the primary taxonomy label.
- `reliability`: a diagnostic triage score, not a correctness guarantee.

See [Reliability Score](reliability_score.md) for the score definition.
