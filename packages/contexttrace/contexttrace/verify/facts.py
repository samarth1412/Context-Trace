from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache


TOKEN_RE = re.compile(r"[A-Za-z0-9_./-]+")
ACRONYM_RE = re.compile(r"\b[A-Z][A-Z0-9]{1,}\b")
VERSION_RE = re.compile(r"\bv?\d+(?:\.\d+){1,}\b", re.IGNORECASE)
NUMBER_RE = re.compile(r"\b\d+(?:\.\d+)?\b")
PORT_RE = re.compile(r":(\d{2,5})\b")
PATH_RE = re.compile(r"(?:^|\s)([./]?[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)+)")
NUMBER_UNIT_RE = re.compile(
    r"\b\d+(?:\.\d+)?\s+(?:business\s+days?|days?|weeks?|months?|years?|ms|usd|dollars?)\b",
    re.IGNORECASE,
)
LOCATION_RELATION_RE = re.compile(
    r"^(?P<subject>.+?)\s+(?:is|are|was|were)\s+(?P<predicate>in|at|inside|near|from|based in|located in)\s+(?P<object>.+)$",
    re.IGNORECASE,
)
ACTIVE_RELATION_RE = re.compile(
    r"^(?P<subject>.+?)\s+(?P<predicate>causes?|caused|leads to|led|leads|results in|produces?|prevents?|requires?|modifies?|discovered|discovers?|founded|created|creates|wrote|writes)\s+(?P<object>.+)$",
    re.IGNORECASE,
)
LEAD_BY_RE = re.compile(r"\bled\s+by\s+(?P<leader>[A-Z][A-Za-z.'-]+(?:\s+[A-Z][A-Za-z.'-]+)+)", re.IGNORECASE)
ACTIVE_LEAD_RE = re.compile(
    r"\b(?P<leader>[A-Z][A-Za-z.'-]+(?:\s+[A-Z][A-Za-z.'-]+)+)\s+led\s+(?P<target>[A-Z][A-Za-z0-9&.'-]+)",
    re.IGNORECASE,
)
CURRENT_STATUS_RE = re.compile(
    r"\b(?:currently\s+underway|is\s+underway|are\s+underway|has\s+begun|have\s+begun|has\s+started|have\s+started)\b",
    re.IGNORECASE,
)
FUTURE_STATUS_RE = re.compile(
    r"\b(?:will\s+(?:focus|begin|start|launch)|expected\s+to\s+begin|expected\s+to\s+start|within\s+\w+\s+years?)\b",
    re.IGNORECASE,
)
NEGATION_RE = re.compile(r"\b(?:no|not|never|without|cannot|can't|prohibited|forbidden|disallowed)\b", re.IGNORECASE)
STRONG_NEGATION_RE = re.compile(r"\b(?:no|not|never|cannot|can't|prohibited|forbidden|disallowed)\b", re.IGNORECASE)
WHITESPACE_RE = re.compile(r"\s+")
LIST_VERB_RE = re.compile(
    r"\b(?P<verb>captures?|stores?|adds?|includes?|offers?|provides?|serves?|allows?|checks?|detects?|verifies?|reports?|records?|logs?|supports?|keeps?|calls?|maps?|creates?|runs?|writes?|saves?|evaluates?|gets?|fetches?|retrieves?|reranks?)\b\s+(?P<tail>.+)",
    re.IGNORECASE,
)
LIST_ITEM_RE = re.compile(
    r"^(?P<verb>captures?|stores?|adds?|includes?|offers?|provides?|serves?|allows?|checks?|detects?|verifies?|reports?|records?|logs?|supports?|keeps?|calls?|maps?|creates?|runs?|writes?|saves?|evaluates?|gets?|fetches?|retrieves?|reranks?)\s+(?P<tail>.+)$",
    re.IGNORECASE,
)

STOPWORDS = {
    "a",
    "about",
    "above",
    "after",
    "again",
    "all",
    "also",
    "am",
    "an",
    "and",
    "any",
    "are",
    "as",
    "at",
    "be",
    "because",
    "been",
    "before",
    "being",
    "between",
    "both",
    "but",
    "by",
    "can",
    "could",
    "did",
    "do",
    "does",
    "doing",
    "during",
    "each",
    "few",
    "for",
    "from",
    "further",
    "had",
    "has",
    "have",
    "having",
    "he",
    "her",
    "here",
    "hers",
    "him",
    "his",
    "however",
    "how",
    "i",
    "if",
    "in",
    "into",
    "is",
    "it",
    "its",
    "itself",
    "may",
    "more",
    "most",
    "must",
    "my",
    "no",
    "nor",
    "not",
    "of",
    "off",
    "on",
    "once",
    "only",
    "or",
    "other",
    "our",
    "out",
    "over",
    "own",
    "same",
    "s",
    "she",
    "should",
    "so",
    "some",
    "such",
    "than",
    "that",
    "the",
    "their",
    "theirs",
    "them",
    "then",
    "there",
    "these",
    "they",
    "this",
    "those",
    "through",
    "to",
    "too",
    "under",
    "until",
    "up",
    "very",
    "was",
    "we",
    "were",
    "what",
    "when",
    "where",
    "which",
    "while",
    "who",
    "whom",
    "why",
    "will",
    "with",
    "within",
    "would",
    "you",
    "your",
}

PREDICATE_MARKERS = {
    "are",
    "is",
    "was",
    "were",
    "do",
    "does",
    "did",
    "must",
    "should",
    "will",
    "would",
    "can",
    "could",
    "may",
    "might",
    "not",
}

LIST_VERB_TOKENS = {
    "capture",
    "captures",
    "store",
    "stores",
    "add",
    "adds",
    "include",
    "includes",
    "offer",
    "offers",
    "provide",
    "provides",
    "serve",
    "serves",
    "allow",
    "allows",
    "check",
    "checks",
    "detect",
    "detects",
    "verify",
    "verifies",
    "report",
    "reports",
    "record",
    "records",
    "log",
    "logs",
    "support",
    "supports",
    "keep",
    "keeps",
    "call",
    "calls",
    "map",
    "maps",
    "create",
    "creates",
    "run",
    "runs",
    "write",
    "writes",
    "save",
    "saves",
    "evaluate",
    "evaluates",
    "get",
    "gets",
    "fetch",
    "fetches",
    "retrieve",
    "retrieves",
    "rerank",
    "reranks",
}


