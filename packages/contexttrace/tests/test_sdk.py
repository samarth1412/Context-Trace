from contexttrace import ContextTrace


class FakeTransport:
    def __init__(self):
        self.calls = []

    def post(self, path, payload=None):
        self.calls.append(("POST", path, payload or {}))
        if path == "/v1/traces/start":
            return {"trace_id": "trace_123", "project_id": "project_123"}
        if path.endswith("/evaluate"):
            return {
                "citation_checks": [
                    {
                        "claim": "Refunds are available within 30 days.",
                        "source_chunk_id": "chunk_12",
                        "verdict": "directly_supported",
                        "support_score": 0.98,
                        "reason": "The source says refunds are available within 30 days.",
                    }
                ],
                "failure": {
                    "failure_type": "no_failure_detected",
                    "severity": "none",
                    "root_cause": "All cited claims are supported.",
                    "suggested_fix": "No fix required.",
                },
            }
        return {"trace_id": "trace_123", "accepted": 1}

    def get(self, path):
        self.calls.append(("GET", path, {}))
        return {"id": "trace_123"}


def test_sdk_trace_context_posts_expected_payloads():
    transport = FakeTransport()
    ct = ContextTrace(api_key="ctx_test", project="support-rag", transport=transport)

    with ct.trace(query="What is the refund policy?") as trace:
        trace.log_retrieval(
            [
                {
                    "id": "chunk_12",
                    "text": "Customers can request refunds within 30 days.",
                    "source": "refund-policy.md",
                    "score": 0.91,
                }
            ],
            retriever_name="test-retriever",
        )
        trace.log_context(chunk_ids=["chunk_12"])
        trace.log_answer(
            "Refunds are available within 30 days.",
            model="gpt-4.1-mini",
            usage={"total_tokens": 1200},
        )
        trace.log_citations(
            [
                {
                    "claim": "Refunds are available within 30 days.",
                    "source_chunk_id": "chunk_12",
                }
            ]
        )
        result = trace.evaluate()

    assert result["failure"]["failure_type"] == "no_failure_detected"
    assert transport.calls[0] == (
        "POST",
        "/v1/traces/start",
        {
            "project": "support-rag",
            "query": "What is the refund policy?",
            "metadata": {},
        },
    )
    retrieval_payload = transport.calls[1][2]
    assert retrieval_payload["chunks"][0]["chunk_id"] == "chunk_12"
    assert retrieval_payload["chunks"][0]["content"] == (
        "Customers can request refunds within 30 days."
    )
    assert retrieval_payload["chunks"][0]["relevance_score"] == 0.91
    assert transport.calls[-1][1] == "/v1/traces/trace_123/evaluate"


def test_sdk_requires_context_manager_before_logging():
    ct = ContextTrace(api_key="ctx_test", project="support-rag", transport=FakeTransport())
    trace = ct.trace(query="What is the refund policy?")

    try:
        trace.log_answer("Refunds are available within 30 days.")
    except RuntimeError as exc:
        assert "Trace has not started" in str(exc)
    else:
        raise AssertionError("Expected RuntimeError")
