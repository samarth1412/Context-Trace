from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

from contexttrace.verify.schema import TraceContext


@dataclass(frozen=True)
class EvidenceMatch:
    context_id: str | None
    context_text: str
    score: float
    matched_terms: list[str]
    snippet: str

    def to_dict(self) -> dict[str, object]:
        return {
            "best_context_id": self.context_id,
            "best_context_text": self.context_text,
            "best_score": self.score,
            "matched_terms": list(self.matched_terms),
            "evidence_snippet": self.snippet,
        }


TOKEN_RE = re.compile(r"[A-Za-z0-9]+")
SENTENCE_RE = re.compile(r"[^.!?\n]+(?:[.!?]+|$)", re.MULTILINE)

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


def find_best_evidence(
    claim_text: str,
    contexts: Iterable[TraceContext],
    *,
    mode: str = "lexical",
) -> EvidenceMatch:
    best = EvidenceMatch(
        context_id=None,
        context_text="",
        score=0.0,
        matched_terms=[],
        snippet="",
    )
    for context in contexts:
        candidate = score_claim_against_context(claim_text, context, mode=mode)
        if best.context_id is None or candidate.score > best.score:
            best = candidate
    return best


def score_claim_against_context(
    claim_text: str,
    context: TraceContext,
    *,
    mode: str = "lexical",
) -> EvidenceMatch:
    snippets = _sentences(context.text) or [context.text]
    best_score = 0.0
    best_terms: list[str] = []
    best_snippet = ""
    for snippet in snippets:
        score, terms = lexical_score(claim_text, snippet, mode=mode)
        if score > best_score:
            best_score = score
            best_terms = terms
            best_snippet = snippet.strip()
    if not best_snippet:
        best_snippet = context.text.strip()
    return EvidenceMatch(
        context_id=context.id,
        context_text=context.text,
        score=best_score,
        matched_terms=best_terms,
        snippet=best_snippet,
    )


def lexical_score(claim_text: str, evidence_text: str, *, mode: str = "lexical") -> tuple[float, list[str]]:
    claim_terms = unique_important_tokens(claim_text, mode=mode)
    if not claim_terms:
        return 0.0, []

    evidence_terms = set(unique_important_tokens(evidence_text, mode=mode))
    matched_canonical = [term for term in claim_terms if term in evidence_terms]
    coverage = len(matched_canonical) / len(claim_terms)
    union_size = len(set(claim_terms).union(evidence_terms)) or 1
    jaccard = len(matched_canonical) / union_size

    score = (0.78 * coverage) + (0.22 * jaccard)
    if _compact_text(claim_text, mode=mode) and _compact_text(claim_text, mode=mode) in _compact_text(evidence_text, mode=mode):
        score += 0.12

    claim_numbers = extract_numbers(claim_text)
    evidence_numbers = extract_numbers(evidence_text)
    if claim_numbers:
        if set(claim_numbers).issubset(set(evidence_numbers)):
            score += 0.08
        elif evidence_numbers:
            score -= 0.18

    if mode == "semantic":
        score += _semantic_phrase_bonus(claim_text, evidence_text)

    matched_terms = display_matched_terms(claim_text, evidence_terms, mode=mode)
    return round(max(0.0, min(1.0, score)), 3), matched_terms


def unique_important_tokens(text: str, *, mode: str = "lexical") -> list[str]:
    seen = set()
    tokens: list[str] = []
    normalized_text = _semantic_text(text) if mode == "semantic" else str(text or "").lower()
    for token in TOKEN_RE.findall(normalized_text):
        if token in STOPWORDS:
            continue
        if len(token) == 1 and not token.isdigit():
            continue
        canonical = canonical_token(token, mode=mode)
        if canonical and canonical not in seen:
            seen.add(canonical)
            tokens.append(canonical)
    return tokens


def display_matched_terms(claim_text: str, evidence_terms: set[str], *, mode: str = "lexical") -> list[str]:
    matched: list[str] = []
    seen = set()
    for token in TOKEN_RE.findall(str(claim_text or "").lower()):
        if token in STOPWORDS:
            continue
        canonical = canonical_token(token, mode=mode)
        if canonical in evidence_terms and token not in seen:
            seen.add(token)
            matched.append(token)
    return matched


def canonical_token(token: str, *, mode: str = "lexical") -> str:
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


def extract_numbers(text: str) -> list[str]:
    return re.findall(r"\b\d+(?:\.\d+)?\b", str(text or ""))


def _sentences(text: str) -> list[str]:
    return [match.group(0).strip() for match in SENTENCE_RE.finditer(str(text or "")) if match.group(0).strip()]


def _compact_text(text: str, *, mode: str = "lexical") -> str:
    value = _semantic_text(text) if mode == "semantic" else str(text or "").lower()
    return " ".join(TOKEN_RE.findall(value))


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
    "receipt": "proof",
    "documentation": "proof",
    "documents": "proof",
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
    ("proof of purchase", "proof"),
)


def _semantic_text(text: str) -> str:
    value = str(text or "").lower()
    for source, replacement in SEMANTIC_PHRASES:
        value = value.replace(source, replacement)
    return value


def _semantic_phrase_bonus(claim_text: str, evidence_text: str) -> float:
    claim = _semantic_text(claim_text)
    evidence = _semantic_text(evidence_text)
    bonus = 0.0
    for _, replacement in SEMANTIC_PHRASES:
        if replacement in claim and replacement in evidence:
            bonus += 0.03
    return min(0.09, bonus)
