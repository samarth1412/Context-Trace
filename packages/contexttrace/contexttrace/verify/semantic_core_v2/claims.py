"""Exact-offset, deterministic claim unitization for semantic_core_v2."""

from __future__ import annotations

import re
from dataclasses import dataclass

from .constants import CLAIM_UNITIZER_VERSION

_CITATION_RE = re.compile(r"\[[^\]\r\n]{1,256}\]")
_LIST_PREFIX_RE = re.compile(r"^(?:[-*•]|\d+[.)])\s+")
_WORD_RE = re.compile(r"[^\W_]+", flags=re.UNICODE)
_FILLERS = {
    "thanks",
    "thank you",
    "hope this helps",
    "i hope this helps",
    "sure",
    "certainly",
}


@dataclass(frozen=True)
class ClaimUnit:
    id: str
    text: str
    verification_text: str
    start_char: int
    end_char: int
    unitizer_version: str = CLAIM_UNITIZER_VERSION
    query_context: str = ""
    answer_fragment: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "claim_id": self.id,
            "text": self.text,
            "verification_text": self.verification_text,
            "start_char": self.start_char,
            "end_char": self.end_char,
            "unitizer_version": self.unitizer_version,
        }


def unitize_claims(
    answer: str, *, query: str = "", max_claims: int = 64
) -> tuple[list[ClaimUnit], bool]:
    """Split answer prose while preserving exact UTF-8 character offsets."""

    del query

    units: list[ClaimUnit] = []
    for start, end in _sentence_spans(str(answer or "")):
        for part_start, part_end in _semicolon_parts(answer, start, end):
            raw = answer[part_start:part_end]
            leading = len(raw) - len(raw.lstrip())
            trailing = len(raw) - len(raw.rstrip())
            exact_start = part_start + leading
            exact_end = part_end - trailing
            text = answer[exact_start:exact_end]
            if not text:
                continue
            prefix = _LIST_PREFIX_RE.match(text)
            if prefix:
                exact_start += prefix.end()
                text = answer[exact_start:exact_end]
            verification = _normalize_verification_text(text)
            if not _is_propositional(verification):
                continue
            units.append(
                ClaimUnit(
                    id=f"claim_{len(units) + 1}",
                    text=text,
                    verification_text=verification,
                    start_char=exact_start,
                    end_char=exact_end,
                )
            )
            if len(units) == max_claims:
                return units, True
    return units, False


def _sentence_spans(text: str) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    start = 0
    for index, char in enumerate(text):
        if char not in ".!?":
            continue
        if char == "." and _internal_period(text, index):
            continue
        end = index + 1
        if text[start:end].strip():
            spans.append((start, end))
        start = end
    if text[start:].strip():
        spans.append((start, len(text)))
    return spans


def _internal_period(text: str, index: int) -> bool:
    previous = text[index - 1] if index else ""
    following = text[index + 1] if index + 1 < len(text) else ""
    if previous.isdigit() and following.isdigit():
        return True
    if previous.isalpha() and following.isalpha():
        return True
    prefix = text[max(0, index - 5) : index + 1].casefold()
    return prefix.endswith(("e.g.", "i.e.", "u.s.", "u.k."))


def _semicolon_parts(text: str, start: int, end: int) -> list[tuple[int, int]]:
    parts: list[tuple[int, int]] = []
    cursor = start
    for index in range(start, end):
        if text[index] != ";":
            continue
        if text[cursor:index].strip():
            parts.append((cursor, index))
        cursor = index + 1
    if text[cursor:end].strip():
        parts.append((cursor, end))
    return parts


def _normalize_verification_text(text: str) -> str:
    without_citations = _CITATION_RE.sub(" ", text)
    return " ".join(without_citations.strip().split())


def _is_propositional(text: str) -> bool:
    normalized = text.strip().strip(".!?").casefold()
    if not normalized or normalized in _FILLERS:
        return False
    words = _WORD_RE.findall(normalized)
    if not words:
        return False
    return len(words) != 1 or any(char.isdigit() for char in normalized)
