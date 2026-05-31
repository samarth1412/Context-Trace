"""Generate a local HTML report from a traced RAG run."""

from contexttrace import ContextTrace


def main() -> None:
    ct = ContextTrace(
        api_key="ctx_test",
        project="support-rag",
        base_url="http://localhost:8000",
    )

    with ct.trace(query="What is the refund policy?", metadata={"example": "local_report"}) as trace:
        trace.log_retrieval(
            [
                {
                    "chunk_id": "chunk_refunds_1",
                    "content": "Customers can request refunds within 30 days of purchase.",
                    "source": "refund-policy.md",
                    "relevance_score": 0.95,
                }
            ]
        )
        trace.log_context(chunk_ids=["chunk_refunds_1"])
        trace.log_answer(
            "Refunds are available within 30 days of purchase.",
            model="example-llm",
            usage={"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120},
            metadata={"latency_ms": 250},
        )
        trace.log_citations(
            [
                {
                    "claim": "Refunds are available within 30 days of purchase.",
                    "source_chunk_id": "chunk_refunds_1",
                }
            ]
        )
        trace.evaluate()
        report_path = trace.export_report(path="examples/local_report.html")

    print("Wrote %s" % report_path)


if __name__ == "__main__":
    main()
