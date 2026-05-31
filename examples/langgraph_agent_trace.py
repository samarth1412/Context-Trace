"""Placeholder LangGraph agent tracing example.

The v1 agent event API can be called from LangGraph node hooks or callbacks:

    trace.log_planner_step(...)
    trace.log_tool_call(...)
    trace.log_tool_result(...)
    trace.log_memory_read(...)
    trace.log_memory_write(...)
    trace.log_agent_error(...)

Wire these calls around graph nodes that plan, call tools, read memory, write memory,
and produce final answers. A full LangGraph integration can wrap this pattern in a
callback adapter in a later task.
"""

from contexttrace import ContextTrace


def main() -> None:
    ct = ContextTrace(api_key="ctx_test", project="langgraph-agent")

    with ct.trace(query="Resolve the refund ticket.", metadata={"framework": "langgraph"}) as trace:
        trace.log_planner_step(
            "graph_plan",
            input_json={"query": "Resolve the refund ticket."},
            output_json={"next_node": "policy_tool"},
        )
        trace.log_tool_call("policy_tool", input_json={"query": "refund policy"})
        trace.log_tool_result("policy_tool", output_json={"result_count": 2})
        trace.log_answer("LangGraph placeholder answer.")

    print("Trace:", trace.trace_id)


if __name__ == "__main__":
    main()
