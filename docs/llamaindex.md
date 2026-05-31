# LlamaIndex Integration

ContextTrace includes a LlamaIndex callback adapter for tracing query, retrieval, source nodes, final response, metadata, and latency.

## Installation

```bash
pip install -e "packages/contexttrace[llamaindex]"
```

## Basic Usage

```python
from contexttrace import ContextTraceLlamaIndexCallbackHandler
from llama_index.core import Settings
from llama_index.core.callbacks import CallbackManager

handler = ContextTraceLlamaIndexCallbackHandler(
    api_key="ctx_test",
    project="support-rag",
    base_url="http://localhost:8000",
    trace_metadata={"pipeline": "llamaindex-rag"},
)

Settings.callback_manager = CallbackManager([handler])
response = query_engine.query("What is the refund policy?")
```

## Node Conversion

Source nodes are converted into ContextTrace chunks with:

```python
{
    "chunk_id": node.node_id,
    "content": node.get_content(),
    "source": node.metadata.get("source"),
    "metadata": node.metadata,
    "relevance_score": score,
}
```

## What Gets Captured

```text
query
retrieved nodes
final response
source nodes
metadata
latency
```

## Example

See `examples/llamaindex_rag.py`.

## Notes

The adapter does not replace LlamaIndex retrieval or response synthesis. It records the evidence and response so the ContextTrace backend can verify citations and classify RAG failures.
