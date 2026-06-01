# LangGraph Beta Integration

`ContextTraceLangGraphTracer` is a lightweight beta adapter for LangGraph-style agent workflows. It logs graph node starts/ends, tool calls/results, errors, and final answers into the ContextTrace agent timeline.

## Install

```bash
pip install "contexttrace[langgraph]"
```

## Usage

```python
from contexttrace import ContextTrace, ContextTraceLangGraphTracer

ct = ContextTrace(mode="local", project="agent-rag")
tracer = ContextTraceLangGraphTracer(client=ct)

tracer.start_trace("Resolve the refund ticket.")
tracer.on_node_start("planner", {"query": "Resolve the refund ticket."})
tracer.on_node_end("planner", {"next": "policy_tool"})
tracer.on_tool_start("policy_tool", {"query": "refund policy"})
tracer.on_tool_end("policy_tool", {"matches": 3})
tracer.end_trace(answer="Refunds are available within 30 days.")
```

## Wrapping Nodes

```python
def planner_node(state):
    return {"next": "policy_tool"}

planner_node = tracer.wrap_node("planner", planner_node)
```

The wrapper supports sync and async node functions. Exceptions are logged as agent timeline errors and then re-raised.

## Runnable Example

```bash
python examples/langgraph_agent_trace.py
```

