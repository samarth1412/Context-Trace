from __future__ import annotations

import time
import uuid
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.judge import LLMJudgeProvider
from app.models import User
from app.playground.documents import DocumentParser, TokenAwareChunker
from app.playground.providers import AnswerProvider, EmbeddingProvider, GeneratedAnswer
from app.playground.retrieval import (
    STRATEGY_DENSE_TOP_K,
    RetrievalRequestContext,
    get_retrieval_strategy,
)
from app.playground.vector_store import VectorRecord, VectorStore
from app.schemas import (
    AnswerRequest,
    ChunkPayload,
    CitationPayload,
    CitationsRequest,
    ContextRequest,
    PlaygroundCompareRequest,
    PlaygroundCompareResponse,
    PlaygroundChunk,
    PlaygroundComparisonMetrics,
    PlaygroundComparisonResult,
    PlaygroundDocumentUploadResponse,
    PlaygroundQueryRequest,
    PlaygroundQueryResponse,
    RetrievalRequest,
    RetrievalStrategyName,
    TraceStartRequest,
)
from app.services.errors import BadRequestError
from app.services.traces import TraceService


class PlaygroundService:
    def __init__(
        self,
        *,
        db: Session,
        user: User,
        settings: Settings,
        embedding_provider: EmbeddingProvider,
        vector_store: VectorStore,
        answer_provider: Optional[AnswerProvider] = None,
        judge_provider: Optional[LLMJudgeProvider] = None,
    ) -> None:
        self.db = db
        self.user = user
        self.settings = settings
        self.embedding_provider = embedding_provider
        self.vector_store = vector_store
        self.answer_provider = answer_provider
        self.judge_provider = judge_provider

    async def ingest_document(
        self,
        *,
        filename: str,
        content: bytes,
        content_type: Optional[str],
    ) -> PlaygroundDocumentUploadResponse:
        if not filename:
            raise BadRequestError("Uploaded file must have a filename.")
        if not content:
            raise BadRequestError("Uploaded file is empty.")

        try:
            document = DocumentParser().parse(
                filename=filename,
                content=content,
                content_type=content_type,
            )
        except ValueError as exc:
            raise BadRequestError(str(exc)) from exc

        chunker = TokenAwareChunker(
            max_tokens=self.settings.playground_chunk_tokens,
            overlap_tokens=self.settings.playground_chunk_overlap_tokens,
        )
        chunks = chunker.chunk(document)
        if not chunks:
            raise BadRequestError("Document did not contain extractable text.")

        document_id = str(uuid.uuid4())
        embeddings = await self.embedding_provider.embed_texts([chunk.content for chunk in chunks])
        payloads = []
        for chunk in chunks:
            chunk_id = "%s_%s" % (document_id, chunk.chunk_id)
            metadata = {
                **chunk.metadata,
                "document_id": document_id,
                "original_chunk_id": chunk.chunk_id,
            }
            payloads.append(
                {
                    "user_id": self.user.id,
                    "document_id": document_id,
                    "chunk_id": chunk_id,
                    "content": chunk.content,
                    "source": chunk.source,
                    "metadata": metadata,
                }
            )

        await self.vector_store.upsert(vectors=embeddings, payloads=payloads)
        return PlaygroundDocumentUploadResponse(
            document_id=document_id,
            filename=document.filename,
            chunk_count=len(chunks),
        )

    async def query(self, request: PlaygroundQueryRequest) -> PlaygroundQueryResponse:
        result = await self._run_strategy(
            query=request.query,
            top_k=request.top_k,
            strategy_name=STRATEGY_DENSE_TOP_K,
            project=request.project,
            metadata=request.metadata,
            mode="playground",
            query_vector=None,
        )
        return PlaygroundQueryResponse(
            answer=result.answer,
            trace_id=result.trace_id,
            retrieved_chunks=result.retrieved_chunks,
            citations=result.citations,
            evaluation=result.evaluation,
        )

    async def compare(self, request: PlaygroundCompareRequest) -> PlaygroundCompareResponse:
        strategies = [strategy.value for strategy in request.strategies]
        if not strategies:
            raise BadRequestError("At least one retrieval strategy is required.")

        query_vector = (await self.embedding_provider.embed_texts([request.query]))[0]
        results = []
        for strategy_name in strategies:
            results.append(
                await self._run_strategy(
                    query=request.query,
                    top_k=request.top_k,
                    strategy_name=strategy_name,
                    project=request.project,
                    metadata=request.metadata,
                    mode="playground_compare",
                    query_vector=query_vector,
                )
            )

        return PlaygroundCompareResponse(query=request.query, results=results)

    async def _run_strategy(
        self,
        *,
        query: str,
        top_k: int,
        strategy_name: str,
        project: Optional[str],
        metadata: Dict[str, Any],
        mode: str,
        query_vector: Optional[List[float]],
    ) -> PlaygroundComparisonResult:
        if self.answer_provider is None or self.judge_provider is None:
            raise RuntimeError("Playground strategy runs require answer and judge providers.")

        started_at = time.perf_counter()
        if query_vector is None:
            query_vector = (await self.embedding_provider.embed_texts([query]))[0]

        try:
            strategy = get_retrieval_strategy(strategy_name)
        except ValueError as exc:
            raise BadRequestError(str(exc)) from exc

        retrieved = await strategy.retrieve(
            vector_store=self.vector_store,
            context=RetrievalRequestContext(
                query=query,
                query_vector=query_vector,
                top_k=top_k,
                filters={"user_id": self.user.id},
            ),
        )
        chunk_payloads = [self._record_to_chunk_payload(record) for record in retrieved]
        answer = await self.answer_provider.generate_answer(
            query=query,
            chunks=[self._chunk_payload_to_provider_dict(chunk) for chunk in chunk_payloads],
        )

        answer_text = answer.answer or "I do not have enough indexed context to answer this question."
        trace_service = TraceService(self.db, self.user)
        trace = self._create_trace_for_strategy(
            trace_service=trace_service,
            query=query,
            project=project,
            metadata=metadata,
            mode=mode,
            strategy_name=strategy_name,
            chunk_payloads=chunk_payloads,
            answer=answer,
            answer_text=answer_text,
            latency_ms=round((time.perf_counter() - started_at) * 1000, 2),
        )

        citations = self._citation_payloads(answer, chunk_payloads)
        trace_service.log_citations(trace.trace_id, CitationsRequest(citations=citations))
        evaluation = await trace_service.evaluate_trace(trace.trace_id, self.judge_provider)
        latency_ms = round((time.perf_counter() - started_at) * 1000, 2)

        return PlaygroundComparisonResult(
            strategy=RetrievalStrategyName(strategy_name),
            answer=answer_text,
            trace_id=trace.trace_id,
            retrieved_chunks=[self._record_to_response_chunk(record) for record in retrieved],
            citations=[
                {
                    "claim": citation.claim,
                    "source_chunk_id": citation.source_chunk_id,
                }
                for citation in citations
            ],
            metrics=PlaygroundComparisonMetrics(
                citation_support=self._citation_support(evaluation.citation_checks),
                unsupported_claim_rate=self._unsupported_claim_rate(evaluation.citation_checks),
                failure_type=evaluation.failure.failure_type.value,
                token_usage=answer.usage,
                latency_ms=latency_ms,
            ),
            evaluation=evaluation,
        )

    def _create_trace_for_strategy(
        self,
        *,
        trace_service: TraceService,
        query: str,
        project: Optional[str],
        metadata: Dict[str, Any],
        mode: str,
        strategy_name: str,
        chunk_payloads: List[ChunkPayload],
        answer: GeneratedAnswer,
        answer_text: str,
        latency_ms: float,
    ):
        trace_metadata = {
            **metadata,
            "mode": mode,
            "retrieval_strategy": strategy_name,
            "retrieved_count": len(chunk_payloads),
        }
        trace = trace_service.start_trace(
            TraceStartRequest(
                project=project or self.settings.playground_project,
                query=query,
                metadata=trace_metadata,
            )
        )
        trace_service.log_retrieval(
            trace.trace_id,
            RetrievalRequest(
                retriever_name="contexttrace-playground-%s" % strategy_name,
                chunks=chunk_payloads,
                metadata={
                    "vector_store": self.settings.playground_vector_store,
                    "strategy": strategy_name,
                },
            ),
        )
        trace_service.log_context(
            trace.trace_id,
            ContextRequest(
                chunks=chunk_payloads,
                metadata={"selection": "top_k", "strategy": strategy_name},
            ),
        )
        trace_service.log_answer(
            trace.trace_id,
            AnswerRequest(
                answer=answer_text,
                model=answer.model,
                usage=answer.usage,
                metadata={**answer.metadata, "latency_ms": latency_ms},
            ),
        )
        return trace

    def _record_to_chunk_payload(self, record: VectorRecord) -> ChunkPayload:
        return ChunkPayload(
            chunk_id=record.chunk_id,
            content=record.content,
            source=record.source,
            metadata=record.metadata,
            relevance_score=record.score,
        )

    def _record_to_response_chunk(self, record: VectorRecord) -> PlaygroundChunk:
        return PlaygroundChunk(
            chunk_id=record.chunk_id,
            content=record.content,
            source=record.source,
            score=record.score,
            metadata=record.metadata,
        )

    def _chunk_payload_to_provider_dict(self, chunk: ChunkPayload) -> Dict[str, Any]:
        return {
            "chunk_id": chunk.chunk_id,
            "content": chunk.content,
            "source": chunk.source,
            "metadata": chunk.metadata,
            "relevance_score": chunk.relevance_score,
        }

    def _citation_payloads(
        self,
        answer: GeneratedAnswer,
        chunks: List[ChunkPayload],
    ) -> List[CitationPayload]:
        valid_chunk_ids = {chunk.chunk_id for chunk in chunks if chunk.chunk_id}
        citations: List[CitationPayload] = []
        for item in answer.citations:
            if not isinstance(item, dict):
                continue
            claim = str(item.get("claim") or "").strip()
            source_chunk_id = str(item.get("source_chunk_id") or "").strip()
            if not claim or source_chunk_id not in valid_chunk_ids:
                continue
            citations.append(CitationPayload(claim=claim, source_chunk_id=source_chunk_id))
        return citations

    def _citation_support(self, citation_checks: list) -> float:
        if not citation_checks:
            return 0.0
        return round(
            sum(check.support_score for check in citation_checks) / len(citation_checks),
            3,
        )

    def _unsupported_claim_rate(self, citation_checks: list) -> float:
        if not citation_checks:
            return 1.0
        unsupported = [
            check
            for check in citation_checks
            if check.verdict.value in {"unsupported", "contradicted", "not_enough_info"}
        ]
        return round(len(unsupported) / len(citation_checks), 3)
