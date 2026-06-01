from __future__ import annotations

import os
from typing import Any, Optional


class OpenTelemetryExporter:
    """Optional OpenTelemetry exporter for ContextTrace trace dictionaries."""

    def __init__(
        self,
        *,
        enabled: Optional[bool] = None,
        tracer: Any = None,
        tracer_name: str = "contexttrace",
    ) -> None:
        self.enabled = _enabled(enabled)
        self.tracer = tracer if tracer is not None else self._load_tracer(tracer_name)

    def export_trace(self, trace: dict[str, Any]) -> list[str]:
        if not self.enabled or self.tracer is None:
            return []

        exported = []
        with self.tracer.start_as_current_span("contexttrace.trace") as span:
            _set(span, "contexttrace.trace_id", trace.get("id") or trace.get("trace_id"))
            _set(span, "contexttrace.project", trace.get("project") or trace.get("project_id"))
            _set(span, "contexttrace.query", trace.get("query"))
            failure = (trace.get("evaluation") or {}).get("failure") or trace.get("failure") or {}
            _set(span, "contexttrace.failure_type", failure.get("failure_type") or failure.get("type"))
            exported.append("contexttrace.trace")

            for chunk in trace.get("chunks") or []:
                _event(
                    span,
                    "contexttrace.chunk",
                    {
                        "chunk_id": chunk.get("chunk_id"),
                        "source": chunk.get("source"),
                        "selected": bool(chunk.get("selected")),
                    },
                )
                exported.append("contexttrace.chunk")

            answer = trace.get("answer") or {}
            if answer:
                _event(
                    span,
                    "contexttrace.answer",
                    {
                        "model": answer.get("model"),
                        "total_tokens": (answer.get("usage") or {}).get("total_tokens"),
                    },
                )
                exported.append("contexttrace.answer")

            for check in trace.get("citation_checks") or []:
                _event(
                    span,
                    "contexttrace.citation_check",
                    {
                        "claim": check.get("claim"),
                        "source_chunk_id": check.get("source_chunk_id"),
                        "support_status": check.get("support_status") or check.get("verdict"),
                        "support_score": check.get("support_score"),
                    },
                )
                exported.append("contexttrace.citation_check")

            for event in trace.get("agent_events") or []:
                _event(
                    span,
                    "contexttrace.agent_event",
                    {
                        "event_type": event.get("event_type"),
                        "name": event.get("name"),
                        "latency_ms": event.get("latency_ms"),
                        "error": event.get("error_message"),
                    },
                )
                exported.append("contexttrace.agent_event")
        return exported

    def _load_tracer(self, tracer_name: str) -> Any:
        if not self.enabled:
            return None
        try:
            from opentelemetry import trace as otel_trace
        except Exception:
            return None
        return otel_trace.get_tracer(tracer_name)


def export_contexttrace_trace(trace: dict[str, Any], *, enabled: Optional[bool] = None, tracer: Any = None) -> list[str]:
    return OpenTelemetryExporter(enabled=enabled, tracer=tracer).export_trace(trace)


def _enabled(value: Optional[bool]) -> bool:
    if value is not None:
        return value
    return os.getenv("CONTEXTTRACE_OTEL_ENABLED", "").lower() in {"1", "true", "yes", "on"}


def _set(span: Any, key: str, value: Any) -> None:
    if value is not None:
        span.set_attribute(key, value)


def _event(span: Any, name: str, attributes: dict[str, Any]) -> None:
    span.add_event(name, {key: value for key, value in attributes.items() if value is not None})

