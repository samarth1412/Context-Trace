from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from contexttrace.capture import capture_rag_trace
from contexttrace.endpoint_eval import (
    EndpointCaller,
    _default_caller,
    _extract,
    _normalize_chunks,
    _normalize_citations,
    _render_body,
)
from contexttrace.verify.schema import RAGTrace


@dataclass(frozen=True)
class EndpointCapture:
    """A captured portable trace plus the raw endpoint response used to build it."""

    trace: RAGTrace
    response: dict[str, Any]
    request_body: dict[str, Any] | None


def capture_endpoint_trace(
    *,
    endpoint: str,
    query: str,
    method: str = "POST",
    headers: dict[str, str] | None = None,
    body_template: dict[str, Any] | None = None,
    input_key: str = "question",
    answer_path: str = "$.answer",
    contexts_path: str = "$.contexts",
    citations_path: str = "$.citations",
    metadata_path: str = "$.metadata",
    timeout: float = 30.0,
    caller: EndpointCaller | None = None,
) -> EndpointCapture:
    """Call a RAG endpoint once and convert the response to a portable verify trace."""

    if not str(endpoint or "").strip():
        raise ValueError("endpoint is required.")
    if not str(query or "").strip():
        raise ValueError("query is required.")

    resolved_method = method.upper()
    request_body = (
        _render_body(body_template, query=query)
        if body_template is not None
        else {input_key: query}
    )
    response = (caller or _default_caller)(
        endpoint,
        resolved_method,
        headers or {},
        request_body,
        timeout,
    )
    if not isinstance(response, dict):
        raise ValueError("RAG endpoint response must be a JSON object.")

    trace = _trace_from_response(
        response=response,
        query=query,
        answer_path=answer_path,
        contexts_path=contexts_path,
        citations_path=citations_path,
        metadata_path=metadata_path,
        metadata_defaults={
            "capture_source": "endpoint",
            "endpoint": endpoint,
            "method": resolved_method,
        },
    )
    return EndpointCapture(trace=trace, response=response, request_body=request_body)


def capture_response_trace(
    *,
    response: dict[str, Any],
    query: str,
    response_source: str | None = None,
    answer_path: str = "$.answer",
    contexts_path: str = "$.contexts",
    citations_path: str = "$.citations",
    metadata_path: str = "$.metadata",
) -> EndpointCapture:
    """Convert a saved RAG endpoint response JSON object to a portable verify trace."""

    if not str(query or "").strip():
        raise ValueError("query is required.")
    if not isinstance(response, dict):
        raise ValueError("RAG endpoint response must be a JSON object.")

    trace = _trace_from_response(
        response=response,
        query=query,
        answer_path=answer_path,
        contexts_path=contexts_path,
        citations_path=citations_path,
        metadata_path=metadata_path,
        metadata_defaults={
            "capture_source": "saved_response",
            "response_source": response_source or "response_json",
        },
    )
    return EndpointCapture(trace=trace, response=response, request_body=None)


def _trace_from_response(
    *,
    response: dict[str, Any],
    query: str,
    answer_path: str,
    contexts_path: str,
    citations_path: str,
    metadata_path: str,
    metadata_defaults: dict[str, Any],
) -> RAGTrace:
    answer = _extract(response, answer_path)
    if answer is None or str(answer).strip() == "":
        raise ValueError("Endpoint response did not contain an answer at %s." % answer_path)

    raw_contexts = _extract(response, contexts_path)
    if raw_contexts is None:
        raw_contexts = _extract(response, "$.retrieved_chunks")
    chunks = _normalize_chunks(raw_contexts or [])

    raw_citations = _extract(response, citations_path) or []
    citations = _normalize_citations(
        raw_citations,
        answer=answer,
        chunks=chunks,
        default_to_first_chunk=False,
    )

    metadata = _metadata_from_response(
        response=response,
        metadata_path=metadata_path,
        metadata_defaults=metadata_defaults,
        answer_path=answer_path,
        contexts_path=contexts_path,
        citations_path=citations_path,
    )
    trace = capture_rag_trace(
        query=str(query),
        answer=str(answer),
        contexts=chunks,
        citations=citations,
        metadata=metadata,
    )
    return trace


def _metadata_from_response(
    *,
    response: dict[str, Any],
    metadata_path: str,
    metadata_defaults: dict[str, Any],
    answer_path: str,
    contexts_path: str,
    citations_path: str,
) -> dict[str, Any]:
    extracted = _extract(response, metadata_path) if metadata_path else None
    metadata = dict(extracted) if isinstance(extracted, dict) else {}
    for key, value in metadata_defaults.items():
        metadata.setdefault(key, value)
    metadata.setdefault("answer_path", answer_path)
    metadata.setdefault("contexts_path", contexts_path)
    metadata.setdefault("citations_path", citations_path)
    return metadata
