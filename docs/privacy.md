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
privacy: strict
hash_only: false
retention_days: 30
metadata_allowlist: request_id,tenant_id
```

Use `log_chunk_text: false` or `log_answer_text: false` when traces should preserve metadata and metrics without storing sensitive text.

`privacy="strict"` covers queries, chunks, answers, citation claims, metadata,
tool inputs and outputs, event names, and agent errors before they reach local or
hosted persistence. Strict mode hashes source identifiers so citation edges stay
joinable without retaining the original IDs. `hash_only=True` replaces captured
text with salted SHA-256 values.

For selective redaction, pass regexes or custom callables:

```python
ct = ContextTrace(
    redaction_patterns=(r"[\w.+-]+@[\w.-]+",),
    custom_redactors=(remove_customer_ids,),
    metadata_allowlist=("request_id", "tenant_id"),
    retention_days=30,
)
```

Local SQLite directories are created with mode `0700` and database files with
mode `0600` where the operating system supports POSIX permissions. Applications
can provide a `TextCipher` implementation through `text_cipher=`; values are
encrypted before persistence and decrypted when traces are fetched. ContextTrace
does not manage encryption keys.

TTL cleanup runs when the local transport starts and before a new trace is
created. Deletion is permanent, so retain only the minimum operational window.
