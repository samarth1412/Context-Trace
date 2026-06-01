# LangChain Integration

ContextTrace ships a `ContextTraceCallbackHandler` for LangChain callback pipelines. It captures:

- query/input
- retrieved documents
- selected context
- final answer/output
- citations when the chain returns them
- metadata, tags, run IDs, model, token usage, and latency
- tool calls, tool results, and chain/tool errors as agent timeline events

## Install

```bash
pip install "contexttrace[langchain]"
```

## Usage

```python
from contexttrace import ContextTraceCallbackHandler

handler = ContextTraceCallbackHandler(
    api_key="ctx_test",
    project="support-rag",
    base_url="http://localhost:8000",
    trace_metadata={"pipeline": "langchain-rag"},
    selected_context_limit=5,
)

result = chain.invoke(
    {"query": "What is the refund policy?"},
    config={"callbacks": [handler]},
)
```

For private/local usage:

```python
from contexttrace import ContextTrace, ContextTraceCallbackHandler

ct = ContextTrace(mode="local", project="support-rag")
handler = ContextTraceCallbackHandler(client=ct)
```

## Custom Extractors

Use custom extractors when your chain does not use common keys such as `query`, `answer`, or `citations`.

```python
handler = ContextTraceCallbackHandler(
    client=ct,
    query_extractor=lambda inputs: inputs["messages"][-1]["content"],
    answer_extractor=lambda outputs: outputs["final"]["text"],
    citation_extractor=lambda outputs: outputs["final"].get("citations", []),
)
```

Documents can also be converted with `document_converter(document, index)`.

## Runnable Example

```bash
python examples/langchain_rag.py
```

The example uses mock LangChain-like objects and local mode so it runs without external services.

