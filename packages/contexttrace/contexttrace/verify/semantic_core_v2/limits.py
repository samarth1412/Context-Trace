"""Explicit bounded-input handling for semantic_core_v2."""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from typing import Any

from contexttrace.verify.schema import RAGTrace, TraceContext


@dataclass(frozen=True)
class V2Limits:
    max_query_chars: int = 4096
    max_answer_chars: int = 16384
    max_contexts: int = 20
    max_context_chars: int = 16384
    max_total_context_chars: int = 65536
    max_claims: int = 64

    def __post_init__(self) -> None:
        for name, value in asdict(self).items():
            if value <= 0:
                raise ValueError(f"{name} must be greater than zero.")

    def to_dict(self) -> dict[str, int]:
        return asdict(self)


DEFAULT_V2_LIMITS = V2Limits()


def apply_limits(trace: RAGTrace, limits: V2Limits) -> tuple[RAGTrace, dict[str, Any]]:
    query = trace.query[: limits.max_query_chars]
    answer = trace.answer[: limits.max_answer_chars]
    contexts: list[TraceContext] = []
    remaining = limits.max_total_context_chars
    context_text_truncated = False
    for context in trace.contexts[: limits.max_contexts]:
        if remaining <= 0:
            break
        allowed = min(limits.max_context_chars, remaining)
        text = context.text[:allowed]
        context_text_truncated = context_text_truncated or len(text) < len(context.text)
        if not text:
            continue
        metadata = dict(context.metadata)
        if len(text) < len(context.text):
            metadata["contexttrace_v2_truncated"] = True
        contexts.append(replace(context, text=text, metadata=metadata))
        remaining -= len(text)

    original_context_chars = sum(len(context.text) for context in trace.contexts)
    used_context_chars = sum(len(context.text) for context in contexts)
    record = {
        "applied": any(
            (
                len(query) < len(trace.query),
                len(answer) < len(trace.answer),
                len(contexts) < len(trace.contexts),
                used_context_chars < original_context_chars,
            )
        ),
        "query_chars_original": len(trace.query),
        "query_chars_used": len(query),
        "answer_chars_original": len(trace.answer),
        "answer_chars_used": len(answer),
        "contexts_original": len(trace.contexts),
        "contexts_used": len(contexts),
        "context_chars_original": original_context_chars,
        "context_chars_used": used_context_chars,
        "query_truncated": len(query) < len(trace.query),
        "answer_truncated": len(answer) < len(trace.answer),
        "contexts_truncated": len(contexts) < len(trace.contexts),
        "context_text_truncated": context_text_truncated
        or used_context_chars < original_context_chars,
        "limits": limits.to_dict(),
    }
    limited = replace(trace, query=query, answer=answer, contexts=contexts)
    return limited, record
