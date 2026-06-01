"""Runnable LangGraph-style agent tracing example.

The beta adapter is framework-adjacent: use it around LangGraph nodes/tools or
wrap node functions directly. This example runs without LangGraph installed.
"""

from __future__ import annotations

from contexttrace import ContextTrace, ContextTraceLangGraphTracer


def policy_node(state: dict) -> dict:
    return {"next": "policy_tool", "query": state["query"]}


def main() -> None:
    ct = ContextTrace(mode="local", project="langgraph-agent")
    tracer = ContextTraceLangGraphTracer(
        client=ct,
        trace_metadata={"environment": "local", "framework": "langgraph"},
    )

    tracer.start_trace("Resolve the refund ticket.")
    wrapped_policy_node = tracer.wrap_node("policy_planner", policy_node)
    plan = wrapped_policy_node({"query": "Resolve the refund ticket."})

    tracer.on_tool_start("policy_tool", {"query": plan["query"]})
    tracer.on_tool_end(
        "policy_tool",
        {"matches": [{"chunk_id": "refund_policy_1", "content": "Refunds are available within 30 days."}]},
    )
    trace = tracer.end_trace(answer="Refunds are available within 30 days.")

    print("LangGraph-style trace written locally:", trace.trace_id if trace else "unknown")


if __name__ == "__main__":
    main()

