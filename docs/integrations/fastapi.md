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
)
```

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

