# Privacy

ContextTrace is local-first by default.

What stays local:

- queries
- retrieved chunks
- selected context
- answers
- citations
- failure reports
- local HTML reports

Default storage:

```text
.contexttrace/contexttrace.db
```

Network behavior:

- No network call is made for local SDK tracing.
- `contexttrace eval --endpoint ...` calls only the endpoint you provide.
- LLM judge calls happen only when you configure a judge provider.

Redaction controls:

```yaml
local_only: true
log_chunk_text: false
log_answer_text: false
storage_path: .contexttrace/contexttrace.db
```

Use `log_chunk_text: false` or `log_answer_text: false` when traces should preserve metadata and metrics without storing sensitive text.
