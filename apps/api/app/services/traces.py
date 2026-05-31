from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import (
    Answer,
    AgentEvent,
    Chunk,
    CitationCheck,
    FailureReport,
    Project,
    RetrievalEvent,
    SupportStatus,
    Trace,
    User,
)
from app.schemas import (
    AnswerRead,
    AnswerRequest,
    AgentEventRead,
    AgentEventRequest,
    AgentEventResponse,
    AgentEventsResponse,
    ChunkPayload,
    ChunkRead,
    CitationCheckRead,
    CitationsRequest,
    ContextRequest,
    EvaluatedCitationCheck,
    EvaluationResponse,
    FailurePayload,
    RetrievalRequest,
    TraceEventResponse,
    TraceRead,
    TraceStartRequest,
    TraceStartResponse,
)
from app.judge import LLMJudgeProvider
from app.models import CitationVerdict, FailureType, Severity
from app.services.citation_verifier import CitationVerificationResult, CitationVerifier
from app.services.errors import InvalidTraceState, NotFoundError
from app.services.failure_analyzer import FailureAnalyzer


class TraceService:
    def __init__(self, db: Session, user: User) -> None:
        self.db = db
        self.user = user

    def start_trace(self, request: TraceStartRequest) -> TraceStartResponse:
        project = self.db.scalar(
            select(Project).where(
                Project.user_id == self.user.id,
                Project.name == request.project,
            )
        )
        if project is None:
            project = Project(user_id=self.user.id, name=request.project)
            self.db.add(project)
            self.db.flush()

        trace = Trace(
            project_id=project.id,
            query=request.query,
            trace_metadata=request.metadata,
        )
        self.db.add(trace)
        self.db.commit()
        self.db.refresh(trace)
        return TraceStartResponse(trace_id=trace.id, project_id=project.id)

    def log_retrieval(self, trace_id: str, request: RetrievalRequest) -> TraceEventResponse:
        trace = self._get_trace(trace_id)
        event = RetrievalEvent(
            trace_id=trace.id,
            retriever_name=request.retriever_name,
            event_metadata=request.metadata,
        )
        self.db.add(event)

        for position, chunk in enumerate(request.chunks):
            self._upsert_chunk(trace, chunk, position=position, selected=False)

        trace.status = "retrieval_logged"
        self.db.commit()
        return TraceEventResponse(trace_id=trace.id, accepted=len(request.chunks))

    def log_context(self, trace_id: str, request: ContextRequest) -> TraceEventResponse:
        trace = self._get_trace(trace_id)
        accepted = 0

        if request.chunk_ids:
            chunks = self.db.scalars(
                select(Chunk).where(
                    Chunk.trace_id == trace.id,
                    Chunk.external_id.in_(request.chunk_ids),
                )
            ).all()
            for chunk in chunks:
                chunk.selected = True
            accepted += len(chunks)

        if request.chunks:
            start_position = len(trace.chunks)
            for offset, chunk in enumerate(request.chunks):
                self._upsert_chunk(
                    trace,
                    chunk,
                    position=start_position + offset,
                    selected=True,
                )
            accepted += len(request.chunks)

        trace.status = "context_logged"
        self.db.commit()
        return TraceEventResponse(trace_id=trace.id, accepted=accepted)

    def log_answer(self, trace_id: str, request: AnswerRequest) -> TraceEventResponse:
        trace = self._get_trace(trace_id)
        if trace.answer is None:
            trace.answer = Answer(trace_id=trace.id, content=request.answer)

        trace.answer.content = request.answer
        trace.answer.model = request.model
        trace.answer.usage = request.usage
        trace.answer.answer_metadata = request.metadata
        trace.status = "answer_logged"
        self.db.commit()
        return TraceEventResponse(trace_id=trace.id, accepted=1)

    def log_citations(self, trace_id: str, request: CitationsRequest) -> TraceEventResponse:
        trace = self._get_trace(trace_id)
        self.db.execute(delete(CitationCheck).where(CitationCheck.trace_id == trace.id))
        for citation in request.citations:
            self.db.add(
                CitationCheck(
                    trace_id=trace.id,
                    claim=citation.claim,
                    source_chunk_id=citation.source_chunk_id,
                    support_status=SupportStatus.PENDING.value,
                    citation_metadata=citation.metadata,
                )
            )

        trace.status = "citations_logged"
        self.db.commit()
        return TraceEventResponse(trace_id=trace.id, accepted=len(request.citations))

    def get_trace(self, trace_id: str) -> TraceRead:
        return self._trace_read(self._get_trace(trace_id))

    def log_agent_event(self, trace_id: str, request: AgentEventRequest) -> AgentEventResponse:
        trace = self._get_trace(trace_id)
        event = AgentEvent(
            trace_id=trace.id,
            event_type=request.event_type.value,
            name=request.name,
            input_json=request.input_json,
            output_json=request.output_json,
            metadata_json=request.metadata_json,
            latency_ms=request.latency_ms,
            error_message=request.error_message,
        )
        self.db.add(event)
        trace.status = "agent_event_logged"
        self.db.commit()
        self.db.refresh(event)
        return AgentEventResponse(trace_id=trace.id, event_id=event.id, accepted=1)

    def list_agent_events(self, trace_id: str) -> AgentEventsResponse:
        trace = self._get_trace(trace_id)
        events = self.db.scalars(
            select(AgentEvent)
            .where(AgentEvent.trace_id == trace.id)
            .order_by(AgentEvent.created_at)
        ).all()
        return AgentEventsResponse(
            trace_id=trace.id,
            events=[self._agent_event_read(event) for event in events],
        )

    async def evaluate_trace(
        self,
        trace_id: str,
        judge_provider: LLMJudgeProvider,
    ) -> EvaluationResponse:
        trace = self._get_trace(trace_id)
        if trace.answer is None:
            raise InvalidTraceState("Cannot evaluate a trace before an answer is logged.")

        citation_verifier = CitationVerifier(judge_provider)
        failure_analyzer = FailureAnalyzer(judge_provider)
        chunk_by_external_id = {chunk.external_id: chunk for chunk in trace.chunks}

        evaluated_checks = []
        for check in trace.citation_checks:
            source_chunk = chunk_by_external_id.get(check.source_chunk_id)
            if source_chunk is None:
                result = CitationVerificationResult(
                    verdict=CitationVerdict.NOT_ENOUGH_INFO,
                    support_score=0.0,
                    reason="The cited source chunk was not found in this trace.",
                )
            else:
                result = await citation_verifier.verify(
                    claim=check.claim,
                    source_chunk_text=source_chunk.content,
                )

            check.support_status = result.verdict.value
            check.support_score = result.support_score
            check.rationale = result.reason
            evaluated_checks.append(
                {
                    "claim": check.claim,
                    "source_chunk_id": check.source_chunk_id,
                    "verdict": result.verdict.value,
                    "support_score": result.support_score,
                    "reason": result.reason,
                }
            )

        chunks = [self._chunk_to_dict(chunk) for chunk in trace.chunks]
        selected_context = [
            self._chunk_to_dict(chunk) for chunk in trace.chunks if chunk.selected
        ]
        failure = await failure_analyzer.analyze(
            query=trace.query,
            chunks=chunks,
            selected_context=selected_context,
            answer=trace.answer.content,
            citation_checks=evaluated_checks,
        )

        scores = self._score_summary(evaluated_checks)
        if trace.failure_report is None:
            trace.failure_report = FailureReport(
                trace_id=trace.id,
                failure_type=failure.failure_type.value,
                severity=failure.severity.value,
                root_cause=failure.root_cause,
                suggested_fix=failure.suggested_fix,
                scores=scores,
                report_metadata={},
            )
        else:
            trace.failure_report.failure_type = failure.failure_type.value
            trace.failure_report.severity = failure.severity.value
            trace.failure_report.root_cause = failure.root_cause
            trace.failure_report.suggested_fix = failure.suggested_fix
            trace.failure_report.scores = scores
            trace.failure_report.report_metadata = {}

        trace.status = "evaluated"
        self.db.commit()
        self.db.refresh(trace)
        return self._evaluation_response(trace)

    def _get_trace(self, trace_id: str) -> Trace:
        trace = self.db.scalar(
            select(Trace)
            .join(Project)
            .where(
                Trace.id == trace_id,
                Project.user_id == self.user.id,
            )
        )
        if trace is None:
            raise NotFoundError("Trace not found.")
        return trace

    def _upsert_chunk(
        self,
        trace: Trace,
        chunk: ChunkPayload,
        *,
        position: int,
        selected: bool,
    ) -> Chunk:
        external_id = chunk.chunk_id or f"chunk_{position}"
        existing = self.db.scalar(
            select(Chunk).where(
                Chunk.trace_id == trace.id,
                Chunk.external_id == external_id,
            )
        )
        if existing is None:
            existing = Chunk(
                trace_id=trace.id,
                external_id=external_id,
                position=position,
            )
            self.db.add(existing)

        existing.content = chunk.content
        existing.source = chunk.source
        existing.chunk_metadata = chunk.metadata
        existing.relevance_score = chunk.relevance_score
        existing.selected = existing.selected or selected
        return existing

    def _trace_read(self, trace: Trace) -> TraceRead:
        return TraceRead(
            id=trace.id,
            project_id=trace.project_id,
            project=trace.project.name,
            query=trace.query,
            metadata=trace.trace_metadata or {},
            status=trace.status,
            chunks=[
                ChunkRead(
                    id=chunk.id,
                    chunk_id=chunk.external_id,
                    content=chunk.content,
                    source=chunk.source,
                    metadata=chunk.chunk_metadata or {},
                    relevance_score=chunk.relevance_score,
                    position=chunk.position,
                    selected=chunk.selected,
                )
                for chunk in trace.chunks
            ],
            answer=(
                AnswerRead(
                    id=trace.answer.id,
                    answer=trace.answer.content,
                    model=trace.answer.model,
                    usage=trace.answer.usage or {},
                    metadata=trace.answer.answer_metadata or {},
                )
                if trace.answer
                else None
            ),
            citation_checks=[
                CitationCheckRead(
                    id=check.id,
                    claim=check.claim,
                    source_chunk_id=check.source_chunk_id,
                    support_status=check.support_status,
                    support_score=check.support_score,
                    rationale=check.rationale,
                )
                for check in trace.citation_checks
            ],
            agent_events=[self._agent_event_read(event) for event in trace.agent_events],
            evaluation=self._evaluation_response(trace) if trace.failure_report else None,
            created_at=trace.created_at,
            updated_at=trace.updated_at,
        )

    def _agent_event_read(self, event: AgentEvent) -> AgentEventRead:
        return AgentEventRead(
            id=event.id,
            trace_id=event.trace_id,
            event_type=event.event_type,
            name=event.name,
            input_json=event.input_json,
            output_json=event.output_json,
            metadata_json=event.metadata_json or {},
            latency_ms=event.latency_ms,
            error_message=event.error_message,
            created_at=event.created_at,
        )

    def _evaluation_response(self, trace: Trace) -> EvaluationResponse:
        report = trace.failure_report
        if report is None:
            return EvaluationResponse(
                citation_checks=[],
                failure=FailurePayload(
                    failure_type=FailureType.UNKNOWN,
                    severity=Severity.MEDIUM,
                    root_cause="Trace has not been evaluated.",
                    suggested_fix="Run evaluation for this trace.",
                ),
            )

        return EvaluationResponse(
            citation_checks=[
                EvaluatedCitationCheck(
                    claim=check.claim,
                    source_chunk_id=check.source_chunk_id,
                    verdict=check.support_status,
                    support_score=check.support_score or 0.0,
                    reason=check.rationale or "",
                )
                for check in trace.citation_checks
                if check.support_status != SupportStatus.PENDING.value
            ],
            failure=FailurePayload(
                failure_type=report.failure_type,
                severity=report.severity,
                root_cause=report.root_cause,
                suggested_fix=report.suggested_fix,
            ),
        )

    def _chunk_to_dict(self, chunk: Chunk) -> dict:
        return {
            "chunk_id": chunk.external_id,
            "content": chunk.content,
            "source": chunk.source,
            "metadata": chunk.chunk_metadata or {},
            "relevance_score": chunk.relevance_score,
            "selected": chunk.selected,
        }

    def _score_summary(self, evaluated_checks: list) -> dict:
        if not evaluated_checks:
            return {
                "citation_support": 0.0,
                "unsupported_claim_rate": 1.0,
            }
        support_scores = [check["support_score"] for check in evaluated_checks]
        unsupported = [
            check
            for check in evaluated_checks
            if check["verdict"]
            in {
                CitationVerdict.UNSUPPORTED.value,
                CitationVerdict.CONTRADICTED.value,
                CitationVerdict.NOT_ENOUGH_INFO.value,
            }
        ]
        return {
            "citation_support": round(sum(support_scores) / len(support_scores), 3),
            "unsupported_claim_rate": round(len(unsupported) / len(evaluated_checks), 3),
        }
