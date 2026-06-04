from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from contexttrace.verify.claims import extract_claims
from contexttrace.verify.schema import RAGTrace


def inspect_trace(trace: RAGTrace, *, trace_path: str | None = None) -> dict[str, Any]:
    """Inspect a portable RAG trace before running verification or audit."""

    claims = extract_claims(trace.answer)
    context_ids = [context.id for context in trace.contexts]
    context_counts = Counter(context_ids)
    duplicate_context_ids = sorted(context_id for context_id, count in context_counts.items() if count > 1)
    empty_context_ids = sorted(context.id for context in trace.contexts if not context.text.strip())
    citation_source_ids = [citation.source_id for citation in trace.citations]
    known_context_ids = set(context_ids)
    missing_citation_sources = sorted(
        source_id for source_id in set(citation_source_ids) if source_id not in known_context_ids
    )
    warnings = _warnings(
        trace=trace,
        claims_count=len(claims),
        duplicate_context_ids=duplicate_context_ids,
        empty_context_ids=empty_context_ids,
        missing_citation_sources=missing_citation_sources,
    )
    return {
        "trace_path": trace_path,
        "query": trace.query,
        "answer_preview": _preview(trace.answer, limit=220),
        "claims": [claim.to_dict() for claim in claims],
        "contexts": {
            "count": len(trace.contexts),
            "unique_ids": len(known_context_ids),
            "duplicate_ids": duplicate_context_ids,
            "empty_text_ids": empty_context_ids,
        },
        "citations": {
            "count": len(trace.citations),
            "source_ids": citation_source_ids,
            "missing_source_ids": missing_citation_sources,
        },
        "metadata_keys": sorted(str(key) for key in trace.metadata.keys()),
        "warnings": warnings,
        "suggested_next_commands": _suggested_commands(trace_path),
    }


def _warnings(
    *,
    trace: RAGTrace,
    claims_count: int,
    duplicate_context_ids: list[str],
    empty_context_ids: list[str],
    missing_citation_sources: list[str],
) -> list[str]:
    warnings = []
    if not trace.contexts:
        warnings.append("Trace has no retrieved contexts; verification will likely recommend abstention.")
    if claims_count == 0:
        warnings.append("No factual claims were extracted from the answer.")
    if duplicate_context_ids:
        warnings.append("Duplicate context IDs found: %s." % ", ".join(duplicate_context_ids))
    if empty_context_ids:
        warnings.append("Contexts with empty text found: %s." % ", ".join(empty_context_ids))
    if trace.citations and missing_citation_sources:
        warnings.append("Citations reference missing context IDs: %s." % ", ".join(missing_citation_sources))
    if not trace.citations and claims_count:
        warnings.append("Trace has factual claims but no citations; verification will check support without citation grounding.")
    return warnings


def _suggested_commands(trace_path: str | None) -> list[str]:
    if trace_path:
        path = str(Path(trace_path))
        return [
            "contexttrace verify %s --report" % path,
            "contexttrace audit %s --corpus <corpus_dir> --report" % path,
        ]
    return [
        "contexttrace verify <trace.json> --report",
        "contexttrace audit <trace.json> --corpus <corpus_dir> --report",
    ]


def _preview(value: object, *, limit: int) -> str:
    text = "" if value is None else str(value).replace("\n", " ").strip()
    return text if len(text) <= limit else text[: limit - 1] + "..."
