from __future__ import annotations

from types import TracebackType
from typing import Any, Iterable

from contexttrace.report import ReportGenerator
from contexttrace.transport import HttpTransport, Transport


class ContextTrace:
    def __init__(
        self,
        *,
        api_key: str,
        project: str,
        base_url: str = "http://localhost:8000",
        transport: Transport | None = None,
        timeout: float = 30.0,
    ) -> None:
        self.project = project
        self._transport = transport or HttpTransport(
            base_url=base_url,
            api_key=api_key,
            timeout=timeout,
        )

    def trace(self, *, query: str, metadata: dict[str, Any] | None = None) -> "TraceSession":
        return TraceSession(
            transport=self._transport,
            project=self.project,
            query=query,
            metadata=metadata or {},
        )

    def close(self) -> None:
        close = getattr(self._transport, "close", None)
        if close:
            close()


class TraceSession:
    def __init__(
        self,
        *,
        transport: Transport,
        project: str,
        query: str,
        metadata: dict[str, Any],
    ) -> None:
        self._transport = transport
        self.project = project
        self.query = query
        self.metadata = metadata
        self.trace_id: str | None = None
        self.project_id: str | None = None

    def __enter__(self) -> "TraceSession":
        response = self._transport.post(
            "/v1/traces/start",
            {
                "project": self.project,
                "query": self.query,
                "metadata": self.metadata,
            },
        )
        self.trace_id = response["trace_id"]
        self.project_id = response["project_id"]
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool:
        return False

    def log_retrieval(
        self,
        chunks: Iterable[Any],
        *,
        retriever_name: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self._post(
            "retrieval",
            {
                "chunks": [_normalize_chunk(chunk) for chunk in chunks],
                "retriever_name": retriever_name,
                "metadata": metadata or {},
            },
        )

    def log_context(
        self,
        chunks: Iterable[Any] | None = None,
        *,
        chunk_ids: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "chunk_ids": chunk_ids,
            "metadata": metadata or {},
        }
        if chunks is not None:
            payload["chunks"] = [_normalize_chunk(chunk) for chunk in chunks]
        return self._post("context", payload)

    def log_answer(
        self,
        answer: str,
        *,
        model: str | None = None,
        usage: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self._post(
            "answer",
            {
                "answer": answer,
                "model": model,
                "usage": usage or {},
                "metadata": metadata or {},
            },
        )

    def log_citations(self, citations: Iterable[dict[str, Any]]) -> dict[str, Any]:
        return self._post("citations", {"citations": list(citations)})

    def evaluate(self) -> dict[str, Any]:
        return self._post("evaluate", {})

    def export_report(self, *, path: str = "report.html") -> str:
        trace = self.fetch()
        return ReportGenerator().generate(trace, path=path)

    def fetch(self) -> dict[str, Any]:
        self._require_started()
        return self._transport.get(f"/v1/traces/{self.trace_id}")

    def _post(self, endpoint: str, payload: dict[str, Any]) -> dict[str, Any]:
        self._require_started()
        return self._transport.post(f"/v1/traces/{self.trace_id}/{endpoint}", payload)

    def _require_started(self) -> None:
        if not self.trace_id:
            raise RuntimeError("Trace has not started. Use ContextTrace.trace(...) as a context manager.")


def _normalize_chunk(chunk: Any) -> dict[str, Any]:
    if isinstance(chunk, dict):
        chunk_id = (
            chunk.get("chunk_id")
            or chunk.get("id")
            or chunk.get("source_chunk_id")
        )
        content = chunk.get("content") or chunk.get("text") or chunk.get("page_content")
        source = chunk.get("source")
        metadata = chunk.get("metadata") or {}
        relevance_score = chunk.get("relevance_score") or chunk.get("score")
    else:
        chunk_id = (
            getattr(chunk, "chunk_id", None)
            or getattr(chunk, "id", None)
            or getattr(chunk, "source_chunk_id", None)
        )
        content = (
            getattr(chunk, "content", None)
            or getattr(chunk, "text", None)
            or getattr(chunk, "page_content", None)
        )
        source = getattr(chunk, "source", None)
        metadata = getattr(chunk, "metadata", None) or {}
        relevance_score = getattr(chunk, "relevance_score", None) or getattr(chunk, "score", None)

    if not content:
        raise ValueError("Each chunk must include content, text, or page_content.")

    return {
        "chunk_id": str(chunk_id) if chunk_id is not None else None,
        "content": str(content),
        "source": source,
        "metadata": metadata,
        "relevance_score": relevance_score,
    }
