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
        self.span = MockSpan()

    def start_as_current_span(self, name):
        self.span.name = name
        return self.span


def test_opentelemetry_exporter_writes_span_attributes_and_events():
    tracer = MockTracer()
    exporter = OpenTelemetryExporter(enabled=True, tracer=tracer)

    exported = exporter.export_trace(
        {
            "id": "trace_123",
            "project": "support-rag",
            "query": "What is the refund policy?",
            "chunks": [{"chunk_id": "chunk_12", "source": "refund.md", "selected": True}],
            "answer": {"model": "gpt-4.1-mini", "usage": {"total_tokens": 120}},
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
    assert tracer.span.attributes["contexttrace.trace_id"] == "trace_123"
    event_names = [name for name, _attributes in tracer.span.events]
    assert "contexttrace.chunk" in event_names
    assert "contexttrace.answer" in event_names
    assert "contexttrace.citation_check" in event_names
    assert "contexttrace.agent_event" in event_names


def test_opentelemetry_exporter_noops_when_disabled():
    tracer = MockTracer()
    exporter = OpenTelemetryExporter(enabled=False, tracer=tracer)

    assert exporter.export_trace({"id": "trace_123"}) == []
    assert tracer.span.attributes == {}

