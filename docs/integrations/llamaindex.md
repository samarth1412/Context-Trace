# LlamaIndex Integration

ContextTrace includes `ContextTraceLlamaIndexCallbackHandler` for LlamaIndex callback events. It captures:

- query
- retrieved nodes
- source nodes used in the response
- final response text
- metadata and latency

## Install

```bash
pip install "contexttrace[llamaindex]"
```

## Usage

```python
from contexttrace import ContextTraceLlamaIndexCallbackHandler
from llama_index.core import Settings
from llama_index.core.callbacks import CallbackManager

handler = ContextTraceLlamaIndexCallbackHandler(
    api_key="ctx_test",
    project="support-rag",
    base_url="http://localhost:8000",
    selected_context_limit=5,
)

Settings.callback_manager = CallbackManager([handler])
response = query_engine.query("What is the refund policy?")
```

## Custom Conversion

Use `node_converter(node, index)` if your nodes expose non-standard fields.

```python
handler = ContextTraceLlamaIndexCallbackHandler(
    client=ct,
    node_converter=lambda node, index: {
        "chunk_id": node.node_id,
        "content": node.get_content(),
        "source": node.metadata.get("source"),
        "metadata": node.metadata,
        "relevance_score": getattr(node, "score", None),
    },
)
```

## Runnable Example

```bash
python examples/llamaindex_rag.py
```

The example uses mock nodes and local mode so it runs without external services.

