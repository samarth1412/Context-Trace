# Local Mode

ContextTrace is local-first by default. A new SDK client stores traces in SQLite under:

```text
.contexttrace/contexttrace.db
```

No backend server is required for normal SDK, CLI, report, or viewer workflows.

```python
from contexttrace import ContextTrace

ct = ContextTrace(project="support-rag")

with ct.trace(query="What is the refund policy?") as trace:
    trace.log_retrieval([
        {"chunk_id": "refund_1", "content": "Refunds are available within 30 days."}
    ])
    trace.log_context(chunk_ids=["refund_1"])
    trace.log_answer("Refunds are available within 30 days.")
    trace.log_citations([
        {"claim": "Refunds are available within 30 days.", "source_chunk_id": "refund_1"}
    ])
    trace.evaluate()
    trace.export_report(path=".contexttrace/reports/refund.html")
```

Configuration can come from constructor arguments, environment variables, or `contexttrace.yaml`.

```yaml
mode: local
project: support-rag
storage_path: .contexttrace/contexttrace.db
local_only: true
log_chunk_text: true
log_answer_text: true
judge_provider: local
```

Privacy controls:

- `local_only: true` keeps trace storage local unless you explicitly configure a hosted API.
- `log_chunk_text: false` redacts chunk text before writing the local store.
- `log_answer_text: false` redacts answer text before writing the local store.

Useful commands:

```bash
contexttrace init
contexttrace status
contexttrace demo --dataset refund_policy
contexttrace traces list
contexttrace report --last --open
contexttrace viewer
```
