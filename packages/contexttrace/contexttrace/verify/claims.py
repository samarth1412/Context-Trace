from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Claim:
    id: str
    text: str

    def to_dict(self) -> dict[str, str]:
        return {"id": self.id, "text": self.text}


_WHITESPACE_RE = re.compile(r"\s+")
_COMPOUND_SPLIT_RE = re.compile(r"\s+(?:and|but)\s+", re.IGNORECASE)

_FILLER_EXACT = {
    "thanks",
    "thank you",
    "sure",
    "certainly",
    "of course",
    "hope this helps",
    "i hope this helps",
    "i do not know",
    "i don't know",
    "i am not sure",
    "i'm not sure",
    "i cannot answer that from the provided context",
    "i can't answer that from the provided context",
    "the context does not provide that information",
}

_FILLER_PREFIXES = (
    "here is ",
    "here are ",
    "based on the provided context",
    "based on the retrieved context",
    "according to the provided context",
)

_MAIN_VERBS = {
    "captures",
    "checks",
    "creates",
    "detects",
    "fetches",
    "filters",
    "generates",
    "includes",
    "keeps",
    "logs",
    "maps",
    "records",
    "reports",
    "retrieves",
    "runs",
    "saves",
    "stores",
    "supports",
    "uses",
    "verifies",
    "writes",
}


def extract_claims(answer: str) -> list[Claim]:
    """Split an answer into lightweight factual claim candidates."""

    normalized_answer = _WHITESPACE_RE.sub(" ", str(answer or "")).strip()
    if not normalized_answer:
        return []

    sentences = _split_sentences(normalized_answer)
    if not sentences:
        sentences = [normalized_answer]

    claims: list[Claim] = []
    for sentence in sentences:
        sentence = _clean_sentence(sentence)
        if not sentence or _is_filler(sentence):
            continue
        for atomic in _atomic_claims(sentence):
            if atomic and not _is_filler(atomic):
                claims.append(Claim(id="claim_%s" % (len(claims) + 1), text=atomic))
    return claims


def _clean_sentence(value: str) -> str:
    cleaned = _WHITESPACE_RE.sub(" ", value).strip()
    return cleaned.strip("-* \t")


def _split_sentences(text: str) -> list[str]:
    sentences: list[str] = []
    start = 0
    for index, char in enumerate(text):
        if char not in ".!?":
            continue
        if char == "." and _is_internal_period(text, index):
            continue
        sentence = text[start : index + 1].strip()
        if sentence:
            sentences.append(sentence)
        start = index + 1
    tail = text[start:].strip()
    if tail:
        sentences.append(tail)
    return sentences


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


def _is_filler(sentence: str) -> bool:
    normalized = sentence.strip().strip(".!?").lower()
    if normalized in _FILLER_EXACT:
        return True
    if len(normalized.split()) <= 2 and normalized in _FILLER_EXACT:
        return True
    return any(normalized.startswith(prefix) and len(normalized.split()) <= 5 for prefix in _FILLER_PREFIXES)


def _atomic_claims(sentence: str) -> list[str]:
    stripped = sentence.strip()
    terminal = "." if stripped.endswith(".") else stripped[-1:] if stripped[-1:] in "!?." else "."
    body = stripped.rstrip(".!?").strip()
    parts = [part.strip(" ,;") for part in _COMPOUND_SPLIT_RE.split(body) if part.strip(" ,;")]
    if len(parts) <= 1:
        return [_ensure_terminal(stripped, terminal)]

    prefix = _subject_prefix(parts[0])
    auxiliary = _auxiliary(parts[0])
    if not prefix or any(not _is_splitworthy_continuation(part, auxiliary) for part in parts[1:]):
        return [_ensure_terminal(stripped, terminal)]

    atomic = [_ensure_terminal(parts[0], terminal)]
    for part in parts[1:]:
        if _has_subject(part) or not prefix:
            atomic.append(_ensure_terminal(part, terminal))
        elif _starts_with_auxiliary(part):
            atomic.append(_ensure_terminal("%s %s" % (prefix, part), terminal))
        elif auxiliary and _needs_auxiliary(part):
            atomic.append(_ensure_terminal("%s %s %s" % (prefix, auxiliary, part), terminal))
        else:
            atomic.append(_ensure_terminal("%s %s" % (prefix, part), terminal))
    return atomic


def _ensure_terminal(text: str, terminal: str) -> str:
    value = _WHITESPACE_RE.sub(" ", text).strip()
    if not value:
        return ""
    if value[-1:] in ".!?":
        return value
    return value + (terminal if terminal in ".!?" else ".")


def _subject_prefix(clause: str) -> str:
    words = clause.split()
    for index, word in enumerate(words):
        if _clean_word(word) in {
            "is",
            "are",
            "was",
            "were",
            "can",
            "could",
            "may",
            "might",
            "must",
            "should",
            "will",
            "would",
            "has",
            "have",
            "had",
        }:
            return " ".join(words[:index])
    for index, word in enumerate(words):
        if index > 0 and _clean_word(word) in _MAIN_VERBS:
            return " ".join(words[:index])
    return " ".join(words[:2]) if len(words) >= 3 else ""


def _auxiliary(clause: str) -> str:
    for word in clause.split():
        cleaned = _clean_word(word)
        if cleaned in {"is", "are", "was", "were", "can", "could", "may", "might", "must", "should", "will", "would"}:
            return cleaned
    return ""


def _has_subject(clause: str) -> bool:
    words = clause.split()
    if len(words) < 2:
        return False
    return _clean_word(words[1]) in {
        "is",
        "are",
        "was",
        "were",
        "can",
        "could",
        "may",
        "might",
        "must",
        "should",
        "will",
        "would",
        "has",
        "have",
        "had",
    }


def _starts_with_auxiliary(clause: str) -> bool:
    first = _clean_word(clause.split()[0]) if clause.split() else ""
    return first in {
        "is",
        "are",
        "was",
        "were",
        "can",
        "could",
        "may",
        "might",
        "must",
        "should",
        "will",
        "would",
        "has",
        "have",
        "had",
    }


def _looks_like_predicate_continuation(clause: str) -> bool:
    first = _clean_word(clause.split()[0]) if clause.split() else ""
    return first.endswith("ed") or first in {
        "allowed",
        "available",
        "eligible",
        "include",
        "includes",
        "process",
        "processed",
        "require",
        "requires",
        "required",
    }


def _clean_word(word: str) -> str:
    return word.strip(".,;:!?()[]{}\"'").lower()


def _is_splitworthy_continuation(clause: str, auxiliary: str) -> bool:
    return _has_subject(clause) or _starts_with_auxiliary(clause) or (
        bool(auxiliary) and _looks_like_predicate_continuation(clause)
    )


def _needs_auxiliary(clause: str) -> bool:
    first = _clean_word(clause.split()[0]) if clause.split() else ""
    return first.endswith("ed") or first in {"allowed", "available", "eligible", "processed", "required"}
