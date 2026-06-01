from contexttrace import ContextTrace


class FakeTransport:
    def __init__(self):
        self.calls = []

    def post(self, path, payload=None):
        self.calls.append(("POST", path, payload or {}))
        if path == "/v1/traces/start":
            return {"trace_id": "trace_123", "project_id": "project_123"}
        if path == "/v1/eval-sets":
            return {"eval_set_id": "eval_123", "name": payload["name"]}
        if path.endswith("/questions"):
            return {
                "eval_set_id": "eval_123",
                "accepted": len(payload["questions"]),
                "questions": payload["questions"],
            }
        if path.endswith("/runs"):
            return {
                "eval_set_id": "eval_123",
                "avg_citation_support": 0.9,
                "unsupported_claim_rate": 0.1,
                "failure_type_distribution": {"no_failure_detected": 1},
                "worst_traces": [],
            }
        if path.endswith("/agent-events"):
            return {"trace_id": "trace_123", "event_id": "agent_event_123", "accepted": 1}
        if path == "/v1/projects/project_123/external-endpoints":
            return {"id": "endpoint_123", **payload}
        if path == "/v1/external-endpoints/endpoint_123/test":
            return {
                "endpoint_id": "endpoint_123",
                "trace_id": "trace_123",
                "mapped": {
                    "answer": "Refunds are available within 30 days.",
                    "retrieved_chunks": [],
                    "citations": [],
                    "usage": {},
                    "model": None,
                    "raw_response": {},
                },
            }
        if path == "/v1/external-endpoints/endpoint_123/run-eval":
            return {
                "endpoint_id": "endpoint_123",
                "eval_set_id": payload["eval_set_id"],
                "traces": [],
                "summary": {"evaluated_trace_count": 1},
            }
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
        return {
            "id": "trace_123",
            "project": "support-rag",
            "query": "What is the refund policy?",
            "metadata": {"latency_ms": 842},
            "status": "evaluated",
            "chunks": [
                {
                    "id": "chunk_db_12",
                    "chunk_id": "chunk_12",
                    "content": "Customers can request refunds within 30 days.",
                    "source": "refund-policy.md",
                    "metadata": {},
                    "relevance_score": 0.91,
                    "position": 0,
                    "selected": True,
                },
                {
                    "id": "chunk_db_13",
                    "chunk_id": "chunk_13",
                    "content": "Shipping time depends on destination.",
                    "source": "shipping.md",
                    "metadata": {},
                    "relevance_score": 0.42,
                    "position": 1,
                    "selected": False,
                },
            ],
            "answer": {
                "id": "answer_123",
                "answer": "Refunds are available within 30 days.",
                "model": "gpt-4.1-mini",
                "usage": {
                    "prompt_tokens": 1000,
                    "completion_tokens": 200,
                    "total_tokens": 1200,
                },
                "metadata": {},
            },
            "citation_checks": [
                {
                    "id": "check_123",
                    "claim": "Refunds are available within 30 days.",
                    "source_chunk_id": "chunk_12",
                    "support_status": "directly_supported",
                    "support_score": 0.98,
                    "rationale": "The source says refunds are available within 30 days.",
                }
            ],
            "agent_events": [
                {
                    "id": "agent_event_123",
                    "trace_id": "trace_123",
                    "event_type": "tool_call",
                    "name": "policy_search",
                    "input_json": {"query": "refund policy"},
                    "output_json": {},
                    "metadata_json": {},
                    "latency_ms": 12.5,
                    "error_message": None,
                    "created_at": "2026-05-31T12:00:00Z",
                }
            ],
            "evaluation": {
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
            },
            "created_at": "2026-05-31T12:00:00Z",
            "updated_at": "2026-05-31T12:00:01Z",
        }


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


def test_trace_export_report_creates_html_with_required_sections(tmp_path):
    transport = FakeTransport()
    ct = ContextTrace(api_key="ctx_test", project="support-rag", transport=transport)
    report_path = tmp_path / "report.html"

    with ct.trace(query="What is the refund policy?") as trace:
        written_path = trace.export_report(path=str(report_path))

    assert written_path == str(report_path)
    assert report_path.exists()

    html = report_path.read_text(encoding="utf-8")
    assert "ContextTrace Report" in html
    assert "Query" in html
    assert "What is the refund policy?" in html
    assert "Answer" in html
    assert "Refunds are available within 30 days." in html
    assert "Retrieved Chunks" in html
    assert "Selected Context" in html
    assert "Citation Checks" in html
    assert "directly_supported" in html
    assert "Failure Analysis" in html
    assert "Reliability Score" in html
    assert "Raw Metrics" in html
    assert "Component Scores" in html
    assert "no_failure_detected" in html
    assert "Severity" in html
    assert "Root Cause" in html
    assert "Suggested Fix" in html
    assert "Prompt Tokens" in html
    assert "1200" in html
    assert "842" in html
    assert transport.calls[-1] == ("GET", "/v1/traces/trace_123", {})


