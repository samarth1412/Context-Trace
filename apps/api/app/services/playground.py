from __future__ import annotations

import time
import uuid
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.judge import LLMJudgeProvider
from app.models import User
from app.playground.documents import DocumentParser, TokenAwareChunker
from app.playground.policy import (
    POLICY_ABSTAIN_LOW_CONFIDENCE,
    POLICY_COMPRESSED_CONTEXT,
    PolicyDecision,
    PolicySelector,
    QueryClassification,
    QueryClassifier,
)
from app.playground.providers import AnswerProvider, EmbeddingProvider, GeneratedAnswer
from app.playground.retrieval import (
    STRATEGY_CONTEXTTRACE_ADAPTIVE,
    STRATEGY_DENSE_TOP_K,
    RetrievalRequestContext,
    get_retrieval_strategy,
)
from app.playground.samples import get_sample, list_samples
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
    PlaygroundChunkPreview,
    PlaygroundComparisonMetrics,
    PlaygroundComparisonResult,
    PlaygroundDocumentUploadResponse,
    PlaygroundQueryRequest,
    PlaygroundQueryResponse,
    PlaygroundSampleDataset,
    PlaygroundSampleLoadResponse,
    PlaygroundSamplesResponse,
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

        return await self._ingest_parsed_document(document=document)

    async def list_sample_datasets(self) -> PlaygroundSamplesResponse:
        return PlaygroundSamplesResponse(
            samples=[
                PlaygroundSampleDataset(
                    sample_id=sample.sample_id,
                    name=sample.name,
                    description=sample.description,
                    suggested_queries=sample.suggested_queries,
                )
                for sample in list_samples()
            ]
        )

    async def load_sample_dataset(self, sample_id: str) -> PlaygroundSampleLoadResponse:
        try:
            sample = get_sample(sample_id)
        except ValueError as exc:
            raise BadRequestError(str(exc)) from exc

        documents = []
        for sample_document in sample.documents:
            parsed = DocumentParser().parse(
                filename=sample_document.filename,
                content=sample_document.content.encode("utf-8"),
                content_type=sample_document.content_type,
            )
            parsed.metadata.update({"sample_id": sample.sample_id, "sample_name": sample.name})
            documents.append(await self._ingest_parsed_document(document=parsed))

        return PlaygroundSampleLoadResponse(
            sample_id=sample.sample_id,
            name=sample.name,
            description=sample.description,
            suggested_queries=sample.suggested_queries,
            documents=documents,
            chunk_count=sum(document.chunk_count for document in documents),
        )

    async def _ingest_parsed_document(
        self,
        *,
        document,
    ) -> PlaygroundDocumentUploadResponse:
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
        preview_chunks: List[PlaygroundChunkPreview] = []
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
            preview_chunks.append(
                PlaygroundChunkPreview(
                    chunk_id=chunk_id,
                    content=chunk.content,
                    source=chunk.source,
                    token_count=int(metadata.get("token_count") or len(chunk.content.split())),
                    metadata=metadata,
                )
            )

        await self.vector_store.upsert(vectors=embeddings, payloads=payloads)
        return PlaygroundDocumentUploadResponse(
            document_id=document_id,
            filename=document.filename,
            chunk_count=len(chunks),
            text_preview=self._preview(document.text),
            chunks=preview_chunks,
        )

    async def query(self, request: PlaygroundQueryRequest) -> PlaygroundQueryResponse:
        result = await self._run_strategy(
            query=request.query,
            top_k=request.top_k,
            strategy_name=request.strategy.value,
            project=request.project,
            metadata=request.metadata,
            mode="playground",
            query_vector=None,
            use_policy_runtime=request.strategy.value == STRATEGY_CONTEXTTRACE_ADAPTIVE,
        )
        return PlaygroundQueryResponse(
            answer=result.answer,
            trace_id=result.trace_id,
            strategy=result.strategy,
            retrieved_chunks=result.retrieved_chunks,
            selected_context=result.selected_context,
            dropped_context=result.dropped_context,
            citations=result.citations,
            metrics=result.metrics,
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
                    use_policy_runtime=False,
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
        use_policy_runtime: bool,
    ) -> PlaygroundComparisonResult:
        if self.answer_provider is None or self.judge_provider is None:
            raise RuntimeError("Playground strategy runs require answer and judge providers.")

        started_at = time.perf_counter()
        if query_vector is None:
            query_vector = (await self.embedding_provider.embed_texts([query]))[0]

        classification, policy_decision, retrieval_confidence = await self._select_policy(
            query=query,
            query_vector=query_vector,
            requested_strategy_name=strategy_name,
            use_policy_runtime=use_policy_runtime,
        )
        effective_strategy_name = policy_decision.retrieval_strategy or STRATEGY_DENSE_TOP_K
        candidate_top_k = self._candidate_top_k(top_k, policy_decision.selected_policy)

        try:
            strategy = get_retrieval_strategy(effective_strategy_name)
        except ValueError as exc:
            raise BadRequestError(str(exc)) from exc

        retrieved = await strategy.retrieve(
            vector_store=self.vector_store,
            context=RetrievalRequestContext(
                query=query,
                query_vector=query_vector,
                top_k=candidate_top_k,
                filters={"user_id": self.user.id},
            ),
        )
        selected_chunks, dropped_chunk_ids = self._select_context_chunks(
            records=retrieved,
            top_k=top_k,
            policy_decision=policy_decision,
        )
        selected_chunk_payloads = [
            self._record_to_chunk_payload(record) for record in selected_chunks
        ]
        retrieved_chunk_payloads = [self._record_to_chunk_payload(record) for record in retrieved]
        dropped_records = [record for record in retrieved if record.chunk_id in set(dropped_chunk_ids)]

        if policy_decision.selected_policy == POLICY_ABSTAIN_LOW_CONFIDENCE:
            answer = GeneratedAnswer(
                answer="I do not have enough retrieved evidence to answer this question reliably.",
                citations=[],
                model="context-policy-runtime",
                metadata={"provider": "context_policy_runtime"},
            )
        else:
            answer = await self.answer_provider.generate_answer(
                query=query,
                chunks=[
                    self._chunk_payload_to_provider_dict(chunk)
                    for chunk in selected_chunk_payloads
                ],
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
            effective_strategy_name=effective_strategy_name,
            retrieved_chunk_payloads=retrieved_chunk_payloads,
            selected_chunk_payloads=selected_chunk_payloads,
            answer=answer,
            answer_text=answer_text,
            latency_ms=round((time.perf_counter() - started_at) * 1000, 2),
            classification=classification,
            policy_decision=policy_decision,
            retrieval_confidence=retrieval_confidence,
            dropped_chunk_ids=dropped_chunk_ids,
        )

        citations = self._citation_payloads(answer, selected_chunk_payloads)
        trace_service.log_citations(trace.trace_id, CitationsRequest(citations=citations))
        evaluation = await trace_service.evaluate_trace(trace.trace_id, self.judge_provider)
        latency_ms = round((time.perf_counter() - started_at) * 1000, 2)

        return PlaygroundComparisonResult(
            strategy=RetrievalStrategyName(strategy_name),
            answer=answer_text,
            trace_id=trace.trace_id,
            retrieved_chunks=[self._record_to_response_chunk(record) for record in retrieved],
            selected_context=[
                self._chunk_payload_to_response_chunk(chunk) for chunk in selected_chunk_payloads
            ],
            dropped_context=[self._record_to_response_chunk(record) for record in dropped_records],
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
                estimated_cost_usd=self._estimated_cost(answer.usage),
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
        effective_strategy_name: str,
        retrieved_chunk_payloads: List[ChunkPayload],
        selected_chunk_payloads: List[ChunkPayload],
        answer: GeneratedAnswer,
        answer_text: str,
        latency_ms: float,
        classification: QueryClassification,
        policy_decision: PolicyDecision,
        retrieval_confidence: float,
        dropped_chunk_ids: List[str],
    ):
        selected_chunk_ids = [
            chunk.chunk_id for chunk in selected_chunk_payloads if chunk.chunk_id is not None
        ]
        trace_metadata = {
            **metadata,
            "mode": mode,
            "retrieval_strategy": strategy_name,
            "effective_retrieval_strategy": effective_strategy_name,
            "retrieved_count": len(retrieved_chunk_payloads),
            "context_policy": {
                "query_class": classification.query_class,
                "query_class_reason": classification.reason,
                "selected_policy": policy_decision.selected_policy,
                "reason": policy_decision.reason,
                "retrieval_confidence": retrieval_confidence,
                "retrieval_strategy": effective_strategy_name,
                "token_budget": policy_decision.token_budget,
                "selected_chunk_ids": selected_chunk_ids,
                "dropped_chunk_ids": dropped_chunk_ids,
            },
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
                chunks=retrieved_chunk_payloads,
                metadata={
                    "vector_store": self.settings.playground_vector_store,
                    "strategy": strategy_name,
                    "effective_strategy": effective_strategy_name,
                },
            ),
        )
        trace_service.log_context(
            trace.trace_id,
            ContextRequest(
                chunks=selected_chunk_payloads,
                metadata={
                    "selection": "context_policy",
                    "strategy": strategy_name,
                    "policy": policy_decision.selected_policy,
                },
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

    async def _select_policy(
        self,
        *,
        query: str,
        query_vector: List[float],
        requested_strategy_name: str,
        use_policy_runtime: bool,
    ) -> tuple:
        if not use_policy_runtime:
            return (
                QueryClassification(
                    query_class="manual_strategy",
                    reason="The retrieval strategy was selected explicitly for comparison.",
                ),
                PolicyDecision(
                    selected_policy=requested_strategy_name,
                    retrieval_strategy=requested_strategy_name,
                    reason="Manual retrieval strategy comparison.",
                    token_budget=1600,
                ),
                1.0,
            )

        initial_records = await get_retrieval_strategy(STRATEGY_DENSE_TOP_K).retrieve(
            vector_store=self.vector_store,
            context=RetrievalRequestContext(
                query=query,
                query_vector=query_vector,
                top_k=5,
                filters={"user_id": self.user.id},
            ),
        )
        retrieval_confidence = self._retrieval_confidence(initial_records, query=query)
        classification = QueryClassifier().classify(query)
        policy_decision = PolicySelector().select(
            classification=classification,
            retrieval_confidence=retrieval_confidence,
        )
        return classification, policy_decision, retrieval_confidence

    def _retrieval_confidence(self, records: List[VectorRecord], *, query: str) -> float:
        if not records:
            return 0.0
        best_score = max(record.score for record in records)
        query_terms = self._normalized_terms(query)
        lexical_confidence = 0.0
        if query_terms:
            lexical_confidence = max(
                (
                    len(query_terms & self._normalized_terms(record.content))
                    / max(len(query_terms), 1)
                    for record in records
                ),
                default=0.0,
            )
        return round(max(0.0, min(max(best_score, lexical_confidence), 1.0)), 3)

    def _normalized_terms(self, text: str) -> set:
        return {
            token.rstrip("s")
            for token in text.lower().replace("?", " ").replace(".", " ").split()
            if len(token.rstrip("s")) > 2
        }

    def _candidate_top_k(self, top_k: int, selected_policy: str) -> int:
        if selected_policy == POLICY_COMPRESSED_CONTEXT:
            return max(top_k * 3, top_k + 6)
        if selected_policy == POLICY_ABSTAIN_LOW_CONFIDENCE:
            return max(top_k, 3)
        return max(top_k * 2, top_k + 3)

    def _select_context_chunks(
        self,
        *,
        records: List[VectorRecord],
        top_k: int,
        policy_decision: PolicyDecision,
    ) -> tuple:
        if policy_decision.selected_policy == POLICY_ABSTAIN_LOW_CONFIDENCE:
            return [], [record.chunk_id for record in records]

        if policy_decision.selected_policy == POLICY_COMPRESSED_CONTEXT:
            selected = self._compressed_records(
                records[: max(top_k * 2, top_k)],
                token_budget=policy_decision.token_budget,
            )
            selected_original_ids = {
                record.metadata.get("original_chunk_id", record.chunk_id) for record in selected
            }
            dropped = [
                record.chunk_id for record in records if record.chunk_id not in selected_original_ids
            ]
            return selected, dropped

        selected = records[:top_k]
        dropped = [record.chunk_id for record in records[top_k:]]
        return selected, dropped

    def _compressed_records(
        self,
        records: List[VectorRecord],
        *,
        token_budget: int,
    ) -> List[VectorRecord]:
        if not records or token_budget <= 0:
            return []
        tokens_per_chunk = max(32, token_budget // len(records))
        compressed = []
        for record in records:
            tokens = record.content.split()
            content = " ".join(tokens[:tokens_per_chunk])
            metadata = {
                **record.metadata,
                "compressed": True,
                "original_chunk_id": record.chunk_id,
                "original_token_count": len(tokens),
                "token_budget": tokens_per_chunk,
            }
            compressed.append(
                VectorRecord(
                    chunk_id="%s_compressed" % record.chunk_id,
                    content=content,
                    source=record.source,
                    metadata=metadata,
                    score=record.score,
                )
            )
        return compressed

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

    def _chunk_payload_to_response_chunk(self, chunk: ChunkPayload) -> PlaygroundChunk:
        return PlaygroundChunk(
            chunk_id=chunk.chunk_id or "unknown_chunk",
            content=chunk.content,
            source=chunk.source,
            score=chunk.relevance_score or 0.0,
            metadata=chunk.metadata,
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

    def _estimated_cost(self, usage: Dict[str, Any]) -> float:
        total_tokens = usage.get("total_tokens")
        if not isinstance(total_tokens, (int, float)):
            total_tokens = 0
        return round(float(total_tokens) / 1000 * 0.0008, 6)

    def _preview(self, text: str, *, limit: int = 520) -> str:
        normalized = " ".join(text.split())
        if len(normalized) <= limit:
            return normalized
        return normalized[: limit - 3].rstrip() + "..."
