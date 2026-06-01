from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Optional

from contexttrace.errors import ContextTraceLocalError
from contexttrace.reliability import ReliabilityScorer
from contexttrace.storage import SQLiteTraceStore

logger = logging.getLogger("contexttrace")


class LocalTransport:
    def __init__(
        self,
        *,
        store_dir: str = ".contexttrace",
        storage_path: Optional[str] = None,
        debug: bool = False,
        log_chunk_text: bool = True,
        log_answer_text: bool = True,
    ) -> None:
        self.storage_path = storage_path or str(Path(store_dir) / "contexttrace.db")
        self.store = SQLiteTraceStore(self.storage_path)
        self.debug = debug
        self.log_chunk_text = log_chunk_text
        self.log_answer_text = log_answer_text

    def post(self, path: str, payload: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        payload = payload or {}
        self._debug("POST", path, payload)
        if path == "/v1/traces/start":
            trace = self.store.create_trace(
                project=payload["project"],
                query=payload["query"],
                metadata=payload.get("metadata") or {},
            )
            return {"trace_id": trace["id"], "project_id": trace["project_id"]}

        trace_id, action = _parse_trace_action(path)
        if action == "retrieval":
            chunks = [
                _chunk(
                    chunk,
                    index=index,
                    selected=False,
                    log_chunk_text=self.log_chunk_text,
                )
                for index, chunk in enumerate(payload.get("chunks") or [])
            ]
            accepted = self.store.upsert_chunks(trace_id, chunks, selected=False)
            return {"trace_id": trace_id, "accepted": accepted}

        if action == "context":
            accepted = self.store.mark_context(trace_id, list(payload.get("chunk_ids") or []))
            chunks = [
                _chunk(
                    chunk,
                    index=index,
                    selected=True,
                    log_chunk_text=self.log_chunk_text,
                )
                for index, chunk in enumerate(payload.get("chunks") or [])
            ]
            accepted += self.store.upsert_chunks(trace_id, chunks, selected=True)
            return {"trace_id": trace_id, "accepted": accepted}

        if action == "answer":
            answer_text = payload["answer"] if self.log_answer_text else "[answer text redacted]"
            self.store.save_answer(
                trace_id,
                {
                    "answer": answer_text,
                    "model": payload.get("model"),
                    "usage": payload.get("usage") or {},
                    "metadata": payload.get("metadata") or {},
                },
            )
            return {"trace_id": trace_id, "accepted": 1}

        if action == "citations":
            accepted = self.store.save_citations(trace_id, list(payload.get("citations") or []))
            return {"trace_id": trace_id, "accepted": accepted}

        if action == "agent-events":
            return self.store.add_agent_event(trace_id, payload)

        if action == "evaluate":
            trace = self.store.get_trace(trace_id)
            evaluation = _evaluate_trace(trace)
            self.store.save_evaluation(trace_id, evaluation)
            return evaluation

        raise ContextTraceLocalError("Unsupported local POST path: %s" % path)

    def get(self, path: str) -> dict[str, Any]:
        self._debug("GET", path, None)
        if path.startswith("/v1/traces?") or path == "/v1/traces":
            limit = _query_int(path, "limit", default=20)
            return {"traces": self.store.list_traces(limit=limit)}
        if path == "/v1/traces/last":
            trace = self.store.last_trace()
            if trace is None:
                raise ContextTraceLocalError("No local traces found.")
            return trace
        if path == "/v1/status":
            last_eval = self.store.last_eval_run()
            return {
                "storage_path": self.storage_path,
                "trace_count": self.store.trace_count(),
                "last_eval_run": last_eval,
            }
        parts = path.strip("/").split("/")
        if len(parts) == 4 and parts[:2] == ["v1", "traces"] and parts[3] == "agent-events":
            trace = self.store.get_trace(parts[2])
            return {"trace_id": parts[2], "events": trace.get("agent_events") or []}
        if len(parts) == 3 and parts[:2] == ["v1", "eval-runs"]:
            return self.store.get_eval_run(parts[2])
        if path == "/v1/eval-runs":
            return {"eval_runs": self.store.list_eval_runs()}
        if path.startswith("/v1/traces/"):
            trace_id = path.rsplit("/", 1)[-1]
            return self.store.get_trace(trace_id)
        raise ContextTraceLocalError("Unsupported local GET path: %s" % path)

    def close(self) -> None:
        return None

    def _debug(self, method: str, path: str, payload: Optional[dict[str, Any]]) -> None:
        if self.debug:
            logger.debug("%s %s", method, path)


def _parse_trace_action(path: str) -> tuple[str, str]:
    parts = path.strip("/").split("/")
    if len(parts) != 4 or parts[0] != "v1" or parts[1] != "traces":
        raise ContextTraceLocalError("Unsupported local trace path: %s" % path)
    return parts[2], parts[3]


def _chunk(
    chunk: dict[str, Any],
    *,
    index: int,
    selected: bool,
    log_chunk_text: bool,
) -> dict[str, Any]:
    chunk_id = chunk.get("chunk_id") or chunk.get("id") or "chunk_%s" % index
    content = str(chunk.get("content") or chunk.get("text") or chunk.get("page_content") or "")
    return {
        "chunk_id": str(chunk_id),
        "content": content if log_chunk_text else "[chunk text redacted]",
        "source": chunk.get("source"),
        "metadata": chunk.get("metadata") or {},
        "relevance_score": chunk.get("relevance_score") or chunk.get("score"),
        "selected": selected,
    }


def _evaluate_trace(trace: dict[str, Any]) -> dict[str, Any]:
    chunks_by_id = {chunk["chunk_id"]: chunk for chunk in trace.get("chunks") or []}
    evaluated = []
    for citation in trace.get("citation_checks") or []:
        source = chunks_by_id.get(citation["source_chunk_id"])
        score = _support_score(citation["claim"], source.get("content", "") if source else "")
        verdict = "directly_supported" if score >= 0.65 else "unsupported"
        evaluated.append(
            {
                "claim": citation["claim"],
                "source_chunk_id": citation["source_chunk_id"],
                "verdict": verdict,
                "support_score": score,
                "reason": "Local lexical support score %.2f." % score,
            }
        )
    unsupported = [check for check in evaluated if check["verdict"] != "directly_supported"]
    failure_type = "no_failure_detected" if not unsupported else "unsupported_answer"
    severity = "none" if failure_type == "no_failure_detected" else "medium"
    scores = _score_summary(evaluated)
    reliability = ReliabilityScorer().score_trace(
        {
            **trace,
            "evaluation": {
                "scores": scores,
                "failure": {"failure_type": failure_type},
                "citation_checks": evaluated,
            },
        }
    ).to_dict()
    return {
        "scores": scores,
        "reliability": reliability,
        "citation_checks": evaluated,
        "failure": {
            "failure_type": failure_type,
            "severity": severity,
            "root_cause": "Local lexical evaluation completed.",
            "suggested_fix": "Use a configured judge provider for model-based citation analysis.",
        },
    }


def _score_summary(evaluated_checks: list[dict[str, Any]]) -> dict[str, float]:
    if not evaluated_checks:
        return {
            "citation_support": 0.0,
            "unsupported_claim_rate": 1.0,
        }
    support_scores = [float(check.get("support_score") or 0.0) for check in evaluated_checks]
    unsupported = [
        check
        for check in evaluated_checks
        if check.get("verdict") in {"unsupported", "contradicted", "not_enough_info"}
    ]
    return {
        "citation_support": round(sum(support_scores) / len(support_scores), 3),
        "unsupported_claim_rate": round(len(unsupported) / len(evaluated_checks), 3),
    }


def _support_score(claim: str, source: str) -> float:
    claim_terms = _terms(claim)
    if not claim_terms:
        return 0.0
    source_terms = _terms(source)
    return round(len(claim_terms & source_terms) / len(claim_terms), 3)


def _terms(text: str) -> set:
    return {
        token.strip(".,:;!?()[]{}\"'").lower().rstrip("s")
        for token in text.split()
        if len(token.strip(".,:;!?()[]{}\"'")) > 2
    }


def _query_int(path: str, key: str, *, default: int) -> int:
    if "?" not in path:
        return default
    _, query = path.split("?", 1)
    for part in query.split("&"):
        if "=" not in part:
            continue
        name, value = part.split("=", 1)
        if name == key:
            try:
                return int(value)
            except ValueError:
                return default
    return default