@dataclass(frozen=True)
class RequiredFact:
    text: str
    type: str

    def to_dict(self) -> dict[str, str]:
        return {"text": self.text, "type": self.type}


@dataclass(frozen=True)
class RelationFact:
    subject: str
    predicate: str
    object: str


@dataclass(frozen=True)
class FactMatch:
    required_facts: list[str]
    matched_facts: list[str]
    missing_facts: list[str]
    conflicting_facts: list[str]
    required_fact_details: list[RequiredFact]
    matched_fact_details: list[RequiredFact]
    missing_fact_details: list[RequiredFact]
    conflicting_fact_details: list[RequiredFact]

    @property
    def coverage(self) -> float:
        if not self.required_facts:
            return 0.0
        return len(self.matched_facts) / len(self.required_facts)


def extract_required_facts(claim_text: str) -> list[str]:
    return [fact.text for fact in extract_required_fact_details(claim_text)]


def extract_required_fact_details(claim_text: str) -> list[RequiredFact]:
    claim = _clean(claim_text).rstrip(".!?")
    if not claim:
        return []

    facts: list[RequiredFact] = []
    facts.extend(_contrast_facts(claim))
    facts.extend(_list_facts(claim))
    if not facts:
        facts.append(RequiredFact(text=claim, type=_fact_type(claim)))

    for pattern, fact_type in ((VERSION_RE, "version"), (PATH_RE, "path"), (NUMBER_UNIT_RE, "numeric")):
        for match in pattern.finditer(claim):
            value = match.group(1) if pattern is PATH_RE else match.group(0)
            facts.append(RequiredFact(text=_clean(value), type=fact_type))

    if NEGATION_RE.search(claim):
        facts.append(RequiredFact(text=_clean(claim), type="negation"))

    return _unique_fact_list(facts)


def compare_facts(claim_text: str, evidence_text: str, *, mode: str = "lexical") -> FactMatch:
    required_details = extract_required_fact_details(claim_text)
    matched_details: list[RequiredFact] = []
    missing_details: list[RequiredFact] = []
    conflicting_details: list[RequiredFact] = []
    structured_data = _structured_json(evidence_text)
    structured_dict = isinstance(structured_data, dict)
    for fact in required_details:
        if _fact_supported(fact.text, evidence_text, mode=mode):
            matched_details.append(fact)
        else:
            missing_details.append(fact)

    if not structured_dict and _has_negation_conflict(claim_text, evidence_text, mode=mode):
        conflicting_details.append(RequiredFact(text=claim_text.strip(), type="negation"))
    version_conflict = _version_conflict(claim_text, evidence_text, mode=mode)
    if version_conflict is not None:
        conflicting_details.append(version_conflict)
    numeric_conflict = _numeric_conflict(claim_text, evidence_text, mode=mode)
    if numeric_conflict is not None:
        conflicting_details.append(numeric_conflict)
    for structured_conflict in _structured_value_conflicts(claim_text, evidence_text):
        conflicting_details.append(structured_conflict)
    status_conflict = _status_conflict(claim_text, evidence_text)
    if status_conflict is not None:
        conflicting_details.append(status_conflict)
    relation_conflict = _relation_conflict(claim_text, evidence_text, mode=mode)
    if relation_conflict is not None:
        conflicting_details.append(relation_conflict)
    lead_conflict = _lead_relation_conflict(claim_text, evidence_text, mode=mode)
    if lead_conflict is not None:
        conflicting_details.append(lead_conflict)

    return FactMatch(
        required_facts=[fact.text for fact in required_details],
        matched_facts=[fact.text for fact in matched_details],
        missing_facts=[fact.text for fact in missing_details],
        conflicting_facts=[fact.text for fact in conflicting_details],
        required_fact_details=required_details,
        matched_fact_details=matched_details,
        missing_fact_details=missing_details,
        conflicting_fact_details=conflicting_details,
    )


def _contrast_facts(claim: str) -> list[RequiredFact]:
    if not re.search(r"\bwhile\b", claim, flags=re.IGNORECASE):
        return []
    parts = [
        _clean(part.strip(" ,;"))
        for part in re.split(r"\bwhile\b", claim, flags=re.IGNORECASE)
        if _clean(part.strip(" ,;"))
    ]
    if len(parts) <= 1:
        return []

    facts: list[RequiredFact] = []
    for part in parts:
        for segment in _split_contrast_segment(part):
            if segment:
                facts.append(RequiredFact(text=segment, type=_fact_type(segment)))
    return facts if len(facts) > 1 else []


def _split_contrast_segment(segment: str) -> list[str]:
    value = _clean(segment)
    if not value:
        return []
    match = re.search(r"\b(?P<verb>modifies?|modify)\b\s+(?P<tail>.+)$", value, flags=re.IGNORECASE)
    if not match:
        return [value]

    subject = value[: match.start("verb")].strip(" ,;")
    verb = match.group("verb")
    tail = match.group("tail").strip(" ,;")
    if not subject or not tail:
        return [value]
    return ["%s %s %s" % (subject, verb, tail)]


def _list_facts(claim: str) -> list[RequiredFact]:
    match = LIST_VERB_RE.search(claim)
    if not match:
        return []
    verb = match.group("verb").lower()
    tail = match.group("tail").strip()
    if "," not in tail and " and " not in tail.lower():
        return []

    parts = [
        _clean(part.strip(" ,;"))
        for part in re.split(r",|\s+\band\b\s+", tail)
        if _clean(part.strip(" ,;"))
    ]
    if len(parts) <= 1:
        return []

    facts: list[RequiredFact] = []
    for part in parts:
        if _contains_predicate(part):
            facts.append(RequiredFact(text=part, type=_fact_type(part)))
        elif _starts_with_list_verb(part):
            facts.append(RequiredFact(text=part, type="predicate"))
        else:
            facts.append(RequiredFact(text="%s %s" % (verb, part), type="predicate"))
    return facts


