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
from app.playground.vector_store import VectorRecord, VectorStore
from app.schemas import (
    AnswerRequest,
    ChunkPayload,
    CitationPayload,
    CitationsRequest,
    ContextRequest,
    PlaygroundChunk,
    PlaygroundDocumentUploadResponse,
    PlaygroundQueryRequest,
    PlaygroundQueryResponse,
    RetrievalRequest,
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
        if self.answer_provider is None or self.judge_provider is None:
            raise RuntimeError("Playground query requires answer and judge providers.")

        started_at = time.perf_counter()
        query_embedding = (await self.embedding_provider.embed_texts([request.query]))[0]
        retrieved = await self.vector_store.search(
            vector=query_embedding,
            limit=request.top_k,
            filters={"user_id": self.user.id},
        )
        chunk_payloads = [self._record_to_chunk_payload(record) for record in retrieved]
        answer = await self.answer_provider.generate_answer(
            query=request.query,
            chunks=[self._chunk_payload_to_provider_dict(chunk) for chunk in chunk_payloads],
        )

        trace_service = TraceService(self.db, self.user)
        trace_metadata = {
            **request.metadata,
            "mode": "playground",
            "retrieved_count": len(chunk_payloads),
        }
        trace = trace_service.start_trace(
            TraceStartRequest(
                project=request.project or self.settings.playground_project,
                query=request.query,
                metadata=trace_metadata,
            )
        )

        trace_service.log_retrieval(
            trace.trace_id,
            RetrievalRequest(
                retriever_name="contexttrace-playground",
                chunks=chunk_payloads,
                metadata={"vector_store": self.settings.playground_vector_store},
            ),
        )
        trace_service.log_context(
            trace.trace_id,
            ContextRequest(chunks=chunk_payloads, metadata={"selection": "top_k"}),
        )
        answer_text = answer.answer or "I do not have enough indexed context to answer this question."
        trace_service.log_answer(
            trace.trace_id,
            AnswerRequest(
                answer=answer_text,
                model=answer.model,
                usage=answer.usage,
                metadata={
                    **answer.metadata,
                    "latency_ms": round((time.perf_counter() - started_at) * 1000, 2),
                },
            ),
        )

        citations = self._citation_payloads(answer, chunk_payloads)
        trace_service.log_citations(trace.trace_id, CitationsRequest(citations=citations))
        evaluation = await trace_service.evaluate_trace(trace.trace_id, self.judge_provider)

        return PlaygroundQueryResponse(
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
            evaluation=evaluation,
        )

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
