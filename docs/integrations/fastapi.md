# FastAPI Middleware

`ContextTraceFastAPIMiddleware` traces incoming RAG API requests without installing SDK calls inside each endpoint.

It is ASGI middleware, so it works with sync or async FastAPI endpoints.

## Install

```bash
pip install "contexttrace[fastapi]"
```

## Usage

```python
from fastapi import FastAPI
from contexttrace import ContextTrace, ContextTraceFastAPIMiddleware

app = FastAPI()
ct = ContextTrace(api_key="ctx_test", project="support-rag")

app.add_middleware(
    ContextTraceFastAPIMiddleware,
    client=ct,
    should_trace=lambda request: request["path"] == "/query",
    route_allowlist=("/query", "/v1/rag/*"),
    content_type_allowlist=("application/json",),
    max_capture_bytes=1_048_576,
)
```

Request and response bodies are bounded tees: ASGI messages are forwarded as
they arrive, while at most `max_capture_bytes` is retained for extraction.
Server-sent events and attachment responses are forwarded without capturing
their bodies. Truncation and skipped-stream counters are available through
`middleware.metrics`.

Set `background_logging=True` with `max_pending_logs=` to move persistence out
of the request path. Call `await middleware.drain()` during application shutdown
to flush queued writes. When the queue is full, traces are dropped instead of
applying unbounded backpressure, and `logging_dropped` is incremented.

The default extractor looks for:

- request query: `query`, `question`, `input`, or `prompt`
- response answer: `answer`, `response`, `output`, `result`, or `text`
- response evidence: `retrieved_chunks`, `contexts`, `chunks`, `selected_context`, or `context`
- citations: `citations` or `sources`

## Custom Extractors

```python
def request_extractor(request):
    return {
        "query": request["json"]["messages"][-1]["content"],
        "metadata": {"route": request["path"]},
    }

def response_extractor(response, request):
    body = response["json"]
    return {
        "answer": body["data"]["answer"],
        "retrieved_chunks": body["data"]["contexts"],
        "citations": body["data"].get("citations", []),
    }

app.add_middleware(
    ContextTraceFastAPIMiddleware,
    client=ct,
    request_extractor=request_extractor,
    response_extractor=response_extractor,
)
```

Logging failures are swallowed by default so tracing does not break the production endpoint. Set `raise_logging_errors=True` during development.
