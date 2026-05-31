# Citation Verification

Citation verification checks whether a cited source chunk supports a specific answer claim. ContextTrace evaluates at the claim and evidence level rather than only scoring the whole answer.

## Input

Each citation includes:

```json
{
  "claim": "Refunds are available within 30 days.",
  "source_chunk_id": "chunk_12"
}
```

The `source_chunk_id` must match a chunk logged through `log_retrieval()` or `log_context()`.

## Verdicts

### `directly_supported`

The source explicitly supports the claim.

### `partially_supported`

The source supports part of the claim but omits or weakly supports some detail.

### `unsupported`

The source does not provide evidence for the claim.

### `contradicted`

The source says the opposite of the claim.

### `not_enough_info`

The cited chunk is missing, incomplete, or too ambiguous to judge.

## Output

```json
{
  "claim": "Refunds are available within 30 days.",
  "source_chunk_id": "chunk_12",
  "verdict": "directly_supported",
  "support_score": 0.98,
  "reason": "The source explicitly states the 30-day refund window."
}
```

`support_score` is normalized from `0.0` to `1.0`.

## Provider Abstraction

The backend uses an `LLMJudgeProvider` interface. Business logic calls the provider abstraction and does not hardcode OpenAI calls.

Local development defaults to the mock provider:

```env
CONTEXTTRACE_JUDGE_PROVIDER=mock
```

OpenAI-compatible providers use:

```env
CONTEXTTRACE_JUDGE_PROVIDER=openai_compatible
CONTEXTTRACE_OPENAI_COMPATIBLE_BASE_URL=https://api.openai.com/v1
CONTEXTTRACE_OPENAI_COMPATIBLE_API_KEY=...
CONTEXTTRACE_OPENAI_COMPATIBLE_MODEL=gpt-4.1-mini
```

## Structured JSON

The verifier requests structured JSON and validates:

```json
{
  "verdict": "directly_supported",
  "support_score": 0.98,
  "reason": "Short rationale."
}
```

If the provider returns invalid JSON, ContextTrace retries once. If parsing still fails, the trace evaluation falls back to safe unknown or unsupported states depending on the failing stage.

## Best Practices

Use sentence-level claims. Do not cite a whole answer paragraph as one claim.

Prefer stable chunk IDs from your source system. This makes reports easier to audit.

Log selected context separately from retrieved chunks. Citation verification can then reveal whether the generator ignored or misused selected evidence.
