# Citation Verification

ContextTrace checks whether cited chunks support answer claims.

Citation input:

```json
{
  "claim": "Refunds are available within 30 days.",
  "source_chunk_id": "refund_policy_1"
}
```

Verdicts:

- `directly_supported`
- `partially_supported`
- `unsupported`
- `contradicted`
- `not_enough_info`

Local mode uses lightweight lexical checks so demos and tests run without network access. You can configure an LLM judge provider for deeper claim verification when needed.

Reports show every claim, cited chunk, verdict, support score, and reason so the raw evidence remains visible.
