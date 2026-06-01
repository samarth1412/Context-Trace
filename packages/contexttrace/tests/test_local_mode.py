from contexttrace import ContextTrace


class UploadTransport:
    def __init__(self):
        self.calls = []
        self.trace_count = 0

    def post(self, path, payload=None):
        self.calls.append(("POST", path, payload or {}))
        if path == "/v1/traces/start":
            self.trace_count += 1
            return {"trace_id": "remote_trace_%s" % self.trace_count, "project_id": "project_1"}
        return {"trace_id": "remote_trace_%s" % self.trace_count, "accepted": 1}

    def get(self, path):
        self.calls.append(("GET", path, {}))
        return {}


def test_local_mode_stores_traces_and_exports_report(tmp_path):
    report_path = tmp_path / "report.html"
    ct = ContextTrace(
        mode="local",
        project="support-rag",
        local_store_dir=str(tmp_path / "store"),
    )

    with ct.trace(query="What is the refund policy?") as trace:
        trace.log_retrieval(
            [
                {
                    "chunk_id": "chunk_1",
                    "content": "Refunds are available within 30 days.",
                    "source": "refund-policy.md",
                }
            ]
        )
        trace.log_context(chunk_ids=["chunk_1"])
        trace.log_answer("Refunds are available within 30 days.", usage={"total_tokens": 42})
        trace.log_citations(
            [
                {
                    "claim": "Refunds are available within 30 days.",
                    "source_chunk_id": "chunk_1",
                }
            ]
        )
        result = trace.evaluate()
        written = trace.export_report(path=str(report_path))

    traces = ct.list_traces()
    last_trace = ct.last_trace()

    assert result["failure"]["failure_type"] == "no_failure_detected"
    assert written == str(report_path)
    assert report_path.exists()
    assert "Refunds are available within 30 days." in report_path.read_text(encoding="utf-8")
    assert len(traces) == 1
    assert traces[0]["id"] == trace.trace_id
    assert last_trace["id"] == trace.trace_id
    assert (tmp_path / "store" / "contexttrace.db").exists()
    assert last_trace["citation_checks"][0]["support_status"] == "directly_supported"
    assert last_trace["evaluation"]["failure"]["failure_type"] == "no_failure_detected"


def test_default_client_uses_local_sqlite_without_network(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    ct = ContextTrace(project="support-rag")

    with ct.trace(query="What is the refund policy?") as trace:
        trace.log_retrieval([{"chunk_id": "chunk_1", "content": "Refunds are available within 30 days."}])
        trace.log_context(chunk_ids=["chunk_1"])
        trace.log_answer("Refunds are available within 30 days.")
        trace.log_citations([{"claim": "Refunds are available within 30 days.", "source_chunk_id": "chunk_1"}])
        trace.evaluate()

    assert (tmp_path / ".contexttrace" / "contexttrace.db").exists()
    assert ct.last_trace()["id"] == trace.trace_id


def test_local_text_redaction_options(tmp_path):
    ct = ContextTrace(
        project="privacy-rag",
        storage_path=str(tmp_path / "contexttrace.db"),
        log_chunk_text=False,
        log_answer_text=False,
    )

    with ct.trace(query="Private query") as trace:
        trace.log_retrieval([{"chunk_id": "chunk_1", "content": "Sensitive chunk text."}])
        trace.log_answer("Sensitive answer text.")

    fetched = trace.fetch()
    assert fetched["chunks"][0]["content"] == "[chunk text redacted]"
    assert fetched["answer"]["answer"] == "[answer text redacted]"


def test_batch_upload_replays_local_traces(tmp_path):
    ct = ContextTrace(
        mode="local",
        project="support-rag",
        local_store_dir=str(tmp_path / "store"),
    )

    with ct.trace(query="What is the refund policy?") as trace:
        trace.log_retrieval(
            [{"chunk_id": "chunk_1", "content": "Refunds are available within 30 days."}]
        )
        trace.log_context(chunk_ids=["chunk_1"])
        trace.log_answer("Refunds are available within 30 days.")
        trace.log_citations(
            [{"claim": "Refunds are available within 30 days.", "source_chunk_id": "chunk_1"}]
        )

    target = UploadTransport()
    result = ct.upload_traces(trace_ids=[trace.trace_id], target_transport=target)

    assert result["uploaded"] == 1
    assert result["traces"][0]["local_trace_id"] == trace.trace_id
    assert target.calls[0][1] == "/v1/traces/start"
    assert target.calls[1][1] == "/v1/traces/remote_trace_1/retrieval"
    assert target.calls[-1][1] == "/v1/traces/remote_trace_1/citations"


def test_local_mode_stores_agent_events(tmp_path):
    ct = ContextTrace(
        mode="local",
        project="agent-support",
        local_store_dir=str(tmp_path / "store"),
    )

    with ct.trace(query="Resolve the refund ticket.") as trace:
        trace.log_planner_step("plan_refund_lookup", output_json={"next": "policy_search"})
        trace.log_tool_call("policy_search", input_json={"query": "refund policy"})
        trace.log_agent_error("Policy search timed out.", name="policy_search")
        events = trace.list_agent_events()
        fetched = trace.fetch()

    assert [event["event_type"] for event in events["events"]] == [
        "planner_step",
        "tool_call",
        "error",
    ]
    assert fetched["agent_events"][-1]["error_message"] == "Policy search timed out."
