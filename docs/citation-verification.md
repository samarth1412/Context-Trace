# Citation Verification

Citation verification checks whether a cited source chunk supports a specific
answer claim. ContextTrace evaluates at the claim and evidence level rather
than only scoring the whole answer.

## Input

Each citation includes:

```json
{
  "claim": "Refunds are available within 30 days.",
  "source_chunk_id": "chunk_12"
}
```

The `source_chunk_id` must match a chunk logged through `log_retrieval()` or
`log_context()`.

## Verdicts

- `directly_supported`: the source explicitly supports the claim.
- `partially_supported`: the source supports only part of the claim.
- `unsupported`: the source does not provide evidence for the claim.
- `contradicted`: the source says the opposite of the claim.
- `not_enough_info`: the cited chunk is missing, incomplete, or ambiguous.

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

## Verification Modes

Local lexical and semantic modes run without network access. Optional local NLI
and local judge modes provide stronger checks when configured. Remote judges
require an explicit provider configuration and are blocked while
`local_only: true` is active.

The backend uses an `LLMJudgeProvider` interface, so verification logic does
not depend on a specific vendor.

## Best Practices

- Use sentence-level claims instead of citing a whole answer paragraph.
- Prefer stable source chunk IDs from the source system.
- Log selected context separately from all retrieved chunks.
- Inspect the raw evidence for high-stakes or ambiguous verdicts.
