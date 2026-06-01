from __future__ import annotations

import json
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any, Optional


SCHEMA_VERSION = 1


class SQLiteTraceStore:
    def __init__(self, path: str = ".contexttrace/contexttrace.db") -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def create_trace(self, *, project: str, query: str, metadata: dict[str, Any]) -> dict[str, Any]:
        trace_id = _new_id("trace")
        project_id = _new_id("project")
        now = _now()
        with self._connect() as db:
            db.execute(
                """
                INSERT INTO traces (id, project_id, project, query, metadata_json, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (trace_id, project_id, project, query, _json(metadata), "started", now, now),
            )
        return self.get_trace(trace_id)

    def upsert_chunks(self, trace_id: str, chunks: list[dict[str, Any]], *, selected: bool) -> int:
        with self._connect() as db:
            current_count = db.execute(
                "SELECT COUNT(*) FROM chunks WHERE trace_id = ?",
                (trace_id,),
            ).fetchone()[0]
            for offset, chunk in enumerate(chunks):
                chunk_id = str(chunk.get("chunk_id") or chunk.get("id") or f"chunk_{current_count + offset}")
                existing = db.execute(
                    "SELECT id, selected FROM chunks WHERE trace_id = ? AND chunk_id = ?",
                    (trace_id, chunk_id),
                ).fetchone()
                if existing:
                    db.execute(
                        """
                        UPDATE chunks
                        SET content = ?, source = ?, metadata_json = ?, relevance_score = ?,
                            selected = ?, updated_at = ?
                        WHERE id = ?
                        """,
                        (
                            str(chunk.get("content") or ""),
                            chunk.get("source"),
                            _json(chunk.get("metadata") or {}),
                            chunk.get("relevance_score"),
                            bool(existing["selected"]) or selected,
                            _now(),
                            existing["id"],
                        ),
                    )
                else:
                    db.execute(
                        """
                        INSERT INTO chunks (
                            id, trace_id, chunk_id, content, source, metadata_json,
                            relevance_score, position, selected, created_at, updated_at
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            _new_id("chunk"),
                            trace_id,
                            chunk_id,
                            str(chunk.get("content") or ""),
                            chunk.get("source"),
                            _json(chunk.get("metadata") or {}),
                            chunk.get("relevance_score"),
                            current_count + offset,
                            selected,
                            _now(),
                            _now(),
                        ),
                    )
            self._set_status(db, trace_id, "context_logged" if selected else "retrieval_logged")
        return len(chunks)

    def mark_context(self, trace_id: str, chunk_ids: list[str]) -> int:
        if not chunk_ids:
            return 0
        with self._connect() as db:
            placeholders = ",".join("?" for _ in chunk_ids)
            params = [trace_id, *chunk_ids]
            db.execute(
                f"UPDATE chunks SET selected = 1, updated_at = ? WHERE trace_id = ? AND chunk_id IN ({placeholders})",
                [_now(), *params],
            )
            accepted = db.execute(
                f"SELECT COUNT(*) FROM chunks WHERE trace_id = ? AND chunk_id IN ({placeholders}) AND selected = 1",
                params,
            ).fetchone()[0]
            self._set_status(db, trace_id, "context_logged")
        return int(accepted)

    def save_answer(self, trace_id: str, answer: dict[str, Any]) -> None:
        with self._connect() as db:
            existing = db.execute("SELECT id FROM answers WHERE trace_id = ?", (trace_id,)).fetchone()
            values = (
                str(answer.get("answer") or ""),
                answer.get("model"),
                _json(answer.get("usage") or {}),
                _json(answer.get("metadata") or {}),
                _now(),
            )
            if existing:
                db.execute(
                    """
                    UPDATE answers
                    SET answer = ?, model = ?, usage_json = ?, metadata_json = ?, updated_at = ?
                    WHERE trace_id = ?
                    """,
                    (*values, trace_id),
                )
            else:
                db.execute(
                    """
                    INSERT INTO answers (id, trace_id, answer, model, usage_json, metadata_json, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (_new_id("answer"), trace_id, *values[:-1], _now(), values[-1]),
                )
            self._set_status(db, trace_id, "answer_logged")

    def save_citations(self, trace_id: str, citations: list[dict[str, Any]]) -> int:
        with self._connect() as db:
            db.execute("DELETE FROM citation_checks WHERE trace_id = ?", (trace_id,))
            for citation in citations:
                db.execute(
                    """
                    INSERT INTO citation_checks (
                        id, trace_id, claim, source_chunk_id, support_status,
                        support_score, rationale, metadata_json, created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        _new_id("check"),
                        trace_id,
                        citation["claim"],
                        citation["source_chunk_id"],
                        "pending",
                        None,
                        None,
                        _json(citation.get("metadata") or {}),
                        _now(),
                        _now(),
                    ),
                )
            self._set_status(db, trace_id, "citations_logged")
        return len(citations)

    def save_evaluation(self, trace_id: str, evaluation: dict[str, Any]) -> None:
        failure = evaluation.get("failure") or {}
        with self._connect() as db:
            for check in evaluation.get("citation_checks") or []:
                db.execute(
                    """
                    UPDATE citation_checks
                    SET support_status = ?, support_score = ?, rationale = ?, updated_at = ?
                    WHERE trace_id = ? AND claim = ? AND source_chunk_id = ?
                    """,
                    (
                        check.get("verdict"),
                        check.get("support_score"),
                        check.get("reason"),
                        _now(),
                        trace_id,
                        check.get("claim"),
                        check.get("source_chunk_id"),
                    ),
                )
            existing = db.execute("SELECT id FROM failure_reports WHERE trace_id = ?", (trace_id,)).fetchone()
            values = (
                failure.get("failure_type") or "unknown",
                failure.get("severity") or "medium",
                failure.get("root_cause") or "",
                failure.get("suggested_fix") or "",
                _json(evaluation.get("scores") or {}),
                _json(evaluation.get("reliability") or {}),
                _json(evaluation.get("metadata") or {}),
                _now(),
            )
            if existing:
                db.execute(
                    """
                    UPDATE failure_reports
                    SET failure_type = ?, severity = ?, root_cause = ?, suggested_fix = ?,
                        scores_json = ?, reliability_json = ?, metadata_json = ?, updated_at = ?
                    WHERE trace_id = ?
                    """,
                    (*values, trace_id),
                )
            else:
                db.execute(
                    """
                    INSERT INTO failure_reports (
                        id, trace_id, failure_type, severity, root_cause, suggested_fix,
                        scores_json, reliability_json, metadata_json, created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (_new_id("failure"), trace_id, *values[:-1], _now(), values[-1]),
                )
            self._set_status(db, trace_id, "evaluated")

    def add_agent_event(self, trace_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        event_id = _new_id("agent_event")
        with self._connect() as db:
            db.execute(
                """
                INSERT INTO agent_events (
                    id, trace_id, event_type, name, input_json, output_json,
                    metadata_json, latency_ms, error_message, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event_id,
                    trace_id,
                    payload["event_type"],
                    payload.get("name"),
                    _json(payload.get("input_json") if payload.get("input_json") is not None else {}),
                    _json(payload.get("output_json") if payload.get("output_json") is not None else {}),
                    _json(payload.get("metadata_json") or {}),
                    payload.get("latency_ms"),
                    payload.get("error_message"),
                    _now(),
                ),
            )
            self._set_status(db, trace_id, "agent_event_logged")
        return {"trace_id": trace_id, "event_id": event_id, "accepted": 1}

    def create_eval_run(self, *, dataset: str, endpoint: Optional[str], summary: dict[str, Any]) -> str:
        run_id = _new_id("eval_run")
        with self._connect() as db:
            db.execute(
                """
                INSERT INTO eval_runs (id, dataset, endpoint, summary_json, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (run_id, dataset, endpoint, _json(summary), _now()),
            )
        return run_id

    def add_eval_question(self, *, eval_run_id: str, question: dict[str, Any], trace_id: Optional[str], position: int) -> None:
        with self._connect() as db:
            db.execute(
                """
                INSERT INTO eval_questions (id, eval_run_id, trace_id, question_json, position, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (_new_id("eval_question"), eval_run_id, trace_id, _json(question), position, _now()),
            )

    def last_eval_run(self) -> Optional[dict[str, Any]]:
        with self._connect() as db:
            row = db.execute("SELECT * FROM eval_runs ORDER BY created_at DESC LIMIT 1").fetchone()
        return _eval_run_from_row(row) if row else None

    def get_eval_run(self, eval_run_id: str) -> dict[str, Any]:
        with self._connect() as db:
            row = db.execute("SELECT * FROM eval_runs WHERE id = ?", (eval_run_id,)).fetchone()
            questions = db.execute(
                "SELECT * FROM eval_questions WHERE eval_run_id = ? ORDER BY position",
                (eval_run_id,),
            ).fetchall()
        if row is None:
            raise KeyError("Eval run not found: %s" % eval_run_id)
        result = _eval_run_from_row(row)
        result["questions"] = [
            {
                "id": question["id"],
                "trace_id": question["trace_id"],
                "question": _loads(question["question_json"], {}),
                "position": question["position"],
                "created_at": question["created_at"],
            }
            for question in questions
        ]
        return result

    def list_eval_runs(self, *, limit: int = 20) -> list[dict[str, Any]]:
        with self._connect() as db:
            rows = db.execute(
                "SELECT * FROM eval_runs ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [_eval_run_from_row(row) for row in rows]

    def get_trace(self, trace_id: str) -> dict[str, Any]:
        with self._connect() as db:
            trace = db.execute("SELECT * FROM traces WHERE id = ?", (trace_id,)).fetchone()
            if trace is None:
                raise KeyError("Trace not found: %s" % trace_id)
            chunks = db.execute(
                "SELECT * FROM chunks WHERE trace_id = ? ORDER BY position, created_at",
                (trace_id,),
            ).fetchall()
            answer = db.execute("SELECT * FROM answers WHERE trace_id = ?", (trace_id,)).fetchone()
            checks = db.execute(
                "SELECT * FROM citation_checks WHERE trace_id = ? ORDER BY created_at",
                (trace_id,),
            ).fetchall()
            failure = db.execute("SELECT * FROM failure_reports WHERE trace_id = ?", (trace_id,)).fetchone()
            events = db.execute(
                "SELECT * FROM agent_events WHERE trace_id = ? ORDER BY created_at",
                (trace_id,),
            ).fetchall()
        return _trace_from_rows(trace, chunks, answer, checks, failure, events)

    def list_traces(self, *, limit: int = 20) -> list[dict[str, Any]]:
        with self._connect() as db:
            rows = db.execute(
                "SELECT id FROM traces ORDER BY updated_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [self.get_trace(row["id"]) for row in rows]

    def last_trace(self) -> Optional[dict[str, Any]]:
        traces = self.list_traces(limit=1)
        return traces[0] if traces else None

    def trace_count(self) -> int:
        with self._connect() as db:
            return int(db.execute("SELECT COUNT(*) FROM traces").fetchone()[0])

    def _init_db(self) -> None:
        with self._connect() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute(
                "CREATE TABLE IF NOT EXISTS schema_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)"
            )
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS traces (
                    id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    project TEXT NOT NULL,
                    query TEXT NOT NULL,
                    metadata_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS chunks (
                    id TEXT PRIMARY KEY,
                    trace_id TEXT NOT NULL,
                    chunk_id TEXT NOT NULL,
                    content TEXT NOT NULL,
                    source TEXT,
                    metadata_json TEXT NOT NULL,
                    relevance_score REAL,
                    position INTEGER NOT NULL,
                    selected INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(trace_id, chunk_id)
                )
                """
            )
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS answers (
                    id TEXT PRIMARY KEY,
                    trace_id TEXT NOT NULL UNIQUE,
                    answer TEXT NOT NULL,
                    model TEXT,
                    usage_json TEXT NOT NULL,
                    metadata_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS citation_checks (
                    id TEXT PRIMARY KEY,
                    trace_id TEXT NOT NULL,
                    claim TEXT NOT NULL,
                    source_chunk_id TEXT NOT NULL,
                    support_status TEXT NOT NULL,
                    support_score REAL,
                    rationale TEXT,
                    metadata_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS failure_reports (
                    id TEXT PRIMARY KEY,
                    trace_id TEXT NOT NULL UNIQUE,
                    failure_type TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    root_cause TEXT NOT NULL,
                    suggested_fix TEXT NOT NULL,
                    scores_json TEXT NOT NULL,
                    reliability_json TEXT NOT NULL,
                    metadata_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS agent_events (
                    id TEXT PRIMARY KEY,
                    trace_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    name TEXT,
                    input_json TEXT NOT NULL,
                    output_json TEXT NOT NULL,
                    metadata_json TEXT NOT NULL,
                    latency_ms REAL,
                    error_message TEXT,
                    created_at TEXT NOT NULL
                )
                """
            )
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS eval_runs (
                    id TEXT PRIMARY KEY,
                    dataset TEXT NOT NULL,
                    endpoint TEXT,
                    summary_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS eval_questions (
                    id TEXT PRIMARY KEY,
                    eval_run_id TEXT NOT NULL,
                    trace_id TEXT,
                    question_json TEXT NOT NULL,
                    position INTEGER NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            db.execute(
                "INSERT OR REPLACE INTO schema_meta (key, value) VALUES ('schema_version', ?)",
                (str(SCHEMA_VERSION),),
            )

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(str(self.path))
        db.row_factory = sqlite3.Row
        return db

    def _set_status(self, db: sqlite3.Connection, trace_id: str, status: str) -> None:
        db.execute(
            "UPDATE traces SET status = ?, updated_at = ? WHERE id = ?",
            (status, _now(), trace_id),
        )


def _trace_from_rows(
    trace: sqlite3.Row,
    chunks: list[sqlite3.Row],
    answer: Optional[sqlite3.Row],
    checks: list[sqlite3.Row],
    failure: Optional[sqlite3.Row],
    events: list[sqlite3.Row],
) -> dict[str, Any]:
    citation_checks = [
        {
            "id": row["id"],
            "claim": row["claim"],
            "source_chunk_id": row["source_chunk_id"],
            "support_status": row["support_status"],
            "support_score": row["support_score"],
            "rationale": row["rationale"],
            "metadata": _loads(row["metadata_json"], {}),
        }
        for row in checks
    ]
    evaluation = None
    if failure is not None:
        evaluated = [
            {
                "claim": check["claim"],
                "source_chunk_id": check["source_chunk_id"],
                "verdict": check["support_status"],
                "support_score": check["support_score"] or 0.0,
                "reason": check["rationale"] or "",
            }
            for check in citation_checks
            if check["support_status"] != "pending"
        ]
        evaluation = {
            "scores": _loads(failure["scores_json"], {}),
            "reliability": _loads(failure["reliability_json"], {}),
            "citation_checks": evaluated,
            "failure": {
                "failure_type": failure["failure_type"],
                "severity": failure["severity"],
                "root_cause": failure["root_cause"],
                "suggested_fix": failure["suggested_fix"],
            },
        }

    return {
        "id": trace["id"],
        "project_id": trace["project_id"],
        "project": trace["project"],
        "query": trace["query"],
        "metadata": _loads(trace["metadata_json"], {}),
        "status": trace["status"],
        "chunks": [
            {
                "id": row["id"],
                "chunk_id": row["chunk_id"],
                "content": row["content"],
                "source": row["source"],
                "metadata": _loads(row["metadata_json"], {}),
                "relevance_score": row["relevance_score"],
                "position": row["position"],
                "selected": bool(row["selected"]),
            }
            for row in chunks
        ],
        "answer": (
            {
                "id": answer["id"],
                "answer": answer["answer"],
                "model": answer["model"],
                "usage": _loads(answer["usage_json"], {}),
                "metadata": _loads(answer["metadata_json"], {}),
            }
            if answer is not None
            else None
        ),
        "citation_checks": citation_checks,
        "agent_events": [
            {
                "id": row["id"],
                "trace_id": row["trace_id"],
                "event_type": row["event_type"],
                "name": row["name"],
                "input_json": _loads(row["input_json"], {}),
                "output_json": _loads(row["output_json"], {}),
                "metadata_json": _loads(row["metadata_json"], {}),
                "latency_ms": row["latency_ms"],
                "error_message": row["error_message"],
                "created_at": row["created_at"],
            }
            for row in events
        ],
        "evaluation": evaluation,
        "created_at": trace["created_at"],
        "updated_at": trace["updated_at"],
    }


def _eval_run_from_row(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "dataset": row["dataset"],
        "endpoint": row["endpoint"],
        "summary": _loads(row["summary_json"], {}),
        "created_at": row["created_at"],
    }


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True)


def _loads(value: str, default: Any) -> Any:
    try:
        return json.loads(value) if value else default
    except json.JSONDecodeError:
        return default


def _new_id(prefix: str) -> str:
    return "%s_%s" % (prefix, uuid.uuid4().hex[:12])


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
