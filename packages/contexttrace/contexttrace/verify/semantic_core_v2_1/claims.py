"""Conservative atomic-claim unitization for the v2.1 development profile."""

from __future__ import annotations

import re

from contexttrace.verify.semantic_core_v2.claims import ClaimUnit

ATOMIC_CLAIM_UNITIZER_VERSION = "claim-unitizer-v2.1.1"

_CITATION_RE = re.compile(r"\[[^\]\r\n]{1,256}\]")
_LIST_PREFIX_RE = re.compile(r"^(?:[-*•]|\d+[.)])\s+")
_WORD_RE = re.compile(r"[^\W_]+(?:[-'][^\W_]+)*", flags=re.UNICODE)
_COORDINATOR_RE = re.compile(r"\b(?:and|but|whereas|while)\b", re.IGNORECASE)
_FILLERS = {
    "thanks",
    "thank you",
    "hope this helps",
    "i hope this helps",
    "sure",
    "certainly",
}
_SUBJECT_PRONOUNS = {
    "he",
    "i",
    "it",
    "she",
    "that",
    "these",
    "they",
    "this",
    "those",
    "we",
    "you",
}
_DETERMINERS = {"a", "an", "each", "every", "the"}
_CLAUSE_ADVERBS = {"also", "then"}
_FINITE_AUXILIARIES = {
    "am",
    "are",
    "can",
    "could",
    "did",
    "do",
    "does",
    "had",
    "has",
    "have",
    "is",
    "may",
    "might",
    "must",
    "shall",
    "should",
    "was",
    "were",
    "will",
    "would",
}
_AUXILIARY_CHAIN = _FINITE_AUXILIARIES | {"be", "been", "being"}
_COMMON_FINITE_VERBS = {
    "accept",
    "accepts",
    "allow",
    "allows",
    "apply",
    "applies",
    "contain",
    "contains",
    "deny",
    "denies",
    "expire",
    "expires",
    "fail",
    "fails",
    "include",
    "includes",
    "permit",
    "permits",
    "reject",
    "rejects",
    "require",
    "requires",
    "return",
    "returns",
    "store",
    "stores",
    "support",
    "supports",
    "use",
    "uses",
}
_ABBREVIATIONS = {
    "dr.",
    "e.g.",
    "etc.",
    "i.e.",
    "mr.",
    "mrs.",
    "ms.",
    "prof.",
    "u.k.",
    "u.s.",
    "vs.",
}


def unitize_atomic_claims(
    answer: str, *, query: str = "", max_claims: int = 64
) -> tuple[list[ClaimUnit], bool]:
    """Return bounded atomic claims with offsets into the unmodified answer.

    Splits are deliberately conservative: punctuation always provides a safe
    boundary, while coordinators split only when the right side has an explicit
    subject and predicate, or a finite predicate can reuse an observable subject
    from the left side.
    """

    text = str(answer or "")
    candidates: list[tuple[int, int, str | None]] = []
    for sentence_start, sentence_end in _sentence_spans(text):
        for part_start, part_end in _structural_parts(
            text, sentence_start, sentence_end
        ):
            candidates.extend(_atomic_parts(text, part_start, part_end))

    units: list[ClaimUnit] = []
    for start, end, carried_subject in candidates:
        exact_start, exact_end = _trimmed_span(text, start, end)
        if exact_start >= exact_end:
            continue
        surface = text[exact_start:exact_end]
        prefix = _LIST_PREFIX_RE.match(surface)
        if prefix:
            exact_start += prefix.end()
            surface = text[exact_start:exact_end]
        verification = _normalize_verification_text(surface)
        if carried_subject:
            verification = f"{carried_subject} {verification}"
        answer_fragment = _is_query_conditioned_fragment(
            verification,
            query=query,
        )
        if not _is_propositional(verification) and not answer_fragment:
            continue
        units.append(
            ClaimUnit(
                id=f"claim_{len(units) + 1}",
                text=surface,
                verification_text=verification,
                start_char=exact_start,
                end_char=exact_end,
                unitizer_version=ATOMIC_CLAIM_UNITIZER_VERSION,
                query_context=str(query or "") if answer_fragment else "",
                answer_fragment=answer_fragment,
            )
        )
        if len(units) == max_claims:
            return units, True
    return units, False


def _sentence_spans(text: str) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    start = 0
    index = 0
    while index < len(text):
        char = text[index]
        if char in "!?" or (char == "." and not _internal_period(text, index)):
            end = index + 1
            while end < len(text) and text[end] in "\"')]}’”":
                end += 1
            if text[start:end].strip():
                spans.append((start, end))
            start = end
            index = end
            continue
        index += 1
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
    if _is_list_marker_period(text, index):
        return True

    token_start = index
    while token_start and not text[token_start - 1].isspace():
        token_start -= 1
    token = text[token_start : index + 1].casefold().strip("\"'(")
    if token in _ABBREVIATIONS:
        return True
    if "://" in token or token.startswith("www."):
        return True
    if len(token) == 2 and token[0].isalpha():
        return True
    return bool(re.fullmatch(r"(?:[a-z]\.){2,}", token))


def _is_list_marker_period(text: str, index: int) -> bool:
    if index + 1 >= len(text) or not text[index + 1].isspace():
        return False
    digit_start = index
    while digit_start and text[digit_start - 1].isdigit():
        digit_start -= 1
    if not text[digit_start:index].isdigit():
        return False
    prefix = digit_start
    while prefix and text[prefix - 1].isspace():
        prefix -= 1
    return prefix == 0 or text[prefix - 1] in ".!?;\n"


