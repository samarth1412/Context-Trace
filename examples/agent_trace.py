"""Trace a simple tool-using agent with ContextTrace.

Run the API first:

    docker compose up -d postgres qdrant
    cd apps/api
    alembic upgrade head
    uvicorn app.main:app --reload
"""

from contexttrace import ContextTrace


def lookup_refund_policy(query):
    return {
        "chunk_id": "refund_policy_1",
        "content": "Customers can request refunds within 30 days of purchase.",
        "source": "refund-policy.md",
        "relevance_score": 0.94,
    }


def main() -> None:
    query = "Resolve the customer refund ticket."
    ct = ContextTrace(
        api_key="ctx_test",
        project="support-agent",
        base_url="http://localhost:8000",
    )

    with ct.trace(query=query, metadata={"example": "agent_trace", "trace_kind": "agent"}) as trace:
        trace.log_planner_step(
            "plan_refund_lookup",
            input_json={"query": query},
            output_json={"next": "lookup_refund_policy"},
        )

        trace.log_tool_call(
            "lookup_refund_policy",
            input_json={"query": "refund policy"},
            metadata={"tool_type": "retriever"},
        )
        chunk = lookup_refund_policy("refund policy")
        trace.log_tool_result(
            "lookup_refund_policy",
            output_json={"chunk_id": chunk["chunk_id"], "matched": True},
            latency_ms=42,
        )

        trace.log_memory_read(
            "customer_profile",
            input_json={"customer_id": "cust_123"},
            output_json={"tier": "pro", "region": "us"},
        )
        trace.log_memory_write(
            "ticket_summary",
            input_json={"ticket_id": "ticket_123", "status": "answered"},
        )

        trace.log_retrieval([chunk], retriever_name="agent-policy-tool")
        trace.log_context([chunk])
        trace.log_answer(
            "The customer can request a refund within 30 days of purchase.",
            model="agent-example",
            usage={"total_tokens": 180},
        )
        trace.log_citations(
            [
                {
                    "claim": "The customer can request a refund within 30 days of purchase.",
                    "source_chunk_id": "refund_policy_1",
                }
            ]
        )
        trace.evaluate()

    print("Trace:", trace.trace_id)


if __name__ == "__main__":
    main()