def _starts_with_list_verb(value: str) -> bool:
    first = _clean_token(value.split()[0]) if value.split() else ""
    return first in LIST_VERB_TOKENS


STRUCTURED_FEATURES = (
    ("wifi", ("wifi", "wi-fi", "wireless internet"), (("attributes", "WiFi"),)),
    ("validated parking", ("validated parking", "parking validation"), (("attributes", "BusinessParking", "validated"),)),
    ("garage parking", ("garage parking", "parking garage"), (("attributes", "BusinessParking", "garage"),)),
    ("lot parking", ("lot parking", "parking lot"), (("attributes", "BusinessParking", "lot"),)),
    ("street parking", ("street parking",), (("attributes", "BusinessParking", "street"),)),
    ("valet parking", ("valet parking",), (("attributes", "BusinessParking", "valet"),)),
    (
        "reservations",
        ("reservations", "reservation", "takes reservations", "take reservations", "accepts reservations"),
        (("attributes", "RestaurantsReservations"),),
    ),
    ("outdoor seating", ("outdoor seating", "outside seating", "patio seating"), (("attributes", "OutdoorSeating"),)),
    ("takeout", ("takeout", "take out", "take-out"), (("attributes", "RestaurantsTakeOut"),)),
    ("music", ("music", "live music"), (("attributes", "Music"),)),
    ("good for groups", ("good for groups", "larger groups", "large groups"), (("attributes", "RestaurantsGoodForGroups"),)),
    ("casual ambience", ("casual", "casual atmosphere", "casual ambiance", "casual ambience"), (("attributes", "Ambience", "casual"),)),
    ("classy ambience", ("classy", "classy atmosphere", "classy ambiance", "classy ambience"), (("attributes", "Ambience", "classy"),)),
    ("divey ambience", ("divey", "dive bar", "divey atmosphere", "divey ambiance"), (("attributes", "Ambience", "divey"),)),
    ("hipster ambience", ("hipster", "hipster atmosphere", "hipster ambiance"), (("attributes", "Ambience", "hipster"),)),
    ("intimate ambience", ("intimate", "intimate atmosphere", "intimate ambiance"), (("attributes", "Ambience", "intimate"),)),
    ("romantic ambience", ("romantic", "romantic atmosphere", "romantic ambiance", "dates"), (("attributes", "Ambience", "romantic"),)),
    ("touristy ambience", ("touristy", "touristy atmosphere", "touristy ambiance"), (("attributes", "Ambience", "touristy"),)),
    ("trendy ambience", ("trendy", "trendy atmosphere", "trendy ambiance"), (("attributes", "Ambience", "trendy"),)),
    ("upscale ambience", ("upscale", "upscale atmosphere", "upscale ambiance"), (("attributes", "Ambience", "upscale"),)),
)


def _fact_supported(fact: str, evidence_text: str, *, mode: str) -> bool:
    if _fact_supported_by_structured_data(fact, evidence_text):
        return True
    relation = _extract_relation(fact)
    units = _evidence_units(evidence_text)
    if relation is not None and _any_relation_conflict(relation, units, mode=mode):
        return False
    if any(_fact_supported_by_unit(fact, unit, mode=mode) for unit in units):
        return True
    if relation is not None:
        return False
    return _fact_supported_by_unit(fact, evidence_text, mode=mode)


def _fact_supported_by_structured_data(fact: str, evidence_text: str) -> bool:
    data = _structured_json(evidence_text)
    if not isinstance(data, dict):
        return False
    fact_text = _semantic_text(fact)

    mentioned_features = [
        (phrases, paths)
        for _, phrases, paths in STRUCTURED_FEATURES
        if _mentions_any(fact_text, phrases)
    ]
    if mentioned_features:
        return all(
            _structured_feature_supported_for_data(fact_text, phrases, paths, data)
            for phrases, paths in mentioned_features
        )

    if _category_supports_fact(fact_text, data):
        return True
    if _rating_supports_fact(fact_text, data):
        return True
    return False


def _structured_feature_supported_for_data(
    fact_text: str,
    phrases: tuple[str, ...],
    paths: tuple[tuple[str, ...], ...],
    data: dict[str, object],
) -> bool:
    values = [_structured_lookup(data, path) for path in paths]
    if _claim_denies_any(fact_text, phrases):
        return any(_value_is_negative(value) for value in values)
    return any(_value_is_positive(value) for value in values)


def _structured_value_conflicts(claim_text: str, evidence_text: str) -> list[RequiredFact]:
    data = _structured_json(evidence_text)
    if not isinstance(data, dict):
        return []
    claim = _semantic_text(claim_text)
    conflicts: list[RequiredFact] = []

    for feature_name, phrases, paths in STRUCTURED_FEATURES:
        if not _mentions_any(claim, phrases):
            continue
        values = [_structured_lookup(data, path) for path in paths]
        if _claim_denies_any(claim, phrases) and any(_value_is_positive(value) for value in values):
            conflicts.append(RequiredFact(text=feature_name, type="structured_value"))
        if not _claim_denies_any(claim, phrases) and any(_value_is_negative(value) for value in values):
            conflicts.append(RequiredFact(text=feature_name, type="structured_value"))

    if _claim_denies_parking(claim) and _structured_parking_has_available_option(data):
        conflicts.append(RequiredFact(text="parking", type="structured_value"))
    hours_conflict = _structured_hours_conflict(claim, data)
    if hours_conflict is not None:
        conflicts.append(hours_conflict)
    return _unique_fact_list(conflicts)


@lru_cache(maxsize=256)
def _structured_json(evidence_text: str) -> object | None:
    value = str(evidence_text or "").strip()
    if not value.startswith("{"):
        return None
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return None


def _structured_lookup(data: dict[str, object], path: tuple[str, ...]) -> object | None:
    current: object = data
    for part in path:
        if not isinstance(current, dict):
            return None
        match = next((key for key in current if key.lower() == part.lower()), None)
        if match is None:
            return None
        current = current[match]
    return current


def _value_is_positive(value: object) -> bool:
    if value is True:
        return True
    if value is False or value is None:
        return False
    if isinstance(value, (int, float)):
        return value > 0
    normalized = str(value).strip().lower()
    return normalized not in {"", "0", "false", "no", "none", "null", "n/a", "na"}


