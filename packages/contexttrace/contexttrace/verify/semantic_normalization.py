from __future__ import annotations

import re
import unicodedata
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime
from typing import Iterator


ENTITY_ALIASES = {
    "u.s.": "united states",
    "u.s": "united states",
    "usa": "united states",
    "uk": "united kingdom",
    "u.k.": "united kingdom",
    "nyc": "new york city",
}

NUMBER_WORDS = {
    "zero": "0",
    "one": "1",
    "two": "2",
    "three": "3",
    "four": "4",
    "five": "5",
    "six": "6",
    "seven": "7",
    "eight": "8",
    "nine": "9",
    "ten": "10",
    "eleven": "11",
    "twelve": "12",
    "thirteen": "13",
    "fourteen": "14",
    "fifteen": "15",
    "sixteen": "16",
    "seventeen": "17",
    "eighteen": "18",
    "nineteen": "19",
    "twenty": "20",
}

MONTHS = {
    name.lower(): index
    for index, name in enumerate(
        (
            "January", "February", "March", "April", "May", "June",
            "July", "August", "September", "October", "November", "December",
        ),
        start=1,
    )
}
MONTH_PATTERN = "|".join(MONTHS)
_ENABLED: ContextVar[bool] = ContextVar("contexttrace_semantic_normalization_enabled", default=True)


@contextmanager
def semantic_normalization(enabled: bool) -> Iterator[None]:
    token = _ENABLED.set(bool(enabled))
    try:
        yield
    finally:
        _ENABLED.reset(token)


def normalize_semantic_text(text: object) -> str:
    value = unicodedata.normalize("NFKD", str(text or "")).encode("ascii", "ignore").decode("ascii")
    value = value.lower()
    if not _ENABLED.get():
        return value
    value = re.sub(r"\bcan(?:not|'t)\b", "not", value)
    value = re.sub(r"\b([a-z]+)n't\b", r"\1 not", value)
    for alias, canonical in ENTITY_ALIASES.items():
        value = re.sub(r"\b%s\b" % re.escape(alias.strip(".")), canonical, value)
    value = re.sub(r"\bgreater than\b|\bhigher than\b", "more than", value)
    value = re.sub(r"\blower than\b|\bfewer than\b", "less than", value)
    for word, number in NUMBER_WORDS.items():
        value = re.sub(r"\b%s\b" % word, number, value)
    value = _normalize_written_dates(value)
    value = re.sub(r"(?<=\d),(?=\d{3}\b)", "", value)
    return re.sub(r"\s+", " ", value).strip()


def extract_normalized_dates(text: object) -> set[str]:
    normalized = normalize_semantic_text(text)
    return set(re.findall(r"\b\d{4}-\d{2}-\d{2}\b", normalized))


def _normalize_written_dates(value: str) -> str:
    pattern = re.compile(
        rf"\b(?P<month>{MONTH_PATTERN})\s+(?P<day>\d{{1,2}})(?:st|nd|rd|th)?[,]?\s+(?P<year>\d{{4}})\b",
        flags=re.IGNORECASE,
    )

    def replace(match: re.Match[str]) -> str:
        month = MONTHS[match.group("month").lower()]
        try:
            return datetime(int(match.group("year")), month, int(match.group("day"))).strftime("%Y-%m-%d")
        except ValueError:
            return match.group(0)

    return pattern.sub(replace, value)
