from __future__ import annotations

import logging
from types import TracebackType
from typing import Any, Iterable, Optional

from contexttrace.config import ContextTraceConfig, load_config
from contexttrace.errors import ContextTraceConfigError
from contexttrace.local import LocalTransport
from contexttrace.report import ReportGenerator
from contexttrace.transport import AsyncHttpTransport, AsyncTransport, HttpTransport, Transport

logger = logging.getLogger("contexttrace")


class ContextTrace:
    def __init__(
        self,
        *,
        api_key: Optional[str] = None,
        project: Optional[str] = None,
        base_url: Optional[str] = None,
        mode: Optional[str] = None,
        transport: Transport | None = None,
        timeout: Optional[float] = None,
        retries: Optional[int] = None,
        debug: Optional[bool] = None,
        local_store_dir: Optional[str] = None,
        config_path: Optional[str] = None,
    ) -> None:
        self.config = load_config(
            api_key=api_key,
            project=project,
            base_url=base_url,
            mode=mode,
            timeout=timeout,
            retries=retries,
            debug=debug,
            local_store_dir=local_store_dir,
            config_path=config_path,
        )
        _configure_logging(self.config)
        self.project = self.config.project
        self.mode = self.config.mode
        self._transport = transport or self._build_transport(self.config)

    def _build_transport(self, config: ContextTraceConfig) -> Transport:
        if config.mode == "local":
            return LocalTransport(store_dir=config.local_store_dir, debug=config.debug)
        if not config.api_key:
            raise ContextTraceConfigError(
                "ContextTrace api_key is required in hosted mode. Pass api_key=..., "
                "set CONTEXTTRACE_API_KEY, or run with mode='local'."
            )
        return HttpTransport(
            base_url=config.base_url,
            api_key=config.api_key,
            timeout=config.timeout,
            retries=config.retries,
            debug=config.debug,
        )

    def trace(self, *, query: str, metadata: dict[str, Any] | None = None) -> "TraceSession":
        return TraceSession(
            transport=self._transport,
            project=self.project,
            query=query,
            metadata=metadata or {},
        )

    def create_eval_set(
        self,
        name: str,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self._transport.post(
            "/v1/eval-sets",
            {
                "name": name,
                "metadata": metadata or {},
            },
        )

    def add_eval_questions(
        self,
        eval_set_id: str,
        questions: Iterable[Any],
    ) -> dict[str, Any]:
        return self._transport.post(
            f"/v1/eval-sets/{eval_set_id}/questions",
            {"questions": [_normalize_eval_question(question) for question in questions]},
        )

    def evaluate_existing_traces(self, eval_set_id: str) -> dict[str, Any]:
        return self._transport.post(f"/v1/eval-sets/{eval_set_id}/runs", {})

    def register_rag_endpoint(
        self,
        *,
        project_id: str,
        name: str,
        url: str,
        method: str = "POST",
        headers: Optional[dict[str, str]] = None,
        body_template: Optional[dict[str, Any]] = None,
        response_mapping: Optional[dict[str, str]] = None,
    ) -> dict[str, Any]:
        return self._transport.post(
            f"/v1/projects/{project_id}/external-endpoints",
            {
                "name": name,
                "url": url,
                "method": method,
                "headers": headers or {},
                "body_template": body_template or {"question": "{{query}}"},
                "response_mapping": response_mapping
                or {
                    "answer": "$.answer",
                    "citations": "$.citations",
                    "retrieved_chunks": "$.retrieved_chunks",
                },
            },
        )

    def test_rag_endpoint(
        self,
        endpoint_id: str,
        *,
        query: str,
        metadata: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        return self._transport.post(
            f"/v1/external-endpoints/{endpoint_id}/test",
            {
                "query": query,
                "metadata": metadata or {},
            },
        )

    def evaluate_rag_endpoint(
        self,
        endpoint_id: str,
        *,
        eval_set_id: str,
    ) -> dict[str, Any]:
        return self._transport.post(
            f"/v1/external-endpoints/{endpoint_id}/run-eval",
            {"eval_set_id": eval_set_id},
        )

    def list_traces(self, *, limit: int = 20) -> list[dict[str, Any]]:
        response = self._transport.get(f"/v1/traces?limit={limit}")
        traces = response.get("traces") or []
        if not isinstance(traces, list):
            raise ValueError("Trace list response did not include a traces list.")
        return traces[:limit]

    def last_trace(self) -> Optional[dict[str, Any]]:
        try:
            return self._transport.get("/v1/traces/last")
        except Exception:
            traces = self.list_traces(limit=1)
            return traces[0] if traces else None

    def export_report(
        self,
        *,
        trace_id: Optional[str] = None,
        path: str = "report.html",
        last: bool = False,
    ) -> str:
        if last:
            trace = self.last_trace()
            if trace is None:
                raise ValueError("No traces found to export.")
        elif trace_id:
            trace = self._transport.get(f"/v1/traces/{trace_id}")
        else:
            raise ValueError("Pass trace_id=... or last=True.")
        return ReportGenerator().generate(trace, path=path)

    def upload_traces(
        self,
        *,
        trace_ids: Optional[Iterable[str]] = None,
        target_transport: Optional[Transport] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        project: Optional[str] = None,
    ) -> dict[str, Any]:
        traces = (
            [self._transport.get(f"/v1/traces/{trace_id}") for trace_id in trace_ids]
            if trace_ids is not None
            else self.list_traces(limit=1000)
        )

        created_transport = False
        transport = target_transport
        if transport is None:
            resolved_api_key = api_key or self.config.api_key
            if not resolved_api_key:
                raise ContextTraceConfigError(
                    "api_key is required to upload local traces to a hosted ContextTrace API."
                )
            transport = HttpTransport(
                base_url=base_url or self.config.base_url,
                api_key=resolved_api_key,
                timeout=self.config.timeout,
                retries=self.config.retries,
                debug=self.config.debug,
            )
            created_transport = True

        uploaded = []
        try:
            for trace in traces:
                uploaded.append(_replay_trace(trace, transport=transport, project=project or self.project))
        finally:
            if created_transport:
                close = getattr(transport, "close", None)
                if close:
                    close()

        return {"uploaded": len(uploaded), "traces": uploaded}

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


class AsyncContextTrace:
    def __init__(
        self,
        *,
        api_key: Optional[str] = None,
        project: Optional[str] = None,
        base_url: Optional[str] = None,
        mode: Optional[str] = None,
        transport: AsyncTransport | None = None,
        timeout: Optional[float] = None,
        retries: Optional[int] = None,
        debug: Optional[bool] = None,
        local_store_dir: Optional[str] = None,
        config_path: Optional[str] = None,
    ) -> None:
        self.config = load_config(
            api_key=api_key,
            project=project,
            base_url=base_url,
            mode=mode,
            timeout=timeout,
            retries=retries,
            debug=debug,
            local_store_dir=local_store_dir,
            config_path=config_path,
        )
        _configure_logging(self.config)
        self.project = self.config.project
        self.mode = self.config.mode
        self._transport = transport or self._build_transport(self.config)

    def _build_transport(self, config: ContextTraceConfig) -> AsyncTransport:
        if config.mode == "local":
            return _AsyncTransportAdapter(LocalTransport(store_dir=config.local_store_dir, debug=config.debug))
        if not config.api_key:
            raise ContextTraceConfigError(
                "ContextTrace api_key is required in hosted mode. Pass api_key=..., "
                "set CONTEXTTRACE_API_KEY, or run with mode='local'."
            )
        return AsyncHttpTransport(
            base_url=config.base_url,
            api_key=config.api_key,
            timeout=config.timeout,
            retries=config.retries,
            debug=config.debug,
        )

    def trace(self, *, query: str, metadata: dict[str, Any] | None = None) -> "AsyncTraceSession":
        return AsyncTraceSession(
            transport=self._transport,
            project=self.project,
            query=query,
            metadata=metadata or {},
        )

    async def create_eval_set(
        self,
        name: str,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return await self._transport.post(
            "/v1/eval-sets",
            {
                "name": name,
                "metadata": metadata or {},
            },
        )

    async def add_eval_questions(
        self,
        eval_set_id: str,
        questions: Iterable[Any],
    ) -> dict[str, Any]:
        return await self._transport.post(
            f"/v1/eval-sets/{eval_set_id}/questions",
            {"questions": [_normalize_eval_question(question) for question in questions]},
        )

    async def evaluate_existing_traces(self, eval_set_id: str) -> dict[str, Any]:
        return await self._transport.post(f"/v1/eval-sets/{eval_set_id}/runs", {})

    async def register_rag_endpoint(
        self,
        *,
        project_id: str,
        name: str,
        url: str,
        method: str = "POST",
        headers: Optional[dict[str, str]] = None,
        body_template: Optional[dict[str, Any]] = None,
        response_mapping: Optional[dict[str, str]] = None,
    ) -> dict[str, Any]:
        return await self._transport.post(
            f"/v1/projects/{project_id}/external-endpoints",
            {
                "name": name,
                "url": url,
                "method": method,
                "headers": headers or {},
                "body_template": body_template or {"question": "{{query}}"},
                "response_mapping": response_mapping
                or {
                    "answer": "$.answer",
                    "citations": "$.citations",
                    "retrieved_chunks": "$.retrieved_chunks",
                },
            },
        )

    async def test_rag_endpoint(
        self,
        endpoint_id: str,
        *,
        query: str,
        metadata: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        return await self._transport.post(
            f"/v1/external-endpoints/{endpoint_id}/test",
            {
                "query": query,
                "metadata": metadata or {},
            },
        )

    async def evaluate_rag_endpoint(
        self,
        endpoint_id: str,
        *,
        eval_set_id: str,
    ) -> dict[str, Any]:
        return await self._transport.post(
            f"/v1/external-endpoints/{endpoint_id}/run-eval",
            {"eval_set_id": eval_set_id},
        )

    async def close(self) -> None:
        close = getattr(self._transport, "close", None)
        if close:
            result = close()
            if hasattr(result, "__await__"):
                await result


class AsyncTraceSession:
    def __init__(
        self,
        *,
        transport: AsyncTransport,
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

    async def __aenter__(self) -> "AsyncTraceSession":
        response = await self._transport.post(
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

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool:
        return False

    async def log_retrieval(
        self,
        chunks: Iterable[Any],
        *,
        retriever_name: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return await self._post(
            "retrieval",
            {
                "chunks": [_normalize_chunk(chunk) for chunk in chunks],
                "retriever_name": retriever_name,
                "metadata": metadata or {},
            },
        )

    async def log_context(
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
        return await self._post("context", payload)

    async def log_answer(
        self,
        answer: str,
        *,
        model: str | None = None,
        usage: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return await self._post(
            "answer",
            {
                "answer": answer,
                "model": model,
                "usage": usage or {},
                "metadata": metadata or {},
            },
        )

    async def log_citations(self, citations: Iterable[dict[str, Any]]) -> dict[str, Any]:
        return await self._post("citations", {"citations": list(citations)})

    async def evaluate(self) -> dict[str, Any]:
        return await self._post("evaluate", {})

    async def export_report(self, *, path: str = "report.html") -> str:
        trace = await self.fetch()
        return ReportGenerator().generate(trace, path=path)

    async def fetch(self) -> dict[str, Any]:
        self._require_started()
        return await self._transport.get(f"/v1/traces/{self.trace_id}")

    async def _post(self, endpoint: str, payload: dict[str, Any]) -> dict[str, Any]:
        self._require_started()
        return await self._transport.post(f"/v1/traces/{self.trace_id}/{endpoint}", payload)

    def _require_started(self) -> None:
        if not self.trace_id:
            raise RuntimeError("Trace has not started. Use AsyncContextTrace.trace(...) as an async context manager.")


class _AsyncTransportAdapter:
    def __init__(self, transport: Transport) -> None:
        self._transport = transport

    async def post(self, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        return self._transport.post(path, payload)

    async def get(self, path: str) -> dict[str, Any]:
        return self._transport.get(path)

    def close(self) -> None:
        close = getattr(self._transport, "close", None)
        if close:
            close()


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


def _normalize_eval_question(question: Any) -> dict[str, Any]:
    if isinstance(question, str):
        return {
            "question": question,
            "trace_id": None,
            "expected_answer": None,
            "metadata": {},
        }

    if not isinstance(question, dict):
        raise ValueError("Eval questions must be strings or dictionaries.")

    text = question.get("question") or question.get("query")
    if not text:
        raise ValueError("Each eval question must include question or query.")

    return {
        "question": str(text),
        "trace_id": question.get("trace_id"),
        "expected_answer": question.get("expected_answer"),
        "metadata": question.get("metadata") or {},
    }


def _replay_trace(trace: dict[str, Any], *, transport: Transport, project: str) -> dict[str, Any]:
    started = transport.post(
        "/v1/traces/start",
        {
            "project": trace.get("project") or project,
            "query": trace.get("query") or "",
            "metadata": trace.get("metadata") or {},
        },
    )
    remote_trace_id = started["trace_id"]
    chunks = trace.get("chunks") or []
    if chunks:
        transport.post(
            f"/v1/traces/{remote_trace_id}/retrieval",
            {"chunks": chunks, "retriever_name": "contexttrace-batch-upload", "metadata": {}},
        )
        selected = [chunk for chunk in chunks if chunk.get("selected")]
        if selected:
            transport.post(
                f"/v1/traces/{remote_trace_id}/context",
                {"chunks": selected, "metadata": {"source": "contexttrace-batch-upload"}},
            )

    answer = trace.get("answer") or {}
    if answer.get("answer"):
        transport.post(
            f"/v1/traces/{remote_trace_id}/answer",
            {
                "answer": answer["answer"],
                "model": answer.get("model"),
                "usage": answer.get("usage") or {},
                "metadata": answer.get("metadata") or {},
            },
        )

    checks = trace.get("citation_checks") or []
    citations = [
        {
            "claim": check.get("claim"),
            "source_chunk_id": check.get("source_chunk_id"),
        }
        for check in checks
        if check.get("claim") and check.get("source_chunk_id")
    ]
    if citations:
        transport.post(f"/v1/traces/{remote_trace_id}/citations", {"citations": citations})

    return {"local_trace_id": trace.get("id"), "trace_id": remote_trace_id}


def _configure_logging(config: ContextTraceConfig) -> None:
    if config.debug:
        logging.basicConfig(level=logging.DEBUG)
        logger.debug("ContextTrace config loaded: %s", config)