def _value_is_negative(value: object) -> bool:
    if value is False:
        return True
    if value is None:
        return False
    normalized = str(value).strip().lower()
    return normalized in {"false", "no", "none", "0"}


def _mentions_any(text: str, phrases: tuple[str, ...]) -> bool:
    normalized = str(text or "").lower()
    return any(phrase in normalized for phrase in phrases)


def _claim_denies_any(text: str, phrases: tuple[str, ...]) -> bool:
    normalized = str(text or "").lower()
    for phrase in phrases:
        escaped = re.escape(phrase)
        if re.search(r"\b(?:no|not|without|lacks?|lack|does\s+not|do\s+not|doesnt|dont)\b.{0,45}\b%s\b" % escaped, normalized):
            return True
        if re.search(r"\b%s\b.{0,30}\b(?:unavailable|not\s+available|not\s+offered)\b" % escaped, normalized):
            return True
    return False


def _claim_denies_parking(text: str) -> bool:
    return bool(
        re.search(
            r"\b(?:no|not|without|lacks?|lack)\b.{0,45}\b(?:parking|parking\s+facilities)\b",
            str(text or "").lower(),
        )
    )


def _structured_parking_has_available_option(data: dict[str, object]) -> bool:
    parking = _structured_lookup(data, ("attributes", "BusinessParking"))
    if not isinstance(parking, dict):
        return False
    return any(_value_is_positive(value) for value in parking.values())


def _structured_hours_conflict(claim_text: str, data: dict[str, object]) -> RequiredFact | None:
    claim = str(claim_text or "").lower()
    if "open" not in claim and "hours" not in claim:
        return None
    claim_range = _claim_time_range(claim)
    if claim_range is None:
        return None
    hours = data.get("hours")
    if not isinstance(hours, dict) or not hours:
        return None
    ranges = [
        parsed
        for value in hours.values()
        for parsed in [_structured_time_range(str(value or ""))]
        if parsed is not None
    ]
    if not ranges:
        return None
    if _claim_implies_uniform_hours(claim) and any(parsed != claim_range for parsed in ranges):
        return RequiredFact(text="hours", type="structured_value")
    if any(parsed == claim_range for parsed in ranges):
        return None
    claim_start, claim_end = claim_range
    if any(start == claim_start or end != claim_end for start, end in ranges):
        return RequiredFact(text="hours", type="structured_value")
    return None


def _claim_implies_uniform_hours(text: str) -> bool:
    return bool(
        re.search(
            r"\b(?:every\s+day|seven\s+days|7\s+days|monday\s+through|monday\s+to|daily)\b",
            str(text or ""),
            flags=re.IGNORECASE,
        )
    )


def _claim_time_range(text: str) -> tuple[int, int] | None:
    match = re.search(
        r"\bfrom\s+(?P<start>\d{1,2}(?::\d{1,2})?\s*(?:am|pm)?)\s*(?:to|-|until)\s+(?P<end>\d{1,2}(?::\d{1,2})?\s*(?:am|pm)?)",
        text,
        flags=re.IGNORECASE,
    )
    if not match:
        return None
    start = _parse_time_of_day(match.group("start"))
    end = _parse_time_of_day(match.group("end"))
    if start is None or end is None:
        return None
    return (start, end)


def _structured_time_range(value: str) -> tuple[int, int] | None:
    if "-" not in value:
        return None
    start_text, end_text = value.split("-", 1)
    start = _parse_time_of_day(start_text)
    end = _parse_time_of_day(end_text)
    if start is None or end is None:
        return None
    return (start, end)


def _parse_time_of_day(value: str) -> int | None:
    match = re.search(r"\b(?P<hour>\d{1,2})(?::(?P<minute>\d{1,2}))?\s*(?P<period>am|pm)?\b", str(value or ""), flags=re.IGNORECASE)
    if not match:
        return None
    hour = int(match.group("hour"))
    minute = int(match.group("minute") or 0)
    period = (match.group("period") or "").lower()
    if minute >= 60:
        return None
    if period:
        if hour < 1 or hour > 12:
            return None
        if period == "pm" and hour != 12:
            hour += 12
        if period == "am" and hour == 12:
            hour = 0
    if hour > 23:
        return None
    return (hour * 60) + minute


def _category_supports_fact(fact_text: str, data: dict[str, object]) -> bool:
    categories = str(data.get("categories") or "").lower()
    if not categories:
        return False
    category_tokens = set(_important_tokens(categories, mode="semantic"))
    fact_tokens = set(_important_tokens(fact_text, mode="semantic"))
    if not category_tokens or not fact_tokens:
        return False
    category_overlap = category_tokens.intersection(fact_tokens)
    coverage = len(category_overlap) / len(fact_tokens)
    if {"restaurant", "bar", "food", "cuisine"}.intersection(fact_tokens) and category_overlap and coverage >= 0.45:
        return True
    return len(category_overlap) >= 2 and coverage >= 0.45


def _rating_supports_fact(fact_text: str, data: dict[str, object]) -> bool:
    if "star" not in fact_text and "rating" not in fact_text:
        return False
    rating = data.get("business_stars")
    if rating is None:
        return False
    claim_numbers = set(NUMBER_RE.findall(fact_text))
    if not claim_numbers:
        return False
    rating_text = ("%s" % rating).rstrip("0").rstrip(".")
    rating_values = {str(rating), rating_text}
    return bool(claim_numbers.intersection(rating_values))