def test_sdk_eval_set_methods_post_expected_payloads():
    transport = FakeTransport()
    ct = ContextTrace(api_key="ctx_test", project="support-rag", transport=transport)

    eval_set = ct.create_eval_set("refund-policy-regression")
    questions = ct.add_eval_questions(
        eval_set["eval_set_id"],
        [
            {
                "query": "What is the refund policy?",
                "trace_id": "trace_123",
                "expected_answer": "Refunds are available within 30 days.",
            },
            "Can the answer cite refund evidence?",
        ],
    )
    summary = ct.evaluate_existing_traces(eval_set["eval_set_id"])

    assert eval_set["eval_set_id"] == "eval_123"
    assert questions["accepted"] == 2
    assert summary["avg_citation_support"] == 0.9
    assert transport.calls[-3] == (
        "POST",
        "/v1/eval-sets",
        {"name": "refund-policy-regression", "metadata": {}},
    )
    assert transport.calls[-2][1] == "/v1/eval-sets/eval_123/questions"
    assert transport.calls[-2][2]["questions"][0]["question"] == "What is the refund policy?"
    assert transport.calls[-2][2]["questions"][1]["question"] == (
        "Can the answer cite refund evidence?"
    )
    assert transport.calls[-1] == ("POST", "/v1/eval-sets/eval_123/runs", {})


def test_sdk_agent_event_methods_post_expected_payloads():
    transport = FakeTransport()
    ct = ContextTrace(api_key="ctx_test", project="support-rag", transport=transport)

    with ct.trace(query="Resolve the refund ticket.") as trace:
        planner = trace.log_planner_step(
            "plan_refund_lookup",
            input_json={"query": "Resolve the refund ticket."},
            output_json={"next": "policy_search"},
            latency_ms=8.0,
        )
        trace.log_tool_call(
            "policy_search",
            input_json={"query": "refund policy"},
            metadata={"tool_type": "retriever"},
        )
        trace.log_tool_result(
            "policy_search",
            output_json={"matches": 3},
            latency_ms=30.0,
        )
        trace.log_memory_read(output_json={"customer_tier": "pro"})
        trace.log_memory_write(input_json={"ticket_id": "ticket_123"})
        trace.log_agent_error("Policy search timed out.", name="policy_search")

    assert planner["event_id"] == "agent_event_123"
    assert transport.calls[1] == (
        "POST",
        "/v1/traces/trace_123/agent-events",
        {
            "event_type": "planner_step",
            "name": "plan_refund_lookup",
            "input_json": {"query": "Resolve the refund ticket."},
            "output_json": {"next": "policy_search"},
            "metadata_json": {},
            "latency_ms": 8.0,
            "error_message": None,
        },
    )
    event_types = [call[2]["event_type"] for call in transport.calls[1:]]
    assert event_types == [
        "planner_step",
        "tool_call",
        "tool_result",
        "memory_read",
        "memory_write",
        "error",
    ]
    assert transport.calls[-1][2]["error_message"] == "Policy search timed out."


def test_sdk_external_rag_endpoint_methods_post_expected_payloads():
    transport = FakeTransport()
    ct = ContextTrace(api_key="ctx_test", project="support-rag", transport=transport)

    endpoint = ct.register_rag_endpoint(
        project_id="project_123",
        name="support-api",
        url="https://rag.example/query",
        headers={"Authorization": "Bearer token"},
        body_template={"question": "{{query}}"},
        response_mapping={
            "answer": "$.answer",
            "citations": "$.sources",
            "retrieved_chunks": "$.contexts",
        },
    )
    test = ct.test_rag_endpoint(
        endpoint["id"],
        query="What is the refund policy?",
        metadata={"tenant": "support"},
    )
    run = ct.evaluate_rag_endpoint(endpoint["id"], eval_set_id="eval_123")

    assert endpoint["id"] == "endpoint_123"
    assert test["trace_id"] == "trace_123"
    assert run["summary"]["evaluated_trace_count"] == 1
    assert transport.calls[-3] == (
        "POST",
        "/v1/projects/project_123/external-endpoints",
        {
            "name": "support-api",
            "url": "https://rag.example/query",
            "method": "POST",
            "headers": {"Authorization": "Bearer token"},
            "body_template": {"question": "{{query}}"},
            "response_mapping": {
                "answer": "$.answer",
                "citations": "$.sources",
                "retrieved_chunks": "$.contexts",
            },
        },
    )
    assert transport.calls[-2] == (
        "POST",
        "/v1/external-endpoints/endpoint_123/test",
        {"query": "What is the refund policy?", "metadata": {"tenant": "support"}},
    )
    assert transport.calls[-1] == (
        "POST",
        "/v1/external-endpoints/endpoint_123/run-eval",
        {"eval_set_id": "eval_123"},
    )
