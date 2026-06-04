from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

from contexttrace.verify.schema import TraceContext


@dataclass(frozen=True)
class EvidenceSpan:
    context_id: str
    text: str
    start_char: int
    end_char: int
    span_hash: str
    metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "context_id": self.context_id,
            "text": self.text,
            "start_char": self.start_char,
            "end_char": self.end_char,
            "span_hash": self.span_hash,
            "metadata": dict(self.metadata),
        }


def split_context_spans(context: TraceContext) -> list[EvidenceSpan]:
    spans: list[EvidenceSpan] = []
    for start, end, text in _sentence_offsets(context.text):
        spans.append(
            EvidenceSpan(
                context_id=context.id,
                text=text,
                start_char=start,
                end_char=end,
                span_hash=_span_hash(context.id, text),
                metadata=dict(context.metadata),
            )
        )
    if not spans and context.text.strip():
        text = context.text.strip()
        start = context.text.find(text)
        spans.append(
            EvidenceSpan(
                context_id=context.id,
                text=text,
                start_char=max(0, start),
                end_char=max(0, start) + len(text),
                span_hash=_span_hash(context.id, text),
                metadata=dict(context.metadata),
            )
        )
    return spans


def _sentence_offsets(text: str) -> list[tuple[int, int, str]]:
    value = str(text or "")
    spans: list[tuple[int, int, str]] = []
    start = 0
    for index, char in enumerate(value):
        if char not in ".!?":
            continue
        if char == "." and _is_internal_period(value, index):
            continue
        _append_span(spans, value, start, index + 1)
        start = index + 1
    _append_span(spans, value, start, len(value))
    return spans


def _append_span(spans: list[tuple[int, int, str]], value: str, raw_start: int, raw_end: int) -> None:
    text = value[raw_start:raw_end]
    stripped = text.strip()
    if not stripped:
        return
    leading = len(text) - len(text.lstrip())
    start = raw_start + leading
    end = start + len(stripped)
    spans.append((start, end, stripped))


def _is_internal_period(text: str, index: int) -> bool:
    previous = text[index - 1] if index > 0 else ""
    next_char = text[index + 1] if index + 1 < len(text) else ""
    if previous.isdigit() and next_char.isdigit():
        return True
    if previous.isalnum() and next_char.isalnum():
        return True
    if next_char.isalnum() and (not previous or previous.isspace() or previous in "([{/\\$"):
        return True
    if previous.isalnum() and next_char in "_-/\\":
        return True
    if previous in "_-/\\" and next_char.isalnum():
        return True
    return False


def _span_hash(context_id: str, text: str) -> str:
    digest = hashlib.sha256(("%s\n%s" % (context_id, " ".join(text.split()))).encode("utf-8")).hexdigest()
    return "sha256:%s" % digest[:16]
