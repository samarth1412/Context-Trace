import asyncio

from contexttrace import ContextTrace, ContextTraceLangGraphTracer


class FakeTransport:
    def __init__(self):
        self.calls = []

    def post(self, path, payload=None):
        self.calls.append(("POST", path, payload or {}))
        if path == "/v1/traces/start":
            return {"trace_id": "trace_langgraph", "project_id": "project_123"}
        return {"trace_id": "trace_langgraph", "accepted": 1}

    def get(self, path):
        self.calls.append(("GET", path, {}))
        return {"id": "trace_langgraph"}


def test_langgraph_tracer_logs_node_tool_and_final_answer_events():
    transport = FakeTransport()
    client = ContextTrace(api_key="ctx_test", project="agent-rag", transport=transport)
    tracer = ContextTraceLangGraphTracer(client=client, trace_metadata={"suite": "unit"})

    tracer.start_trace("Resolve the refund ticket.")
    tracer.on_node_start("planner", {"query": "Resolve the refund ticket."})
    tracer.on_node_end("planner", {"next": "policy_tool"})
    tracer.on_tool_start("policy_tool", {"query": "refund policy"})
    tracer.on_tool_end("policy_tool", {"matches": 2})
    trace = tracer.end_trace(answer="Refunds are available within 30 days.")

    assert trace is not None
    assert transport.calls[0][1] == "/v1/traces/start"
    event_paths = [call[1] for call in transport.calls if call[1].endswith("/agent-events")]
    assert len(event_paths) == 5
    assert transport.calls[-2][1] == "/v1/traces/trace_langgraph/answer"
    assert transport.calls[-1][2]["event_type"] == "final_answer"


def test_langgraph_wrap_node_supports_sync_and_async_nodes():
    transport = FakeTransport()
    client = ContextTrace(api_key="ctx_test", project="agent-rag", transport=transport)
    tracer = ContextTraceLangGraphTracer(client=client)
    tracer.start_trace("Route the query.")

    def planner(state):
        return {"next": "retrieve", "query": state["query"]}

    async def retrieve(state):
        return {"chunks": 2, "query": state["query"]}

    wrapped_planner = tracer.wrap_node("planner", planner)
    wrapped_retrieve = tracer.wrap_node("retrieve", retrieve, event_type="retrieval")

    assert wrapped_planner({"query": "refund policy"})["next"] == "retrieve"
    assert asyncio.run(wrapped_retrieve({"query": "refund policy"}))["chunks"] == 2

    event_payloads = [call[2] for call in transport.calls if call[1].endswith("/agent-events")]
    assert event_payloads[0]["event_type"] == "planner_step"
    assert event_payloads[2]["event_type"] == "retrieval"

