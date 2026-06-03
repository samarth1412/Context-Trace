from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


class VerificationInputError(ValueError):
    """Raised when a portable verification trace cannot be loaded."""


@dataclass(frozen=True)
class TraceContext:
    id: str
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "text": self.text,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class TraceCitation:
    claim: str
    source_id: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "claim": self.claim,
            "source_id": self.source_id,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class RAGTrace:
    query: str
    answer: str
    contexts: list[TraceContext]
    citations: list[TraceCitation] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "query": self.query,
            "answer": self.answer,
            "contexts": [context.to_dict() for context in self.contexts],
        }
        if self.citations:
            payload["citations"] = [citation.to_dict() for citation in self.citations]
        if self.metadata:
            payload["metadata"] = dict(self.metadata)
        return payload


def load_trace_file(path: str | Path) -> RAGTrace:
    trace_path = Path(path)
    try:
        raw = trace_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise VerificationInputError("Could not read trace file %s: %s" % (trace_path, exc)) from exc

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise VerificationInputError(
            "Invalid JSON in %s at line %s column %s: %s"
            % (trace_path, exc.lineno, exc.colno, exc.msg)
        ) from exc

    return load_trace(payload, source=str(trace_path))


def load_trace(payload: Any, *, source: str = "trace") -> RAGTrace:
    if not isinstance(payload, dict):
        raise VerificationInputError("%s must be a JSON object." % source)

    query = _required_string(payload, "query", source=source)
    answer = _required_string(payload, "answer", source=source)

    if "contexts" not in payload:
        raise VerificationInputError("%s must include a contexts list." % source)
    contexts_payload = payload.get("contexts")
    if not isinstance(contexts_payload, list):
        raise VerificationInputError("%s contexts must be a list." % source)

    contexts = [
        _load_context(item, index=index, source=source)
        for index, item in enumerate(contexts_payload)
    ]
    citations = [
        _load_citation(item, index=index, source=source)
        for index, item in enumerate(payload.get("citations") or [])
    ]
    metadata = _metadata(payload.get("metadata"), field_name="metadata", source=source)

    return RAGTrace(
        query=query,
        answer=answer,
        contexts=contexts,
        citations=citations,
        metadata=metadata,
    )


def _load_context(item: Any, *, index: int, source: str) -> TraceContext:
    location = "%s contexts[%s]" % (source, index)
    if not isinstance(item, dict):
        raise VerificationInputError("%s must be an object." % location)
    context_id = _required_string(item, "id", source=location)
    text = _required_string(item, "text", source=location)
    metadata = _metadata(item.get("metadata"), field_name="metadata", source=location)
    return TraceContext(id=context_id, text=text, metadata=metadata)


def _load_citation(item: Any, *, index: int, source: str) -> TraceCitation:
    location = "%s citations[%s]" % (source, index)
    if not isinstance(item, dict):
        raise VerificationInputError("%s must be an object." % location)
    claim = _required_string(item, "claim", source=location)
    source_id = item.get("source_id") or item.get("source_chunk_id") or item.get("chunk_id")
    if source_id is None or str(source_id).strip() == "":
        raise VerificationInputError(
            "%s must include source_id, source_chunk_id, or chunk_id." % location
        )
    metadata = _metadata(item.get("metadata"), field_name="metadata", source=location)
    return TraceCitation(claim=claim, source_id=str(source_id).strip(), metadata=metadata)


def _required_string(payload: dict[str, Any], key: str, *, source: str) -> str:
    if key not in payload:
        raise VerificationInputError("%s must include %s." % (source, key))
    value = payload.get(key)
    if value is None or str(value).strip() == "":
        raise VerificationInputError("%s %s must be a non-empty string." % (source, key))
    return str(value).strip()


def _metadata(value: Any, *, field_name: str, source: str) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise VerificationInputError("%s %s must be an object when provided." % (source, field_name))
    return dict(value)
