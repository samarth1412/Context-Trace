from __future__ import annotations

import re
from dataclasses import dataclass


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
NEGATION_RE = re.compile(r"\b(?:no|not|never|without|cannot|can't|prohibited|forbidden|disallowed)\b", re.IGNORECASE)
WHITESPACE_RE = re.compile(r"\s+")
LIST_VERB_RE = re.compile(
    r"\b(?P<verb>captures?|stores?|adds?|includes?|checks?|detects?|verifies?|reports?|records?|logs?|supports?|keeps?|calls?|maps?|creates?|runs?|writes?|saves?|evaluates?)\b\s+(?P<tail>.+)",
    re.IGNORECASE,
)
LIST_ITEM_RE = re.compile(
    r"^(?P<verb>captures?|stores?|adds?|includes?|checks?|detects?|verifies?|reports?|records?|logs?|supports?|keeps?|calls?|maps?|creates?|runs?|writes?|saves?|evaluates?)\s+(?P<tail>.+)$",
    re.IGNORECASE,
)

STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "in",
    "is",
    "it",
    "of",
    "or",
    "so",
    "that",
    "the",
    "to",
    "under",
    "with",
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


@dataclass(frozen=True)
class RequiredFact:
    text: str
    type: str

    def to_dict(self) -> dict[str, str]:
        return {"text": self.text, "type": self.type}


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
    for fact in required_details:
        if _fact_supported(fact.text, evidence_text, mode=mode):
            matched_details.append(fact)
        else:
            missing_details.append(fact)

    if _has_negation_conflict(claim_text, evidence_text, mode=mode):
        conflicting_details.append(RequiredFact(text=claim_text.strip(), type="negation"))
    version_conflict = _version_conflict(claim_text, evidence_text, mode=mode)
    if version_conflict is not None:
        conflicting_details.append(version_conflict)
    numeric_conflict = _numeric_conflict(claim_text, evidence_text, mode=mode)
    if numeric_conflict is not None:
        conflicting_details.append(numeric_conflict)

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
        else:
            facts.append(RequiredFact(text="%s %s" % (verb, part), type="predicate"))
    return facts


def _fact_supported(fact: str, evidence_text: str, *, mode: str) -> bool:
    if _missing_exact_terms(fact, evidence_text):
        return False

    fact_tokens = _important_tokens(fact, mode=mode)
    if not fact_tokens:
        return False
    evidence_tokens = set(_important_tokens(evidence_text, mode=mode))
    matched = [token for token in fact_tokens if token in evidence_tokens]
    coverage = len(matched) / len(fact_tokens)
    if coverage >= 0.72:
        return True

    compact_fact = _compact(fact, mode=mode)
    compact_evidence = _compact(evidence_text, mode=mode)
    if compact_fact and compact_fact in compact_evidence:
        return True

    if _list_item_supported(fact, evidence_text, evidence_tokens, mode=mode):
        return True

    return len(matched) >= 2 and coverage >= 0.62


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
    claim_negated = bool(NEGATION_RE.search(claim_text))
    units = _evidence_units(evidence_text)
    if not units:
        return False

    same_polarity_support = any(
        bool(NEGATION_RE.search(unit)) == claim_negated
        and _token_overlap(claim_text, unit, mode=mode) >= 0.40
        for unit in units
    )
    if same_polarity_support:
        return False

    return any(
        bool(NEGATION_RE.search(unit)) != claim_negated
        and _token_overlap(claim_text, unit, mode=mode) >= 0.55
        for unit in units
    )


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
    present = {term.lower() for term in TOKEN_RE.findall(str(evidence_text or ""))}
    return sorted(required - present)


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
    "repay": "refund",
    "repayment": "refund",
    "id": "number",
    "identifier": "number",
    "retriever": "retrieval",
    "retrievers": "retrieval",
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
)


def _semantic_text(text: str) -> str:
    value = str(text or "").lower()
    for source, replacement in SEMANTIC_PHRASES:
        value = value.replace(source, replacement)
    return value
