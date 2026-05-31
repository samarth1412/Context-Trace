from __future__ import annotations

import math
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional

from app.playground.vector_store import VectorRecord, VectorStore


STRATEGY_DENSE_TOP_K = "dense_top_k"
STRATEGY_BM25_TOP_K = "bm25_top_k"
STRATEGY_HYBRID = "hybrid"
STRATEGY_HYBRID_RERANK = "hybrid_rerank"
DEFAULT_STRATEGIES = [
    STRATEGY_DENSE_TOP_K,
    STRATEGY_BM25_TOP_K,
    STRATEGY_HYBRID,
    STRATEGY_HYBRID_RERANK,
]


@dataclass
class RetrievalRequestContext:
    query: str
    query_vector: List[float]
    top_k: int
    filters: Dict[str, str]


class RetrievalStrategy(ABC):
    name: str

    @abstractmethod
    async def retrieve(
        self,
        *,
        vector_store: VectorStore,
        context: RetrievalRequestContext,
    ) -> List[VectorRecord]:
        ...


class DenseTopKStrategy(RetrievalStrategy):
    name = STRATEGY_DENSE_TOP_K

    async def retrieve(
        self,
        *,
        vector_store: VectorStore,
        context: RetrievalRequestContext,
    ) -> List[VectorRecord]:
        return await vector_store.search(
            vector=context.query_vector,
            limit=context.top_k,
            filters=context.filters,
        )


class BM25TopKStrategy(RetrievalStrategy):
    name = STRATEGY_BM25_TOP_K

    async def retrieve(
        self,
        *,
        vector_store: VectorStore,
        context: RetrievalRequestContext,
    ) -> List[VectorRecord]:
        records = await vector_store.list_records(filters=context.filters)
        return _bm25_rank(context.query, records, limit=context.top_k)


class HybridStrategy(RetrievalStrategy):
    name = STRATEGY_HYBRID

    async def retrieve(
        self,
        *,
        vector_store: VectorStore,
        context: RetrievalRequestContext,
    ) -> List[VectorRecord]:
        candidate_limit = max(context.top_k * 4, 20)
        dense = await vector_store.search(
            vector=context.query_vector,
            limit=candidate_limit,
            filters=context.filters,
        )
        bm25 = _bm25_rank(
            context.query,
            await vector_store.list_records(filters=context.filters),
            limit=candidate_limit,
        )
        return _merge_ranked_records(
            dense,
            bm25,
            limit=context.top_k,
            dense_weight=0.5,
            lexical_weight=0.5,
        )


class HybridRerankStrategy(RetrievalStrategy):
    name = STRATEGY_HYBRID_RERANK

    async def retrieve(
        self,
        *,
        vector_store: VectorStore,
        context: RetrievalRequestContext,
    ) -> List[VectorRecord]:
        candidate_limit = max(context.top_k * 5, 30)
        dense = await vector_store.search(
            vector=context.query_vector,
            limit=candidate_limit,
            filters=context.filters,
        )
        all_records = await vector_store.list_records(filters=context.filters)
        bm25 = _bm25_rank(context.query, all_records, limit=candidate_limit)
        candidates = _merge_ranked_records(
            dense,
            bm25,
            limit=candidate_limit,
            dense_weight=0.45,
            lexical_weight=0.55,
        )

        query_tokens = set(_tokenize(context.query))
        reranked = []
        for record in candidates:
            content_tokens = set(_tokenize(record.content))
            overlap = len(query_tokens & content_tokens) / max(len(query_tokens), 1)
            phrase_bonus = _phrase_bonus(context.query, record.content)
            reranked.append((record.score + overlap * 0.25 + phrase_bonus, record))
        reranked.sort(key=lambda item: item[0], reverse=True)
        return [_with_score(record, score) for score, record in reranked[: context.top_k]]


def get_retrieval_strategy(name: str) -> RetrievalStrategy:
    strategies = {
        STRATEGY_DENSE_TOP_K: DenseTopKStrategy(),
        STRATEGY_BM25_TOP_K: BM25TopKStrategy(),
        STRATEGY_HYBRID: HybridStrategy(),
        STRATEGY_HYBRID_RERANK: HybridRerankStrategy(),
    }
    try:
        return strategies[name]
    except KeyError as exc:
        raise ValueError("Unknown retrieval strategy: %s" % name) from exc


