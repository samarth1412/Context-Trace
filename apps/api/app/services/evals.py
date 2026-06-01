from __future__ import annotations

from typing import Dict, List

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import EvalQuestion, EvalSet, FailureReport, Project, Trace, User
from app.models.enums import FailureType, Severity
from app.schemas import (
    EvalQuestionRead,
    EvalQuestionsRequest,
    EvalQuestionsResponse,
    EvalSetCreateRequest,
    EvalSetResponse,
    EvalSetSummary,
    WorstTrace,
)
from app.services.errors import NotFoundError
from app.services.reliability_scorer import ReliabilityScorer


class EvalSetService:
    def __init__(self, db: Session, user: User) -> None:
        self.db = db
        self.user = user

    def create_eval_set(self, request: EvalSetCreateRequest) -> EvalSetResponse:
        eval_set = self.db.scalar(
            select(EvalSet).where(
                EvalSet.user_id == self.user.id,
                EvalSet.name == request.name,
            )
        )
        if eval_set is None:
            eval_set = EvalSet(
                user_id=self.user.id,
                name=request.name,
                eval_metadata=request.metadata,
            )
            self.db.add(eval_set)
            self.db.commit()
            self.db.refresh(eval_set)

        return self._eval_set_response(eval_set)

    def add_questions(
        self,
        eval_set_id: str,
        request: EvalQuestionsRequest,
    ) -> EvalQuestionsResponse:
        eval_set = self._get_eval_set(eval_set_id)
        start_position = len(eval_set.questions)
        created: List[EvalQuestion] = []

        for offset, question in enumerate(request.questions):
            if question.trace_id:
                self._get_owned_trace(question.trace_id)

            eval_question = EvalQuestion(
                eval_set_id=eval_set.id,
                trace_id=question.trace_id,
                question=question.question,
                expected_answer=question.expected_answer,
                question_metadata=question.metadata,
                position=start_position + offset,
            )
            self.db.add(eval_question)
            created.append(eval_question)

        self.db.commit()
        for question in created:
            self.db.refresh(question)

        return EvalQuestionsResponse(
            eval_set_id=eval_set.id,
            accepted=len(created),
            questions=[self._question_read(question) for question in created],
        )

    def run_existing_traces(self, eval_set_id: str) -> EvalSetSummary:
        return self.get_summary(eval_set_id)

    def get_summary(self, eval_set_id: str) -> EvalSetSummary:
        eval_set = self._get_eval_set(eval_set_id)
        return aggregate_eval_set(eval_set)

    def _get_eval_set(self, eval_set_id: str) -> EvalSet:
        eval_set = self.db.scalar(
            select(EvalSet).where(
                EvalSet.id == eval_set_id,
                EvalSet.user_id == self.user.id,
            )
        )
        if eval_set is None:
            raise NotFoundError("Eval set not found.")
        return eval_set

    def _get_owned_trace(self, trace_id: str) -> Trace:
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

    def _eval_set_response(self, eval_set: EvalSet) -> EvalSetResponse:
        return EvalSetResponse(
            eval_set_id=eval_set.id,
            name=eval_set.name,
            metadata=eval_set.eval_metadata or {},
            created_at=eval_set.created_at,
        )

    def _question_read(self, question: EvalQuestion) -> EvalQuestionRead:
        return EvalQuestionRead(
            id=question.id,
            question=question.question,
            trace_id=question.trace_id,
            expected_answer=question.expected_answer,
            metadata=question.question_metadata or {},
            position=question.position,
        )


def aggregate_eval_set(eval_set: EvalSet) -> EvalSetSummary:
    total_questions = len(eval_set.questions)
    linked_questions = [question for question in eval_set.questions if question.trace_id]
    evaluated_questions = [
        question
        for question in linked_questions
        if question.trace is not None and question.trace.failure_report is not None
    ]

    failure_distribution: Dict[str, int] = {}
    citation_support_values: List[float] = []
    unsupported_values: List[float] = []
    worst_candidates: List[WorstTrace] = []
    failure_count = 0

    for question in evaluated_questions:
        trace = question.trace
        report = trace.failure_report if trace else None
        if report is None:
            continue

        failure_distribution[report.failure_type] = (
            failure_distribution.get(report.failure_type, 0) + 1
        )
        if report.failure_type != FailureType.NO_FAILURE_DETECTED.value:
            failure_count += 1
        citation_support = _score(report, "citation_support")
        unsupported_claim_rate = _score(report, "unsupported_claim_rate")
        citation_support_values.append(citation_support)
        unsupported_values.append(unsupported_claim_rate)
        worst_candidates.append(
            WorstTrace(
                trace_id=trace.id,
                question_id=question.id,
                question=question.question,
                failure_type=report.failure_type,
                severity=report.severity,
                citation_support=citation_support,
                unsupported_claim_rate=unsupported_claim_rate,
                root_cause=report.root_cause,
            )
        )

    worst_candidates.sort(key=_worst_trace_sort_key)

    avg_citation_support = _average(citation_support_values)
    unsupported_claim_rate = _average(unsupported_values)
    failure_rate = _average_rate(failure_count, len(evaluated_questions))

    return EvalSetSummary(
        eval_set_id=eval_set.id,
        name=eval_set.name,
        total_questions=total_questions,
        linked_trace_count=len(linked_questions),
        evaluated_trace_count=len(evaluated_questions),
        unevaluated_trace_count=len(linked_questions) - len(evaluated_questions),
        avg_citation_support=avg_citation_support,
        unsupported_claim_rate=unsupported_claim_rate,
        failure_rate=failure_rate,
        reliability=ReliabilityScorer().score(
            citation_support=avg_citation_support,
            unsupported_claim_rate=unsupported_claim_rate,
            failure_rate=failure_rate,
        ).to_dict(),
        failure_type_distribution=failure_distribution,
        worst_traces=worst_candidates[:5],
    )


def _score(report: FailureReport, key: str) -> float:
    value = (report.scores or {}).get(key, 0.0)
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return 0.0


def _average(values: List[float]) -> float:
    if not values:
        return 0.0
    return round(sum(values) / len(values), 3)


def _average_rate(count: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return round(count / total, 3)


def _worst_trace_sort_key(trace: WorstTrace) -> tuple:
    severity_rank = {
        Severity.HIGH.value: 0,
        Severity.MEDIUM.value: 1,
        Severity.LOW.value: 2,
        Severity.NONE.value: 3,
    }
    failure_rank = 1 if trace.failure_type == FailureType.NO_FAILURE_DETECTED else 0
    return (
        failure_rank,
        severity_rank.get(trace.severity.value, 4),
        -trace.unsupported_claim_rate,
        trace.citation_support,
    )
