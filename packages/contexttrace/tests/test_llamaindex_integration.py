from contexttrace import ContextTrace, ContextTraceLlamaIndexCallbackHandler
from contexttrace.integrations.llamaindex import llamaindex_node_to_chunk


class FakeTransport:
    def __init__(self):
        self.calls = []

    def post(self, path, payload=None):
        self.calls.append(("POST", path, payload or {}))
        if path == "/v1/traces/start":
            return {"trace_id": "trace_llamaindex", "project_id": "project_123"}
        return {"trace_id": "trace_llamaindex", "accepted": 1}

    def get(self, path):
        self.calls.append(("GET", path, {}))
        return {"id": "trace_llamaindex"}


class MockNode:
    def __init__(self, text, metadata=None, node_id="node_1"):
        self.text = text
        self.metadata = metadata or {}
        self.node_id = node_id

    def get_content(self):
        return self.text


class MockNodeWithScore:
    def __init__(self, node, score):
        self.node = node
        self.score = score


class MockResponse:
    def __init__(self, response, source_nodes):
        self.response = response
        self.source_nodes = source_nodes

    def __str__(self):
        return self.response


def test_llamaindex_node_to_chunk_converts_node_with_score():
    node = MockNode(
        "Refunds are available within 30 days.",
        metadata={"source": "refund-policy.md", "chunk_id": "chunk_12"},
    )
    node_with_score = MockNodeWithScore(node, 0.94)

    chunk = llamaindex_node_to_chunk(node_with_score)

    assert chunk == {
        "chunk_id": "chunk_12",
        "content": "Refunds are available within 30 days.",
        "source": "refund-policy.md",
        "metadata": {"source": "refund-policy.md", "chunk_id": "chunk_12"},
        "relevance_score": 0.94,
    }


def test_llamaindex_callback_logs_query_retrieved_nodes_source_nodes_and_response():
    transport = FakeTransport()
    client = ContextTrace(api_key="ctx_test", project="support-rag", transport=transport)
    handler = ContextTraceLlamaIndexCallbackHandler(
        client=client,
        trace_metadata={"suite": "unit", "project_area": "refunds"},
    )

    retrieved_nodes = [
        MockNodeWithScore(
            MockNode(
                "Customers can request refunds within 30 days.",
                metadata={"source": "refund-policy.md", "chunk_id": "chunk_12"},
                node_id="node_12",
            ),
            0.91,
        ),
        MockNodeWithScore(
            MockNode(
                "Shipping time depends on destination.",
                metadata={"source": "shipping.md", "chunk_id": "chunk_13"},
                node_id="node_13",
            ),
            0.42,
        ),
    ]
    source_nodes = [retrieved_nodes[0]]

    handler.on_event_start(
        "query",
        {"query_str": "What is the refund policy?"},
        event_id="query_event",
        parent_id="root",
        metadata={"tenant": "test"},
    )
    handler.on_event_end(
        "retrieve",
        {"nodes": retrieved_nodes},
        event_id="retrieve_event",
    )
    handler.on_event_end(
        "query",
        {"response": MockResponse("Refunds are available within 30 days.", source_nodes)},
        event_id="query_event",
    )

    assert transport.calls[0] == (
        "POST",
        "/v1/traces/start",
        {
            "project": "support-rag",
            "query": "What is the refund policy?",
            "metadata": {
                "suite": "unit",
                "project_area": "refunds",
                "integration": "llamaindex",
                "start_event": "query_start",
                "llamaindex": {
                    "event_type": "query",
                    "event_id": "query_event",
                    "parent_id": "root",
                    "metadata": {"tenant": "test"},
                    "payload_keys": ["query_str"],
                },
            },
        },
    )

    retrieval_call = transport.calls[1]
    assert retrieval_call[1] == "/v1/traces/trace_llamaindex/retrieval"
    assert len(retrieval_call[2]["chunks"]) == 2
    assert retrieval_call[2]["chunks"][0]["chunk_id"] == "chunk_12"

    context_call = transport.calls[2]
    assert context_call[1] == "/v1/traces/trace_llamaindex/context"
    assert len(context_call[2]["chunks"]) == 1
    assert context_call[2]["chunks"][0]["chunk_id"] == "chunk_12"
    assert context_call[2]["metadata"]["source"] == "llamaindex_source_nodes"

    answer_call = transport.calls[3]
    assert answer_call[1] == "/v1/traces/trace_llamaindex/answer"
    assert answer_call[2]["answer"] == "Refunds are available within 30 days."
    assert answer_call[2]["metadata"]["source_node_count"] == 1
    assert answer_call[2]["metadata"]["retrieved_node_count"] == 2
    assert answer_call[2]["metadata"]["latency_ms"] >= 0


def test_llamaindex_adapter_manual_methods_work_without_callback_manager():
    transport = FakeTransport()
    client = ContextTrace(api_key="ctx_test", project="support-rag", transport=transport)
    handler = ContextTraceLlamaIndexCallbackHandler(client=client)

    handler.trace_query("Can I return final-sale items?", metadata={"mode": "manual"})
    handler.trace_retrieved_nodes(
        [
            MockNodeWithScore(
                MockNode("Final sale items are not refundable.", metadata={"id": "policy_1"}),
                0.97,
            )
        ]
    )
    handler.trace_response(
        {
            "response": "Final-sale items are not refundable.",
            "source_nodes": [
                MockNodeWithScore(
                    MockNode("Final sale items are not refundable.", metadata={"id": "policy_1"}),
                    0.97,
                )
            ],
        }
    )

    assert transport.calls[0][1] == "/v1/traces/start"
    assert transport.calls[0][2]["query"] == "Can I return final-sale items?"
    assert transport.calls[1][1] == "/v1/traces/trace_llamaindex/retrieval"
    assert transport.calls[2][1] == "/v1/traces/trace_llamaindex/context"
    assert transport.calls[3][1] == "/v1/traces/trace_llamaindex/answer"


def test_llamaindex_callback_supports_custom_extractors_and_context_limit():
    transport = FakeTransport()
    client = ContextTrace(api_key="ctx_test", project="support-rag", transport=transport)
    handler = ContextTraceLlamaIndexCallbackHandler(
        client=client,
        selected_context_limit=1,
        query_extractor=lambda payload: payload["messages"][-1],
        response_extractor=lambda response: response["final_text"],
        node_converter=lambda node, index: {
            "chunk_id": f"node_{index}",
            "content": node.node.get_content(),
            "source": node.node.metadata.get("source"),
            "metadata": node.node.metadata,
            "relevance_score": node.score,
        },
    )
    nodes = [
        MockNodeWithScore(MockNode("First source.", metadata={"source": "a.md"}), 0.9),
        MockNodeWithScore(MockNode("Second source.", metadata={"source": "b.md"}), 0.8),
    ]

    handler.on_event_start("query", {"messages": ["Custom query?"]})
    handler.on_event_end("retrieve", {"nodes": nodes})
    handler.trace_response({"final_text": "Custom answer.", "source_nodes": nodes})

    assert transport.calls[0][2]["query"] == "Custom query?"
    assert transport.calls[1][2]["chunks"][0]["chunk_id"] == "node_0"
    assert len(transport.calls[2][2]["chunks"]) == 1
    assert transport.calls[3][2]["answer"] == "Custom answer."