TOKEN_RE = re.compile(r"[a-zA-Z0-9_]+")


def _tokenize(text: str) -> List[str]:
    return TOKEN_RE.findall(text.lower())


def _bm25_rank(query: str, records: List[VectorRecord], *, limit: int) -> List[VectorRecord]:
    query_terms = _tokenize(query)
    if not query_terms or not records:
        return []

    tokenized_docs = [_tokenize(record.content) for record in records]
    avg_doc_length = sum(len(doc) for doc in tokenized_docs) / max(len(tokenized_docs), 1)
    document_frequency: Dict[str, int] = {}
    for doc in tokenized_docs:
        for term in set(doc):
            document_frequency[term] = document_frequency.get(term, 0) + 1

    scored = []
    for record, doc_terms in zip(records, tokenized_docs):
        score = _bm25_score(
            query_terms=query_terms,
            doc_terms=doc_terms,
            document_frequency=document_frequency,
            document_count=len(records),
            avg_doc_length=avg_doc_length,
        )
        if score > 0:
            scored.append((_with_score(record, score), score))

    scored.sort(key=lambda item: item[1], reverse=True)
    return [record for record, _ in scored[:limit]]


def _bm25_score(
    *,
    query_terms: List[str],
    doc_terms: List[str],
    document_frequency: Dict[str, int],
    document_count: int,
    avg_doc_length: float,
) -> float:
    term_frequency: Dict[str, int] = {}
    for term in doc_terms:
        term_frequency[term] = term_frequency.get(term, 0) + 1

    score = 0.0
    k1 = 1.5
    b = 0.75
    doc_length = len(doc_terms)
    for term in query_terms:
        frequency = term_frequency.get(term, 0)
        if frequency == 0:
            continue
        doc_freq = document_frequency.get(term, 0)
        inverse_doc_frequency = math.log(
            1 + (document_count - doc_freq + 0.5) / (doc_freq + 0.5)
        )
        denominator = frequency + k1 * (
            1 - b + b * doc_length / max(avg_doc_length, 1.0)
        )
        score += inverse_doc_frequency * (frequency * (k1 + 1)) / denominator
    return score


def _merge_ranked_records(
    dense: List[VectorRecord],
    lexical: List[VectorRecord],
    *,
    limit: int,
    dense_weight: float,
    lexical_weight: float,
) -> List[VectorRecord]:
    dense_scores = _normalize_scores(dense)
    lexical_scores = _normalize_scores(lexical)
    by_id: Dict[str, VectorRecord] = {}
    for record in list(dense) + list(lexical):
        by_id[record.chunk_id] = record

    scored = []
    for chunk_id, record in by_id.items():
        score = dense_scores.get(chunk_id, 0.0) * dense_weight
        score += lexical_scores.get(chunk_id, 0.0) * lexical_weight
        scored.append((_with_score(record, score), score))

    scored.sort(key=lambda item: item[1], reverse=True)
    return [record for record, _ in scored[:limit]]


def _normalize_scores(records: Iterable[VectorRecord]) -> Dict[str, float]:
    records_list = list(records)
    if not records_list:
        return {}
    scores = [record.score for record in records_list]
    min_score = min(scores)
    max_score = max(scores)
    if max_score == min_score:
        return {record.chunk_id: 1.0 for record in records_list}
    return {
        record.chunk_id: (record.score - min_score) / (max_score - min_score)
        for record in records_list
    }


def _with_score(record: VectorRecord, score: float) -> VectorRecord:
    return VectorRecord(
        chunk_id=record.chunk_id,
        content=record.content,
        source=record.source,
        metadata=record.metadata,
        score=score,
    )


def _phrase_bonus(query: str, content: str) -> float:
    query_tokens = _tokenize(query)
    if len(query_tokens) < 2:
        return 0.0
    normalized_content = " ".join(_tokenize(content))
    pairs = ["%s %s" % (left, right) for left, right in zip(query_tokens, query_tokens[1:])]
    hits = sum(1 for pair in pairs if pair in normalized_content)
    return min(hits * 0.05, 0.2)
