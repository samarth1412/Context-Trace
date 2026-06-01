"""Runnable LangChain-style RAG tracing example.

This example uses small mock objects so it can run without LangChain installed:

    python examples/langchain_rag.py

In a real LangChain app, pass ContextTraceCallbackHandler in `config={"callbacks": [handler]}`.
"""

from __future__ import annotations

from contexttrace import ContextTrace, ContextTraceCallbackHandler


class MockDocument:
    def __init__(self, page_content: str, metadata: dict):
        self.page_content = page_content
        self.metadata = metadata


class MockLLMResponse:
    llm_output = {
        "model_name": "gpt-4.1-mini",
        "token_usage": {"prompt_tokens": 180, "completion_tokens": 40, "total_tokens": 220},
    }


def main() -> None:
    ct = ContextTrace(mode="local", project="support-rag")
    handler = ContextTraceCallbackHandler(
        client=ct,
        trace_metadata={"environment": "local", "pipeline": "langchain-rag"},
        selected_context_limit=2,
    )

    handler.on_chain_start({"name": "RetrievalQA"}, {"query": "What is the refund policy?"})
    handler.on_retriever_start({"name": "VectorStoreRetriever"}, "What is the refund policy?")
    handler.on_retriever_end(
        [
            MockDocument(
                "Customers may request refunds within 30 calendar days.",
                {"chunk_id": "refund_policy_1", "source": "refund_policy.md", "score": 0.94},
            ),
            MockDocument(
                "Final sale items and gift cards are not eligible for refunds.",
                {"chunk_id": "refund_policy_2", "source": "refund_policy.md", "score": 0.82},
            ),
        ]
    )
    handler.on_llm_end(MockLLMResponse())
    handler.on_chain_end(
        {
            "answer": "Refunds are available within 30 calendar days.",
            "citations": [
                {
                    "claim": "Refunds are available within 30 calendar days.",
                    "source_chunk_id": "refund_policy_1",
                }
            ],
        }
    )

    trace_id = handler.trace.trace_id if handler.trace else "unknown"
    print(f"LangChain-style trace written locally: {trace_id}")


if __name__ == "__main__":
    main()

