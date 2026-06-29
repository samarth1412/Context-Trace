from __future__ import annotations

import hashlib
import json
import re
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
    spans.extend(_json_context_spans(context))
    passage_spans = _passage_context_spans(context)
    spans.extend(passage_spans)
    sentence_source = [] if passage_spans else _sentence_offsets(context.text)
    for start, end, text in sentence_source:
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
    return _dedupe_spans(spans)


def _json_context_spans(context: TraceContext) -> list[EvidenceSpan]:
    value = str(context.text or "").strip()
    if not value.startswith("{"):
        return []
    try:
        data = json.loads(value)
    except json.JSONDecodeError:
        return []
    if not isinstance(data, dict):
        return []

    spans: list[EvidenceSpan] = []
    for key, item in data.items():
        if isinstance(item, (str, int, float, bool)) or item is None:
            _append_json_pair_span(spans, context, key, item)
        elif key == "hours" and isinstance(item, dict):
            _append_json_pair_span(spans, context, key, item)
            for day, hours in item.items():
                _append_json_pair_span(spans, context, day, hours)
        elif key == "attributes" and isinstance(item, dict):
            _append_nested_json_scalar_spans(spans, context, item)
        elif key == "review_info" and isinstance(item, list):
            _append_review_spans(spans, context, item)
    return spans


def _passage_context_spans(context: TraceContext) -> list[EvidenceSpan]:
    value = str(context.text or "")
    matches = list(re.finditer(r"(?i)\bpassage\s*\d+\s*:", value))
    if not matches:
        return []

    spans: list[EvidenceSpan] = []
    for index, match in enumerate(matches):
        raw_start = match.start()
        raw_end = matches[index + 1].start() if index + 1 < len(matches) else len(value)
        _append_evidence_span(spans, context, raw_start, raw_end)
        block_text = value[raw_start:raw_end]
        for sentence_start, sentence_end, _ in _sentence_offsets(block_text):
            if sentence_start == 0 and sentence_end == len(block_text.strip()):
                continue
            _append_evidence_span(spans, context, raw_start + sentence_start, raw_start + sentence_end)
    return spans


def _append_nested_json_scalar_spans(spans: list[EvidenceSpan], context: TraceContext, data: dict[str, Any]) -> None:
    for key, value in data.items():
        if isinstance(value, dict):
            _append_nested_json_scalar_spans(spans, context, value)
        elif isinstance(value, (str, int, float, bool)) or value is None:
            _append_json_pair_span(spans, context, key, value)


def _append_json_pair_span(spans: list[EvidenceSpan], context: TraceContext, key: str, value: Any) -> None:
    snippet = '%s: %s' % (json.dumps(str(key), ensure_ascii=False), json.dumps(value, ensure_ascii=False))
    _append_derived_span(spans, context, snippet)


def _append_review_spans(spans: list[EvidenceSpan], context: TraceContext, reviews: list[Any]) -> None:
    for item in reviews:
        if not isinstance(item, dict):
            continue
        text = str(item.get("review_text") or "").strip()
        if not text:
            continue
        _append_derived_span(spans, context, text)
        for _, _, sentence in _sentence_offsets(text):
            _append_derived_span(spans, context, sentence)


def _append_derived_span(spans: list[EvidenceSpan], context: TraceContext, text: str) -> None:
    snippet = str(text or "").strip()
    if not snippet:
        return
    start = _find_json_snippet_start(context.text, snippet)
    end = start + len(snippet)
    spans.append(
        EvidenceSpan(
            context_id=context.id,
            text=snippet,
            start_char=start,
            end_char=end,
            span_hash=_span_hash(context.id, snippet),
            metadata=dict(context.metadata),
        )
    )


def _find_json_snippet_start(source: str, snippet: str) -> int:
    value = str(source or "")
    direct = value.find(snippet)
    if direct >= 0:
        return direct
    escaped = json.dumps(snippet, ensure_ascii=False)[1:-1]
    escaped_match = value.find(escaped)
    if escaped_match >= 0:
        return escaped_match
    return 0


def _append_evidence_span(spans: list[EvidenceSpan], context: TraceContext, raw_start: int, raw_end: int) -> None:
    text = str(context.text or "")[raw_start:raw_end]
    stripped = text.strip()
    if not stripped:
        return
    leading = len(text) - len(text.lstrip())
    start = raw_start + leading
    spans.append(
        EvidenceSpan(
            context_id=context.id,
            text=stripped,
            start_char=start,
            end_char=start + len(stripped),
            span_hash=_span_hash(context.id, stripped),
            metadata=dict(context.metadata),
        )
    )


def _dedupe_spans(spans: list[EvidenceSpan]) -> list[EvidenceSpan]:
    deduped: list[EvidenceSpan] = []
    seen: set[tuple[str, str]] = set()
    for span in spans:
        key = (span.context_id, " ".join(span.text.split()))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(span)
    return deduped


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
    if (
        previous.isupper()
        and re.search(r"\b[A-Z][a-z]+\s+[A-Z]$", text[:index])
        and re.match(r"\s+[A-Z][a-z]", text[index + 1 :])
    ):
        return True
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
