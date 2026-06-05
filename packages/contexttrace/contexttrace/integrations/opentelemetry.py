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
            _set(span, "gen_ai.operation.name", "invoke_workflow")
            _set(span, "openinference.span.kind", "CHAIN")
            failure = (trace.get("evaluation") or {}).get("failure") or trace.get("failure") or {}
            _set(span, "contexttrace.failure_type", failure.get("failure_type") or failure.get("type"))
            exported.append("contexttrace.trace")

            chunks = list(trace.get("chunks") or [])
            if chunks:
                with self.tracer.start_as_current_span("contexttrace.retrieval") as retrieval_span:
                    _set(retrieval_span, "gen_ai.operation.name", "retrieval")
                    _set(retrieval_span, "openinference.span.kind", "RETRIEVER")
                    _set(retrieval_span, "contexttrace.chunk_count", len(chunks))
                    _set(
                        retrieval_span,
                        "contexttrace.selected_chunk_count",
                        len([chunk for chunk in chunks if chunk.get("selected")]),
                    )
                    for chunk in chunks:
                        _event(retrieval_span, "contexttrace.chunk", _chunk_event_attributes(chunk))
                exported.append("contexttrace.retrieval")

            for chunk in chunks:
                _event(
                    span,
                    "contexttrace.chunk",
                    _chunk_event_attributes(chunk),
                )
                exported.append("contexttrace.chunk")

            answer = trace.get("answer") or {}
            if answer:
                model = answer.get("model")
                with self.tracer.start_as_current_span(
                    "chat %s" % model if model else "contexttrace.answer"
                ) as answer_span:
                    _set(answer_span, "gen_ai.operation.name", "chat")
                    _set(answer_span, "openinference.span.kind", "LLM")
                    _set(answer_span, "gen_ai.request.model", model)
                    _set(answer_span, "gen_ai.response.model", model)
                    _set(answer_span, "gen_ai.usage.input_tokens", (answer.get("usage") or {}).get("prompt_tokens"))
                    _set(answer_span, "gen_ai.usage.output_tokens", (answer.get("usage") or {}).get("completion_tokens"))
                    _set(answer_span, "gen_ai.usage.total_tokens", (answer.get("usage") or {}).get("total_tokens"))
                    _set(answer_span, "contexttrace.answer.redacted", _is_redacted(answer.get("answer")))
                exported.append("contexttrace.answer_span")
                _event(
                    span,
                    "contexttrace.answer",
                    {
                        "model": answer.get("model"),
                        "total_tokens": (answer.get("usage") or {}).get("total_tokens"),
                    },
                )
                exported.append("contexttrace.answer")

            citation_checks = list(trace.get("citation_checks") or [])
            if citation_checks:
                with self.tracer.start_as_current_span("contexttrace.verify") as verify_span:
                    _set(verify_span, "openinference.span.kind", "EVALUATOR")
                    _set(verify_span, "contexttrace.citation_check_count", len(citation_checks))
                    for check in citation_checks:
                        _event(verify_span, "contexttrace.citation_check", _citation_event_attributes(check))
                exported.append("contexttrace.verify")

            for check in citation_checks:
                _event(
                    span,
                    "contexttrace.citation_check",
                    _citation_event_attributes(check),
                )
                exported.append("contexttrace.citation_check")

            for event in trace.get("agent_events") or []:
                span_name = _agent_span_name(event)
                with self.tracer.start_as_current_span(span_name) as event_span:
                    _set(event_span, "gen_ai.operation.name", _agent_operation_name(event))
                    _set(event_span, "openinference.span.kind", _agent_span_kind(event))
                    _set(event_span, "gen_ai.tool.name", event.get("name") if _is_tool_event(event) else None)
                    _set(event_span, "contexttrace.agent_event.type", event.get("event_type"))
                    _set(event_span, "contexttrace.agent_event.name", event.get("name"))
                    _set(event_span, "contexttrace.latency_ms", event.get("latency_ms"))
                    _set(event_span, "contexttrace.error", event.get("error_message"))
                exported.append("contexttrace.agent_event_span")
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


def _chunk_event_attributes(chunk: dict[str, Any]) -> dict[str, Any]:
    return {
        "chunk_id": chunk.get("chunk_id"),
        "source": chunk.get("source"),
        "selected": bool(chunk.get("selected")),
        "relevance_score": chunk.get("relevance_score"),
    }


def _citation_event_attributes(check: dict[str, Any]) -> dict[str, Any]:
    return {
        "claim": check.get("claim"),
        "source_chunk_id": check.get("source_chunk_id"),
        "support_status": check.get("support_status") or check.get("verdict"),
        "support_score": check.get("support_score"),
    }


def _is_tool_event(event: dict[str, Any]) -> bool:
    return str(event.get("event_type") or "") in {"tool_call", "tool_result"}


def _agent_operation_name(event: dict[str, Any]) -> str:
    event_type = str(event.get("event_type") or "")
    if event_type in {"tool_call", "tool_result"}:
        return "execute_tool"
    if event_type in {"memory_read", "memory_write"}:
        return "retrieval"
    return "invoke_agent"


def _agent_span_kind(event: dict[str, Any]) -> str:
    event_type = str(event.get("event_type") or "")
    if event_type in {"tool_call", "tool_result"}:
        return "TOOL"
    if event_type in {"memory_read", "memory_write"}:
        return "RETRIEVER"
    return "AGENT"


def _agent_span_name(event: dict[str, Any]) -> str:
    operation = _agent_operation_name(event)
    name = event.get("name")
    return "%s %s" % (operation, name) if name else "contexttrace.agent_event"


def _is_redacted(value: Any) -> bool:
    return isinstance(value, str) and value.strip().lower().startswith("[") and "redacted" in value.lower()
