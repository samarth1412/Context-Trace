from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from app.playground.retrieval import (
    STRATEGY_DENSE_TOP_K,
    STRATEGY_HYBRID,
    STRATEGY_HYBRID_RERANK,
)

QUERY_FACT_SPECIFIC = "fact_specific"
QUERY_BROAD_SUMMARY = "broad_summary"
QUERY_MULTI_HOP = "multi_hop"
QUERY_AMBIGUOUS = "ambiguous"
QUERY_UNANSWERABLE_RISK = "unanswerable_risk"

POLICY_DENSE_TOP_K = "dense_top_k"
POLICY_HYBRID = "hybrid"
POLICY_HYBRID_RERANK = "hybrid_rerank"
POLICY_COMPRESSED_CONTEXT = "compressed_context"
POLICY_ABSTAIN_LOW_CONFIDENCE = "abstain_low_confidence"


@dataclass(frozen=True)
class QueryClassification:
    query_class: str
    reason: str


@dataclass(frozen=True)
class PolicyDecision:
    selected_policy: str
    retrieval_strategy: Optional[str]
    reason: str
    token_budget: int


class QueryClassifier:
    def classify(self, query: str) -> QueryClassification:
        normalized = " ".join(query.lower().split())
        tokens = _tokens(normalized)

        if not tokens:
            return QueryClassification(
                query_class=QUERY_AMBIGUOUS,
                reason="The query is empty after normalization.",
            )

        if _has_any(normalized, ["latest", "current", "today", "future", "predict", "forecast"]):
            return QueryClassification(
                query_class=QUERY_UNANSWERABLE_RISK,
                reason="The query asks for time-sensitive or predictive information.",
            )

        if _has_any(normalized, ["summarize", "summary", "overview", "walk me through", "explain all"]):
            return QueryClassification(
                query_class=QUERY_BROAD_SUMMARY,
                reason="The query asks for a broad synthesis rather than a narrow fact.",
            )

        if _has_any(normalized, ["compare", "contrast", "relationship between", "difference between"]):
            return QueryClassification(
                query_class=QUERY_MULTI_HOP,
                reason="The query requires comparing or connecting multiple pieces of evidence.",
            )

        if _looks_multi_part(normalized):
            return QueryClassification(
                query_class=QUERY_MULTI_HOP,
                reason="The query contains multiple linked sub-questions.",
            )

        if len(tokens) <= 2 or _has_any(normalized, ["what about it", "this policy", "that one"]):
            return QueryClassification(
                query_class=QUERY_AMBIGUOUS,
                reason="The query lacks enough specificity to select evidence confidently.",
            )

        return QueryClassification(
            query_class=QUERY_FACT_SPECIFIC,
            reason="The query asks for a specific answerable fact.",
        )


class PolicySelector:
    def select(
        self,
        *,
        classification: QueryClassification,
        retrieval_confidence: float,
    ) -> PolicyDecision:
        confidence = max(0.0, min(retrieval_confidence, 1.0))
        query_class = classification.query_class

        if confidence < 0.15:
            return PolicyDecision(
                selected_policy=POLICY_ABSTAIN_LOW_CONFIDENCE,
                retrieval_strategy=None,
                reason="Retrieval confidence is too low to support an answer.",
                token_budget=0,
            )

        if query_class == QUERY_UNANSWERABLE_RISK:
            if confidence < 0.65:
                return PolicyDecision(
                    selected_policy=POLICY_ABSTAIN_LOW_CONFIDENCE,
                    retrieval_strategy=None,
                    reason="The query has unanswerable risk and retrieved evidence is weak.",
                    token_budget=0,
                )
            return PolicyDecision(
                selected_policy=POLICY_HYBRID_RERANK,
                retrieval_strategy=STRATEGY_HYBRID_RERANK,
                reason="Time-sensitive or risky queries need stronger reranked evidence.",
                token_budget=1800,
            )

        if query_class == QUERY_AMBIGUOUS:
            if confidence < 0.45:
                return PolicyDecision(
                    selected_policy=POLICY_ABSTAIN_LOW_CONFIDENCE,
                    retrieval_strategy=None,
                    reason="The query is ambiguous and retrieval confidence is not high enough.",
                    token_budget=0,
                )
            return PolicyDecision(
                selected_policy=POLICY_HYBRID,
                retrieval_strategy=STRATEGY_HYBRID,
                reason="Ambiguous queries use hybrid retrieval to improve evidence coverage.",
                token_budget=1400,
            )

        if query_class == QUERY_BROAD_SUMMARY:
            return PolicyDecision(
                selected_policy=POLICY_COMPRESSED_CONTEXT,
                retrieval_strategy=STRATEGY_HYBRID_RERANK,
                reason="Broad summaries need more evidence compressed into a bounded context.",
                token_budget=900,
            )

        if query_class == QUERY_MULTI_HOP:
            return PolicyDecision(
                selected_policy=POLICY_HYBRID_RERANK,
                retrieval_strategy=STRATEGY_HYBRID_RERANK,
                reason="Multi-hop queries benefit from hybrid retrieval with reranking.",
                token_budget=1800,
            )

        if confidence >= 0.45:
            return PolicyDecision(
                selected_policy=POLICY_DENSE_TOP_K,
                retrieval_strategy=STRATEGY_DENSE_TOP_K,
                reason="A specific query with strong retrieval confidence can use dense top-k.",
                token_budget=1200,
            )

        return PolicyDecision(
            selected_policy=POLICY_HYBRID,
            retrieval_strategy=STRATEGY_HYBRID,
            reason="A specific query with moderate confidence should add lexical retrieval.",
            token_budget=1400,
        )


TOKEN_RE = re.compile(r"[a-zA-Z0-9_]+")


def _tokens(text: str) -> list:
    return TOKEN_RE.findall(text)


def _has_any(text: str, needles: list) -> bool:
    return any(needle in text for needle in needles)


def _looks_multi_part(text: str) -> bool:
    if text.count("?") > 1:
        return True
    return bool(re.search(r"\b(and|then|after that)\b.+\b(why|how|what|when|where)\b", text))
