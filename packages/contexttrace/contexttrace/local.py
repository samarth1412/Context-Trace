from __future__ import annotations

import json
import logging
import time
import uuid
from pathlib import Path
from typing import Any, Optional

from contexttrace.errors import ContextTraceLocalError

logger = logging.getLogger("contexttrace")


class LocalStore:
    def __init__(self, directory: str = ".contexttrace") -> None:
        self.directory = Path(directory)
        self.traces_dir = self.directory / "traces"
        self.traces_dir.mkdir(parents=True, exist_ok=True)

    def create_trace(self, *, project: str, query: str, metadata: dict[str, Any]) -> dict[str, Any]:
        trace_id = _new_id("local_trace")
        now = _now()
        trace = {
            "id": trace_id,
            "project_id": _new_id("local_project"),
            "project": project,
            "query": query,
            "metadata": metadata,
            "status": "started",
            "chunks": [],
            "answer": None,
            "citation_checks": [],
            "agent_events": [],
            "evaluation": None,
            "created_at": now,
            "updated_at": now,
        }
        self.save_trace(trace)
        self._write_last_trace_id(trace_id)
        return trace

    def save_trace(self, trace: dict[str, Any]) -> None:
        trace["updated_at"] = _now()
        self._path(trace["id"]).write_text(json.dumps(trace, indent=2), encoding="utf-8")
        self._write_last_trace_id(trace["id"])

    def get_trace(self, trace_id: str) -> dict[str, Any]:
        path = self._path(trace_id)
        if not path.exists():
            raise ContextTraceLocalError("Local trace not found: %s" % trace_id)
        return json.loads(path.read_text(encoding="utf-8"))

    def list_traces(self, *, limit: int = 20) -> list[dict[str, Any]]:
        traces = []
        for path in sorted(self.traces_dir.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True):
            traces.append(json.loads(path.read_text(encoding="utf-8")))
            if len(traces) >= limit:
                break
        return traces

    def last_trace(self) -> Optional[dict[str, Any]]:
        last_path = self.directory / "last_trace"
        if last_path.exists():
            trace_id = last_path.read_text(encoding="utf-8").strip()
            if trace_id:
                try:
                    return self.get_trace(trace_id)
                except ContextTraceLocalError:
                    pass
        traces = self.list_traces(limit=1)
        return traces[0] if traces else None

    def _path(self, trace_id: str) -> Path:
        return self.traces_dir / ("%s.json" % trace_id)

    def _write_last_trace_id(self, trace_id: str) -> None:
        (self.directory / "last_trace").write_text(trace_id, encoding="utf-8")