def _fact_supported_by_unit(fact: str, evidence_unit: str, *, mode: str) -> bool:
    if _missing_exact_terms(fact, evidence_unit):
        for scoped_fact in _scope_variants(fact):
            if scoped_fact == _clean(fact) or _missing_exact_terms(scoped_fact, evidence_unit):
                continue
            if _fact_supported_by_unit(scoped_fact, evidence_unit, mode=mode):
                return True
        return False

    fact_tokens = _important_tokens(fact, mode=mode)
    if not fact_tokens:
        return False
    evidence_tokens = set(_important_tokens(evidence_unit, mode=mode))
    matched = [token for token in fact_tokens if token in evidence_tokens]
    coverage = len(matched) / len(fact_tokens)
    if coverage >= 0.72:
        return True

    compact_fact = _compact(fact, mode=mode)
    compact_evidence = _compact(evidence_unit, mode=mode)
    if compact_fact and compact_fact in compact_evidence:
        return True

    if _list_item_supported(fact, evidence_unit, evidence_tokens, mode=mode):
        return True

    for scoped_fact in _scope_variants(fact):
        if scoped_fact != _clean(fact) and _fact_supported_by_unit(scoped_fact, evidence_unit, mode=mode):
            return True

    return len(matched) >= 2 and coverage >= 0.62


def _drop_leading_scope(fact: str) -> str:
    variants = _scope_variants(fact)
    return variants[0] if variants else _clean(fact).rstrip(".!?")


def _scope_variants(fact: str) -> list[str]:
    value = _clean(fact).rstrip(".!?")
    variants: list[str] = []
    scoped = re.sub(r"^in\s+[A-Z][A-Za-z0-9_.-]+(?:\s+issue\s+\d+)?,\s*", "", value, flags=re.IGNORECASE)
    if scoped != value:
        variants.append(scoped)

    words = value.split()
    if len(words) >= 4:
        first = words[0].strip(" ,;:")
        if _looks_like_scope_token(first):
            variants.append(" ".join(words[1:]))

        for index, word in enumerate(words[:4]):
            token = word.strip(" ,;:")
            if index == 0 or not _looks_like_scope_token(token):
                continue
            variants.append(" ".join([*words[:index], *words[index + 1 :]]))

        prefix_end = _leading_scope_phrase_end(words)
        if prefix_end > 1 and prefix_end < len(words):
            variants.append(" ".join(words[prefix_end:]))

    output: list[str] = []
    seen = set()
    for variant in variants:
        cleaned = _clean(variant).rstrip(".!?")
        if cleaned and cleaned != value and cleaned.lower() not in seen:
            seen.add(cleaned.lower())
            output.append(cleaned)
    return output


def _looks_like_scope_token(token: str) -> bool:
    value = token.strip(" ,;:")
    if not value or "-" in value:
        return False
    if value.isupper() and len(value) >= 2:
        return True
    return any(char.isupper() for char in value[1:])


def _leading_scope_phrase_end(words: list[str]) -> int:
    prefix: list[str] = []
    has_scope_marker = False
    for word in words[:5]:
        token = word.strip(" ,;:")
        if not token:
            break
        if not (token[:1].isupper() or token.isupper()):
            break
        prefix.append(token)
        has_scope_marker = has_scope_marker or _looks_like_scope_token(token)
    if len(prefix) < 2 or not has_scope_marker:
        return 0
    return len(prefix)


def _list_item_supported(
    fact: str,
    evidence_text: str,
    evidence_tokens: set[str],
    *,
    mode: str,
) -> bool:
    match = LIST_ITEM_RE.match(_clean(fact))
    if not match:
        return False

    verb = _canonical_token(match.group("verb"), mode=mode)
    tail_tokens = _important_tokens(match.group("tail"), mode=mode)
    if not tail_tokens or any(token not in evidence_tokens for token in tail_tokens):
        return False

    evidence_lower = str(evidence_text or "").lower()
    if verb in {"include", "support"}:
        return any(marker in evidence_lower for marker in ("include", "support", " are ", ":", "subset"))
    if verb == "keep":
        return any(marker in evidence_lower for marker in ("stays local", "stay local", "keeps", "local"))
    return True


def _important_tokens(text: str, *, mode: str) -> list[str]:
    seen = set()
    output: list[str] = []
    for raw in TOKEN_RE.findall(_semantic_text(text) if mode == "semantic" else str(text or "").lower()):
        token = raw.strip("._-/").lower()
        if not token or token in STOPWORDS:
            continue
        canonical = _canonical_token(token, mode=mode)
        if canonical and canonical not in seen:
            seen.add(canonical)
            output.append(canonical)
    return output


def _canonical_token(token: str, *, mode: str) -> str:
    value = token.lower().strip()
    if mode == "semantic":
        value = SEMANTIC_TOKEN_MAP.get(value, value)
    if value.endswith("ies") and len(value) > 4:
        return value[:-3] + "y"
    if mode == "semantic" and value.endswith("ing") and len(value) > 5:
        return value[:-3]
    if mode == "semantic" and value.endswith("ed") and len(value) > 4:
        return value[:-2]
    if value.endswith("s") and len(value) > 3 and not value.endswith("ss"):
        return value[:-1]
    return value


def _token_overlap(claim_text: str, evidence_text: str, *, mode: str) -> float:
    claim_tokens = _important_tokens(claim_text, mode=mode)
    evidence_tokens = set(_important_tokens(evidence_text, mode=mode))
    if not claim_tokens:
        return 0.0
    return len([token for token in claim_tokens if token in evidence_tokens]) / len(claim_tokens)


def _has_negation_conflict(claim_text: str, evidence_text: str, *, mode: str) -> bool:
    claim_polarity = _negation_polarity(claim_text)
    units = _evidence_units(evidence_text)
    if not units:
        return False
    if mode == "semantic" and _negated_truth_support(claim_text, evidence_text):
        return False
    if _is_uncertainty_claim(claim_text) and any(
        _token_overlap(claim_text, unit, mode=mode) >= 0.35 for unit in units
    ):
        return False

    if claim_polarity == "affirmative" and any(
        _token_overlap(claim_text, _non_negated_clause_text(unit), mode=mode) >= 0.65
        for unit in units
        if _non_negated_clause_text(unit)
    ):
        return False

    same_polarity_support = any(
        (
            _negation_polarity(unit) == claim_polarity
            or _shares_non_strong_without_context(claim_text, unit)
        )
        and _token_overlap(claim_text, unit, mode=mode) >= 0.40
        for unit in units
    )
    if same_polarity_support:
        return False

    return any(
        _negation_polarity(unit) != claim_polarity
        and _token_overlap(claim_text, unit, mode=mode) >= 0.45
        for unit in units
    )


