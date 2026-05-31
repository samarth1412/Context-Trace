from __future__ import annotations

from typing import List, Optional

from sqlalchemy import Boolean, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, new_uuid
from app.models.enums import FailureType, Severity, SupportStatus


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    email: Mapped[Optional[str]] = mapped_column(String(320), nullable=True, unique=True)
    api_key_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)

    projects: Mapped[List["Project"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    eval_sets: Mapped[List["EvalSet"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )


class Project(Base, TimestampMixin):
    __tablename__ = "projects"
    __table_args__ = (UniqueConstraint("user_id", "name", name="uq_projects_user_name"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)

    user: Mapped[User] = relationship(back_populates="projects")
    traces: Mapped[List["Trace"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )
    external_rag_endpoints: Mapped[List["ExternalRAGEndpoint"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )


class Trace(Base, TimestampMixin):
    __tablename__ = "traces"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False)
    query: Mapped[str] = mapped_column(Text, nullable=False)
    trace_metadata: Mapped[dict] = mapped_column("metadata", JSON, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="started", nullable=False)

    project: Mapped[Project] = relationship(back_populates="traces")
    retrieval_events: Mapped[List["RetrievalEvent"]] = relationship(
        back_populates="trace",
        cascade="all, delete-orphan",
    )
    chunks: Mapped[List["Chunk"]] = relationship(
        back_populates="trace",
        cascade="all, delete-orphan",
        order_by="Chunk.position",
    )
    answer: Mapped[Optional["Answer"]] = relationship(
        back_populates="trace",
        cascade="all, delete-orphan",
        uselist=False,
    )
    citation_checks: Mapped[List["CitationCheck"]] = relationship(
        back_populates="trace",
        cascade="all, delete-orphan",
    )
    failure_report: Mapped[Optional["FailureReport"]] = relationship(
        back_populates="trace",
        cascade="all, delete-orphan",
        uselist=False,
    )
    eval_questions: Mapped[List["EvalQuestion"]] = relationship(back_populates="trace")


class RetrievalEvent(Base, TimestampMixin):
    __tablename__ = "retrieval_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    trace_id: Mapped[str] = mapped_column(ForeignKey("traces.id"), nullable=False)
    retriever_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    event_metadata: Mapped[dict] = mapped_column("metadata", JSON, default=dict, nullable=False)

    trace: Mapped[Trace] = relationship(back_populates="retrieval_events")


class Chunk(Base, TimestampMixin):
    __tablename__ = "chunks"
    __table_args__ = (UniqueConstraint("trace_id", "external_id", name="uq_chunks_trace_external"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    trace_id: Mapped[str] = mapped_column(ForeignKey("traces.id"), nullable=False)
    external_id: Mapped[str] = mapped_column(String(300), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    chunk_metadata: Mapped[dict] = mapped_column("metadata", JSON, default=dict, nullable=False)
    relevance_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    selected: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    trace: Mapped[Trace] = relationship(back_populates="chunks")


class Answer(Base, TimestampMixin):
    __tablename__ = "answers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    trace_id: Mapped[str] = mapped_column(ForeignKey("traces.id"), nullable=False, unique=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    model: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    usage: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    answer_metadata: Mapped[dict] = mapped_column("metadata", JSON, default=dict, nullable=False)

    trace: Mapped[Trace] = relationship(back_populates="answer")


class CitationCheck(Base, TimestampMixin):
    __tablename__ = "citation_checks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    trace_id: Mapped[str] = mapped_column(ForeignKey("traces.id"), nullable=False)
    claim: Mapped[str] = mapped_column(Text, nullable=False)
    source_chunk_id: Mapped[str] = mapped_column(String(300), nullable=False)
    support_status: Mapped[str] = mapped_column(
        String(50),
        default=SupportStatus.PENDING.value,
        nullable=False,
    )
    support_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    rationale: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    citation_metadata: Mapped[dict] = mapped_column("metadata", JSON, default=dict, nullable=False)

    trace: Mapped[Trace] = relationship(back_populates="citation_checks")


class FailureReport(Base, TimestampMixin):
    __tablename__ = "failure_reports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    trace_id: Mapped[str] = mapped_column(ForeignKey("traces.id"), nullable=False, unique=True)
    failure_type: Mapped[str] = mapped_column(
        String(80),
        default=FailureType.UNKNOWN.value,
        nullable=False,
    )
    severity: Mapped[str] = mapped_column(
        String(50),
        default=Severity.MEDIUM.value,
        nullable=False,
    )
    root_cause: Mapped[str] = mapped_column(Text, nullable=False)
    suggested_fix: Mapped[str] = mapped_column(Text, nullable=False)
    scores: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    report_metadata: Mapped[dict] = mapped_column("metadata", JSON, default=dict, nullable=False)

    trace: Mapped[Trace] = relationship(back_populates="failure_report")


class EvalSet(Base, TimestampMixin):
    __tablename__ = "eval_sets"
    __table_args__ = (UniqueConstraint("user_id", "name", name="uq_eval_sets_user_name"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    eval_metadata: Mapped[dict] = mapped_column("metadata", JSON, default=dict, nullable=False)

    user: Mapped[User] = relationship(back_populates="eval_sets")
    questions: Mapped[List["EvalQuestion"]] = relationship(
        back_populates="eval_set",
        cascade="all, delete-orphan",
        order_by="EvalQuestion.position",
    )


class EvalQuestion(Base, TimestampMixin):
    __tablename__ = "eval_questions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    eval_set_id: Mapped[str] = mapped_column(ForeignKey("eval_sets.id"), nullable=False)
    trace_id: Mapped[Optional[str]] = mapped_column(ForeignKey("traces.id"), nullable=True)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    expected_answer: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    question_metadata: Mapped[dict] = mapped_column("metadata", JSON, default=dict, nullable=False)

    eval_set: Mapped[EvalSet] = relationship(back_populates="questions")
    trace: Mapped[Optional[Trace]] = relationship(back_populates="eval_questions")


class ExternalRAGEndpoint(Base, TimestampMixin):
    __tablename__ = "external_rag_endpoints"
    __table_args__ = (UniqueConstraint("project_id", "name", name="uq_external_rag_endpoints_project_name"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    method: Mapped[str] = mapped_column(String(10), default="POST", nullable=False)
    headers_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    body_template_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    response_mapping_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    project: Mapped[Project] = relationship(back_populates="external_rag_endpoints")
