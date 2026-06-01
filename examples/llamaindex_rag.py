"""Runnable LlamaIndex-style RAG tracing example.

This example uses mock nodes so it can run without LlamaIndex installed:

    python examples/llamaindex_rag.py

In a real LlamaIndex app, register ContextTraceLlamaIndexCallbackHandler with
`Settings.callback_manager = CallbackManager([handler])`.
"""

from __future__ import annotations

from contexttrace import ContextTrace, ContextTraceLlamaIndexCallbackHandler


class MockNode:
    def __init__(self, text: str, metadata: dict, node_id: str):
        self.text = text
        self.metadata = metadata
        self.node_id = node_id

    def get_content(self) -> str:
        return self.text


class MockNodeWithScore:
    def __init__(self, node: MockNode, score: float):
        self.node = node
        self.score = score


class MockResponse:
    def __init__(self, response: str, source_nodes: list[MockNodeWithScore]):
        self.response = response
        self.source_nodes = source_nodes

    def __str__(self) -> str:
        return self.response


def main() -> None:
    ct = ContextTrace(mode="local", project="support-rag")
    handler = ContextTraceLlamaIndexCallbackHandler(
        client=ct,
        trace_metadata={"environment": "local", "pipeline": "llamaindex-rag"},
    )

    nodes = [
        MockNodeWithScore(
            MockNode(
                "Customers may request refunds within 30 calendar days.",
                {"chunk_id": "refund_policy_1", "source": "refund_policy.md"},
                "node_1",
            ),
            0.94,
        )
    ]
    handler.on_event_start("query", {"query_str": "What is the refund policy?"}, event_id="query_1")
    handler.on_event_end("retrieve", {"nodes": nodes}, event_id="retrieve_1")
    handler.on_event_end(
        "query",
        {"response": MockResponse("Refunds are available within 30 calendar days.", nodes)},
        event_id="query_1",
    )

    trace_id = handler.trace.trace_id if handler.trace else "unknown"
    print(f"LlamaIndex-style trace written locally: {trace_id}")


if __name__ == "__main__":
    main()

