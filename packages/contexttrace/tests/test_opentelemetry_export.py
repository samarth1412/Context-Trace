from contexttrace import OpenTelemetryExporter


class MockSpan:
    def __init__(self):
        self.attributes = {}
        self.events = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def set_attribute(self, key, value):
        self.attributes[key] = value

    def add_event(self, name, attributes):
        self.events.append((name, attributes))


class MockTracer:
    def __init__(self):
        self.spans = []
        self.span = None

    def start_as_current_span(self, name):
        span = MockSpan()
        span.name = name
        self.spans.append(span)
        if self.span is None:
            self.span = span
        return span


def test_opentelemetry_exporter_writes_span_attributes_and_events():
    tracer = MockTracer()
    exporter = OpenTelemetryExporter(enabled=True, tracer=tracer)

    exported = exporter.export_trace(
        {
            "id": "trace_123",
            "project": "support-rag",
            "query": "What is the refund policy?",
            "chunks": [{"chunk_id": "chunk_12", "source": "refund.md", "selected": True}],
            "answer": {"model": "gpt-4.1-mini", "usage": {"prompt_tokens": 90, "completion_tokens": 30, "total_tokens": 120}},
            "citation_checks": [
                {
                    "claim": "Refunds are available within 30 days.",
                    "source_chunk_id": "chunk_12",
                    "support_status": "directly_supported",
                    "support_score": 0.97,
                }
            ],
            "agent_events": [{"event_type": "tool_call", "name": "search", "latency_ms": 10}],
        }
    )

    assert "contexttrace.trace" in exported
    assert "contexttrace.retrieval" in exported
    assert "contexttrace.answer_span" in exported
    assert "contexttrace.verify" in exported
    assert "contexttrace.agent_event_span" in exported
    assert tracer.span.attributes["contexttrace.trace_id"] == "trace_123"
    assert tracer.span.attributes["gen_ai.operation.name"] == "invoke_workflow"
    event_names = [name for name, _attributes in tracer.span.events]
    assert "contexttrace.chunk" in event_names
    assert "contexttrace.answer" in event_names
    assert "contexttrace.citation_check" in event_names
    assert "contexttrace.agent_event" in event_names

    spans_by_name = {span.name: span for span in tracer.spans}
    assert spans_by_name["contexttrace.retrieval"].attributes["gen_ai.operation.name"] == "retrieval"
    assert spans_by_name["contexttrace.retrieval"].attributes["openinference.span.kind"] == "RETRIEVER"
    assert spans_by_name["chat gpt-4.1-mini"].attributes["openinference.span.kind"] == "LLM"
    assert spans_by_name["chat gpt-4.1-mini"].attributes["gen_ai.usage.total_tokens"] == 120
    assert spans_by_name["contexttrace.verify"].attributes["openinference.span.kind"] == "EVALUATOR"
    assert spans_by_name["execute_tool search"].attributes["openinference.span.kind"] == "TOOL"


def test_opentelemetry_exporter_noops_when_disabled():
    tracer = MockTracer()
    exporter = OpenTelemetryExporter(enabled=False, tracer=tracer)

    assert exporter.export_trace({"id": "trace_123"}) == []
    assert tracer.spans == []
