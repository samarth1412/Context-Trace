# Python SDK

The `contexttrace` SDK is intentionally small. It records the inputs and evidence from your existing RAG pipeline, then asks the ContextTrace backend to verify citations and classify failures.

## Installation

```bash
pip install -e packages/contexttrace
```

Optional integrations:

```bash
pip install -e "packages/contexttrace[langchain]"
pip install -e "packages/contexttrace[llamaindex]"
```

## Client

```python
from contexttrace import ContextTrace

ct = ContextTrace(
    api_key="ctx_test",
    project="support-rag",
    base_url="http://localhost:8000",
)
```

Configuration precedence is:

1. Direct constructor arguments
2. Environment variables such as `CONTEXTTRACE_API_KEY`, `CONTEXTTRACE_PROJECT`, `CONTEXTTRACE_BASE_URL`, and `CONTEXTTRACE_MODE`
3. `contexttrace.yaml`
4. SDK defaults

Local mode stores traces as JSON files and can generate reports without the backend:

```python
ct = ContextTrace(mode="local", project="support-rag")
```

The CLI can create a starter config:

```bash
contexttrace init
contexttrace config show
```

## Trace Lifecycle

```python
with ct.trace(query="What is the refund policy?", metadata={"env": "local"}) as trace:
    trace.log_retrieval(chunks, retriever_name="hybrid-search")
    trace.log_context(chunks[:5])
    trace.log_answer(answer, model="gpt-4.1-mini", usage={"total_tokens": 1200})
    trace.log_citations(citations)
    evaluation = trace.evaluate()
```

The context manager starts a trace through `POST /v1/traces/start`. Each logging method sends one event to the backend.

## Methods

### `ContextTrace.trace(query, metadata=None)`

Starts a trace context manager.

### `TraceSession.log_retrieval(chunks, retriever_name=None, metadata=None)`

Logs retrieved chunks before context selection. Each chunk may be a dictionary or object with `chunk_id`, `content`, `source`, `metadata`, and `relevance_score`.

### `TraceSession.log_context(chunks=None, chunk_ids=None, metadata=None)`

Logs the chunks selected for the final prompt. You can pass complete chunk payloads or IDs already logged during retrieval.

### `TraceSession.log_answer(answer, model=None, usage=None, metadata=None)`

Logs the generated answer, model name, token usage, and metadata such as latency.

### `TraceSession.log_citations(citations)`

Logs answer claims and their cited source chunk IDs.

### `TraceSession.evaluate()`

Runs citation verification and failure analysis. The result includes citation checks and a failure diagnosis.

### `TraceSession.fetch()`

Fetches the complete trace.

### `TraceSession.export_report(path="report.html")`

Writes a local HTML report from the fetched trace.

### `ContextTrace.list_traces(limit=20)`

Lists recent traces when the active transport supports trace listing, including local mode.

### `ContextTrace.upload_traces(...)`

Uploads stored local traces to a hosted ContextTrace backend by replaying trace events.

## Async SDK

```python
from contexttrace import AsyncContextTrace

ct = AsyncContextTrace(mode="local", project="support-rag")

async with ct.trace(query="What is the refund policy?") as trace:
    await trace.log_retrieval(chunks)
    await trace.log_context(chunks[:5])
    await trace.log_answer(answer)
    result = await trace.evaluate()
```

## Batch Evaluation

Batch eval sets assume traces already exist and are linked to eval questions.

```python
eval_set = ct.create_eval_set("refund-policy-regression")
ct.add_eval_questions(
    eval_set["eval_set_id"],
    [
        {
            "question": "What is the refund policy?",
            "trace_id": "trace_123",
            "expected_answer": "Refunds are available within 30 days.",
        }
    ],
)
summary = ct.evaluate_existing_traces(eval_set["eval_set_id"])
```

## CI Evaluation CLI

```bash
contexttrace eval \
  --dataset evals/questions.json \
  --endpoint https://my-rag-api.com/query \
  --min-citation-support 0.80 \
  --max-unsupported-claim-rate 0.10 \
  --max-failure-rate 0.05
```

The endpoint can also be stored as `eval_endpoint` in `contexttrace.yaml` or `CONTEXTTRACE_EVAL_ENDPOINT`.
The CLI calls your endpoint for each question, logs traces, evaluates them, writes a markdown summary, and exits non-zero when thresholds fail.

Other local CLI commands:

```bash
contexttrace trace list
contexttrace report --last --output report.html
```

## Error Handling

Hosted HTTP calls use timeouts and transient-error retries. Backend request failures raise `ContextTraceHTTPError` with the request method, URL, status, and response detail when available.

Enable SDK debug logging with `ContextTrace(debug=True)` or `CONTEXTTRACE_DEBUG=true`.