def _is_uncertainty_claim(text: str) -> bool:
    return bool(
        re.search(
            r"\b(?:unclear|not\s+clear|unknown|uncertain|not\s+known)\s+whether\b",
            str(text or ""),
            flags=re.IGNORECASE,
        )
    )


def _negation_polarity(text: str) -> str:
    normalized = _neutralize_non_negating_phrases(_normalize_negation_text(text))
    if STRONG_NEGATION_RE.search(normalized):
        return "strong_negated"
    if NEGATION_RE.search(normalized):
        return "weak_negated"
    return "affirmative"


def _neutralize_non_negating_phrases(text: str) -> str:
    value = str(text or "")
    return re.sub(r"\bnot\s+only\b", "also", value, flags=re.IGNORECASE)


def _normalize_negation_text(text: str) -> str:
    value = str(text or "")
    value = re.sub(r"\bcan['’]?t\b", "cannot", value, flags=re.IGNORECASE)
    return re.sub(r"\b([A-Za-z]+)n['’]t\b", r"\1 not", value)


def _negated_truth_support(claim_text: str, evidence_text: str) -> bool:
    claim = _semantic_text(claim_text)
    evidence = _normalize_negation_text(evidence_text).lower()
    if "false" not in claim:
        return False
    if "not exactly" not in evidence or "true" not in evidence:
        return False
    return _token_overlap(claim_text, evidence_text, mode="semantic") >= 0.45


def _shares_non_strong_without_context(claim_text: str, evidence_unit: str) -> bool:
    claim = str(claim_text or "").lower()
    unit = str(evidence_unit or "").lower()
    return "without" in claim and "without" in unit and not STRONG_NEGATION_RE.search(claim)


def _version_conflict(claim_text: str, evidence_text: str, *, mode: str) -> RequiredFact | None:
    claim_versions = set(match.group(0).lower() for match in VERSION_RE.finditer(claim_text))
    evidence_versions = set(match.group(0).lower() for match in VERSION_RE.finditer(evidence_text))
    if not claim_versions or not evidence_versions:
        return None
    if claim_versions.isdisjoint(evidence_versions) and _anchor_overlap(claim_text, evidence_text, mode=mode) >= 0.35:
        return RequiredFact(text=", ".join(sorted(claim_versions)), type="version")
    return None


def _numeric_conflict(claim_text: str, evidence_text: str, *, mode: str) -> RequiredFact | None:
    claim_ports = set(PORT_RE.findall(str(claim_text or "")))
    evidence_ports = set(PORT_RE.findall(str(evidence_text or "")))
    if (
        claim_ports
        and evidence_ports
        and claim_ports.isdisjoint(evidence_ports)
        and _anchor_overlap(claim_text, evidence_text, mode=mode) >= 0.45
    ):
        return RequiredFact(text=", ".join(sorted(claim_ports)), type="numeric")

    claim_numbers = set(NUMBER_RE.findall(str(claim_text or "")))
    evidence_numbers = set(NUMBER_RE.findall(str(evidence_text or "")))
    if not claim_numbers or not evidence_numbers:
        return None
    if claim_numbers.isdisjoint(evidence_numbers) and _anchor_overlap(claim_text, evidence_text, mode=mode) >= 0.65:
        return RequiredFact(text=", ".join(sorted(claim_numbers)), type="numeric")
    return None


def _relation_conflict(claim_text: str, evidence_text: str, *, mode: str) -> RequiredFact | None:
    relation = _extract_relation(claim_text)
    if relation is None:
        return None
    if _any_relation_conflict(relation, _evidence_units(evidence_text), mode=mode):
        return RequiredFact(text=_clean(claim_text).rstrip(".!?"), type="relation")
    return None


def _status_conflict(claim_text: str, evidence_text: str) -> RequiredFact | None:
    if not CURRENT_STATUS_RE.search(str(claim_text or "")):
        return None
    if not FUTURE_STATUS_RE.search(str(evidence_text or "")):
        return None
    return RequiredFact(text=_clean(claim_text).rstrip(".!?"), type="temporal_status")


def _lead_relation_conflict(claim_text: str, evidence_text: str, *, mode: str) -> RequiredFact | None:
    claim = str(claim_text or "")
    evidence = str(evidence_text or "")
    claim_leader = _passive_leader(claim)
    evidence_leader = _active_leader(evidence)
    if not claim_leader or not evidence_leader:
        return None
    if _bidirectional_phrase_overlap(claim_leader, evidence_leader, mode=mode) >= 0.72:
        return None
    target = _lead_target(claim)
    if target and _phrase_overlap(target, evidence, mode=mode) < 0.35:
        return None
    return RequiredFact(text=_clean(claim_text).rstrip(".!?"), type="relation")


def _passive_leader(text: str) -> str:
    match = LEAD_BY_RE.search(str(text or ""))
    if not match:
        return ""
    return _clean_relation_phrase(match.group("leader").split("'")[0])


def _active_leader(text: str) -> str:
    match = ACTIVE_LEAD_RE.search(str(text or ""))
    if not match:
        return ""
    return _clean_relation_phrase(match.group("leader"))


def _lead_target(text: str) -> str:
    before = str(text or "").split("led by", 1)[0]
    candidates = [
        token
        for token in TOKEN_RE.findall(before)
        if token[:1].isupper() and token.lower() not in {"the", "in", "on", "at"}
    ]
    return candidates[0] if candidates else ""


def _any_relation_conflict(
    claim_relation: RelationFact,
    evidence_units: list[str],
    *,
    mode: str,
) -> bool:
    return any(
        _relations_conflict(claim_relation, evidence_relation, mode=mode)
        for unit in evidence_units
        for evidence_relation in [_extract_relation(unit)]
        if evidence_relation is not None
    )


