"""Minimal exact-span evidence attribution for the v2.1 candidate."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

from contexttrace.verify.evidence import (
    exact_surface_spans,
    lexical_score,
    unique_important_tokens,
)
from contexttrace.verify.schema import RAGTrace
from contexttrace.verify.spans import split_context_spans

from .checker import observable_conflicts
from .profile import V21Profile

EVIDENCE_ATTRIBUTION_VERSION = "hierarchical-evidence-attribution-v2.1.0"


@dataclass(frozen=True)
class _Candidate:
    context_id: str
    context_order: int
    text: str
    start_char: int
    end_char: int
    span_hash: str
    score: float
    covered_terms: frozenset[str]
    conflict_keys: frozenset[str]

    @property
    def conflict_count(self) -> int:
        return len(self.conflict_keys)

    @property
    def role(self) -> str:
        return "contradicting" if self.conflict_count else "supporting"

    def to_span(self) -> dict[str, Any]:
        return {
            "context_id": self.context_id,
            "start_char": self.start_char,
            "end_char": self.end_char,
            "text": self.text,
            "role": self.role,
            "span_hash": self.span_hash,
        }


def attribute_evidence_v2_1(
    *,
    claim_id: str,
    claim: str,
    answer_start: int,
    answer_end: int,
    verdict: str,
    trace: RAGTrace,
    profile: V21Profile,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Return a bounded minimal span set and its answer-to-source audit record."""

    claim_terms = frozenset(unique_important_tokens(claim, mode="semantic"))
    candidates = _candidates(claim, claim_terms, trace, profile)
    supporting = [candidate for candidate in candidates if not candidate.conflict_count]
    contradicting = [candidate for candidate in candidates if candidate.conflict_count]

    if verdict == "contradicted" or (
        verdict in {"unsupported", "unverifiable"} and contradicting
    ):
        selected = _select_contradicting(contradicting, profile.max_attribution_spans)
    else:
        selected = _select_supporting(
            supporting,
            claim_terms,
            profile.max_attribution_spans,
        )
        if (
            verdict == "partially_supported"
            and contradicting
            and len(selected) < profile.max_attribution_spans
        ):
            selected.extend(
                _select_contradicting(
                    contradicting,
                    profile.max_attribution_spans - len(selected),
                )
            )

    selected = sorted(
        selected,
        key=lambda item: (
            item.context_order,
            item.start_char,
            item.end_char,
            item.role,
        ),
    )
    spans = [candidate.to_span() for candidate in selected]
    covered = (
        set().union(
            *(
                candidate.covered_terms
                for candidate in selected
                if candidate.role == "supporting"
            )
        )
        if selected
        else set()
    )
    coverage = len(covered & claim_terms) / len(claim_terms) if claim_terms else 0.0
    record = {
        "version": EVIDENCE_ATTRIBUTION_VERSION,
        "claim_id": claim_id,
        "answer_span": {"start_char": answer_start, "end_char": answer_end},
        "candidate_span_count": len(candidates),
        "selected_span_count": len(spans),
        "supporting_span_count": sum(span["role"] == "supporting" for span in spans),
        "contradicting_span_count": sum(
            span["role"] == "contradicting" for span in spans
        ),
        "document_count": len({span["context_id"] for span in spans}),
        "claim_term_coverage": round(coverage, 6),
        "exact_offsets_verified": True,
    }
    return spans, record


def _candidates(
    claim: str,
    claim_terms: frozenset[str],
    trace: RAGTrace,
    profile: V21Profile,
) -> list[_Candidate]:
    candidates: list[_Candidate] = []
    seen: set[tuple[str, int, int]] = set()
    for context_order, context in enumerate(trace.contexts):
        raw_spans = [
            (span.start_char, span.end_char, span.text, span.span_hash)
            for span in split_context_spans(context)
        ]
        raw_spans.extend(
            (
                start,
                end,
                text,
                _span_hash(context.id, start, end, text),
            )
            for start, end, text in exact_surface_spans(claim, context.text)
        )
        for start, end, text, span_hash in raw_spans:
            key = (context.id, start, end)
            if key in seen or context.text[start:end] != text:
                continue
            seen.add(key)
            score, _ = lexical_score(claim, text, mode="semantic")
            conflicts = observable_conflicts(claim, text)
            if score < profile.evidence_span_min_score and not conflicts:
                continue
            covered = (
                frozenset(unique_important_tokens(text, mode="semantic")) & claim_terms
            )
            if not covered and not conflicts:
                continue
            candidates.append(
                _Candidate(
                    context_id=context.id,
                    context_order=context_order,
                    text=text,
                    start_char=start,
                    end_char=end,
                    span_hash=span_hash,
                    score=score,
                    covered_terms=covered,
                    conflict_keys=frozenset(
                        f"{conflict.category}:{conflict.claim_value}:"
                        f"{conflict.evidence_value or ''}"
                        for conflict in conflicts
                    ),
                )
            )
    return candidates


def _select_supporting(
    candidates: list[_Candidate],
    claim_terms: frozenset[str],
    limit: int,
) -> list[_Candidate]:
    remaining = list(candidates)
    uncovered = set(claim_terms)
    selected: list[_Candidate] = []
    while remaining and len(selected) < limit:
        ranked = sorted(
            remaining,
            key=lambda item: (
                len(item.covered_terms & uncovered),
                item.score,
                -len(item.text),
                -item.context_order,
                -item.start_char,
            ),
            reverse=True,
        )
        best = ranked[0]
        if not (best.covered_terms & uncovered):
            break
        selected.append(best)
        uncovered.difference_update(best.covered_terms)
        remaining = [
            candidate
            for candidate in remaining
            if candidate != best and not _contained_by(candidate, best)
        ]
        if not uncovered:
            break
    return selected


def _select_contradicting(candidates: list[_Candidate], limit: int) -> list[_Candidate]:
    uncovered = set().union(*(candidate.conflict_keys for candidate in candidates))
    selected: list[_Candidate] = []
    remaining = list(candidates)
    while remaining and len(selected) < limit:
        ranked = sorted(
            remaining,
            key=lambda item: (
                len(item.conflict_keys & uncovered),
                item.score,
                -len(item.text),
                -item.context_order,
                -item.start_char,
            ),
            reverse=True,
        )
        best = ranked[0]
        if not (best.conflict_keys & uncovered):
            break
        selected.append(best)
        uncovered.difference_update(best.conflict_keys)
        remaining = [
            candidate
            for candidate in remaining
            if candidate != best
            and not _contained_by(candidate, best)
            and not _contained_by(best, candidate)
        ]
    return selected


def _contained_by(candidate: _Candidate, selected: _Candidate) -> bool:
    return bool(
        candidate.context_id == selected.context_id
        and selected.start_char <= candidate.start_char
        and candidate.end_char <= selected.end_char
    )


def _span_hash(context_id: str, start: int, end: int, text: str) -> str:
    payload = f"{context_id}\n{start}:{end}\n{text}".encode()
    return f"sha256:{hashlib.sha256(payload).hexdigest()[:16]}"
