# LangChain Integration

ContextTrace includes a callback handler for LangChain pipelines. It captures chain input, retrieved documents, final output, metadata, token usage when available, and latency.

## Installation

```bash
pip install -e "packages/contexttrace[langchain]"
```

## Basic Usage

```python
from contexttrace import ContextTraceCallbackHandler

handler = ContextTraceCallbackHandler(
    api_key="ctx_test",
    project="support-rag",
    base_url="http://localhost:8000",
    trace_metadata={"pipeline": "langchain-rag"},
)

result = chain.invoke(
    {"query": "What is the refund policy?"},
    config={"callbacks": [handler]},
)
```

## Document Conversion

LangChain documents are converted into ContextTrace chunks:

```python
{
    "chunk_id": document.metadata.get("id"),
    "content": document.page_content,
    "source": document.metadata.get("source"),
    "metadata": document.metadata,
}
```

If no ID is present, the handler derives a stable fallback from the callback event position.

## What Gets Captured

The handler records:

```text
query/input
retrieved documents
selected context
final answer/output
metadata
latency
token usage when available
```

## Example

See `examples/langchain_rag.py`.

## Notes

The callback is intentionally framework-adjacent. Your LangChain chain remains responsible for retrieval, generation, and citation formatting. ContextTrace records what happened and evaluates the evidence after the chain returns.