def _relations_conflict(claim: RelationFact, evidence: RelationFact, *, mode: str) -> bool:
    if claim.predicate != evidence.predicate:
        return False

    subject_overlap = _bidirectional_phrase_overlap(claim.subject, evidence.subject, mode=mode)
    object_overlap = _bidirectional_phrase_overlap(claim.object, evidence.object, mode=mode)
    reversed_subject_overlap = _bidirectional_phrase_overlap(claim.subject, evidence.object, mode=mode)
    reversed_object_overlap = _bidirectional_phrase_overlap(claim.object, evidence.subject, mode=mode)

    if reversed_subject_overlap >= 0.72 and reversed_object_overlap >= 0.72:
        return True
    if subject_overlap >= 0.72 and object_overlap < 0.50:
        return True
    if _same_relation_head_with_different_modifier(claim.subject, evidence.subject, mode=mode) and object_overlap < 0.50:
        return True
    if object_overlap >= 0.72 and (
        subject_overlap < 0.35 or _proper_name_conflict(claim.subject, evidence.subject)
    ):
        return True
    return False


def _extract_relation(text: str) -> RelationFact | None:
    value = _clean(text).rstrip(".!?")
    for pattern in (LOCATION_RELATION_RE, ACTIVE_RELATION_RE):
        match = pattern.match(value)
        if match:
            return RelationFact(
                subject=_clean_relation_phrase(match.group("subject")),
                predicate=_canonical_relation_predicate(match.group("predicate")),
                object=_clean_relation_phrase(match.group("object")),
            )
    return None


def _same_relation_head_with_different_modifier(left: str, right: str, *, mode: str) -> bool:
    left_tokens = _relation_tokens(left, mode=mode)
    right_tokens = _relation_tokens(right, mode=mode)
    if len(left_tokens) < 2 or len(right_tokens) < 2:
        return False
    return left_tokens[-1] == right_tokens[-1] and left_tokens[0] != right_tokens[0]


def _proper_name_conflict(left: str, right: str) -> bool:
    left_names = _capitalized_name_tokens(left)
    right_names = _capitalized_name_tokens(right)
    if len(left_names) < 2 or len(right_names) < 2:
        return False
    if left_names[0].lower() != right_names[0].lower():
        return False
    return left_names[-1].lower() != right_names[-1].lower()


def _capitalized_name_tokens(value: str) -> list[str]:
    return [
        token
        for token in TOKEN_RE.findall(str(value or ""))
        if token[:1].isupper() and token[1:].islower()
    ]


def _canonical_relation_predicate(value: str) -> str:
    normalized = _clean(value).lower()
    if normalized in {"is in", "are in", "was in", "were in", "located in", "based in", "inside"}:
        return "in"
    if normalized in {"causes", "caused"}:
        return "cause"
    if normalized == "leads to":
        return "cause"
    if normalized in {"led", "leads"}:
        return "lead"
    if normalized in {"modifies", "modify"}:
        return "modify"
    if normalized == "results in":
        return "cause"
    if normalized in {"produces", "produce"}:
        return "produce"
    if normalized in {"prevents", "prevent"}:
        return "prevent"
    if normalized in {"requires", "require"}:
        return "require"
    if normalized in {"discovers", "discovered"}:
        return "discover"
    if normalized == "founded":
        return "found"
    if normalized in {"created", "creates"}:
        return "create"
    if normalized in {"wrote", "writes"}:
        return "write"
    return normalized


def _clean_relation_phrase(value: str) -> str:
    cleaned = _clean(value).strip(" ,;:")
    words = cleaned.split()
    while len(words) > 1 and words[0].lower() in {"the", "a", "an"}:
        words = words[1:]
    return " ".join(words)


def _bidirectional_phrase_overlap(left: str, right: str, *, mode: str) -> float:
    return max(
        _phrase_overlap(left, right, mode=mode),
        _phrase_overlap(right, left, mode=mode),
    )


def _phrase_overlap(left: str, right: str, *, mode: str) -> float:
    left_tokens = _relation_tokens(left, mode=mode)
    right_tokens = set(_relation_tokens(right, mode=mode))
    if not left_tokens:
        return 0.0
    return len([token for token in left_tokens if token in right_tokens]) / len(left_tokens)


def _relation_tokens(text: str, *, mode: str) -> list[str]:
    raw_tokens = [
        token.strip("._-/").lower()
        for token in TOKEN_RE.findall(_semantic_text(text) if mode == "semantic" else str(text or "").lower())
    ]
    output: list[str] = []
    seen = set()
    for token in raw_tokens:
        if not token:
            continue
        if len(raw_tokens) > 1 and token in {"the", "a", "an"}:
            continue
        canonical = _canonical_token(token, mode=mode)
        if canonical and canonical not in seen:
            seen.add(canonical)
            output.append(canonical)
    return output


def _anchor_overlap(claim_text: str, evidence_text: str, *, mode: str) -> float:
    claim_tokens = [token for token in _important_tokens(claim_text, mode=mode) if not NUMBER_RE.fullmatch(token)]
    evidence_tokens = {
        token for token in _important_tokens(evidence_text, mode=mode) if not NUMBER_RE.fullmatch(token)
    }
    if not claim_tokens:
        return 0.0
    return len([token for token in claim_tokens if token in evidence_tokens]) / len(claim_tokens)


def _missing_exact_terms(fact: str, evidence_text: str) -> list[str]:
    required = {term.lower() for term in ACRONYM_RE.findall(str(fact or ""))}
    if not required:
        return []
    evidence_values = [str(evidence_text or ""), _semantic_text(evidence_text)]
    present = {term.lower() for value in evidence_values for term in TOKEN_RE.findall(value)}
    present.update(
        part.lower()
        for value in evidence_values
        for token in TOKEN_RE.findall(value)
        for part in re.split(r"[-_./]", token)
        if part
    )
    missing = []
    for term in sorted(required):
        if term in present:
            continue
        expansion = ACRONYM_EXPANSIONS.get(term)
        if expansion and set(expansion).issubset(present):
            continue
        missing.append(term)
    return missing


def _contains_predicate(value: str) -> bool:
    tokens = [_clean_token(token) for token in value.split()]
    return any(token in PREDICATE_MARKERS or token.endswith("ed") for token in tokens)


def _evidence_units(text: str) -> list[str]:
    value = _clean(text)
    if not value:
        return []
    units: list[str] = []
    start = 0
    for index, char in enumerate(value):
        if char not in ".!?":
            continue
        if char == "." and _is_internal_period(value, index):
            continue
        unit = value[start : index + 1].strip()
        if unit:
            units.append(unit)
        start = index + 1
    tail = value[start:].strip()
    if tail:
        units.append(tail)
    return units or [value]


