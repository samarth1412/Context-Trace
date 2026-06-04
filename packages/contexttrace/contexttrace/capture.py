from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

from contexttrace.verify.schema import RAGTrace, TraceCitation, TraceContext, load_trace


def capture_rag_trace(
    *,
    query: str,
    answer: str,
    contexts: Iterable[Any],
    citations: Iterable[Any] | None = None,
    metadata: dict[str, Any] | None = None,
    context_id_prefix: str = "context",
) -> RAGTrace:
    """Create a portable ContextTrace verification trace from common RAG artifacts."""

    payload = {
        "query": query,
        "answer": answer,
        "contexts": [
            context_to_trace_context(context, index=index, id_prefix=context_id_prefix).to_dict()
            for index, context in enumerate(contexts)
        ],
        "citations": [
            citation_to_trace_citation(citation).to_dict()
            for citation in (citations or [])
        ],
        "metadata": dict(metadata or {}),
    }
    return load_trace(payload, source="captured RAG trace")


def write_rag_trace(trace: RAGTrace, path: str | Path) -> str:
    """Write a portable RAG trace JSON file that works with `contexttrace verify`."""

    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(trace.to_dict(), indent=2), encoding="utf-8")
    return str(output_path)


def context_to_trace_context(
    context: Any,
    *,
    index: int = 0,
    id_prefix: str = "context",
) -> TraceContext:
    """Convert dicts, LangChain Documents, or document-like objects to TraceContext."""

    if isinstance(context, TraceContext):
        return context

    if isinstance(context, dict):
        text = _first_present(context, ("text", "content", "page_content"))
        metadata = dict(context.get("metadata") or {})
        context_id = _first_present(
            context,
            ("id", "chunk_id", "source_id", "source_chunk_id", "document_id"),
        )
        source = context.get("source")
        score = context.get("score", context.get("relevance_score"))
    else:
        text = getattr(context, "page_content", None) or getattr(context, "text", None)
        metadata = dict(getattr(context, "metadata", None) or {})
        context_id = getattr(context, "id", None) or metadata.get("chunk_id") or metadata.get("id")
        source = metadata.get("source")
        score = getattr(context, "score", None) or metadata.get("score") or metadata.get("relevance_score")

    context_text = str(text or "").strip()
    if not context_text:
        raise ValueError("Captured context %s did not include text/content/page_content." % index)

    if source is not None and "source" not in metadata:
        metadata["source"] = source
    if score is not None and "score" not in metadata and "relevance_score" not in metadata:
        metadata["score"] = score

    resolved_id = _context_id(
        context_id=context_id,
        metadata=metadata,
        id_prefix=id_prefix,
        index=index,
    )
    return TraceContext(id=resolved_id, text=context_text, metadata=metadata)


def citation_to_trace_citation(citation: Any) -> TraceCitation:
    if isinstance(citation, TraceCitation):
        return citation

    if isinstance(citation, dict):
        claim = citation.get("claim")
        source_id = citation.get("source_id") or citation.get("source_chunk_id") or citation.get("chunk_id")
        metadata = dict(citation.get("metadata") or {})
    else:
        claim = getattr(citation, "claim", None)
        source_id = (
            getattr(citation, "source_id", None)
            or getattr(citation, "source_chunk_id", None)
            or getattr(citation, "chunk_id", None)
        )
        metadata = dict(getattr(citation, "metadata", None) or {})

    if not str(claim or "").strip():
        raise ValueError("Captured citation did not include claim.")
    if not str(source_id or "").strip():
        raise ValueError("Captured citation did not include source_id/source_chunk_id/chunk_id.")
    return TraceCitation(claim=str(claim).strip(), source_id=str(source_id).strip(), metadata=metadata)


def langchain_documents_to_contexts(
    documents: Iterable[Any],
    *,
    id_prefix: str = "langchain_doc",
) -> list[TraceContext]:
    return [
        context_to_trace_context(document, index=index, id_prefix=id_prefix)
        for index, document in enumerate(documents)
    ]


def _first_present(payload: dict[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        value = payload.get(key)
        if value is not None and str(value).strip() != "":
            return value
    return None


def _context_id(
    *,
    context_id: Any,
    metadata: dict[str, Any],
    id_prefix: str,
    index: int,
) -> str:
    if context_id is not None and str(context_id).strip():
        return str(context_id).strip()
    source = metadata.get("source")
    chunk_marker = (
        metadata.get("chunk_id")
        or metadata.get("chunk_index")
        or metadata.get("page")
        or metadata.get("start_index")
    )
    if source is not None and str(source).strip() and chunk_marker is not None:
        return "%s:%s" % (str(source).strip(), str(chunk_marker).strip())
    if source is not None and str(source).strip():
        return "%s:%s" % (str(source).strip(), index + 1)
    return "%s_%s" % (id_prefix, index + 1)