class LocalTransport:
    def __init__(self, *, store_dir: str = ".contexttrace", debug: bool = False) -> None:
        self.store = LocalStore(store_dir)
        self.debug = debug

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
        trace = self.store.get_trace(trace_id)
        if action == "retrieval":
            chunks = [_chunk(chunk, index=index, selected=False) for index, chunk in enumerate(payload.get("chunks") or [])]
            trace["chunks"] = _upsert_chunks(trace["chunks"], chunks)
            trace["status"] = "retrieval_logged"
            self.store.save_trace(trace)
            return {"trace_id": trace_id, "accepted": len(chunks)}
        if action == "context":
            accepted = 0
            chunk_ids = set(payload.get("chunk_ids") or [])
            for chunk in trace["chunks"]:
                if chunk["chunk_id"] in chunk_ids:
                    chunk["selected"] = True
                    accepted += 1
            chunks = [_chunk(chunk, index=len(trace["chunks"]) + index, selected=True) for index, chunk in enumerate(payload.get("chunks") or [])]
            trace["chunks"] = _upsert_chunks(trace["chunks"], chunks)
            accepted += len(chunks)
            trace["status"] = "context_logged"
            self.store.save_trace(trace)
            return {"trace_id": trace_id, "accepted": accepted}
        if action == "answer":
            trace["answer"] = {
                "id": _new_id("local_answer"),
                "answer": payload["answer"],
                "model": payload.get("model"),
                "usage": payload.get("usage") or {},
                "metadata": payload.get("metadata") or {},
            }
            trace["status"] = "answer_logged"
            self.store.save_trace(trace)
            return {"trace_id": trace_id, "accepted": 1}
        if action == "citations":
            trace["citation_checks"] = [
                {
                    "id": _new_id("local_check"),
                    "claim": citation["claim"],
                    "source_chunk_id": citation["source_chunk_id"],
                    "support_status": "pending",
                    "support_score": None,
                    "rationale": None,
                }
                for citation in payload.get("citations") or []
            ]
            trace["status"] = "citations_logged"
            self.store.save_trace(trace)
            return {"trace_id": trace_id, "accepted": len(trace["citation_checks"])}
        if action == "agent-events":
            event = {
                "id": _new_id("local_agent_event"),
                "trace_id": trace_id,
                "event_type": payload["event_type"],
                "name": payload.get("name"),
                "input_json": payload.get("input_json") if payload.get("input_json") is not None else {},
                "output_json": payload.get("output_json") if payload.get("output_json") is not None else {},
                "metadata_json": payload.get("metadata_json") or {},
                "latency_ms": payload.get("latency_ms"),
                "error_message": payload.get("error_message"),
                "created_at": _now(),
            }
            trace.setdefault("agent_events", []).append(event)
            trace["status"] = "agent_event_logged"
            self.store.save_trace(trace)
            return {"trace_id": trace_id, "event_id": event["id"], "accepted": 1}
        if action == "evaluate":
            evaluation = _evaluate_trace(trace)
            trace["evaluation"] = evaluation
            trace["citation_checks"] = [
                {
                    "id": check.get("id", _new_id("local_check")),
                    "claim": evaluated["claim"],
                    "source_chunk_id": evaluated["source_chunk_id"],
                    "support_status": evaluated["verdict"],
                    "support_score": evaluated["support_score"],
                    "rationale": evaluated["reason"],
                }
                for check, evaluated in zip(trace.get("citation_checks") or [], evaluation["citation_checks"])
            ]
            trace["status"] = "evaluated"
            self.store.save_trace(trace)
            return evaluation

        raise ContextTraceLocalError("Unsupported local POST path: %s" % path)

    def get(self, path: str) -> dict[str, Any]:
        self._debug("GET", path, None)
        if path.startswith("/v1/traces?") or path == "/v1/traces":
            return {"traces": self.store.list_traces()}
        if path == "/v1/traces/last":
            trace = self.store.last_trace()
            if trace is None:
                raise ContextTraceLocalError("No local traces found.")
            return trace
        parts = path.strip("/").split("/")
        if len(parts) == 4 and parts[:2] == ["v1", "traces"] and parts[3] == "agent-events":
            trace = self.store.get_trace(parts[2])
            return {"trace_id": parts[2], "events": trace.get("agent_events") or []}
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


def _chunk(chunk: dict[str, Any], *, index: int, selected: bool) -> dict[str, Any]:
    chunk_id = chunk.get("chunk_id") or chunk.get("id") or "chunk_%s" % index
    return {
        "id": _new_id("local_chunk"),
        "chunk_id": str(chunk_id),
        "content": str(chunk.get("content") or chunk.get("text") or chunk.get("page_content") or ""),
        "source": chunk.get("source"),
        "metadata": chunk.get("metadata") or {},
        "relevance_score": chunk.get("relevance_score") or chunk.get("score"),
        "position": index,
        "selected": selected,
    }


def _upsert_chunks(existing: list[dict[str, Any]], incoming: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id = {chunk["chunk_id"]: chunk for chunk in existing}
    for chunk in incoming:
        current = by_id.get(chunk["chunk_id"])
        if current:
            current.update({key: value for key, value in chunk.items() if key != "id"})
            current["selected"] = current.get("selected") or chunk.get("selected")
        else:
            by_id[chunk["chunk_id"]] = chunk
    return list(by_id.values())


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
    return {
        "citation_checks": evaluated,
        "failure": {
            "failure_type": failure_type,
            "severity": severity,
            "root_cause": "Local lexical evaluation completed.",
            "suggested_fix": "Use hosted judge evaluation for model-based citation analysis.",
        },
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


def _new_id(prefix: str) -> str:
    return "%s_%s" % (prefix, uuid.uuid4().hex[:12])


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
