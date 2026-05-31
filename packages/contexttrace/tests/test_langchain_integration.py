from contexttrace import ContextTrace, ContextTraceCallbackHandler
from contexttrace.integrations.langchain import langchain_document_to_chunk


class FakeTransport:
    def __init__(self):
        self.calls = []

    def post(self, path, payload=None):
        self.calls.append(("POST", path, payload or {}))
        if path == "/v1/traces/start":
            return {"trace_id": "trace_langchain", "project_id": "project_123"}
        return {"trace_id": "trace_langchain", "accepted": 1}

    def get(self, path):
        self.calls.append(("GET", path, {}))
        return {"id": "trace_langchain"}


class MockDocument:
    def __init__(self, page_content, metadata=None, doc_id=None, score=None):
        self.page_content = page_content
        self.metadata = metadata or {}
        self.id = doc_id
        self.score = score


class MockLLMResponse:
    llm_output = {
        "model_name": "gpt-4.1-mini",
        "token_usage": {
            "prompt_tokens": 100,
            "completion_tokens": 20,
            "total_tokens": 120,
        },
    }


def test_langchain_document_to_chunk_converts_mock_document():
    document = MockDocument(
        "Refunds are available within 30 days.",
        metadata={
            "source": "refund-policy.md",
            "chunk_id": "chunk_12",
            "relevance_score": 0.93,
        },
    )

    chunk = langchain_document_to_chunk(document)

    assert chunk == {
        "chunk_id": "chunk_12",
        "content": "Refunds are available within 30 days.",
        "source": "refund-policy.md",
        "metadata": {
            "source": "refund-policy.md",
            "chunk_id": "chunk_12",
            "relevance_score": 0.93,
        },
        "relevance_score": 0.93,
    }


def test_callback_handler_logs_query_documents_answer_metadata_and_latency():
    transport = FakeTransport()
    client = ContextTrace(api_key="ctx_test", project="support-rag", transport=transport)
    handler = ContextTraceCallbackHandler(
        client=client,
        trace_metadata={"suite": "unit", "project_area": "refunds"},
    )

    handler.on_chain_start(
        {"name": "RetrievalQA"},
        {"query": "What is the refund policy?"},
        metadata={"tenant": "test"},
        tags=["rag", "support"],
        run_id="run_123",
    )
    handler.on_retriever_end(
        [
            MockDocument(
                "Customers can request refunds within 30 days.",
                metadata={"source": "refund-policy.md", "chunk_id": "chunk_12", "score": 0.91},
            ),
            MockDocument(
                "Shipping time depends on destination.",
                metadata={"source": "shipping.md", "chunk_id": "chunk_13", "score": 0.42},
            ),
        ]
    )
    handler.on_llm_end(MockLLMResponse())
    handler.on_chain_end({"answer": "Refunds are available within 30 days."})

    assert transport.calls[0] == (
        "POST",
        "/v1/traces/start",
        {
            "project": "support-rag",
            "query": "What is the refund policy?",
            "metadata": {
                "suite": "unit",
                "project_area": "refunds",
                "integration": "langchain",
                "start_event": "chain_start",
                "langchain": {
                    "serialized_name": "RetrievalQA",
                    "metadata": {"tenant": "test"},
                    "tags": ["rag", "support"],
                    "run_id": "run_123",
                },
            },
        },
    )

    retrieval_call = transport.calls[1]
    assert retrieval_call[1] == "/v1/traces/trace_langchain/retrieval"
    assert retrieval_call[2]["chunks"][0]["chunk_id"] == "chunk_12"
    assert retrieval_call[2]["chunks"][0]["content"] == (
        "Customers can request refunds within 30 days."
    )

    context_call = transport.calls[2]
    assert context_call[1] == "/v1/traces/trace_langchain/context"
    assert len(context_call[2]["chunks"]) == 2

    answer_call = transport.calls[3]
    assert answer_call[1] == "/v1/traces/trace_langchain/answer"
    assert answer_call[2]["answer"] == "Refunds are available within 30 days."
    assert answer_call[2]["model"] == "gpt-4.1-mini"
    assert answer_call[2]["usage"]["total_tokens"] == 120
    assert "latency_ms" in answer_call[2]["metadata"]
    assert answer_call[2]["metadata"]["latency_ms"] >= 0


def test_callback_can_start_from_retriever_query_and_limit_context():
    transport = FakeTransport()
    client = ContextTrace(api_key="ctx_test", project="support-rag", transport=transport)
    handler = ContextTraceCallbackHandler(client=client, selected_context_limit=1)

    handler.on_retriever_start({"id": ["langchain", "retrievers", "VectorStoreRetriever"]}, "Who can refund?")
    handler.on_retriever_end(
        [
            MockDocument("Refund policy text.", metadata={"id": "doc_1"}),
            MockDocument("Shipping policy text.", metadata={"id": "doc_2"}),
        ]
    )
    handler.on_chain_end({"output": "Customers can request refunds."})

    assert transport.calls[0][2]["query"] == "Who can refund?"
    assert transport.calls[2][1] == "/v1/traces/trace_langchain/context"
    assert len(transport.calls[2][2]["chunks"]) == 1