def _structural_parts(text: str, start: int, end: int) -> list[tuple[int, int]]:
    parts: list[tuple[int, int]] = []
    cursor = start
    for index in range(start, end):
        if text[index] == ";" or text[index] == "\n":
            if text[cursor:index].strip():
                parts.append((cursor, index))
            cursor = index + 1
    if text[cursor:end].strip():
        parts.append((cursor, end))
    return parts


def _atomic_parts(text: str, start: int, end: int) -> list[tuple[int, int, str | None]]:
    queue: list[tuple[int, int, str | None]] = [(start, end, None)]
    parts: list[tuple[int, int, str | None]] = []
    while queue:
        part_start, part_end, carried = queue.pop(0)
        split = _coordinator_split(text, part_start, part_end)
        if split is None:
            parts.append((part_start, part_end, carried))
            continue
        left_end, right_start, subject = split
        queue.insert(0, (right_start, part_end, subject))
        queue.insert(0, (part_start, left_end, carried))
    return parts


def _coordinator_split(
    text: str, start: int, end: int
) -> tuple[int, int, str | None] | None:
    fragment = text[start:end]
    for match in _COORDINATOR_RE.finditer(fragment):
        conjunction = match.group(0).casefold()
        boundary_start = start + match.start()
        right_start = start + match.end()
        left = _normalize_verification_text(text[start:boundary_start].rstrip(" ,"))
        right = _normalize_verification_text(text[right_start:end])
        if not _is_propositional(left) or not _is_propositional(right):
            continue
        if _contains_finite_predicate(left) and _has_explicit_subject_predicate(right):
            return _strip_left_separator(text, boundary_start, start), right_start, None
        if conjunction != "and" or not _starts_with_shared_predicate(right):
            continue
        shared_prefix = _observable_shared_prefix(left, right)
        if shared_prefix:
            return (
                _strip_left_separator(text, boundary_start, start),
                right_start,
                shared_prefix,
            )
    return None


def _has_explicit_subject_predicate(text: str) -> bool:
    words = _WORD_RE.findall(text)
    if len(words) < 2:
        return False
    lowered = [word.casefold() for word in words[:5]]
    if lowered[0] in _SUBJECT_PRONOUNS:
        return _is_finite_verb(lowered[1])
    if lowered[0] in _DETERMINERS:
        return len(lowered) >= 3 and any(_is_finite_verb(word) for word in lowered[2:4])
    return _is_finite_verb(lowered[1])


def _starts_with_shared_predicate(text: str) -> bool:
    words = _WORD_RE.findall(text)
    if not words:
        return False
    first = words[0].casefold()
    if _is_finite_verb(first) or _is_participle(first):
        return True
    return bool(
        first in _CLAUSE_ADVERBS
        and len(words) > 1
        and _is_finite_verb(words[1].casefold())
    )


def _observable_shared_prefix(text: str, right: str) -> str | None:
    words = list(_WORD_RE.finditer(text))
    for index, word in enumerate(words):
        if index and _is_finite_verb(word.group(0).casefold()):
            subject = text[: word.start()].strip(" ,")
            subject_words = _WORD_RE.findall(subject)
            if not 1 <= len(subject_words) <= 8:
                return None
            right_words = _WORD_RE.findall(right)
            right_head = right_words[0].casefold() if right_words else ""
            if _is_participle(right_head):
                prefix_end = word.end()
                for following in words[index + 1 :]:
                    if following.group(0).casefold() not in _AUXILIARY_CHAIN:
                        break
                    prefix_end = following.end()
                return text[:prefix_end].strip(" ,")
            return subject
    return None


def _contains_finite_predicate(text: str) -> bool:
    return any(_is_finite_verb(word.casefold()) for word in _WORD_RE.findall(text))


def _is_finite_verb(word: str) -> bool:
    return word in _FINITE_AUXILIARIES or word in _COMMON_FINITE_VERBS


def _is_participle(word: str) -> bool:
    return len(word) > 3 and word.endswith(("ed", "en"))


def _strip_left_separator(text: str, end: int, floor: int) -> int:
    while end > floor and text[end - 1] in " ,\t":
        end -= 1
    return end


def _trimmed_span(text: str, start: int, end: int) -> tuple[int, int]:
    while start < end and text[start].isspace():
        start += 1
    while end > start and text[end - 1].isspace():
        end -= 1
    return start, end


def _normalize_verification_text(text: str) -> str:
    without_citations = _CITATION_RE.sub(" ", text)
    normalized = " ".join(without_citations.strip().split())
    return re.sub(r"\s+([,.;:!?])", r"\1", normalized)


def _is_propositional(text: str) -> bool:
    normalized = text.strip().strip(".!?").casefold()
    if not normalized or normalized in _FILLERS:
        return False
    words = _WORD_RE.findall(normalized)
    if not words:
        return False
    return len(words) > 1 or any(char.isdigit() for char in normalized)


def _is_query_conditioned_fragment(text: str, *, query: str) -> bool:
    normalized = text.strip().strip(".!?").casefold()
    if not str(query or "").strip() or not normalized or normalized in _FILLERS:
        return False
    words = _WORD_RE.findall(normalized)
    if not 1 <= len(words) <= 4:
        return False
    return not _contains_finite_predicate(normalized)
