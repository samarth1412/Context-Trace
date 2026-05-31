"""Trace a custom RAG pipeline with ContextTrace.

Run the API first:

    docker compose up -d postgres qdrant
    cd apps/api
    alembic upgrade head
    uvicorn app.main:app --reload
"""

from contexttrace import ContextTrace


class ToyRetriever:
    def search(self, query):
        return [
            {
                "chunk_id": "chunk_refunds_1",
                "content": "Customers can request refunds within 30 days of purchase.",
                "source": "refund-policy.md",
                "metadata": {"section": "refunds"},
                "relevance_score": 0.93,
            },
            {
                "chunk_id": "chunk_shipping_1",
                "content": "Shipping time depends on the destination and carrier.",
                "source": "shipping.md",
                "metadata": {"section": "shipping"},
                "relevance_score": 0.41,
            },
        ]


class ToyLLM:
    def generate(self, query, context):
        return "Refunds are available within 30 days of purchase."


def main() -> None:
    query = "What is the refund policy?"
    retriever = ToyRetriever()
    llm = ToyLLM()
    ct = ContextTrace(
        api_key="ctx_test",
        project="support-rag",
        base_url="http://localhost:8000",
    )

    with ct.trace(query=query, metadata={"example": "custom_rag"}) as trace:
        chunks = retriever.search(query)
        trace.log_retrieval(chunks, retriever_name="toy-retriever")

        selected_context = chunks[:1]
        trace.log_context(selected_context)

        answer = llm.generate(query, selected_context)
        trace.log_answer(answer, model="toy-llm", usage={"total_tokens": 128})

        trace.log_citations(
            [
                {
                    "claim": "Refunds are available within 30 days of purchase.",
                    "source_chunk_id": "chunk_refunds_1",
                }
            ]
        )

        evaluation = trace.evaluate()
        print(evaluation)


if __name__ == "__main__":
    main()
