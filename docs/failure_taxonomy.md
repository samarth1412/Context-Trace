# Failure Taxonomy

ContextTrace classifies RAG failures into a small set of actionable categories. The goal is to identify what went wrong in the evidence path, not to produce a generic quality score.

## Labels

### `no_failure_detected`

The answer is supported by selected context and citations are consistent.

Suggested action: no immediate remediation.

### `retrieval_miss`

The needed source was not retrieved.

Suggested action: improve indexing, query rewriting, metadata filters, or hybrid retrieval.

### `low_relevance_context`

Retrieved chunks are weakly related to the query.

Suggested action: tune retriever parameters, add reranking, or improve embedding coverage.

### `citation_mismatch`

A cited source supports some nearby topic but not the specific claim.

Suggested action: verify citations at sentence or claim level before returning the answer.

### `unsupported_answer`

The answer includes claims that are not supported by selected context.

Suggested action: constrain generation to evidence, add abstention, and log uncovered claims.

### `contradicted_answer`

Selected evidence contradicts the answer.

Suggested action: add contradiction checks and force abstention or repair before returning.

### `conflicting_sources`

Retrieved sources disagree with each other.

Suggested action: rank authoritative sources higher and expose conflicts to the user.

### `bad_chunking`

Chunks split concepts, omit needed surrounding context, or contain too much unrelated content.

Suggested action: revise chunk size, overlap, structural splitting, and source metadata.

### `over_compression`

Context compression removed evidence needed to support the answer.

Suggested action: increase token budget or preserve citation-bearing sentences during compression.

### `should_have_abstained`

The system answered when evidence was insufficient or the query was out of scope.

Suggested action: add confidence thresholds and abstention policies.

### `query_needs_decomposition`

The query requires multiple retrieval steps or sub-questions.

Suggested action: decompose the query and trace each sub-step.

### `unknown`

The judge could not confidently classify the issue or returned invalid structured output after retry.

Suggested action: inspect trace evidence manually and improve judge prompts or provider reliability.

## Severity

Severity values are:

```text
none
low
medium
high
```

Use severity to prioritize remediation. A high severity `contradicted_answer` usually requires release blocking; a low severity `low_relevance_context` may be a tuning backlog item.

## Scoring Fields

`citation_support` is the average support score across evaluated citations.

`unsupported_claim_rate` is the share of citations labeled `unsupported`, `contradicted`, or `not_enough_info`.

`failure_type` and `severity` come from the failure analyzer.