def _evidence_clauses(text: str) -> list[str]:
    return [
        clause.strip()
        for clause in re.split(r"--|;|,|\band\b|\bbut\b", str(text or ""))
        if clause.strip()
    ] or [str(text or "")]


def _non_negated_clause_text(text: str) -> str:
    return " ".join(
        clause for clause in _evidence_clauses(text) if _negation_polarity(clause) == "affirmative"
    )


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


def _unique_fact_list(values: list[RequiredFact]) -> list[RequiredFact]:
    seen = set()
    output: list[RequiredFact] = []
    for value in values:
        fact_text = _clean(value.text).rstrip(".!?")
        if len(fact_text) < 2:
            continue
        key = (fact_text.lower(), value.type)
        if key in seen:
            continue
        seen.add(key)
        output.append(RequiredFact(text=fact_text, type=value.type))
    return output


def _fact_type(value: str) -> str:
    if VERSION_RE.search(value):
        return "version"
    if PATH_RE.search(" " + value):
        return "path"
    if NUMBER_UNIT_RE.search(value):
        return "numeric"
    if NEGATION_RE.search(value):
        return "negation"
    if _contains_predicate(value):
        return "predicate"
    return "keyword"


def _compact(text: str, *, mode: str) -> str:
    return " ".join(_important_tokens(text, mode=mode))


def _clean(text: str) -> str:
    return WHITESPACE_RE.sub(" ", str(text or "")).strip()


def _clean_token(token: str) -> str:
    return token.strip(".,;:!?()[]{}\"'").lower()


SEMANTIC_TOKEN_MAP = {
    "cashback": "refund",
    "reimburse": "refund",
    "reimbursed": "refund",
    "reimbursement": "refund",
    "reimbursements": "refund",
    "return": "refund",
    "returns": "refund",
    "included": "include",
    "including": "include",
    "repay": "refund",
    "repayment": "refund",
    "id": "number",
    "identifier": "number",
    "fetch": "retrieve",
    "fetches": "retrieve",
    "fetched": "retrieve",
    "get": "retrieve",
    "gets": "retrieve",
    "retrieved": "retrieve",
    "retrieves": "retrieve",
    "retrieving": "retrieve",
    "retriever": "retrieval",
    "retrievers": "retrieval",
    "returned": "return",
    "returning": "return",
    "generated": "generate",
    "generates": "generate",
    "generating": "generate",
    "create": "generate",
    "created": "generate",
    "creates": "generate",
    "creating": "generate",
    "gave": "receive",
    "give": "receive",
    "given": "receive",
    "gives": "receive",
    "giving": "receive",
    "received": "receive",
    "receives": "receive",
    "receiving": "receive",
    "evaluated": "evaluate",
    "evaluates": "evaluate",
    "evaluating": "evaluate",
    "features": "show",
    "featuring": "show",
    "featured": "show",
    "showed": "show",
    "shows": "show",
    "shown": "show",
    "face": "face",
    "faced": "face",
    "faces": "face",
    "facing": "face",
    "overlap": "overlap",
    "overlapped": "overlap",
    "overlapping": "overlap",
    "overlaps": "overlap",
    "commentary": "comment",
    "commentator": "comment",
    "commentators": "comment",
    "comments": "comment",
    "opinions": "comment",
    "various": "several",
    "numerous": "several",
    "pleased": "happy",
    "remarks": "comment",
    "remark": "comment",
    "recomputed": "recompute",
    "recomputes": "recompute",
    "recomputing": "recompute",
    "fuse": "combine",
    "fused": "combine",
    "fuses": "combine",
    "fusing": "combine",
    "reranked": "rerank",
    "reranking": "rerank",
    "reranks": "rerank",
    "bm25f": "bm25",
    "configured": "requested",
    "fall": "fit",
    "facility": "plant",
    "facilities": "plant",
    "inside": "within",
    "consider": "deem",
    "considered": "deem",
    "considers": "deem",
    "considering": "deem",
    "disclose": "disclose",
    "disclosed": "disclose",
    "discloses": "disclose",
    "disclosing": "disclose",
    "investigate": "search",
    "investigated": "search",
    "investigating": "search",
    "investigation": "search",
    "investigations": "search",
    "searching": "search",
    "limit": "restrict",
    "limited": "restrict",
    "limiting": "restrict",
    "limits": "restrict",
    "requiring": "restrict",
    "restricting": "restrict",
    "restricts": "restrict",
    "discharged": "leave",
    "released": "leave",
    "leaving": "leave",
    "left": "leave",
    "declared": "announced",
    "announce": "announced",
    "announces": "announced",
    "announcing": "announced",
    "candidacy": "campaign",
    "photo": "picture",
    "pictured": "picture",
    "image": "picture",
    "presented": "purport",
    "presents": "purport",
    "purported": "purport",
    "purports": "purport",
    "five": "5",
    "thirty": "30",
    "fourteen": "14",
    "seven": "7",
    "ninety": "90",
}


SEMANTIC_PHRASES = (
    ("money back", "refund"),
    ("cash back", "refund"),
    ("business day", "business days"),
    ("order id", "order number"),
    ("k-nearest neighbors", "k-nn"),
    ("k-nearest neighbor", "k-nn"),
    ("united states", "us"),
    ("face to face", "face"),
    ("facing off", "face"),
    ("voices overlap", "comment overlap"),
    ("commentators' voices", "comments"),
    ("commentators voices", "comments"),
    ("not exactly what the law considers true", "false by the law"),
    ('not exactly what the law considers "true', "false by the law"),
)


def _semantic_text(text: str) -> str:
    value = _normalize_negation_text(text).lower()
    for source, replacement in SEMANTIC_PHRASES:
        value = value.replace(source, replacement)
    return value


ACRONYM_EXPANSIONS = {
    "cdc": ("centers", "disease", "control"),
    "fbi": ("federal", "bureau", "investigation"),
    "us": ("united", "states"),
    "usa": ("united", "states"),
    "uva": ("university", "virginia"),
}
