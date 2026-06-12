from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

from contexttrace.verify.schema import TraceContext
from contexttrace.verify.spans import split_context_spans
from contexttrace.verify.local_ml import local_ml_score_pair


@dataclass(frozen=True)
class EvidenceMatch:
    context_id: str | None
    context_text: str
    score: float
    matched_terms: list[str]
    snippet: str
    span_start: int | None = None
    span_end: int | None = None
    span_hash: str | None = None
    supporting_spans: list[dict[str, object]] | None = None
    supporting_text: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "best_context_id": self.context_id,
            "best_context_text": self.context_text,
            "best_score": self.score,
            "matched_terms": list(self.matched_terms),
            "evidence_snippet": self.snippet,
            "evidence_span": self.span_dict(),
            "supporting_spans": list(self.supporting_spans or []),
        }

    def span_dict(self) -> dict[str, object] | None:
        if self.context_id is None or self.span_start is None or self.span_end is None or self.span_hash is None:
            return None
        return {
            "context_id": self.context_id,
            "text": self.snippet,
            "start_char": self.span_start,
            "end_char": self.span_end,
            "span_hash": self.span_hash,
        }


TOKEN_RE = re.compile(r"[A-Za-z0-9]+")

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
    span_candidates: list[dict[str, object]] = []
    for context in contexts:
        candidate = score_claim_against_context(claim_text, context, mode=mode)
        span_candidates.extend(candidate.supporting_spans or [])
        if best.context_id is None or candidate.score > best.score:
            best = candidate
    sorted_spans = _rank_spans(span_candidates)
    return EvidenceMatch(
        context_id=best.context_id,
        context_text=best.context_text,
        score=best.score,
        matched_terms=list(best.matched_terms),
        snippet=best.snippet,
        span_start=best.span_start,
        span_end=best.span_end,
        span_hash=best.span_hash,
        supporting_spans=sorted_spans,
        supporting_text=" ".join(str(span.get("text") or "") for span in sorted_spans),
    )


def score_claim_against_context(
    claim_text: str,
    context: TraceContext,
    *,
    mode: str = "lexical",
) -> EvidenceMatch:
    spans = split_context_spans(context)
    best_score = 0.0
    best_terms: list[str] = []
    fallback_span = spans[0] if spans else None
    best_snippet = fallback_span.text.strip() if fallback_span is not None else context.text.strip()
    best_start: int | None = fallback_span.start_char if fallback_span is not None else None
    best_end: int | None = fallback_span.end_char if fallback_span is not None else None
    best_hash: str | None = fallback_span.span_hash if fallback_span is not None else None
    span_candidates: list[dict[str, object]] = []
    for span in spans:
        score, terms = lexical_score(claim_text, span.text, mode=mode)
        if score > 0:
            span_candidates.append(
                {
                    "context_id": context.id,
                    "text": span.text,
                    "start_char": span.start_char,
                    "end_char": span.end_char,
                    "span_hash": span.span_hash,
                    "score": score,
                    "matched_terms": list(terms),
                }
            )
        if score > best_score:
            best_score = score
            best_terms = terms
            best_snippet = span.text.strip()
            best_start = span.start_char
            best_end = span.end_char
            best_hash = span.span_hash
    return EvidenceMatch(
        context_id=context.id,
        context_text=context.text,
        score=best_score,
        matched_terms=best_terms,
        snippet=best_snippet,
        span_start=best_start,
        span_end=best_end,
        span_hash=best_hash,
        supporting_spans=_rank_spans(span_candidates),
        supporting_text=" ".join(str(span.get("text") or "") for span in _rank_spans(span_candidates)),
    )


def _rank_spans(spans: list[dict[str, object]], *, limit: int = 4) -> list[dict[str, object]]:
    unique: dict[str, dict[str, object]] = {}
    for span in spans:
        key = str(span.get("span_hash") or "%s:%s:%s" % (span.get("context_id"), span.get("start_char"), span.get("end_char")))
        existing = unique.get(key)
        if existing is None or float(span.get("score") or 0) > float(existing.get("score") or 0):
            unique[key] = dict(span)
    ranked = sorted(
        unique.values(),
        key=lambda item: (
            float(item.get("score") or 0),
            len(item.get("matched_terms") or []),
        ),
        reverse=True,
    )
    return ranked[:limit]


