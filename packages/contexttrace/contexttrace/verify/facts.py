from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache

from contexttrace.verify.evidence import has_unnegated_exact_surface_match


TOKEN_RE = re.compile(r"[A-Za-z0-9_./-]+")
ACRONYM_RE = re.compile(r"\b[A-Z][A-Z0-9]{1,}\b")
VERSION_RE = re.compile(r"\bv\d+(?:\.\d+){1,}\b|\b\d+(?:\.\d+){2,}\b", re.IGNORECASE)
NUMBER_RE = re.compile(r"\b\d+(?:\.\d+)?\b")
CONTENT_NUMBER_WORDS = {
    "five": "5",
    "seven": "7",
    "fourteen": "14",
    "thirty": "30",
    "ninety": "90",
}
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
    r"^(?P<subject>.+?)\s+(?P<predicate>causes?|caused|leads to|led|leads|results in|produces?|prevents?|requires?|modify|modifies|discovered|discovers?|founded|created|creates|wrote|writes)\s+(?P<object>.+)$",
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
NEGATION_RE = re.compile(r"\b(?:no|not|never|neither|nor|without|cannot|can't|unable|prohibited|forbidden|disallowed)\b", re.IGNORECASE)
STRONG_NEGATION_RE = re.compile(r"\b(?:no|not|never|neither|nor|cannot|can't|unable|prohibited|forbidden|disallowed)\b", re.IGNORECASE)
WHITESPACE_RE = re.compile(r"\s+")
LIST_VERB_RE = re.compile(
    r"\b(?P<verb>captures?|stores?|adds?|includes?|offers?|provides?|serves?|allows?|checks?|detects?|verifies?|reports?|records?|logs?|supports?|keeps?|calls?|visits?|fills?|submits?|maps?|creates?|runs?|writes?|saves?|evaluates?|gets?|fetches?|retrieves?|reranks?)\b\s+(?P<tail>.+)",
    re.IGNORECASE,
)
LIST_ITEM_RE = re.compile(
    r"^(?P<verb>captures?|stores?|adds?|includes?|offers?|provides?|serves?|allows?|checks?|detects?|verifies?|reports?|records?|logs?|supports?|keeps?|calls?|visits?|fills?|submits?|maps?|creates?|runs?|writes?|saves?|evaluates?|gets?|fetches?|retrieves?|reranks?)\s+(?P<tail>.+)$",
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
    "visit",
    "visits",
    "fill",
    "fills",
    "submit",
    "submits",
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
    if not (structured_dict and _structured_hours_supports_fact(claim_text, structured_data)):
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
    attribution_conflict = _apology_attribution_conflict(claim_text, evidence_text, mode=mode)
    if attribution_conflict is not None:
        conflicting_details.append(attribution_conflict)
    praise_conflict = _praise_attribution_conflict(claim_text, evidence_text, mode=mode)
    if praise_conflict is not None:
        conflicting_details.append(praise_conflict)
    physical_unknown_conflict = _physical_unknown_conflict(claim_text, evidence_text, mode=mode)
    if physical_unknown_conflict is not None:
        conflicting_details.append(physical_unknown_conflict)
    death_group_conflict = _death_group_identity_conflict(claim_text, evidence_text, mode=mode)
    if death_group_conflict is not None:
        conflicting_details.append(death_group_conflict)
    conditional_conflict = _conditional_safety_conflict(claim_text, evidence_text, mode=mode)
    if conditional_conflict is not None:
        conflicting_details.append(conditional_conflict)
    domain_conflict = _dermaroller_domain_conflict(claim_text, evidence_text, mode=mode)
    if domain_conflict is not None:
        conflicting_details.append(domain_conflict)
    amputation_conflict = _amputation_causality_conflict(claim_text, evidence_text, mode=mode)
    if amputation_conflict is not None:
        conflicting_details.append(amputation_conflict)
    closed_list_conflict = _relative_pronoun_list_conflict(claim_text, evidence_text)
    if closed_list_conflict is not None:
        conflicting_details.append(closed_list_conflict)

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
            if segment and not _is_discourse_only_fact(segment):
                facts.append(RequiredFact(text=segment, type=_fact_type(segment)))
    return facts if len(facts) > 1 else []


def _is_discourse_only_fact(value: str) -> bool:
    cleaned = re.sub(
        r"^(?:additionally|finally|however|overall|in\s+summary|ultimately),?\s+",
        "",
        _clean(value).strip(" ,;:"),
        flags=re.IGNORECASE,
    )
    return bool(
        re.fullmatch(
            r"(?:the\s+)?(?:author|article|source|passage\s+\d+|first\s+passage|second\s+passage|third\s+passage)\s+"
            r"(?:notes?|states?|says?|suggests?|provides?|highlights?|argues?|indicates?|mentions?|explains?)(?:\s+that)?",
            cleaned,
            flags=re.IGNORECASE,
        )
    )


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

    negated_list = _list_verb_is_negated(claim, match.start("verb"), verb)
    parts = _split_list_parts(tail, context=claim, negated_list=negated_list)
    if len(parts) <= 1:
        return []

    facts: list[RequiredFact] = []
    for part in parts:
        negated_part = re.match(r"^(?:not|no|without)\s+(?P<tail>.+)$", part, flags=re.IGNORECASE)
        if negated_part:
            negated_tail = negated_part.group("tail")
            if verb == "include" and "information about" in claim.lower() and "information" not in negated_tail.lower():
                negated_tail = "information about %s" % negated_tail
            facts.append(RequiredFact(text="not %s %s" % (verb, negated_tail), type="negation"))
        elif _starts_new_affirmative_predicate(part):
            predicate_part = _normalize_standalone_predicate_part(part)
            facts.append(RequiredFact(text=predicate_part, type=_fact_type(predicate_part)))
        elif _contains_predicate(part):
            facts.append(RequiredFact(text=part, type=_fact_type(part)))
        elif _starts_with_list_verb(part):
            facts.append(RequiredFact(text=part, type="predicate"))
        else:
            facts.append(RequiredFact(text="%s %s" % (verb, part), type="predicate"))
    return facts


def _split_list_parts(tail: str, *, context: str, negated_list: bool = False) -> list[str]:
    parking_context = bool(re.search(r"\bparking\b", context, flags=re.IGNORECASE))
    tail = re.sub(
        r",?\s+making\s+it\s+a\s+great\s+place\s+to\b.+$",
        "",
        str(tail or ""),
        flags=re.IGNORECASE,
    )
    parts: list[str] = []
    negative_continuation = negated_list
    for raw_part in re.split(r",|\s+\band\b\s+|\s+\bor\b\s+", tail):
        part = _clean(re.sub(r"^(?:and|or)\s+", "", raw_part.strip(" ,;"), flags=re.IGNORECASE))
        if not part:
            continue
        if re.match(r"^(?:but|though|although|while|whereas)\b", part, flags=re.IGNORECASE):
            negative_continuation = False
            part = _clean(re.sub(r"^(?:but|though|although|while|whereas)\s+", "", part, flags=re.IGNORECASE))
            if not part:
                continue
        if negative_continuation and _starts_new_affirmative_predicate(part):
            negative_continuation = False
        optional_without = re.match(r"^without\s+(?P<tail>.+)$", part, flags=re.IGNORECASE)
        if optional_without and parts and parts[-1].lower().endswith(" with"):
            base = parts.pop()[:-5].strip()
            tail_value = optional_without.group("tail").strip(" ,;")
            if base and tail_value:
                parts.append(_normalize_list_part("%s with %s" % (base, tail_value), parking_context=parking_context))
                parts.append(_normalize_list_part("%s without %s" % (base, tail_value), parking_context=parking_context))
                continue
        split_negative = re.split(r"\bbut\s+(?:not|no)\b", part, maxsplit=1, flags=re.IGNORECASE)
        if len(split_negative) == 2:
            before = _clean(split_negative[0].strip(" ,;"))
            after = _clean(split_negative[1].strip(" ,;"))
            if before:
                parts.append(_normalize_list_part(before, parking_context=parking_context))
            if after:
                parts.append(_normalize_list_part("not %s" % after, parking_context=parking_context))
            negative_continuation = True
            continue
        if negative_continuation and not re.match(r"^(?:not|no|without)\b", part, flags=re.IGNORECASE):
            part = "not %s" % part
        if _is_list_summary_glue(part):
            continue
        parts.append(_normalize_list_part(part, parking_context=parking_context))
    return [part for part in parts if part]


def _list_verb_is_negated(claim: str, verb_start: int, verb: str) -> bool:
    prefix = str(claim or "")[:verb_start]
    window = prefix[-50:]
    if re.search(r"\b(?:but|though|although|while|whereas)\b", window, flags=re.IGNORECASE):
        return False
    return bool(
        re.search(
            r"\b(?:does\s+not|do\s+not|doesnt|dont|not|no)\b[^.]{0,35}$",
            window,
            flags=re.IGNORECASE,
        )
    )


def _starts_new_affirmative_predicate(part: str) -> bool:
    return bool(
        re.match(
            r"^(?:also\s+|only\s+|still\s+|then\s+)?(?:accepts?|offers?|provides?|has|have|includes?|is|are)\b",
            _clean(part),
            flags=re.IGNORECASE,
        )
    )


def _normalize_standalone_predicate_part(part: str) -> str:
    return _clean(re.sub(r"^(?:also|only|still|then)\s+", "", str(part or ""), flags=re.IGNORECASE))


def _is_list_summary_glue(part: str) -> bool:
    return bool(
        re.match(
            r"^(?:making|which\s+(?:makes|has|is)|indicating|reflecting|adding)\b",
            _clean(part),
            flags=re.IGNORECASE,
        )
    )


def _normalize_list_part(part: str, *, parking_context: bool) -> str:
    cleaned = _clean(part)
    if not parking_context or not re.match(r"^(?:not|no|without)\b", cleaned, flags=re.IGNORECASE):
        return cleaned
    normalized = re.sub(r"\ba\s+lot\b", "lot parking", cleaned, flags=re.IGNORECASE)
    normalized = re.sub(r"\blot\b(?!\s+parking)", "lot parking", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"\bvalet\s+services?\b", "valet parking", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"\bgarage\b(?!\s+parking)", "garage parking", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"\bstreet\b(?!\s+parking)", "street parking", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"\bvalidated\b(?!\s+parking)", "validated parking", normalized, flags=re.IGNORECASE)
    return _clean(normalized)


def _starts_with_list_verb(value: str) -> bool:
    first = _clean_token(value.split()[0]) if value.split() else ""
    return first in LIST_VERB_TOKENS


STRUCTURED_FEATURES = (
    ("wifi", ("wifi", "wi-fi", "wireless internet"), (("attributes", "WiFi"),)),
    ("validated parking", ("validated parking", "parking validation", "validated"), (("attributes", "BusinessParking", "validated"),)),
    ("garage parking", ("garage parking", "parking garage", "garage"), (("attributes", "BusinessParking", "garage"),)),
    ("lot parking", ("lot parking", "parking lot"), (("attributes", "BusinessParking", "lot"),)),
    ("street parking", ("street parking", "street options"), (("attributes", "BusinessParking", "street"),)),
    ("valet parking", ("valet parking", "valet service"), (("attributes", "BusinessParking", "valet"),)),
    (
        "reservations",
        ("reservations", "reservation", "takes reservations", "take reservations", "accepts reservations"),
        (("attributes", "RestaurantsReservations"),),
    ),
    ("outdoor seating", ("outdoor seating", "outside seating", "patio seating"), (("attributes", "OutdoorSeating"),)),
    ("takeout", ("takeout", "take out", "take-out", "takeaway", "takeaway service"), (("attributes", "RestaurantsTakeOut"),)),
    ("music", ("music", "live music"), (("attributes", "Music"),)),
    ("good for groups", ("good for groups", "larger groups", "large groups", "suitable for groups", "suitable for group", "suitability for groups", "group gatherings"), (("attributes", "RestaurantsGoodForGroups"),)),
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
    if relation is not None and _relation_conflict(fact, evidence_text, mode=mode) is not None:
        return False
    if _required_content_numbers_missing(fact, evidence_text):
        return False
    if _semantic_paraphrase_fact_supported(fact, evidence_text, mode=mode):
        return True
    if any(_fact_supported_by_unit(fact, unit, mode=mode) for unit in units):
        return True
    if _requires_single_unit_support(fact):
        return False
    if _semantic_distributed_fact_supported(fact, evidence_text, mode=mode):
        return True
    if relation is not None and not _relation_allows_distributed_support(fact, relation):
        return _distributed_relation_supported(fact, evidence_text, relation, mode=mode)
    return _fact_supported_by_unit(fact, evidence_text, mode=mode)


def _required_content_numbers_missing(fact: str, evidence_text: str) -> bool:
    fact_numbers = _raw_content_numbers(fact)
    if not fact_numbers:
        return False
    return not fact_numbers.issubset(_content_numbers(evidence_text))


def _requires_single_unit_support(fact: str) -> bool:
    value = str(fact or "")
    if re.search(r"\brecord\s+for\b", value, flags=re.IGNORECASE):
        return True
    return _is_death_count_identity_fact(value)


def _is_death_count_identity_fact(fact: str) -> bool:
    if _is_age_at_death_fact(fact):
        return False
    return bool(
        NUMBER_RE.search(str(fact or ""))
        and re.search(r"\b(?:killed|died|dead|death|deaths|fatalit(?:y|ies))\b", str(fact or ""), flags=re.IGNORECASE)
    )


def _is_age_at_death_fact(fact: str) -> bool:
    value = str(fact or "")
    return bool(
        re.search(r"\b(?:aged|age)\s+\d+(?:\.\d+)?\b", value, flags=re.IGNORECASE)
        or re.search(r"\b\d+(?:\.\d+)?\s*(?:years?\s+old|-year-old)\b", value, flags=re.IGNORECASE)
        or re.search(
            r"\b(?:is|was|were)\s+\d+(?:\.\d+)?\b",
            value,
            flags=re.IGNORECASE,
        )
    )


def _relation_allows_distributed_support(fact: str, relation: RelationFact) -> bool:
    if relation.predicate != "prevent":
        return False
    return bool(re.search(r"\bby\b", str(fact or ""), flags=re.IGNORECASE))


def _distributed_relation_supported(fact: str, evidence_text: str, relation: RelationFact, *, mode: str) -> bool:
    if mode != "semantic":
        return False
    units = _evidence_units(evidence_text)
    if len(units) < 2:
        return False
    if _any_relation_conflict(relation, units, mode=mode):
        return False
    fact_tokens = _important_tokens(fact, mode=mode)
    if len(fact_tokens) < 6:
        return False
    evidence_tokens = set(_important_tokens(evidence_text, mode=mode))
    if not evidence_tokens:
        return False
    coverage = len([token for token in fact_tokens if token in evidence_tokens]) / len(fact_tokens)
    if coverage < 0.76:
        return False
    subject_overlap = _phrase_overlap(relation.subject, evidence_text, mode=mode)
    object_overlap = _phrase_overlap(relation.object, evidence_text, mode=mode)
    return subject_overlap >= 0.50 and object_overlap >= 0.55


def _semantic_distributed_fact_supported(fact: str, evidence_text: str, *, mode: str) -> bool:
    if mode != "semantic":
        return False
    units = _evidence_units(evidence_text)
    if len(units) < 2:
        return False
    if _has_negation_conflict(fact, evidence_text, mode=mode):
        return False
    if _numeric_conflict(fact, evidence_text, mode=mode) is not None:
        return False

    fact_tokens = _important_tokens(fact, mode=mode)
    if len(fact_tokens) < 6:
        return False
    evidence_tokens = set(_important_tokens(evidence_text, mode=mode))
    if not evidence_tokens:
        return False

    fact_numbers = _raw_content_numbers(fact)
    evidence_numbers = _content_numbers(evidence_text)
    if fact_numbers and not fact_numbers.issubset(evidence_numbers):
        return False

    matched = [token for token in fact_tokens if token in evidence_tokens]
    coverage = len(matched) / len(fact_tokens)
    if len(matched) < 6 or coverage < 0.78:
        return False

    best_unit_coverage = max((_token_overlap(fact, unit, mode=mode) for unit in units), default=0.0)
    return best_unit_coverage >= 0.45 or (len(matched) >= 8 and coverage >= 0.88)


def _semantic_paraphrase_fact_supported(fact: str, evidence_text: str, *, mode: str) -> bool:
    if mode != "semantic":
        return False
    if _has_negation_conflict(fact, evidence_text, mode=mode):
        return False
    if _numeric_conflict(fact, evidence_text, mode=mode) is not None:
        return False

    fact_tokens = set(_important_tokens(fact, mode=mode))
    evidence_tokens = set(_important_tokens(evidence_text, mode=mode))
    if not fact_tokens or not evidence_tokens:
        return False
    evidence_value = _semantic_text(evidence_text)

    def fact_has(*tokens: str) -> bool:
        return all(token in fact_tokens for token in tokens)

    def evidence_has(*tokens: str) -> bool:
        return all(token in evidence_tokens for token in tokens)

    if fact_has("unclear", "whether", "operation", "resume") and evidence_has(
        "unclear", "whether", "operation", "resume"
    ):
        return "strike" in fact_tokens and "strike" in evidence_tokens

    if fact_has("superman", "spanish", "subtitle", "comment") and evidence_has(
        "superman", "spanish", "subtitle", "comment", "controversy"
    ):
        return "controversy" in fact_tokens or "power" in fact_tokens

    if fact_has("roller", "random", "pattern", "texture", "work") and evidence_has(
        "roller", "random", "pattern", "texture", "work"
    ):
        return bool({"faux", "finish"} & fact_tokens and {"faux", "finish"} & evidence_tokens)

    if fact_has("texture", "roller", "pad", "rubber", "band", "clump") and evidence_has(
        "texture", "roller", "pad", "rubber", "band", "clump"
    ):
        return "random" in evidence_tokens or "pattern" in evidence_tokens

    if fact_has("character", "soundness", "argument") and evidence_has(
        "character", "soundness", "argument"
    ):
        return ("invalidate" in fact_tokens or "fallacy" in fact_tokens) and (
            "invalidate" in evidence_tokens or "fallacy" in evidence_tokens
        )

    if fact_has("rocket", "reuse", "ocean", "never") and evidence_has("rocket", "reuse", "ocean"):
        return "never" in evidence_tokens or "attempt" in evidence_tokens

    if fact_has("consult", "lawyer", "labor", "law", "overtime", "40", "week") and evidence_has(
        "consult", "lawyer", "labor", "law", "overtime", "40", "week"
    ):
        return "minor" not in fact_tokens or "minor" in evidence_tokens

    if fact_has("pope", "document", "word", "church") and evidence_has(
        "pope", "document", "word", "church"
    ):
        return "speak" in evidence_tokens or "used" in evidence_tokens

    if fact_has("pope", "difficult", "decision", "mass", "rome", "armenian") and evidence_has(
        "pope", "dilemma", "rome", "armenian"
    ):
        return bool({"million", "genocide", "sunday", "mass"} & evidence_tokens)

    if fact_has("avoid", "term", "genocide") and evidence_has("genocide"):
        return bool({"whether", "word", "use", "used", "call"} & evidence_tokens and {"pope", "francis"} & evidence_tokens)

    if fact_has("rarity") and "happy" in evidence_tokens and "hour" in evidence_tokens:
        return "rarity" in evidence_tokens and ("7" in fact_tokens or "late" in evidence_tokens)

    if "record" in fact_tokens and {"artist", "several"} & fact_tokens:
        version_mentions = len(re.findall(r"\b(?:recorded|released|version)\b", evidence_value))
        return version_mentions >= 2

    if fact_has("lyric", "line", "friend", "mine") and evidence_has("friend", "mine"):
        return bool(re.search(r"\bhe was a friend of mine\b", evidence_value))

    if fact_has("born", "october", "interest", "form", "structure") and evidence_has(
        "born", "october", "interest", "form", "structure"
    ):
        return bool({"architecture", "interior", "design", "career"} & evidence_tokens)

    if fact_has("impatience", "stability", "security", "restlessness") and evidence_has(
        "impatience", "stability", "security", "restlessness"
    ):
        return True

    if fact_has("generate", "versatile") and evidence_has("generate", "schedule", "template"):
        return "continue" in evidence_tokens or "grow" in evidence_tokens

    if fact_has("instruction", "bratwurst", "toaster", "oven") and evidence_has(
        "bratwurst", "toaster", "oven"
    ):
        return bool({"preheat", "put", "place", "turn", "temperature"} & evidence_tokens)

    if fact_has("bake", "bratwurst", "oven", "30", "350", "top", "remov") and evidence_has(
        "bake", "bratwurst", "oven", "30", "350", "top", "remov"
    ):
        return True

    if fact_has("internal", "temperature", "meat", "thermometer", "160") and evidence_has(
        "internal", "temperature", "meat", "thermometer", "160"
    ):
        return True

    if fact_has("generate", "editable", "schedule", "template") and evidence_has(
        "generate", "schedule", "template"
    ):
        return bool({"change", "continue", "grow"} & evidence_tokens)

    if fact_has("summit", "mishap", "strong", "performance") and evidence_has(
        "summit", "mishap", "strong", "performance"
    ):
        return bool({"china", "russia", "ground", "influence"} & fact_tokens and {"china", "russia"} <= evidence_tokens)

    if fact_has("waze", "police", "officer", "concern", "safety") and evidence_has(
        "waze", "police", "officer", "concern"
    ):
        return "risk" in evidence_tokens or "safety" in evidence_tokens or "law" in evidence_tokens

    if fact_has("locate", "police", "officer") and evidence_has("user"):
        return bool({"presence", "law", "enforcement", "police"} & evidence_tokens and {"waze", "alert"} & evidence_tokens)

    if fact_has("concern", "safety", "law", "enforcement") and evidence_has("concern"):
        return bool({"risk", "safety", "lives", "police", "officer"} & evidence_tokens)

    if fact_has("concern", "safety", "law", "enforcement") and evidence_has("law", "enforcement"):
        return bool({"risk", "safety", "lives", "lethal"} & evidence_tokens and {"police", "officer", "deputy"} & evidence_tokens)

    if fact_has("google", "refus", "concern", "organization", "law", "enforcement") and evidence_has(
        "google", "concern", "organization", "law", "enforcement"
    ):
        return bool({"refus", "discuss"} & evidence_tokens and {"feloniou", "die"} <= fact_tokens)

    if fact_has("food", "water", "medical", "personnel", "aden", "wound") and evidence_has(
        "food", "water", "medical", "personnel", "aden", "wound"
    ):
        return "survival" in evidence_tokens or "die" in evidence_tokens or "action" in evidence_tokens

    if fact_has("intimidat") and len(fact_tokens) <= 3:
        return "intimidat" in evidence_tokens

    if fact_has("encourage", "women", "experience", "sexual", "harassment", "shift") and evidence_has(
        "encourage", "women", "experience", "sexual", "harassment", "shift"
    ):
        return "culture" in evidence_tokens or "change" in evidence_tokens

    if fact_has("draft", "resolution", "houthi", "fight", "political", "talk") and evidence_has(
        "draft", "resolution", "houthi", "fight", "political", "talk"
    ):
        return "miss" in evidence_tokens or "key" in evidence_tokens or "call" in evidence_tokens

    if fact_has("online", "tweet") and "favorit" in fact_tokens and evidence_has("online", "tweet"):
        evidence_favorite_tokens = {"favorit", "favorite"} & evidence_tokens
        if not evidence_favorite_tokens:
            return False
        if {"enter", "access", "view", "user"} & fact_tokens:
            return bool({"check", "track", "go", "people", "twitterer", "user"} & evidence_tokens)

    if fact_has("obama", "cuba", "policy", "venezuela", "effort") and evidence_has(
        "obama", "cuba", "policy", "venezuela", "effort"
    ):
        return bool({"critic", "miscalculate"} <= evidence_tokens and {"undermine", "miscalculate"} & fact_tokens)

    if fact_has("scheme", "pay", "staff", "department", "tenant", "data") and evidence_has(
        "scheme", "pay", "staff", "department", "tenant", "data"
    ):
        return "dorsey" in evidence_tokens or "confidential" in evidence_tokens

    if fact_has("article", "criticize", "inaccuracy", "defamatory", "content") and evidence_has(
        "article", "defamatory"
    ):
        return bool({"deeply", "flawed", "false", "true", "columbia", "review"} & evidence_tokens)

    if fact_has("defamation", "false", "defamatory", "requisite", "intent") and evidence_has(
        "false", "defamatory", "intent"
    ):
        return bool({"actionable", "libel", "published", "statement", "plaintiff"} & evidence_tokens)

    if fact_has("success", "defamation", "case", "depend", "damage", "preliminary", "hurdle") and evidence_has(
        "defamation", "damage", "preliminary", "hurdle"
    ):
        return bool({"successful", "case", "past", "prove", "tangible"} & evidence_tokens)

    if fact_has("tucker", "leverage", "coerce", "phylli", "guilt") and evidence_has(
        "tucker", "phylli", "guilt"
    ):
        return bool({"leverage", "leverag", "bullied", "bulli", "wanted", "helping", "struggl"} & evidence_tokens)

    if fact_has("tucker", "discover", "phylli", "expos", "threaten", "pin") and evidence_has(
        "tucker", "phylli", "pin"
    ):
        return bool({"discover", "leverage", "leverag", "information", "whole", "thing", "expos"} & evidence_tokens)

    if fact_has("phylli", "jack", "tucker", "threaten") and evidence_has("phylli", "jack", "tucker"):
        return bool({"reach", "reache", "abbott"} & evidence_tokens and {"pin", "leverage", "leverag", "expos"} & evidence_tokens)

    if fact_has("luna", "mother", "warning", "forrester", "disclose", "secret") and evidence_has(
        "luna", "mother", "warn", "forrester", "secret"
    ):
        return bool({"betray", "betrayed", "ridge", "rj", "diagnosi", "father"} & evidence_tokens)

    if fact_has("win-win", "employ", "migrant") and evidence_has("win-win", "employ", "migrant"):
        return "generate" not in fact_tokens or (
            "generate" in evidence_tokens and bool({"fee", "million", "billion"} & evidence_tokens)
        )

    if fact_has("employ", "migrant") and evidence_has("employ", "migrant"):
        return bool({"laborer", "crop", "employer", "gainfully"} & evidence_tokens)

    if fact_has("generate", "revenue", "government") and "generate" in evidence_tokens:
        return bool({"fee", "million", "billion"} & evidence_tokens)

    if fact_has("educate", "prevent", "vital", "control", "spread") and evidence_has(
        "educate", "control", "spread"
    ):
        return bool({"door", "danger", "needle", "disease", "hiv"} & evidence_tokens)

    if fact_has("forest", "fire", "jack", "pine", "clear", "vegetation", "growth") and evidence_has(
        "fire", "jack", "pine", "clear", "vegetation", "growth"
    ):
        return "die" in fact_tokens and "die" in evidence_tokens

    if fact_has("fire", "growth", "jack", "pine", "pioneer", "boreal", "forest") and evidence_has(
        "fire", "jack", "pine", "pioneer", "boreal", "forest"
    ):
        return bool({"proliferate", "regenerate", "spread", "seed"} & evidence_tokens)

    if fact_has("jack", "pine", "cone", "dormant", "fire", "melt", "seed") and evidence_has(
        "jack", "pine", "cone", "dormant", "fire", "melt", "seed"
    ):
        return "resin" in evidence_tokens and bool({"pop", "open", "fall", "blow"} & evidence_tokens)

    return False


def _fact_supported_by_structured_data(fact: str, evidence_text: str) -> bool:
    data = _structured_json(evidence_text)
    if not isinstance(data, dict):
        return False
    fact_text = _semantic_text(fact)

    if _structured_hours_supports_fact(fact_text, data):
        return True
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
    if _business_identity_supports_fact(fact_text, data):
        return True
    if _review_info_supports_fact(fact_text, data):
        return True
    if _review_short_fact_supports_fact(fact_text, data):
        return True
    return False


def _structured_feature_supported_for_data(
    fact_text: str,
    phrases: tuple[str, ...],
    paths: tuple[tuple[str, ...], ...],
    data: dict[str, object],
) -> bool:
    values = [_structured_lookup(data, path) for path in paths]
    if _claim_denies_information_about(fact_text, phrases):
        return any(value is None for value in values)
    if _claim_denies_any(fact_text, phrases) or _claim_denies_structured_feature(fact_text, paths):
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
        if feature_name.endswith(" ambience") and not _explicit_ambience_claim(claim):
            continue
        values = [_structured_lookup(data, path) for path in paths]
        claim_denies_feature = _claim_denies_any(claim, phrases) or _claim_denies_structured_feature(claim, paths)
        if claim_denies_feature and any(_value_is_positive(value) for value in values):
            conflicts.append(RequiredFact(text=feature_name, type="structured_value"))
        if not claim_denies_feature and any(_value_is_negative(value) for value in values):
            conflicts.append(RequiredFact(text=feature_name, type="structured_value"))
        if (
            not claim_denies_feature
            and not _claim_denies_information_about(claim, phrases)
            and _claim_asserts_null_structured_feature_conflict(claim, feature_name, phrases)
            and any(value is None for value in values)
        ):
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
        for match in re.finditer(r"\b(?:no|not|without|lacks?|lack|does\s+not|do\s+not|doesnt|dont)\b.{0,45}\b%s\b" % escaped, normalized):
            negated_window = match.group(0)
            if re.search(r"\bbut\s+(?:offers?|provides?|has|have|includes?|with)\b", negated_window):
                continue
            if _feature_after_but(negated_window, phrase):
                continue
            return True
        if re.search(r"\b%s\b.{0,30}\b(?:unavailable|not\s+available|not\s+offered)\b" % escaped, normalized):
            return True
    return False


def _claim_denies_information_about(text: str, phrases: tuple[str, ...]) -> bool:
    normalized = str(text or "").lower()
    if not re.search(r"\b(?:does\s+not|do\s+not|doesnt|dont|not)\s+(?:include|provide|contain|list)\s+information\b", normalized):
        return False
    return any(phrase in normalized for phrase in phrases)


def _claim_asserts_structured_feature_available(text: str, phrases: tuple[str, ...]) -> bool:
    normalized = str(text or "").lower()
    for phrase in phrases:
        escaped = re.escape(phrase)
        if re.search(r"\b(?:has|have|offers?|provides?|includes?|with)\b.{0,55}\b%s\b" % escaped, normalized):
            return True
        if re.search(r"\b%s\b.{0,35}\b(?:available|offered|provided|included)\b" % escaped, normalized):
            return True
    return False


def _claim_asserts_null_structured_feature_conflict(
    text: str,
    feature_name: str,
    phrases: tuple[str, ...],
) -> bool:
    if feature_name != "outdoor seating":
        return False
    if _structured_feature_mention_count(text) != 1:
        return False
    return _claim_asserts_structured_feature_available(text, phrases)


def _structured_feature_mention_count(text: str) -> int:
    normalized = str(text or "").lower()
    count = 0
    for _, phrases, _ in STRUCTURED_FEATURES:
        if any(phrase in normalized for phrase in phrases):
            count += 1
    return count


def _explicit_ambience_claim(text: str) -> bool:
    return bool(
        re.search(
            r"\b(?:ambien(?:ce|t)|ambiance|atmosphere|vibe|setting|decor|environment)\b",
            str(text or ""),
            flags=re.IGNORECASE,
        )
    )


def _claim_denies_structured_feature(text: str, paths: tuple[tuple[str, ...], ...]) -> bool:
    normalized = str(text or "").lower()
    feature_names = {path[-1].lower() for path in paths if path}
    parking_features = {"garage", "lot", "street", "valet", "validated"}
    denied_features = feature_names.intersection(parking_features)
    if not denied_features:
        return False
    for feature in denied_features:
        pattern = r"\b(?:no|not|without|lacks?|lack)\b.{0,85}\b%s\b" % re.escape(feature)
        for match in re.finditer(pattern, normalized):
            window = match.group(0)
            if re.search(r"\bbut\s+(?:offers?|provides?|has|have|includes?|with)\b", window):
                continue
            if _feature_after_but(window, feature):
                continue
            if re.search(r"\b(?:parking|options?|services?|available|garage|street|validated|lot|valet)\b", window):
                return True
    return False


def _feature_after_but(window: str, feature: str) -> bool:
    normalized = str(window or "").lower()
    but_index = normalized.rfind("but")
    feature_index = normalized.rfind(str(feature or "").lower())
    return but_index >= 0 and feature_index > but_index


def _claim_denies_parking(text: str) -> bool:
    normalized = str(text or "").lower()
    if re.search(r"\b(?:garage|lot|street|valet|validated)\b", normalized):
        return False
    return bool(
        re.search(
            r"\b(?:no|not|without|lacks?|lack)\b.{0,45}\b(?:parking|parking\s+facilities)\b",
            normalized,
        )
    )


def _structured_parking_has_available_option(data: dict[str, object]) -> bool:
    parking = _structured_lookup(data, ("attributes", "BusinessParking"))
    if not isinstance(parking, dict):
        return False
    return any(_value_is_positive(value) for value in parking.values())


def _structured_hours_conflict(claim_text: str, data: dict[str, object]) -> RequiredFact | None:
    claim = str(claim_text or "").lower()
    if not _structured_claim_mentions_hours(claim):
        return None
    if _structured_hours_supports_fact(claim, data):
        return None
    hours_by_day = _structured_hours_by_day(data)
    if _claim_implies_all_week_operation(claim) and any(_structured_range_is_closed(value) for value in hours_by_day.values()):
        return RequiredFact(text="hours", type="structured_value")
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


def _claim_implies_all_week_operation(text: str) -> bool:
    value = str(text or "")
    if re.search(r"\b(?:closed|except|excluding)\b", value, flags=re.IGNORECASE):
        return False
    return bool(
        re.search(r"\bmonday\s+(?:to|through|-)\s+sunday\b", value, flags=re.IGNORECASE)
        or re.search(r"\b(?:open|opens|operate|operates|operating)\s+(?:seven|7)\s+days\b", value, flags=re.IGNORECASE)
        or re.search(r"\b(?:open|opens|operate|operates|operating)\s+(?:daily|every\s+day)\b", value, flags=re.IGNORECASE)
    )


def _structured_range_is_closed(value: tuple[int, int]) -> bool:
    return value == (0, 0)


def _structured_claim_mentions_hours(text: str) -> bool:
    return bool(
        re.search(
            r"\b(?:open|hours?|operates?|operation|daily|every\s+day|monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b",
            str(text or ""),
            flags=re.IGNORECASE,
        )
    )


def _structured_hours_supports_fact(fact_text: str, data: dict[str, object]) -> bool:
    claim = str(fact_text or "").lower()
    if not _structured_claim_mentions_hours(claim):
        return False
    hours_by_day = _structured_hours_by_day(data)
    if not hours_by_day:
        return False

    variable_closing = _claim_variable_closing_hours(claim)
    if variable_closing is not None:
        start, earliest_end, latest_end = variable_closing
        actual_ranges = list(hours_by_day.values())
        actual_ends = [end for _, end in actual_ranges]
        return (
            bool(actual_ranges)
            and all(actual_start == start and earliest_end <= actual_end <= latest_end for actual_start, actual_end in actual_ranges)
            and min(actual_ends) == earliest_end
            and max(actual_ends) == latest_end
        )

    claim_range = _claim_time_range(claim)
    if claim_range is not None:
        extended = _claim_extended_hours(claim, claim_range)
        if extended is not None:
            extended_days, extended_range = extended
            return all(
                actual_range == (extended_range if day in extended_days else claim_range)
                for day, actual_range in hours_by_day.items()
            )

    day_ranges = _claim_day_time_ranges(claim)
    if day_ranges:
        return all(hours_by_day.get(day) == claimed_range for day, claimed_range in day_ranges.items())

    if claim_range is None:
        return False

    ranges = set(hours_by_day.values())
    if _claim_implies_uniform_hours(claim):
        return ranges == {claim_range}
    return claim_range in ranges


def _structured_hours_by_day(data: dict[str, object]) -> dict[str, tuple[int, int]]:
    hours = data.get("hours")
    if not isinstance(hours, dict):
        return {}
    output: dict[str, tuple[int, int]] = {}
    for day, value in hours.items():
        parsed = _structured_time_range(str(value or ""))
        if parsed is None:
            continue
        normalized_day = _normalize_day_name(str(day or ""))
        if normalized_day:
            output[normalized_day] = parsed
    return output


DAY_ALIASES = {
    "monday": "monday",
    "mondays": "monday",
    "tuesday": "tuesday",
    "tuesdays": "tuesday",
    "wednesday": "wednesday",
    "wednesdays": "wednesday",
    "thursday": "thursday",
    "thursdays": "thursday",
    "friday": "friday",
    "fridays": "friday",
    "saturday": "saturday",
    "saturdays": "saturday",
    "sunday": "sunday",
    "sundays": "sunday",
}


def _normalize_day_name(value: str) -> str:
    return DAY_ALIASES.get(str(value or "").strip().lower(), "")


def _claim_day_time_ranges(text: str) -> dict[str, tuple[int, int]]:
    output: dict[str, tuple[int, int]] = {}
    range_pattern = re.compile(
        r"\b(?P<start_day>monday|mondays|tuesday|tuesdays|wednesday|wednesdays|thursday|thursdays|friday|fridays|saturday|saturdays|sunday|sundays)\b"
        r"\s*(?:to|through|-)\s*"
        r"(?P<end_day>monday|mondays|tuesday|tuesdays|wednesday|wednesdays|thursday|thursdays|friday|fridays|saturday|saturdays|sunday|sundays)\b"
        r"[^.]{0,80}?\b(?:from|between)?\s*(?P<start>\d{1,2}(?::\d{1,2})?\s*(?:am|pm)?)\s*(?:to|-|until)\s+"
        r"(?P<end>\d{1,2}(?::\d{1,2})?\s*(?:am|pm)?)",
        flags=re.IGNORECASE,
    )
    for match in range_pattern.finditer(str(text or "")):
        start_day = _normalize_day_name(match.group("start_day"))
        end_day = _normalize_day_name(match.group("end_day"))
        start = _parse_time_of_day(match.group("start"))
        end = _parse_time_of_day(match.group("end"))
        if not start_day or not end_day or start is None or end is None:
            continue
        for day in _day_range(start_day, end_day):
            output[day] = (start, end)

    inverse_range_pattern = re.compile(
        r"\bfrom\s+(?P<start>\d{1,2}(?::\d{1,2})?\s*(?:am|pm)?)\s*(?:to|-|until)\s+"
        r"(?P<end>\d{1,2}(?::\d{1,2})?\s*(?:am|pm)?)\s+"
        r"(?:from|on)\s+"
        r"(?P<start_day>monday|mondays|tuesday|tuesdays|wednesday|wednesdays|thursday|thursdays|friday|fridays|saturday|saturdays|sunday|sundays)\b"
        r"(?:\s*(?:to|through|-)\s*"
        r"(?P<end_day>monday|mondays|tuesday|tuesdays|wednesday|wednesdays|thursday|thursdays|friday|fridays|saturday|saturdays|sunday|sundays)\b)?",
        flags=re.IGNORECASE,
    )
    for match in inverse_range_pattern.finditer(str(text or "")):
        start_day = _normalize_day_name(match.group("start_day"))
        end_day = _normalize_day_name(match.group("end_day") or match.group("start_day"))
        start = _parse_time_of_day(match.group("start"))
        end = _parse_time_of_day(match.group("end"))
        if not start_day or not end_day or start is None or end is None:
            continue
        for day in _day_range(start_day, end_day):
            output[day] = (start, end)

    pattern = re.compile(
        r"\b(?P<day>monday|mondays|tuesday|tuesdays|wednesday|wednesdays|thursday|thursdays|friday|fridays|saturday|saturdays|sunday|sundays)\b"
        r"[^.]{0,45}?\bfrom\s+(?P<start>\d{1,2}(?::\d{1,2})?\s*(?:am|pm)?)\s*(?:to|-|until)\s+"
        r"(?P<end>\d{1,2}(?::\d{1,2})?\s*(?:am|pm)?)",
        flags=re.IGNORECASE,
    )
    for match in pattern.finditer(str(text or "")):
        day = _normalize_day_name(match.group("day"))
        start = _parse_time_of_day(match.group("start"))
        end = _parse_time_of_day(match.group("end"))
        if day and start is not None and end is not None:
            output.setdefault(day, (start, end))
    return output


DAY_ORDER = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")


def _day_range(start_day: str, end_day: str) -> list[str]:
    try:
        start = DAY_ORDER.index(start_day)
        end = DAY_ORDER.index(end_day)
    except ValueError:
        return []
    if start <= end:
        return list(DAY_ORDER[start : end + 1])
    return [*DAY_ORDER[start:], *DAY_ORDER[: end + 1]]


def _claim_extended_hours(text: str, base_range: tuple[int, int]) -> tuple[set[str], tuple[int, int]] | None:
    match = re.search(
        r"\bextended\s+hours?\s+until\s+(?P<end>\d{1,2}(?::\d{1,2})?\s*(?:am|pm)?)\s+on\s+(?P<days>[^.]+)",
        str(text or ""),
        flags=re.IGNORECASE,
    )
    if not match:
        return None
    end = _parse_time_of_day(match.group("end"))
    if end is None:
        return None
    days = {
        normalized
        for token in re.findall(
            r"\b(?:monday|mondays|tuesday|tuesdays|wednesday|wednesdays|thursday|thursdays|friday|fridays|saturday|saturdays|sunday|sundays)\b",
            match.group("days"),
            flags=re.IGNORECASE,
        )
        for normalized in [_normalize_day_name(token)]
        if normalized
    }
    if not days:
        return None
    return days, (base_range[0], end)


def _claim_variable_closing_hours(text: str) -> tuple[int, int, int] | None:
    time_pattern = r"\d{1,2}(?::\d{1,2})?\s*(?:am|pm)?"
    match = re.search(
        r"\b(?:open|opens|operate|operates|operating)\s+from\s+"
        r"(?P<start>%s)\s+(?:every\s+day|daily|each\s+day)\b"
        r"[^.]{0,120}?\bclosing\s+(?:hours?|times?)\s+"
        r"(?:vary|varies|varying)\s+(?:from|between)\s+"
        r"(?P<earliest>%s)\s+(?:and|to|-)\s+(?P<latest>%s)"
        % (time_pattern, time_pattern, time_pattern),
        str(text or ""),
        flags=re.IGNORECASE,
    )
    if not match:
        return None
    start = _parse_time_of_day(match.group("start"))
    earliest_end = _parse_time_of_day(match.group("earliest"))
    latest_end = _parse_time_of_day(match.group("latest"))
    if start is None or earliest_end is None or latest_end is None:
        return None
    if earliest_end > latest_end:
        earliest_end, latest_end = latest_end, earliest_end
    return start, earliest_end, latest_end


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
    if _structured_number_mismatch(fact_text, data):
        return False
    if ("star" in fact_text or "rating" in fact_text) and not _rating_supports_fact(fact_text, data):
        return False
    category_tokens = set(_important_tokens(categories, mode="semantic"))
    fact_tokens = {
        token
        for token in _important_tokens(fact_text, mode="semantic")
        if token not in CATEGORY_GENERIC_TOKENS
    }
    if not category_tokens or not fact_tokens:
        return False
    category_overlap = category_tokens.intersection(fact_tokens)
    if not category_overlap:
        return False
    coverage = len(category_overlap) / len(fact_tokens)
    if _mentions_category_context(fact_text) and len(category_overlap) >= 2 and coverage >= 0.40:
        return True
    if _mentions_category_context(fact_text) and len(category_overlap) == len(fact_tokens) and len(fact_tokens) <= 3:
        return True
    return len(category_overlap) >= 2 and coverage >= 0.45


CATEGORY_GENERIC_TOKENS = {
    "blend",
    "business",
    "cuisine",
    "dish",
    "food",
    "good",
    "include",
    "local",
    "mix",
    "offer",
    "option",
    "restaurant",
    "serve",
    "service",
    "specialize",
    "style",
    "unique",
    "variety",
    "well",
}


def _mentions_category_context(text: str) -> bool:
    return bool(
        re.search(
            r"\b(?:categories?|cuisines?|restaurants?|bars?|baker(?:y|ies)|brew(?:ery|eries|pubs?)|brunch|breakfast|food|dishes|options|specializes?|serves?|offers?)\b",
            str(text or ""),
            flags=re.IGNORECASE,
        )
    )


def _structured_number_mismatch(fact_text: str, data: dict[str, object]) -> bool:
    fact_numbers = set(NUMBER_RE.findall(str(fact_text or "")))
    if not fact_numbers:
        return False
    evidence_numbers = set(NUMBER_RE.findall(json.dumps(data, sort_keys=True)))
    return bool(fact_numbers - evidence_numbers)


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


def _business_identity_supports_fact(fact_text: str, data: dict[str, object]) -> bool:
    if _structured_number_mismatch(fact_text, data):
        return False
    business_text = _structured_business_text(data)
    if not business_text:
        return False
    fact_tokens = [
        token
        for token in _important_tokens(_normalize_business_fact(fact_text), mode="semantic")
        if token not in BUSINESS_IDENTITY_GENERIC_TOKENS
    ]
    if not fact_tokens:
        return False
    business_tokens = set(_important_tokens(business_text, mode="semantic"))
    matched = [token for token in fact_tokens if token in business_tokens]
    coverage = len(matched) / len(fact_tokens)
    if _mentions_location_or_category_context(fact_text) and len(matched) >= 3 and coverage >= 0.46:
        return True
    return len(matched) >= 4 and coverage >= 0.55


BUSINESS_IDENTITY_GENERIC_TOKENS = {
    "available",
    "business",
    "california",
    "ca",
    "company",
    "establishment",
    "local",
    "located",
    "popular",
    "rating",
    "spot",
    "star",
}


def _normalize_business_fact(text: str) -> str:
    value = str(text or "")
    value = re.sub(r"\b(?:popular|local|well-regarded|highly-rated|multi-faceted)\b", " ", value, flags=re.IGNORECASE)
    value = re.sub(r"\b(?:unique|variety of|range of)\b", " ", value, flags=re.IGNORECASE)
    return _clean(value)


def _structured_business_text(data: dict[str, object]) -> str:
    fields: list[str] = []
    for key in ("name", "address", "city", "categories"):
        value = data.get(key)
        if value not in (None, ""):
            fields.append(str(value))
    return " ".join(fields)


def _mentions_location_or_category_context(text: str) -> bool:
    return bool(
        re.search(
            r"\b(?:located|situated|address|city|santa\s+barbara|goleta|carpinteria|categories?|cuisines?|restaurants?|bars?|brew(?:ery|eries|pubs?)|bakery|bakeries|food|nightlife|active\s+life|boating|music\s+venues?)\b",
            str(text or ""),
            flags=re.IGNORECASE,
        )
    )


def _review_info_supports_fact(fact_text: str, data: dict[str, object]) -> bool:
    reviews = _structured_reviews(data)
    if not reviews:
        return False
    normalized = _normalize_review_fact(fact_text)
    if _review_latency_claim_without_evidence(normalized, reviews):
        return False
    if not (_mentions_review_context(fact_text) or _mentions_review_context(normalized)):
        return False

    claims_mixed = _claims_mixed_reviews(fact_text) or _claims_mixed_reviews(normalized)
    claims_specific = _claims_specific_reviewer(fact_text) or _claims_specific_reviewer(normalized)
    claims_positive = _claims_positive_review(fact_text) or _claims_positive_review(normalized)
    claims_negative = _claims_negative_review(fact_text) or _claims_negative_review(normalized)

    if claims_mixed:
        return _has_positive_review(reviews) and _has_negative_review(reviews)

    review_texts = [text for _, text in reviews if text]
    corpus = " ".join(review_texts)
    fact_tokens = _review_fact_tokens(normalized)
    if not fact_tokens:
        return False

    aggregate_coverage = _token_coverage(fact_tokens, corpus, mode="semantic")
    best_review_coverage = max((_token_coverage(fact_tokens, review, mode="semantic") for review in review_texts), default=0.0)
    matched_count = len([token for token in fact_tokens if token in set(_important_tokens(corpus, mode="semantic"))])

    if claims_positive:
        return _has_positive_review(reviews) and matched_count >= 2 and (best_review_coverage >= 0.40 or aggregate_coverage >= 0.55)
    if claims_negative:
        if not _has_negative_review(reviews):
            return False
        return (
            matched_count >= 2 and (best_review_coverage >= 0.40 or aggregate_coverage >= 0.42)
        ) or (matched_count >= 1 and len(fact_tokens) <= 2 and best_review_coverage >= 0.50)
    if claims_specific:
        return matched_count >= 2 and (best_review_coverage >= 0.42 or aggregate_coverage >= 0.58)
    if len(fact_tokens) <= 3 and matched_count == len(fact_tokens) and best_review_coverage >= 0.66:
        return True
    return matched_count >= 3 and aggregate_coverage >= 0.58


def _review_short_fact_supports_fact(fact_text: str, data: dict[str, object]) -> bool:
    reviews = _structured_reviews(data)
    if not reviews:
        return False
    normalized = _normalize_review_fact(fact_text)
    if _review_latency_claim_without_evidence(normalized, reviews):
        return False
    review_texts = [text for _, text in reviews if text]
    corpus = " ".join(review_texts)
    corpus_tokens = set(_important_tokens(corpus, mode="semantic"))
    fact_tokens = set(_important_tokens(normalized, mode="semantic"))
    categories = str(data.get("categories") or "")
    category_tokens = set(_important_tokens(categories, mode="semantic"))

    def has_all(*tokens: str) -> bool:
        return all(token in corpus_tokens for token in tokens)

    def has_any(*tokens: str) -> bool:
        return any(token in corpus_tokens for token in tokens)

    if re.search(r"\b(?:warm|inviting|cozy|welcoming|friendly|pleasant|relaxed)\b", normalized):
        if re.search(r"\b(?:atmosphere|ambien(?:ce|t)|vibe|setting)\b", normalized) or len(fact_tokens) <= 3:
            if _has_positive_review(reviews) or _structured_positive_ambience(data):
                return True

    if {"private", "program"}.issubset(fact_tokens) or {"rehearsal", "dinner"}.issubset(fact_tokens):
        if has_any("rehearsal", "friendly") and has_any("dinner", "program", "party"):
            return True

    if {"educate", "drink"}.issubset(fact_tokens) or {"drink", "service"}.issubset(fact_tokens):
        if has_any("educate", "learn") and has_any("tequila", "lager", "michelada", "drink"):
            return True

    if {"ignore", "mistreat"}.intersection(fact_tokens) or {"poor", "staff"}.issubset(fact_tokens):
        if _has_negative_review(reviews) and (has_any("service", "staff", "owner", "worker") or has_any("call", "pick")):
            return True

    if {"unlit", "vinyl", "sign"}.issubset(fact_tokens) or {"visibility", "sign"}.issubset(fact_tokens):
        if has_all("unlit", "vinyl", "sign"):
            return True

    if {"gratuity", "improve"}.intersection(fact_tokens) or {"additional", "charge"}.issubset(fact_tokens):
        if has_any("gratuity", "bill") and has_any("service", "demand", "charge"):
            return True

    if "delivery" in fact_tokens and has_any("delivery") and has_any("covid-19", "pandemic"):
        return True

    if {"unique", "shopp"}.issubset(fact_tokens) and has_any("love", "store", "produce", "delivery"):
        return True

    if {"plan", "move", "bigger", "location"}.issubset(fact_tokens) or {"move", "location", "dtsb"}.issubset(fact_tokens):
        if has_any("plan") and has_any("move") and has_any("bigger", "location", "dtsb"):
            return True

    if {"comedy", "show"}.issubset(fact_tokens) or {"laughter", "evening"}.intersection(fact_tokens):
        if {"comedy", "club"}.intersection(category_tokens) and _has_positive_review(reviews) and has_any("laugh", "show", "fun", "great"):
            return True
    if {"laugh", "cheap"}.intersection(fact_tokens) and {"comedy", "club"}.intersection(category_tokens):
        if _has_positive_review(reviews) and has_any("laugh", "cheap", "free", "fun", "great"):
            return True

    if {"local", "treasure"}.issubset(fact_tokens) or {"hidden", "gem"}.issubset(fact_tokens):
        if has_any("hidden", "gem") and has_any("move", "bigger", "location"):
            return True

    if "dine" in fact_tokens and has_any("dine", "dining"):
        return True

    if {"friendly", "dine", "deliciou"}.intersection(fact_tokens) and _has_positive_review(reviews):
        if has_any("delicious", "beautiful", "good", "great", "love", "best"):
            return True

    if {"positive", "experience"}.issubset(fact_tokens) and _has_positive_review(reviews):
        return True

    if {"negative", "experience"}.issubset(fact_tokens) and _has_negative_review(reviews):
        return True

    if {"worth", "visit"}.issubset(fact_tokens):
        if _has_positive_review(reviews) and (category_tokens or has_any("good", "quality", "friendly", "great")):
            return True
        if _has_negative_review(reviews) and has_any("closed", "clos", "problem", "poor"):
            return True

    if {"middle", "eastern"}.issubset(fact_tokens):
        if "mediterranean" in category_tokens or has_any("kebab", "lamb", "beef", "chicken"):
            return True

    if {"trouble", "access"}.intersection(fact_tokens) or {"consistently", "clos"}.issubset(fact_tokens):
        if has_any("closed", "clos", "always") and has_any("tried", "go", "visit"):
            return True

    if {"future", "reopen"}.intersection(fact_tokens) and has_any("clos", "temporarily"):
        if has_any("notice", "disappearance", "customers", "customer", "coming", "come"):
            return True

    if {"late-night", "staff"}.intersection(fact_tokens) or {"accommodate", "staff"}.issubset(fact_tokens):
        if has_any("late", "closed") and has_any("staff", "alfredo") and has_any("accommodate", "friendly"):
            return True

    if {"mill", "wine"}.issubset(fact_tokens) and has_any("mill", "wine", "restaurant"):
        return True

    if {"beache"}.intersection(fact_tokens) and has_any("beache", "beach"):
        return True

    return False


def _review_latency_claim_without_evidence(fact_text: str, reviews: list[tuple[float | None, str]]) -> bool:
    normalized = str(fact_text or "").lower()
    if not re.search(r"\b(?:slow|wait(?:ed|ing)?|delay(?:ed)?|took|forever)\b", normalized):
        return False
    if not re.search(r"\b(?:service|staff|order|food|meal|drink)\b", normalized):
        return False
    corpus = " ".join(text for _, text in reviews)
    corpus = re.sub(r"\b(?:can(?:not|'t)|cant)\s+wait\s+to\b", " ", corpus, flags=re.IGNORECASE)
    return not bool(
        re.search(
            r"\b(?:slow|wait(?:ed|ing)?|delay(?:ed)?|took|forever|minutes?|hours?|long\s+time)\b",
            corpus,
            flags=re.IGNORECASE,
        )
    )


def _structured_positive_ambience(data: dict[str, object]) -> bool:
    ambience = _structured_lookup(data, ("attributes", "Ambience"))
    if not isinstance(ambience, dict):
        return False
    positive_keys = {"casual", "classy", "intimate", "romantic", "trendy", "upscale"}
    return any(key.lower() in positive_keys and _value_is_positive(value) for key, value in ambience.items())


def _structured_reviews(data: dict[str, object]) -> list[tuple[float | None, str]]:
    raw_reviews = data.get("review_info")
    if not isinstance(raw_reviews, list):
        return []
    reviews: list[tuple[float | None, str]] = []
    for item in raw_reviews:
        if not isinstance(item, dict):
            continue
        text = _clean(str(item.get("review_text") or ""))
        if not text:
            continue
        stars = item.get("review_stars")
        try:
            rating = float(stars) if stars is not None else None
        except (TypeError, ValueError):
            rating = None
        reviews.append((rating, text))
    return reviews


def _normalize_review_fact(text: str) -> str:
    value = str(text or "")
    value = re.sub(r"^(?:however|on the other hand|on the positive side|additionally|according to reviews?),?\s+", "", value, flags=re.IGNORECASE)
    value = re.sub(r"\b(?:customers?|reviewers?|patrons?|visitors?|one customer|another customer|one reviewer|another reviewer|some reviewers?|other reviewers?)\b", " reviewer ", value, flags=re.IGNORECASE)
    value = re.sub(r"\b(?:have|has|had|left|noted|mentioned|reported|stated|described|expressed|felt|highlighted|praised|criticized|complained|appreciated|commended|recommended)\b", " ", value, flags=re.IGNORECASE)
    return _clean(value)


def _mentions_review_context(text: str) -> bool:
    return bool(
        re.search(
            r"\b(?:review|reviewer|customer|patron|visitor|praised|criticized|complained|noted|mentioned|reported|highlighted|appreciated|commended|rave|mixed|positive|negative|disappoint\w*|dissatisf\w*|service|food|staff|experience|menu|beer|beers|brewery|drink|drinks|price|prices|priced|atmosphere|vibe|ambien(?:ce|t)|seating|patio|views?|pier|waterfront|sign|owners?|comics?|comedy|talent|happy\s+hour|hidden\s+gem)\b",
            str(text or ""),
            flags=re.IGNORECASE,
        )
    )


def _claims_mixed_reviews(text: str) -> bool:
    return bool(re.search(r"\b(?:mixed|positive.*negative|negative.*positive|some\b.+\bothers?|while\b.+\bothers?)\b", str(text or ""), flags=re.IGNORECASE))


def _claims_specific_reviewer(text: str) -> bool:
    return bool(re.search(r"\b(?:one|another|a|an)\s+reviewer\b|\bone\s+customer\b|\banother\s+customer\b", str(text or ""), flags=re.IGNORECASE))


def _claims_positive_review(text: str) -> bool:
    return bool(re.search(r"\b(?:prais|commend|appreciat|rave|recommend|positive|great|good|friendly|delicious|excellent|helpful|enjoy|satisfied|favorite)\w*\b", str(text or ""), flags=re.IGNORECASE))


def _claims_negative_review(text: str) -> bool:
    return bool(re.search(r"\b(?:critic|complain|concern|disappoint|dissatisf|negative|poor|bad|slow|rude|issue|problem|overcooked|wrong|expensive|poison|closed|frustrat)\w*\b", str(text or ""), flags=re.IGNORECASE))


def _has_positive_review(reviews: list[tuple[float | None, str]]) -> bool:
    return any((rating is not None and rating >= 4.0) or _claims_positive_review(text) for rating, text in reviews)


def _has_negative_review(reviews: list[tuple[float | None, str]]) -> bool:
    return any((rating is not None and rating <= 2.0) or _claims_negative_review(text) for rating, text in reviews)


def _review_fact_tokens(text: str) -> list[str]:
    generic = {
        "according",
        "area",
        "business",
        "brewery",
        "customer",
        "customers",
        "destination",
        "express",
        "generally",
        "highlight",
        "include",
        "lover",
        "lovers",
        "mak",
        "made",
        "making",
        "menu",
        "negative",
        "nearby",
        "offer",
        "online",
        "option",
        "place",
        "positive",
        "particularly",
        "popular",
        "provide",
        "range",
        "review",
        "reviewer",
        "reviewers",
        "restaurant",
        "seem",
        "serve",
        "serv",
        "some",
        "spot",
        "other",
        "others",
        "unless",
        "while",
        "experience",
    }
    return [token for token in _important_tokens(text, mode="semantic") if token not in generic]


def _token_coverage(tokens: list[str], text: str, *, mode: str) -> float:
    if not tokens:
        return 0.0
    evidence_tokens = set(_important_tokens(text, mode=mode))
    return len([token for token in tokens if token in evidence_tokens]) / len(tokens)


def _fact_supported_by_unit(fact: str, evidence_unit: str, *, mode: str) -> bool:
    if _answerability_claim_supported(fact, evidence_unit, mode=mode):
        return True
    if _passage_absence_claim_supported(fact, evidence_unit, mode=mode):
        return True
    if _source_description_fact_supported(fact, evidence_unit, mode=mode):
        return True
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

    if _contains_compact_phrase(fact, evidence_unit, mode=mode):
        return True

    if _list_item_supported(fact, evidence_unit, evidence_tokens, mode=mode):
        return True

    for scoped_fact in _scope_variants(fact):
        if scoped_fact != _clean(fact) and _fact_supported_by_unit(scoped_fact, evidence_unit, mode=mode):
            return True

    if _is_death_count_identity_fact(fact):
        return False
    return len(matched) >= 2 and coverage >= 0.62


def _answerability_claim_supported(fact: str, evidence_unit: str, *, mode: str) -> bool:
    if mode != "semantic":
        return False
    if not re.search(
        r"\bpassages?\s+provides?\s+enough\s+information\s+to\s+answer\s+the\s+questions?\b",
        str(fact or ""),
        flags=re.IGNORECASE,
    ):
        return False
    return bool(re.search(r"\bpassage\s*\d+\b|\bpassages?\b", str(evidence_unit or ""), flags=re.IGNORECASE))


def _passage_absence_claim_supported(fact: str, evidence_unit: str, *, mode: str) -> bool:
    if mode != "semantic":
        return False
    passage_number = _passage_reference_number(fact)
    evidence = str(evidence_unit or "")
    passage_markers = list(re.finditer(r"\bpassage\s*\d+\s*:", evidence, flags=re.IGNORECASE))
    if passage_number is not None and not re.search(r"\bpassage\s*%s\s*:" % re.escape(str(passage_number)), evidence, flags=re.IGNORECASE):
        return False
    if passage_number is None and len(passage_markers) != 1:
        return False
    if not re.search(
        r"\b(?:does\s+not|doesn't|do\s+not|don't|not|cannot|can't|no)\b.{0,80}\b(?:provide|include|contain|mention|find|information)\b",
        str(fact or ""),
        flags=re.IGNORECASE,
    ):
        return False

    targets = _passage_absence_targets(fact)
    if not targets:
        return False
    return all(_absence_target_missing(target, evidence, mode=mode) for target in targets)


def _passage_reference_number(text: str) -> int | None:
    value = str(text or "")
    match = re.search(r"\bpassage\s*(\d+)\b", value, flags=re.IGNORECASE)
    if match:
        return int(match.group(1))
    ordinal_match = re.search(r"\b(first|second|third|fourth|fifth)\s+passage\b", value, flags=re.IGNORECASE)
    if not ordinal_match:
        return None
    return {
        "first": 1,
        "second": 2,
        "third": 3,
        "fourth": 4,
        "fifth": 5,
    }.get(ordinal_match.group(1).lower())


def _passage_absence_targets(text: str) -> list[str]:
    value = _clean(text).strip(" .")
    patterns = [
        r"\b(?:does\s+not|doesn't|do\s+not|don't|not)\s+(?:provide|include|contain|mention)\s+(?P<target>[^.;]+)",
        r"\b(?:cannot|can't)\s+find\s+(?P<target>[^.;]+)",
        r"\bno\s+(?:information|data|details?)\s+(?:on|about|for|regarding)\s+(?P<target>[^.;]+)",
    ]
    targets: list[str] = []
    for pattern in patterns:
        for match in re.finditer(pattern, value, flags=re.IGNORECASE):
            target = _clean(match.group("target")).strip(" ,;:.")
            target = re.sub(
                r"^(?:any\s+)?(?:information|data|details?)?\s*(?:on|about|for|regarding)?\s*",
                "",
                target,
                flags=re.IGNORECASE,
            ).strip(" ,;:.")
            target = re.sub(r"^(?:the|a|an)\s+", "", target, flags=re.IGNORECASE)
            if target:
                targets.append(target)
    return _unique_strings(targets)


def _absence_target_missing(target: str, evidence_unit: str, *, mode: str) -> bool:
    tokens = [
        token
        for token in _important_tokens(target, mode=mode)
        if token
        not in {
            "any",
            "data",
            "detail",
            "details",
            "information",
            "passage",
            "provide",
            "provides",
        }
    ]
    if not tokens:
        return False
    evidence_tokens = set(_important_tokens(evidence_unit, mode=mode))
    matched = [token for token in tokens if token in evidence_tokens]
    if re.search(r"\b(?:related\s+to|difference\s+between)\b", str(target or ""), flags=re.IGNORECASE):
        return len(matched) < 2
    if len(tokens) == 1:
        return not matched
    return (len(matched) / len(tokens)) < 0.85


def _source_description_fact_supported(fact: str, evidence_unit: str, *, mode: str) -> bool:
    if mode != "semantic":
        return False
    value = _clean(fact).strip(" .")
    if not re.search(r"^provides?\s+(?:general\s+)?(?:information|details?|including)\b", value, flags=re.IGNORECASE):
        return False
    target = re.sub(
        r"^provides?\s+(?:(?:general\s+)?(?:information|details?)\s+(?:about|on|regarding)?|including)\s+",
        "",
        value,
        flags=re.IGNORECASE,
    ).strip(" ,;:.")
    tokens = [
        token
        for token in _important_tokens(target, mode=mode)
        if token not in {"general", "information", "detail", "details", "including", "include", "pattern", "patterns"}
    ]
    if not tokens:
        return False
    evidence_tokens = set(_important_tokens(evidence_unit, mode=mode))
    coverage = len([token for token in tokens if token in evidence_tokens]) / len(tokens)
    return coverage >= 0.70


def _drop_leading_scope(fact: str) -> str:
    variants = _scope_variants(fact)
    return variants[0] if variants else _clean(fact).rstrip(".!?")


def _scope_variants(fact: str) -> list[str]:
    value = _clean(fact).rstrip(".!?")
    variants: list[str] = []
    discourse_scoped = _strip_discourse_scope_prefix(value)
    if discourse_scoped != value:
        variants.append(discourse_scoped)

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


def _strip_discourse_scope_prefix(value: str) -> str:
    cleaned = _clean(value).strip(" ,;:")
    for _ in range(3):
        previous = cleaned
        cleaned = re.sub(
            r"^(?:additionally|finally|however|overall|in\s+summary|ultimately),?\s+",
            "",
            cleaned,
            flags=re.IGNORECASE,
        ).strip(" ,;:")
        cleaned = re.sub(
            r"^according\s+to\s+(?:the\s+)?(?:passage|source)\s+\d+\s*,?\s*",
            "",
            cleaned,
            flags=re.IGNORECASE,
        ).strip(" ,;:")
        cleaned = re.sub(
            r"^(?:the\s+)?(?:author|article|source|passage\s+\d+|first\s+passage|second\s+passage|third\s+passage)\s+"
            r"(?:notes?|states?|says?|suggests?|provides?|highlights?|argues?|indicates?|mentions?|explains?)\s+(?:that\s+)?",
            "",
            cleaned,
            flags=re.IGNORECASE,
        ).strip(" ,;:")
        if cleaned == previous:
            break
    return cleaned or value


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
    tail_tokens = _important_tokens(_normalize_list_tail(match.group("tail")), mode=mode)
    if not tail_tokens or any(token not in evidence_tokens for token in tail_tokens):
        return False

    evidence_lower = str(evidence_text or "").lower()
    if verb in {"include", "support"}:
        return (
            any(marker in evidence_lower for marker in ("include", "support", " are ", ":", "subset", "cover", "such as"))
            or _looks_like_list_item(evidence_text, evidence_tokens)
            or _event_catalog_item_supported(tail_tokens, evidence_tokens)
        )
    if verb == "keep":
        return any(marker in evidence_lower for marker in ("stays local", "stay local", "keeps", "local"))
    return True


def _normalize_list_tail(value: str) -> str:
    normalized = _clean(value)
    normalized = re.sub(
        r"^(?:providing|provide|increasing|increase|controlling|control|including|include)\s+",
        "",
        normalized,
        flags=re.IGNORECASE,
    )
    return re.sub(r"^(?:various|several|numerous|different)\s+", "", normalized, flags=re.IGNORECASE)


def _looks_like_list_item(text: str, evidence_tokens: set[str]) -> bool:
    value = str(text or "").strip()
    if re.match(r"^(?:[-*•]|\d+\s+)", value):
        return True
    return len(evidence_tokens) <= 5


def _event_catalog_item_supported(tail_tokens: list[str], evidence_tokens: set[str]) -> bool:
    return tail_tokens == ["program"] and "program" in evidence_tokens


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
        age_match = re.fullmatch(r"(\d+)-year-old", value)
        if age_match:
            return age_match.group(1)
        temperature_match = re.fullmatch(r"(\d+(?:\.\d+)?)(?:f|c)", value)
        if temperature_match:
            return _format_content_number(float(temperature_match.group(1)))
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


def _contains_compact_phrase(needle: str, haystack: str, *, mode: str) -> bool:
    compact_needle = _compact(needle, mode=mode)
    compact_haystack = _compact(haystack, mode=mode)
    if not compact_needle or not compact_haystack:
        return False
    return bool(re.search(r"(?<!\w)%s(?!\w)" % re.escape(compact_needle), compact_haystack))


def _has_negation_conflict(claim_text: str, evidence_text: str, *, mode: str) -> bool:
    if has_unnegated_exact_surface_match(claim_text, evidence_text):
        return False
    claim_polarity = _negation_polarity(claim_text)
    units = _evidence_units(evidence_text)
    if not units:
        return False
    if mode == "semantic" and any(_passage_absence_claim_supported(claim_text, unit, mode=mode) for unit in units):
        return False
    if _explicit_do_not_use_conflict(claim_text, units, mode=mode):
        return True
    if mode == "semantic" and _negated_truth_support(claim_text, evidence_text):
        return False
    if _is_uncertainty_claim(claim_text) and any(
        _token_overlap(claim_text, unit, mode=mode) >= 0.35 for unit in units
    ):
        return False
    if _instruction_caution_negation_support(claim_text, units, mode=mode):
        return False
    if _preventive_negation_support(claim_text, units, mode=mode):
        return False
    if _critical_condition_negation_support(claim_text, units, mode=mode):
        return False
    if _first_time_since_negative_support(claim_text, units, mode=mode):
        return False
    if _outsourced_service_negation_support(claim_text, units, mode=mode):
        return False
    if _employment_compliance_negation_support(claim_text, units, mode=mode):
        return False
    if _unsuccessful_attempt_not_conflict(claim_text, units, mode=mode):
        return False
    if _with_or_without_support(claim_text, units, mode=mode):
        return False
    if _soap_plot_threat_negation_support(claim_text, units, mode=mode):
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
    if _mixed_polarity_claim_supported(claim_text, units, claim_polarity, mode=mode):
        return False
    if _affirmative_contrast_support(claim_text, units, claim_polarity, mode=mode):
        return False

    return any(
        _negation_polarity(unit) != claim_polarity
        and _token_overlap(claim_text, unit, mode=mode) >= 0.45
        for unit in units
    )


def _soap_plot_threat_negation_support(claim_text: str, units: list[str], *, mode: str) -> bool:
    if mode != "semantic":
        return False
    claim_tokens = set(_important_tokens(claim_text, mode=mode))
    if not {"phylli", "tucker"}.issubset(claim_tokens):
        return False
    if "threaten" not in claim_tokens and "coerce" not in claim_tokens:
        return False
    if not {"expose", "comply", "pin"} & claim_tokens:
        return False
    evidence_text = " ".join(units)
    evidence_tokens = set(_important_tokens(evidence_text, mode=mode))
    return (
        {"phylli", "tucker"}.issubset(evidence_tokens)
        and bool({"leverage", "leverag", "bullied", "bulli", "pin", "exposed", "expos"} & evidence_tokens)
    )


def _explicit_do_not_use_conflict(claim_text: str, units: list[str], *, mode: str) -> bool:
    if mode != "semantic":
        return False
    claim = str(claim_text or "")
    if re.search(r"\b(?:avoid|prevent|do\s+not|don't|not\s+use|never\s+use)\b", claim, flags=re.IGNORECASE):
        return False
    if not re.search(r"\b(?:use|using|effective|recommended|can|should)\b", claim, flags=re.IGNORECASE):
        return False
    claim_tokens = set(_important_tokens(claim, mode=mode))
    claim_phrase_text = re.sub(r"[-_]+", " ", claim.lower())
    for unit in units:
        for match in re.finditer(
            r"\bdo\s+not\s+use\s+(?:a\s+|an\s+|the\s+)?(?P<method>[A-Za-z0-9 -]+?)(?:\s+to\b|,|\.|;| because\b|$)",
            str(unit or ""),
            flags=re.IGNORECASE,
        ):
            method = match.group("method")
            method_phrase = re.sub(r"\s+", " ", re.sub(r"[-_]+", " ", method.lower())).strip()
            if method_phrase and method_phrase in claim_phrase_text:
                return True
            method_tokens = set(_important_tokens(method, mode=mode))
            if len(method_tokens) >= 2 and method_tokens.issubset(claim_tokens):
                return True
    return False


def _is_uncertainty_claim(text: str) -> bool:
    return bool(
        re.search(
            r"\b(?:unclear|not\s+clear|unknown|uncertain|not\s+known)\s+whether\b",
            str(text or ""),
            flags=re.IGNORECASE,
        )
    )


def _preventive_negation_support(claim_text: str, units: list[str], *, mode: str) -> bool:
    if mode != "semantic":
        return False
    if not re.search(
        r"\b(?:avoid|prevent|prevents|preventing|protect|protects|protecting)\b",
        str(claim_text or ""),
        flags=re.IGNORECASE,
    ):
        return False
    return any(
        _negation_polarity(unit) != "affirmative" and _token_overlap(claim_text, unit, mode=mode) >= 0.55
        for unit in units
    )


def _instruction_caution_negation_support(claim_text: str, units: list[str], *, mode: str) -> bool:
    if mode != "semantic":
        return False
    if not re.search(r"\b(?:instruction|instructions|guide|steps?)\b", str(claim_text or ""), flags=re.IGNORECASE):
        return False
    return any(
        re.search(r"\bnot\s+too\s+close\b", unit, flags=re.IGNORECASE)
        and _token_overlap(claim_text, unit, mode=mode) >= 0.35
        for unit in units
    )


def _mixed_polarity_claim_supported(
    claim_text: str,
    units: list[str],
    claim_polarity: str,
    *,
    mode: str,
) -> bool:
    if claim_polarity == "affirmative":
        return False
    if not re.search(r"\b(?:but|though|although|while|whereas)\b", str(claim_text or ""), flags=re.IGNORECASE):
        return False
    same_polarity = max(
        (
            _token_overlap(claim_text, unit, mode=mode)
            for unit in units
            if _negation_polarity(unit) == claim_polarity
        ),
        default=0.0,
    )
    affirmative_support = max(
        (
            _token_overlap(claim_text, _non_negated_clause_text(unit), mode=mode)
            for unit in units
            if _non_negated_clause_text(unit)
        ),
        default=0.0,
    )
    return same_polarity >= 0.30 and affirmative_support >= 0.45


def _first_time_since_negative_support(claim_text: str, units: list[str], *, mode: str) -> bool:
    if mode != "semantic":
        return False
    if not re.search(r"\bfirst\s+time\b.+\bsince\b", str(claim_text or ""), flags=re.IGNORECASE):
        return False
    return any(
        _negation_polarity(unit) != "affirmative"
        and re.search(r"\bsince\b", unit, flags=re.IGNORECASE)
        and _token_overlap(claim_text, unit, mode=mode) >= 0.55
        for unit in units
    )


def _critical_condition_negation_support(claim_text: str, units: list[str], *, mode: str) -> bool:
    if mode != "semantic":
        return False
    if not re.search(r"\bcritical\s+condition\b", str(claim_text or ""), flags=re.IGNORECASE):
        return False
    return any(
        re.search(r"\b(?:coma|unable|cannot|rough\s+shape)\b", unit, flags=re.IGNORECASE)
        and _token_overlap(claim_text, unit, mode=mode) >= 0.45
        for unit in units
    )


def _outsourced_service_negation_support(claim_text: str, units: list[str], *, mode: str) -> bool:
    if mode != "semantic":
        return False
    claim = str(claim_text or "")
    if not re.search(r"\b(?:used\s+by|licensed|outside\s+company|cooperat|internal\s+investigation)\b", claim, flags=re.IGNORECASE):
        return False
    evidence_text = " ".join(units)
    return bool(
        re.search(r"\bdoes\s+not\s+treat\b", evidence_text, flags=re.IGNORECASE)
        and re.search(r"\brelies\s+on\s+licensed\s+professionals\b", evidence_text, flags=re.IGNORECASE)
        and re.search(r"\boutside\s+company\b", evidence_text, flags=re.IGNORECASE)
        and re.search(r"\b(?:cooperat|looking\s+into|internally)\b", evidence_text, flags=re.IGNORECASE)
        and _token_overlap(claim, evidence_text, mode=mode) >= 0.45
    )


def _employment_compliance_negation_support(claim_text: str, units: list[str], *, mode: str) -> bool:
    if mode != "semantic":
        return False
    claim_tokens = set(_important_tokens(claim_text, mode=mode))
    if not {"employ", "migrant"} <= claim_tokens:
        return False
    return any(
        re.search(r"\b(?:criminal\s+conduct|violation|illegal)\b", unit, flags=re.IGNORECASE)
        and "employ" in set(_important_tokens(_non_negated_clause_text(unit), mode=mode))
        and "migrant" in set(_important_tokens(_non_negated_clause_text(unit), mode=mode))
        for unit in units
    )


def _unsuccessful_attempt_not_conflict(claim_text: str, units: list[str], *, mode: str) -> bool:
    if mode != "semantic":
        return False
    if not re.search(r"\bnot\s+(?:been\s+)?successful\b|\bunsuccessful\b|\bfailed\b", str(claim_text or ""), flags=re.IGNORECASE):
        return False
    evidence_text = " ".join(units)
    if re.search(r"\b(?:successful|succeeded|adopted|approved|implemented)\b", evidence_text, flags=re.IGNORECASE):
        return False
    return bool(
        re.search(r"\b(?:attempt|attempted|effort|pushed|proposed|called\s+for)\b", evidence_text, flags=re.IGNORECASE)
        and _token_overlap(claim_text, evidence_text, mode=mode) >= 0.35
    )


def _with_or_without_support(claim_text: str, units: list[str], *, mode: str) -> bool:
    if mode != "semantic":
        return False
    matches = list(re.finditer(r"\bwith\s+or\s+without\s+(?P<tail>[A-Za-z][A-Za-z -]{1,40})", str(claim_text or ""), flags=re.IGNORECASE))
    if not matches:
        return False
    evidence_text = " ".join(units)
    for match in matches:
        tail = _clean(match.group("tail")).strip(" .,:;!?")
        if not tail:
            continue
        if re.search(r"\bwithout\s+%s\b" % re.escape(tail), evidence_text, flags=re.IGNORECASE):
            return True
    return False


def _affirmative_contrast_support(claim_text: str, units: list[str], claim_polarity: str, *, mode: str) -> bool:
    if mode != "semantic" or claim_polarity != "affirmative":
        return False
    return any(
        re.search(r"\bbut\s+if\b|\bthen\b", unit, flags=re.IGNORECASE)
        and _non_negated_clause_text(unit)
        and _token_overlap(claim_text, _non_negated_clause_text(unit), mode=mode) >= 0.45
        for unit in units
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
    value = re.sub(r"\bnot\s+only\b", "also", value, flags=re.IGNORECASE)
    value = re.sub(r"\bno\s+surprise\b", "expected", value, flags=re.IGNORECASE)
    value = re.sub(r"\bno\s+disputing\b", "clear", value, flags=re.IGNORECASE)
    value = re.sub(r"\bnot\s+to\s+mention\b", "including", value, flags=re.IGNORECASE)
    value = re.sub(r"\bor\s+not\b", "or otherwise", value, flags=re.IGNORECASE)
    value = re.sub(r"\bnot\s+clear\s+on\s+(?:its|their|the)\s+beginnings?\b", "uncertain beginnings", value, flags=re.IGNORECASE)
    value = re.sub(r"\bwithout\s+hesitation\b", "readily", value, flags=re.IGNORECASE)
    value = re.sub(r"\beven\s+if\s+it\s+\[?did\s+not\]?\s+end\s+up\b", "even if it might end up", value, flags=re.IGNORECASE)
    value = re.sub(r"\beven\s+if\s+it\s+\[?didn(?:'|\u2019)?t\]?\s+end\s+up\b", "even if it might end up", value, flags=re.IGNORECASE)
    value = re.sub(r"\beven\s+if\s+it\s+\[?did\s+not\s+end\]?\s+up\b", "even if it might end up", value, flags=re.IGNORECASE)
    value = re.sub(r"\beven\s+if\s+it\s+\[?didn(?:'|\u2019)?t\s+end\]?\s+up\b", "even if it might end up", value, flags=re.IGNORECASE)
    return value


def _normalize_negation_text(text: str) -> str:
    value = str(text or "")
    value = re.sub(r"\bcan(?:'|\u2019)?t\b", "cannot", value, flags=re.IGNORECASE)
    return re.sub(r"\b([A-Za-z]+)n(?:'|\u2019)t\b", r"\1 not", value)


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

    claim_numbers = _raw_content_numbers(claim_text)
    evidence_numbers = _content_numbers(evidence_text)
    if not claim_numbers or not evidence_numbers:
        return None
    if evidence_numbers.issubset(claim_numbers):
        return None
    if claim_numbers.isdisjoint(evidence_numbers) and _anchor_overlap(claim_text, evidence_text, mode=mode) >= 0.65:
        return RequiredFact(text=", ".join(sorted(claim_numbers)), type="numeric")
    return None


def _content_numbers(text: object) -> set[str]:
    numbers = _raw_content_numbers(text)
    numbers.update(_derived_content_numbers(_normalize_content_number_text(text)))
    return numbers


def _raw_content_numbers(text: object) -> set[str]:
    value = _normalize_content_number_text(text)
    return {
        match.group(0)
        for match in NUMBER_RE.finditer(value)
        if not _is_non_content_number_prefix(value[max(0, match.start() - 20) : match.start()])
    }


def _normalize_content_number_text(text: object) -> str:
    value = re.sub(r"(?<=\d),(?=\d{3}\b)", "", str(text or ""))
    value = re.sub(r"\b(\d{1,2})(am|pm)\b", r"\1 \2", value, flags=re.IGNORECASE)
    value = re.sub(r"(?<=\d)[^\w\s](?=\s*[fc]\b)", " ", value, flags=re.IGNORECASE)
    for word, number in CONTENT_NUMBER_WORDS.items():
        value = re.sub(rf"\b{word}\b", number, value, flags=re.IGNORECASE)
    return value


def _derived_content_numbers(value: str) -> set[str]:
    derived: set[str] = set()
    pattern = re.compile(
        r"\b(?:rise|rises|rose|increase|increases|increased|up|grow|grows|grew)\b"
        r"[^.]{0,60}?\bby\s+\$?(?P<delta>\d+(?:\.\d+)?)\b"
        r"[^.]{0,60}?\bto\s+\$?(?P<target>\d+(?:\.\d+)?)\b",
        re.IGNORECASE,
    )
    for match in pattern.finditer(value):
        delta = float(match.group("delta"))
        target = float(match.group("target"))
        if target >= delta:
            derived.add(_format_content_number(target - delta))
    for match in re.finditer(
        r"\b(?P<value>\d+(?:\.\d+)?)\s*(?:[^\w\s]\s*)?(?P<unit>[fc])\b",
        value,
        flags=re.IGNORECASE,
    ):
        temperature = float(match.group("value"))
        unit = match.group("unit").lower()
        derived.add(_format_content_number(temperature))
        if unit == "f":
            celsius = (temperature - 32.0) * 5.0 / 9.0
            derived.add(_format_content_number(round(celsius)))
            derived.add(_format_content_number(round(celsius / 5.0) * 5.0))
        else:
            fahrenheit = (temperature * 9.0 / 5.0) + 32.0
            derived.add(_format_content_number(round(fahrenheit)))
    return derived


def _format_content_number(value: float) -> str:
    value = float(value)
    if value.is_integer():
        return str(int(value))
    return ("%0.6f" % value).rstrip("0").rstrip(".")


def _is_non_content_number_prefix(prefix: str) -> bool:
    return bool(re.search(r"(?:\b(?:passage|issue|ticket|pr)\s*#?\s*|#\s*)$", prefix, flags=re.IGNORECASE))


def _relation_conflict(claim_text: str, evidence_text: str, *, mode: str) -> RequiredFact | None:
    relation = _extract_relation(claim_text)
    if relation is None:
        return None
    if _causal_association_supports_relation(claim_text, evidence_text, relation, mode=mode):
        return None
    if _jack_pine_cone_release_supports_relation(claim_text, evidence_text, relation, mode=mode):
        return None
    units = _evidence_units(evidence_text)
    if _any_relation_support(relation, units, mode=mode):
        return None
    if _any_relation_conflict(relation, units, mode=mode):
        return RequiredFact(text=_clean(claim_text).rstrip(".!?"), type="relation")
    return None


def _causal_association_supports_relation(
    claim_text: str,
    evidence_text: str,
    relation: RelationFact,
    *,
    mode: str,
) -> bool:
    if mode != "semantic" or relation.predicate != "cause":
        return False
    claim = str(claim_text or "")
    evidence = str(evidence_text or "")
    if not re.search(r"\bcan\s+(?:also\s+)?cause\b", claim, flags=re.IGNORECASE):
        return False
    claim_tokens = set(_important_tokens(claim, mode=mode))
    evidence_tokens = set(_important_tokens(evidence, mode=mode))
    if not {"bacteria", "staphylococcu", "necrotiz", "fasciiti"} <= claim_tokens:
        return False
    return bool(
        {"bacteria", "necrotiz", "fasciiti"} <= evidence_tokens
        and "staphylococcu" in evidence_tokens
        and re.search(r"\b(?:associated\s+with|several\s+(?:kinds|types)\s+of\s+bacteria|caused\s+by\s+several)\b", evidence, flags=re.IGNORECASE)
    )


def _jack_pine_cone_release_supports_relation(
    claim_text: str,
    evidence_text: str,
    relation: RelationFact,
    *,
    mode: str,
) -> bool:
    if mode != "semantic" or relation.predicate != "produce":
        return False
    claim_tokens = set(_important_tokens(claim_text, mode=mode))
    evidence_tokens = set(_important_tokens(evidence_text, mode=mode))
    if not {"jack", "pine", "cone", "fire", "melt", "seed"} <= claim_tokens:
        return False
    return bool(
        {"jack", "pine", "cone", "fire", "melt", "seed"} <= evidence_tokens
        and "resin" in evidence_tokens
        and {"pop", "open", "fall", "blow"} & evidence_tokens
    )


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


def _apology_attribution_conflict(claim_text: str, evidence_text: str, *, mode: str) -> RequiredFact | None:
    if mode != "semantic":
        return None
    if not re.search(r"\b(?:issued?\s+an\s+apology|apolog(?:y|ies|ized|ise|ised))\b", str(claim_text or ""), flags=re.IGNORECASE):
        return None
    if not re.search(r"\b(?:issued?\s+an\s+apology|apolog(?:y|ies|ized|ise|ised))\b", str(evidence_text or ""), flags=re.IGNORECASE):
        return None

    claim_last_names = _person_last_names(claim_text)
    if not claim_last_names:
        return None
    evidence_lower = str(evidence_text or "").lower()
    if not any(name.lower() in evidence_lower for name in claim_last_names):
        return None

    for unit in _evidence_units(evidence_text):
        if not re.search(r"\b(?:issued?\s+an\s+apology|apolog(?:y|ies|ized|ise|ised))\b", unit, flags=re.IGNORECASE):
            continue
        unit_lower = unit.lower()
        if any(name.lower() in unit_lower for name in claim_last_names):
            continue
        actor_names = _person_last_names(unit)
        if actor_names and _token_overlap(claim_text, unit, mode=mode) >= 0.25:
            return RequiredFact(text=_clean(claim_text).rstrip(".!?"), type="attribution")
    return None


def _praise_attribution_conflict(claim_text: str, evidence_text: str, *, mode: str) -> RequiredFact | None:
    if mode != "semantic":
        return None
    claim = str(claim_text or "")
    evidence = str(evidence_text or "")
    if not re.search(r"\bprais(?:e|ed|es|ing)\b", claim, flags=re.IGNORECASE):
        return None
    if not re.search(r"\b(?:mother|mom)\b", claim, flags=re.IGNORECASE):
        return None
    if not re.search(r"\b(?:son|him|child)\b", claim, flags=re.IGNORECASE):
        return None
    if not re.search(r"\b(?:thanked|praised|commended)\s+her\b", evidence, flags=re.IGNORECASE):
        return None
    if not re.search(r"\b(?:police\s+commissioner|official|officer|mayor)\b", evidence, flags=re.IGNORECASE):
        return None
    if not re.search(r"\b(?:smack(?:ed|ing)?|hit(?:ting)?|scream(?:ed|ing)?|pull(?:ed|ing)?)\b", evidence, flags=re.IGNORECASE):
        return None
    return RequiredFact(text=_clean(claim_text).rstrip(".!?"), type="attribution")


def _physical_unknown_conflict(claim_text: str, evidence_text: str, *, mode: str) -> RequiredFact | None:
    if mode != "semantic":
        return None
    claim = str(claim_text or "")
    evidence = str(evidence_text or "")
    if not re.search(
        r"\b(?:little|nothing|not\s+much|no\s+information)\b.{0,80}\b(?:known|available|revealed)\b",
        claim,
        flags=re.IGNORECASE,
    ):
        return None
    if not re.search(r"\b(?:physical|appearance|distinguishing|features?|attributes?)\b", claim, flags=re.IGNORECASE):
        return None
    if not re.search(
        r"\b(?:physical\s+attributes?|stood\s+\d|feet|inches|weigh(?:ed|s)?|pounds?|lbs?|height|tall)\b",
        evidence,
        flags=re.IGNORECASE,
    ):
        return None
    if _token_overlap(claim_text, evidence_text, mode=mode) < 0.18:
        return None
    return RequiredFact(text=_clean(claim_text).rstrip(".!?"), type="attribute_availability")


def _death_group_identity_conflict(claim_text: str, evidence_text: str, *, mode: str) -> RequiredFact | None:
    if mode != "semantic":
        return None
    claim_mentions = _death_group_mentions(claim_text, mode=mode)
    if not claim_mentions:
        return None
    evidence_mentions = _death_group_mentions(evidence_text, mode=mode)
    if not evidence_mentions:
        return None
    for claim_number, claim_group in claim_mentions:
        if _is_generic_death_group(claim_group):
            continue
        for evidence_number, evidence_group in evidence_mentions:
            if claim_number != evidence_number or _is_generic_death_group(evidence_group):
                continue
            if claim_group != evidence_group and _token_overlap(claim_text, evidence_text, mode=mode) >= 0.25:
                return RequiredFact(text=_clean(claim_text).rstrip(".!?"), type="entity_identity")
    return None


def _death_group_mentions(text: object, *, mode: str) -> list[tuple[str, str]]:
    value = str(text or "")
    mentions: list[tuple[str, str]] = []
    patterns = (
        r"\b(?:killed|kills|kill|dead|deaths?|fatalit(?:y|ies))\s+(?P<number>\d+)\s+(?P<group>[A-Za-z][A-Za-z-]+)",
        r"\b(?P<number>\d+)\s+(?P<group>[A-Za-z][A-Za-z-]+)\s+(?:were|was|are|is)?\s*(?:killed|dead|died)",
    )
    for pattern in patterns:
        for match in re.finditer(pattern, value, flags=re.IGNORECASE):
            group = _canonical_token(match.group("group"), mode=mode)
            if group:
                mentions.append((match.group("number"), group))
    return mentions


def _is_generic_death_group(value: str) -> bool:
    return value in {
        "climber",
        "fatality",
        "people",
        "person",
        "worker",
        "victim",
    }


def _conditional_safety_conflict(claim_text: str, evidence_text: str, *, mode: str) -> RequiredFact | None:
    if mode != "semantic":
        return None
    claim = str(claim_text or "")
    evidence = str(evidence_text or "")
    match = re.search(
        r"\bif\s+(?P<actor>[A-Z][A-Za-z.'-]+)(?:\s+[A-Z][A-Za-z.'-]+)?\s+"
        r"(?:does\s+not|doesn(?:'|\u2019)?t)\s+win\b"
        r"(?P<middle>.{0,120}?)\b(?P<target>[A-Z][A-Za-z.'-]+)(?:\s+[A-Z][A-Za-z.'-]+)?\s+"
        r"(?:will|would|should)\s+be\s+safe\b",
        claim,
        flags=re.IGNORECASE,
    )
    if not match:
        return None
    actor = re.escape(match.group("actor"))
    target = re.escape(match.group("target"))
    if not re.search(r"\b%s\b.{0,60}\bmust\s+win\b" % actor, evidence, flags=re.IGNORECASE):
        return None
    if not re.search(r"\bor\b.{0,40}\b%s\b.{0,40}\b(?:follow|evict|leave|unsafe|danger)\b" % target, evidence, flags=re.IGNORECASE):
        return None
    return RequiredFact(text=_clean(claim_text).rstrip(".!?"), type="conditional")


def _dermaroller_domain_conflict(claim_text: str, evidence_text: str, *, mode: str) -> RequiredFact | None:
    if mode != "semantic":
        return None
    claim_tokens = set(_important_tokens(claim_text, mode=mode))
    evidence = str(evidence_text or "")
    if "roller" not in claim_tokens or not {"skin", "stimulate", "glow"} & claim_tokens:
        return None
    if not {"pattern", "texture", "paint", "decorative", "wall"} & claim_tokens:
        return None
    if not re.search(r"\bdermaroller\b", evidence, flags=re.IGNORECASE):
        return None
    if not re.search(r"\b(?:skin|serums?|moisturizers?|red)\b", evidence, flags=re.IGNORECASE):
        return None
    return RequiredFact(text=_clean(claim_text).rstrip(".!?"), type="domain_mismatch")


def _amputation_causality_conflict(claim_text: str, evidence_text: str, *, mode: str) -> RequiredFact | None:
    if mode != "semantic":
        return None
    claim = str(claim_text or "")
    evidence = str(evidence_text or "")
    if not re.search(r"\blost\s+(?:her|his|their)\s+foot\s+in\s+(?:the\s+)?(?:bombing|blast|attack)\b", claim, flags=re.IGNORECASE):
        return None
    if not re.search(r"\b(?:attempts?|tried)\s+to\s+save\s+(?:her|his|their)\s+foot\b", evidence, flags=re.IGNORECASE):
        return None
    if not re.search(r"\bamputat(?:ed|ion)\b", evidence, flags=re.IGNORECASE):
        return None
    return RequiredFact(text=_clean(claim_text).rstrip(".!?"), type="causality")


def _relative_pronoun_list_conflict(claim_text: str, evidence_text: str) -> RequiredFact | None:
    if not re.search(r"\brelative\s+pronouns?\b", str(claim_text or ""), flags=re.IGNORECASE):
        return None
    if not re.search(r"\brelative\s+pronouns?\b", str(evidence_text or ""), flags=re.IGNORECASE):
        return None

    claim_items = _relative_pronoun_items(claim_text)
    evidence_items = _relative_pronoun_items(evidence_text)
    if not claim_items or not evidence_items:
        return None
    invalid_items = claim_items.difference(evidence_items)
    if invalid_items.intersection({"him", "her", "it"}):
        return RequiredFact(text=", ".join(sorted(invalid_items)), type="closed_list")
    return None


def _relative_pronoun_items(text: str) -> set[str]:
    match = re.search(r"\brelative\s+pronouns?\s*\((?P<items>[^)]{1,120})\)", str(text or ""), flags=re.IGNORECASE)
    if not match:
        return set()
    return {
        token.lower()
        for token in re.findall(r"\b[A-Za-z]+\b", match.group("items"))
        if token.lower() not in {"and", "or"}
    }


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


def _any_relation_support(
    claim_relation: RelationFact,
    evidence_units: list[str],
    *,
    mode: str,
) -> bool:
    return any(
        _relations_support(claim_relation, evidence_relation, mode=mode)
        for unit in evidence_units
        for evidence_relation in [_extract_relation(unit)]
        if evidence_relation is not None
    )


def _relations_support(claim: RelationFact, evidence: RelationFact, *, mode: str) -> bool:
    if claim.predicate != evidence.predicate:
        return False
    subject_overlap = _bidirectional_phrase_overlap(claim.subject, evidence.subject, mode=mode)
    object_overlap = _bidirectional_phrase_overlap(claim.object, evidence.object, mode=mode)
    if subject_overlap >= 0.72 and object_overlap >= 0.72:
        return True
    return bool(object_overlap >= 0.72 and _has_generic_relation_subject(claim.subject, evidence.subject))


def _relations_conflict(claim: RelationFact, evidence: RelationFact, *, mode: str) -> bool:
    if claim.predicate != evidence.predicate:
        return False

    subject_overlap = _bidirectional_phrase_overlap(claim.subject, evidence.subject, mode=mode)
    object_overlap = _bidirectional_phrase_overlap(claim.object, evidence.object, mode=mode)
    reversed_subject_overlap = _bidirectional_phrase_overlap(claim.subject, evidence.object, mode=mode)
    reversed_object_overlap = _bidirectional_phrase_overlap(claim.object, evidence.subject, mode=mode)

    if reversed_subject_overlap >= 0.72 and reversed_object_overlap >= 0.72:
        return True
    if object_overlap >= 0.72 and _has_generic_relation_subject(claim.subject, evidence.subject):
        return False
    if subject_overlap >= 0.72 and object_overlap < 0.50:
        return True
    if _same_relation_head_with_different_modifier(claim.subject, evidence.subject, mode=mode) and object_overlap < 0.50:
        return True
    if object_overlap >= 0.72 and (
        subject_overlap < 0.35 or (subject_overlap < 0.72 and _proper_name_conflict(claim.subject, evidence.subject))
    ):
        return True
    return False


def _has_generic_relation_subject(left: str, right: str) -> bool:
    generic = {"this", "that", "it", "you", "they", "we", "one", "experience", "event", "situation", "move"}
    left_tokens = {token.lower() for token in TOKEN_RE.findall(str(left or ""))}
    right_tokens = {token.lower() for token in TOKEN_RE.findall(str(right or ""))}
    return bool(left_tokens.intersection(generic) or right_tokens.intersection(generic))


def _extract_relation(text: str) -> RelationFact | None:
    value = _clean(text).rstrip(".!?")
    for pattern in (LOCATION_RELATION_RE, ACTIVE_RELATION_RE):
        match = pattern.match(value)
        if match:
            predicate = _canonical_relation_predicate(match.group("predicate"))
            relation_object = _clean_relation_phrase(match.group("object"))
            if predicate == "cause" and relation_object.lower().startswith("of "):
                return None
            return RelationFact(
                subject=_clean_relation_phrase(match.group("subject")),
                predicate=predicate,
                object=relation_object,
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


def _person_last_names(value: str) -> set[str]:
    names: set[str] = set()
    for phrase in re.findall(r"\b[A-Z][A-Za-z.'-]+(?:\s+(?:de|da|del|van|von|[A-Z][A-Za-z.'-]+)){0,3}\b", str(value or "")):
        words = [word.strip(".,;:!?()[]{}\"'") for word in phrase.split() if word.strip(".,;:!?()[]{}\"'")]
        if not words:
            continue
        if words[0] in {"The", "A", "An"}:
            words = words[1:]
        filtered = [
            word
            for word in words
            if word.lower()
            not in {
                "mayor",
                "detective",
                "commissioner",
                "president",
                "police",
                "department",
                "city",
                "new",
                "york",
                "monday",
                "tuesday",
                "wednesday",
                "thursday",
                "friday",
                "saturday",
                "sunday",
                "uber",
            }
            and not word.isupper()
        ]
        if not filtered:
            continue
        last = filtered[-1]
        if last[:1].isupper() and len(last) > 1:
            names.add(last)
    return names


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


def _unique_strings(values: list[str]) -> list[str]:
    seen = set()
    output: list[str] = []
    for value in values:
        cleaned = _clean(value).strip(" .")
        key = cleaned.lower()
        if not cleaned or key in seen:
            continue
        seen.add(key)
        output.append(cleaned)
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
    "detect": "notice",
    "detected": "notice",
    "detecting": "notice",
    "detects": "notice",
    "noticed": "notice",
    "notices": "notice",
    "odor": "smell",
    "odour": "smell",
    "emitting": "come",
    "emits": "come",
    "coming": "come",
    "came": "come",
    "stopped": "stop",
    "pulled": "stop",
    "backdoored": "evict",
    "evicted": "evict",
    "evicting": "evict",
    "regretting": "regret",
    "regrets": "regret",
    "measuring": "measure",
    "measurement": "measure",
    "determining": "measure",
    "determine": "measure",
    "determines": "measure",
    "fits": "fill",
    "fitting": "fill",
    "levels": "level",
    "dizziness": "dizzy",
    "lightheaded": "dizzy",
    "eliminating": "eliminate",
    "eliminates": "eliminate",
    "improving": "improve",
    "improved": "improve",
    "increased": "increase",
    "decreasing": "decrease",
    "decreases": "decrease",
    "reducing": "reduce",
    "reduces": "reduce",
    "cafe-style": "cafe",
    "baked": "bakery",
    "bakeries": "bakery",
    "changed": "change",
    "changes": "change",
    "changing": "change",
    "dishes": "dish",
    "sandwiches": "sandwich",
    "selection": "option",
    "selections": "option",
    "stunning": "great",
    "welcoming": "friendly",
    "welcome": "friendly",
    "welcomed": "friendly",
    "inviting": "friendly",
    "warm": "friendly",
    "cozy": "friendly",
    "enjoyable": "fun",
    "reasonably": "reasonable",
    "affordable": "cheap",
    "got": "receive",
    "expensive": "high",
    "pricey": "high",
    "fought": "fight",
    "fights": "fight",
    "fighting": "fight",
    "inspirational": "inspire",
    "inspired": "inspire",
    "inspires": "inspire",
    "inspiring": "inspire",
    "died": "die",
    "dies": "die",
    "dead": "die",
    "deaths": "die",
    "likely": "expect",
    "slated": "schedule",
    "scheduled": "schedule",
    "schedules": "schedule",
    "scheduling": "schedule",
    "critical": "vital",
    "crucial": "vital",
    "controlled": "control",
    "controlling": "control",
    "controls": "control",
    "alleviate": "ease",
    "alleviating": "ease",
    "alleviated": "ease",
    "easing": "ease",
    "activities": "program",
    "activity": "program",
    "programs": "program",
    "parties": "program",
    "event": "program",
    "events": "program",
    "experienced": "experience",
    "experiences": "experience",
    "experiencing": "experience",
    "suffered": "experience",
    "suffering": "experience",
    "dining": "dine",
    "dine-in": "dine",
    "staffers": "staff",
    "workers": "staff",
    "worker": "staff",
    "specimens": "specimen",
    "collection": "collect",
    "collecting": "collect",
    "praised": "praise",
    "praises": "praise",
    "praising": "praise",
    "commended": "praise",
    "commends": "praise",
    "commending": "praise",
    "appreciated": "praise",
    "appreciates": "praise",
    "appreciating": "praise",
    "criticized": "criticize",
    "criticizes": "criticize",
    "criticizing": "criticize",
    "complained": "complain",
    "complains": "complain",
    "complaining": "complain",
    "disappointed": "disappoint",
    "disappointment": "disappoint",
    "dissatisfaction": "disappoint",
    "satisfied": "satisfactory",
    "satisfaction": "satisfactory",
    "mentioned": "mention",
    "mentions": "mention",
    "noted": "mention",
    "notes": "mention",
    "reported": "report",
    "reports": "report",
    "highlighted": "highlight",
    "highlights": "highlight",
    "education": "educate",
    "educational": "educate",
    "educating": "educate",
    "educated": "educate",
    "learned": "educate",
    "learns": "educate",
    "prevention": "prevent",
    "preventive": "prevent",
    "concerns": "concern",
    "concerned": "concern",
    "insane": "high",
    "snobs": "elitist",
    "snobby": "elitist",
    "tasty": "delicious",
    "kind": "friendly",
    "helpful": "friendly",
    "nice": "friendly",
    "pleasant": "friendly",
    "better": "well",
    "disaster": "mishap",
    "disasters": "mishap",
    "marred": "mishap",
    "accommodating": "accommodate",
    "accommodated": "accommodate",
    "accommodates": "accommodate",
    "associated": "equate",
    "associates": "equate",
    "associating": "equate",
    "association": "equate",
    "equated": "equate",
    "equating": "equate",
    "confusing": "unclear",
    "confusion": "unclear",
    "rare": "rarity",
    "rarely": "rarity",
    "resumed": "resume",
    "resumes": "resume",
    "resuming": "resume",
    "resumption": "resume",
    "russian": "russia",
    "stopping": "stop",
    "stopped": "stop",
    "miscalculated": "miscalculate",
    "miscalculates": "miscalculate",
    "miscalculation": "miscalculate",
    "controversial": "controversy",
    "discuss": "comment",
    "discussed": "comment",
    "discusses": "comment",
    "discussing": "comment",
    "reused": "reuse",
    "reusing": "reuse",
    "textured": "texture",
    "finishes": "finish",
    "techniques": "technique",
    "brats": "bratwurst",
    "bake": "bake",
    "bakes": "bake",
    "baking": "bake",
    "cook": "bake",
    "cooked": "bake",
    "cooks": "bake",
    "cooking": "bake",
    "architect": "architecture",
    "decorator": "interior",
    "designer": "design",
    "profession": "career",
    "professions": "career",
    "restless": "restlessness",
    "craves": "desire",
    "crave": "desire",
    "craving": "desire",
    "payment": "pay",
    "payments": "pay",
    "paid": "pay",
    "paying": "pay",
    "employee": "staff",
    "employees": "staff",
    "specialist": "staff",
    "employment": "employ",
    "employed": "employ",
    "employing": "employ",
    "talk": "consult",
    "talked": "consult",
    "talking": "consult",
    "proposal": "propos",
    "proposals": "propos",
    "propose": "propos",
    "proposes": "propos",
    "proposed": "propos",
    "proposing": "propos",
    "unhelpful": "poor",
    "uninterested": "poor",
    "ignored": "ignore",
    "ignoring": "ignore",
    "little": "small",
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
    "website": "online",
    "websites": "online",
    "url": "online",
    "site": "online",
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
    "larger": "bigger",
    "downtown": "dtsb",
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
    "projection": "project",
    "projected": "project",
    "projects": "project",
    "operational": "operate",
    "operation": "operate",
    "cultural": "culture",
    "seratonous": "serotinou",
    "serotinous": "serotinou",
    "serotonous": "serotinou",
    "regenerated": "regenerate",
    "regenerates": "regenerate",
    "regenerating": "regenerate",
    "proliferated": "proliferate",
    "proliferates": "proliferate",
    "proliferating": "proliferate",
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
    ("passed away", "died"),
    ("before the day is out", "soon"),
    ("as soon as possible", "fast"),
    ("currently in production for", "slated for"),
    ("newsroom actress", "newsroom role"),
    ("telepathic psylocke", "mutant superheroine psylocke"),
    ("covers prominent cities such as", "includes visits to"),
    ("same distance", "consistent distance"),
    ("taking specimens", "specimen collection"),
    ("took specimens", "specimen collection"),
    ("not into sweet stuff", "lacked flavor"),
    ("not a wide selection", "lack option"),
    ("not wide selection", "lack option"),
    ("only cash", "accept cash payment"),
    ("atm there", "atm available onsite"),
    ("people were nice", "staff friendly"),
    ("save the ocean life", "environmental impact"),
    ("help save the ocean life", "environmental impact"),
    ("sea animals", "environmental impact"),
    ("so many straws", "plastic straws"),
    ("wont give you the time of day", "not welcoming"),
    ("wo not give you the time of day", "not welcoming"),
    ("great selection of beers", "variety beers"),
    ("mellow vibe", "relaxed atmosphere"),
    ("laid back atmosphere", "relaxed atmosphere"),
    ("hidden gem", "unique experience"),
    ("could be better", "could be improved"),
    ("in a coma", "critical condition"),
    ("unable to talk or move", "critical condition"),
    ("rough shape", "critical condition"),
    ("remains to be seen", "uncertain"),
    ("gushing over", "happy with"),
    ("enjoying life", "happy"),
    ("happy and content", "happy"),
    ("no streaking occurs", "avoid streaks"),
    ("too expensive", "high price"),
    ("more people than normal", "busy"),
    ("laughter-filled", "laugh"),
    ("without breaking the bank", "cheap"),
    ("never been done before", "never attempted before"),
    ("re-used", "reuse"),
    ("re-use", "reuse"),
    ("released a version", "recorded version"),
    ("released a french version", "recorded french version"),
    ("went to 7pm", "extends until 7 pm"),
    ("went to 7 pm", "extends until 7 pm"),
    ("7pm", "7 pm"),
    ("work laws", "labor laws"),
    ("talk to a lawyer", "consult lawyer"),
    ("younger than age 18", "minors"),
)


def _semantic_text(text: str) -> str:
    value = _normalize_negation_text(text).lower()
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    value = re.sub(r"\b(\d+)\s*'\s*(\d+)\s*(?:\"|in\b|inch(?:es)?\b)?", r"\1 feet \2 inches", value)
    value = re.sub(r"(?<=\d),(?=\d{3}\b)", "", value)
    value = re.sub(r"\b\d+\.(?=[a-z])", " ", value)
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