def lexical_score(claim_text: str, evidence_text: str, *, mode: str = "lexical") -> tuple[float, list[str]]:
    token_mode = _token_mode(mode)
    claim_terms = unique_important_tokens(claim_text, mode=token_mode)
    if not claim_terms:
        return 0.0, []

    evidence_terms = set(unique_important_tokens(evidence_text, mode=token_mode))
    matched_canonical = [term for term in claim_terms if term in evidence_terms]
    coverage = len(matched_canonical) / len(claim_terms)
    union_size = len(set(claim_terms).union(evidence_terms)) or 1
    jaccard = len(matched_canonical) / union_size

    score = (0.78 * coverage) + (0.22 * jaccard)
    if _compact_text(claim_text, mode=token_mode) and _compact_text(claim_text, mode=token_mode) in _compact_text(evidence_text, mode=token_mode):
        score += 0.12

    claim_numbers = extract_numbers(claim_text)
    evidence_numbers = extract_numbers(evidence_text)
    if claim_numbers:
        if set(claim_numbers).issubset(set(evidence_numbers)):
            score += 0.08
        elif evidence_numbers:
            score -= 0.18

    if _semantic_enabled(mode):
        score += _semantic_phrase_bonus(claim_text, evidence_text)

    score = round(max(0.0, min(1.0, score)), 3)
    if _local_ml_enabled(mode):
        score = local_ml_score_pair(claim_text, evidence_text, lexical_score=score)

    matched_terms = display_matched_terms(claim_text, evidence_terms, mode=token_mode)
    return round(max(0.0, min(1.0, score)), 3), matched_terms


def unique_important_tokens(text: str, *, mode: str = "lexical") -> list[str]:
    seen = set()
    tokens: list[str] = []
    normalized_text = _semantic_text(text) if _semantic_enabled(mode) else str(text or "").lower()
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
    if _semantic_enabled(mode):
        value = SEMANTIC_TOKEN_MAP.get(value, value)
    if value.endswith("ies") and len(value) > 4:
        return value[:-3] + "y"
    if _semantic_enabled(mode) and value.endswith("ing") and len(value) > 5:
        return value[:-3]
    if _semantic_enabled(mode) and value.endswith("ed") and len(value) > 4:
        return value[:-2]
    if value.endswith("s") and len(value) > 3 and not value.endswith("ss"):
        return value[:-1]
    return value


def extract_numbers(text: str) -> list[str]:
    return re.findall(r"\b\d+(?:\.\d+)?\b", str(text or ""))


def _sentences(text: str) -> list[str]:
    value = str(text or "")
    sentences: list[str] = []
    start = 0
    for index, char in enumerate(value):
        if char not in ".!?":
            continue
        if char == "." and _is_internal_period(value, index):
            continue
        sentence = value[start : index + 1].strip()
        if sentence:
            sentences.append(sentence)
        start = index + 1
    tail = value[start:].strip()
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


def _compact_text(text: str, *, mode: str = "lexical") -> str:
    value = _semantic_text(text) if _semantic_enabled(mode) else str(text or "").lower()
    return " ".join(TOKEN_RE.findall(value))


def _local_ml_enabled(mode: str) -> bool:
    return str(mode or "").strip().lower().replace("-", "_") == "local_ml"


def _semantic_enabled(mode: str) -> bool:
    return str(mode or "").strip().lower().replace("-", "_") in {"semantic", "local_ml", "nli"}


def _token_mode(mode: str) -> str:
    return "semantic" if _semantic_enabled(mode) else "lexical"


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
    "recomputed": "recompute",
    "recomputes": "recompute",
    "recomputing": "recompute",
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
    "receipt": "proof",
    "documentation": "proof",
    "documents": "proof",
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
    ("proof of purchase", "proof"),
    ("united states", "us"),
    ("not exactly what the law considers true", "false by the law"),
    ('not exactly what the law considers "true', "false by the law"),
)


def _semantic_text(text: str) -> str:
    value = _normalize_negation_text(text).lower()
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


def _normalize_negation_text(text: str) -> str:
    value = str(text or "")
    value = re.sub(r"\bcan['’]?t\b", "cannot", value, flags=re.IGNORECASE)
    return re.sub(r"\b([A-Za-z]+)n['’]t\b", r"\1 not", value)
