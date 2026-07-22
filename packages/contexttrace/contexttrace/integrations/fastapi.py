from __future__ import annotations

import asyncio
import fnmatch
import inspect
import json
import time
from typing import Any, Awaitable, Callable, Dict, Optional

from contexttrace.client import ContextTrace

ASGIApp = Callable[..., Awaitable[None]]
Extractor = Callable[..., Dict[str, Any]]
ShouldTrace = Callable[[Dict[str, Any]], bool]


class ContextTraceFastAPIMiddleware:
    """ASGI middleware for tracing RAG-style FastAPI endpoints.

    The middleware tees bounded JSON request and response bodies while forwarding ASGI
    messages immediately. Custom extractors can return:
    query, metadata, retrieved_chunks, selected_context, answer, citations, model, and usage.
    """

    def __init__(
        self,
        app: ASGIApp,
        *,
        client: Optional[ContextTrace] = None,
        api_key: Optional[str] = None,
        project: str = "default",
        base_url: str = "http://localhost:8000",
        mode: Optional[str] = None,
        request_extractor: Optional[Extractor] = None,
        response_extractor: Optional[Extractor] = None,
        should_trace: Optional[ShouldTrace] = None,
        trace_metadata: Optional[dict[str, Any]] = None,
        raise_logging_errors: bool = False,
        max_capture_bytes: int = 1_048_576,
        content_type_allowlist: tuple[str, ...] = ("application/json",),
        route_allowlist: tuple[str, ...] | None = None,
        background_logging: bool = False,
        max_pending_logs: int = 100,
    ) -> None:
        self.app = app
        self.client = client or ContextTrace(
            api_key=api_key,
            project=project,
            base_url=base_url,
            mode=mode,
        )
        self.request_extractor = request_extractor or default_request_extractor
        self.response_extractor = response_extractor or default_response_extractor
        self.should_trace = should_trace
        self.trace_metadata = trace_metadata or {}
        self.raise_logging_errors = raise_logging_errors
        if max_capture_bytes < 0:
            raise ValueError("max_capture_bytes must be zero or greater.")
        if max_pending_logs < 1:
            raise ValueError("max_pending_logs must be at least one.")
        self.max_capture_bytes = max_capture_bytes
        self.content_type_allowlist = tuple(item.lower() for item in content_type_allowlist)
        self.route_allowlist = route_allowlist
        self.background_logging = background_logging
        self.max_pending_logs = max_pending_logs
        self._pending_logs: set[asyncio.Task[Any]] = set()
        self.metrics = {
            "traces_attempted": 0,
            "logging_failures": 0,
            "logging_dropped": 0,
            "request_capture_truncated": 0,
            "response_capture_truncated": 0,
            "streaming_responses_skipped": 0,
        }

    async def __call__(
        self,
        scope: dict[str, Any],
        receive: Callable[[], Awaitable[dict[str, Any]]],
        send: Callable[[dict[str, Any]], Awaitable[None]],
    ) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        request_info = _request_info(scope, b"")
        if not _route_allowed(str(request_info.get("path") or ""), self.route_allowlist):
            await self.app(scope, receive, send)
            return
        if not _content_type_allowed(request_info.get("headers") or {}, self.content_type_allowlist):
            await self.app(scope, receive, send)
            return
        if self.should_trace and not self.should_trace(request_info):
            await self.app(scope, receive, send)
            return

        start_time = time.perf_counter()
        request_capture = _BodyCapture(self.max_capture_bytes)
        response_capture = _BodyCapture(self.max_capture_bytes)
        response_start: dict[str, Any] = {}

        async def capture_receive() -> dict[str, Any]:
            message = await receive()
            if message.get("type") == "http.request":
                request_capture.add(message.get("body", b""))
            return message

        async def capture_send(message: dict[str, Any]) -> None:
            if message.get("type") == "http.response.start":
                response_start.update(message)
            await send(message)
            if message.get("type") == "http.response.body":
                headers = _headers(response_start.get("headers") or [])
                if _response_capture_allowed(headers, self.content_type_allowlist):
                    response_capture.add(message.get("body", b""))

        try:
            await self.app(scope, capture_receive, capture_send)
        except BaseException as exc:
            request_info = _request_info(scope, request_capture.body)
            request_info["capture_truncated"] = request_capture.truncated
            await self._log_exception(request_info, exc, start_time)
            raise

        request_info = _request_info(scope, request_capture.body)
        request_info["capture_truncated"] = request_capture.truncated
        response_info = _response_info(
            response_start,
            response_capture,
            start_time,
            content_type_allowlist=self.content_type_allowlist,
        )
        if request_capture.truncated:
            self.metrics["request_capture_truncated"] += 1
        if response_capture.truncated:
            self.metrics["response_capture_truncated"] += 1
        if response_info.get("streaming_capture_skipped"):
            self.metrics["streaming_responses_skipped"] += 1
        await self._submit_log(self._log_trace(request_info, response_info))

    async def drain(self) -> None:
        """Wait for background trace writes, normally during application shutdown."""

        if self._pending_logs:
            await asyncio.gather(*tuple(self._pending_logs), return_exceptions=True)

    async def _submit_log(self, operation: Awaitable[None]) -> None:
        self.metrics["traces_attempted"] += 1
        if not self.background_logging or self.raise_logging_errors:
            await operation
            return
        if len(self._pending_logs) >= self.max_pending_logs:
            self.metrics["logging_dropped"] += 1
            operation.close() if inspect.iscoroutine(operation) else None
            return
        task = asyncio.create_task(operation)
        self._pending_logs.add(task)
        task.add_done_callback(self._background_log_done)
        await asyncio.sleep(0)

    def _background_log_done(self, task: asyncio.Task[Any]) -> None:
        self._pending_logs.discard(task)
        try:
            task.result()
        except BaseException:
            self.metrics["logging_failures"] += 1

    async def _log_exception(
        self,
        request_info: dict[str, Any],
        exc: BaseException,
        start_time: float,
    ) -> None:
        try:
            extracted = await _call_extractor(self.request_extractor, request_info)
            query = extracted.get("query") or request_info.get("path") or "unknown request"
            with self.client.trace(
                query=str(query),
                metadata={
                    **self.trace_metadata,
                    **(extracted.get("metadata") or {}),
                    "integration": "fastapi",
                    "http": _http_metadata(request_info),
                },
            ) as trace:
                trace.log_agent_error(
                    str(exc),
                    name="fastapi_endpoint_error",
                    metadata={"error_type": exc.__class__.__name__},
                    latency_ms=_elapsed_ms(start_time),
                )
        except Exception:
            self.metrics["logging_failures"] += 1
            if self.raise_logging_errors:
                raise

    async def _log_trace(
        self,
        request_info: dict[str, Any],
        response_info: dict[str, Any],
    ) -> None:
        try:
            request_data = await _call_extractor(self.request_extractor, request_info)
            response_data = await _call_extractor(self.response_extractor, response_info, request_info)
            payload = {**request_data, **response_data}
            query = payload.get("query") or request_info.get("path") or "unknown request"
            metadata = {
                **self.trace_metadata,
                **(request_data.get("metadata") or {}),
                **(response_data.get("metadata") or {}),
                "integration": "fastapi",
                "http": _http_metadata(request_info, response_info),
                "capture": {
                    "request_truncated": bool(request_info.get("capture_truncated")),
                    "response_truncated": bool(response_info.get("capture_truncated")),
                    "streaming_capture_skipped": bool(response_info.get("streaming_capture_skipped")),
                    "max_capture_bytes": self.max_capture_bytes,
                },
            }

            with self.client.trace(query=str(query), metadata=metadata) as trace:
                retrieved = payload.get("retrieved_chunks") or payload.get("chunks") or []
                selected = payload.get("selected_context") or payload.get("context") or []
                citations = payload.get("citations") or []
                answer = payload.get("answer")

                if retrieved:
                    trace.log_retrieval(
                        retrieved,
                        retriever_name=payload.get("retriever_name") or "fastapi_endpoint",
                        metadata={"source": "fastapi_response"},
                    )
                if selected:
                    trace.log_context(selected, metadata={"source": "fastapi_response"})
                if answer:
                    trace.log_answer(
                        str(answer),
                        model=payload.get("model"),
                        usage=payload.get("usage") or {},
                        metadata={"latency_ms": response_info.get("latency_ms")},
                    )
                if citations:
                    trace.log_citations(citations)
        except Exception:
            self.metrics["logging_failures"] += 1
            if self.raise_logging_errors:
                raise


def default_request_extractor(request: dict[str, Any]) -> dict[str, Any]:
    body = request.get("json")
    if not isinstance(body, dict):
        return {"query": request.get("path"), "metadata": {}}
    query = _first_string(body, "query", "question", "input", "prompt")
    return {
        "query": query or request.get("path"),
        "metadata": body.get("metadata") if isinstance(body.get("metadata"), dict) else {},
        "retrieved_chunks": body.get("retrieved_chunks") or body.get("chunks") or [],
        "selected_context": body.get("selected_context") or body.get("context") or [],
        "citations": _citations(body.get("citations") or []),
    }


def default_response_extractor(response: dict[str, Any], request: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    body = response.get("json")
    if not isinstance(body, dict):
        return {}
    return {
        "answer": _first_string(body, "answer", "response", "output", "result", "text"),
        "metadata": body.get("metadata") if isinstance(body.get("metadata"), dict) else {},
        "retrieved_chunks": body.get("retrieved_chunks") or body.get("contexts") or body.get("chunks") or [],
        "selected_context": body.get("selected_context") or body.get("context") or [],
        "citations": _citations(body.get("citations") or body.get("sources") or []),
        "model": body.get("model"),
        "usage": body.get("usage") if isinstance(body.get("usage"), dict) else {},
    }


def _request_info(scope: dict[str, Any], body: bytes) -> dict[str, Any]:
    headers = _headers(scope.get("headers", []))
    return {
        "method": scope.get("method"),
        "path": scope.get("path"),
        "headers": headers,
        "body": body,
        "json": _decode_json(body),
        "scope": scope,
    }


def _response_info(
    start_message: dict[str, Any],
    capture: "_BodyCapture",
    start_time: float,
    *,
    content_type_allowlist: tuple[str, ...],
) -> dict[str, Any]:
    headers = _headers(start_message.get("headers") or [])
    body = capture.body
    capture_allowed = _response_capture_allowed(headers, content_type_allowlist)
    return {
        "status_code": start_message.get("status"),
        "headers": headers,
        "body": body,
        "json": _decode_json(body),
        "latency_ms": _elapsed_ms(start_time),
        "capture_truncated": capture.truncated,
        "streaming_capture_skipped": not capture_allowed,
    }


class _BodyCapture:
    def __init__(self, limit: int) -> None:
        self.limit = limit
        self.parts: list[bytes] = []
        self.size = 0
        self.truncated = False

    @property
    def body(self) -> bytes:
        return b"".join(self.parts)

    def add(self, value: Any) -> None:
        chunk = bytes(value or b"")
        remaining = max(0, self.limit - self.size)
        if len(chunk) > remaining:
            self.truncated = True
        if remaining:
            captured = chunk[:remaining]
            self.parts.append(captured)
            self.size += len(captured)


def _headers(raw_headers: Any) -> dict[str, str]:
    return {
        key.decode("latin1").lower(): value.decode("latin1")
        for key, value in raw_headers
    }


def _route_allowed(path: str, allowlist: tuple[str, ...] | None) -> bool:
    if allowlist is None:
        return True
    return any(fnmatch.fnmatch(path, pattern) for pattern in allowlist)


def _content_type_allowed(headers: dict[str, str], allowlist: tuple[str, ...]) -> bool:
    content_type = str(headers.get("content-type") or "").split(";", 1)[0].strip().lower()
    if not content_type:
        return True
    return any(content_type == allowed or (allowed.endswith("/*") and content_type.startswith(allowed[:-1])) for allowed in allowlist)


def _response_capture_allowed(headers: dict[str, str], allowlist: tuple[str, ...]) -> bool:
    content_type = str(headers.get("content-type") or "").split(";", 1)[0].strip().lower()
    disposition = str(headers.get("content-disposition") or "").lower()
    if content_type == "text/event-stream" or "attachment" in disposition:
        return False
    if content_type.endswith("+json"):
        return True
    return _content_type_allowed(headers, allowlist)


async def _call_extractor(extractor: Extractor, *args: Any) -> dict[str, Any]:
    try:
        value = extractor(*args)
    except TypeError:
        value = extractor(args[0])
    if inspect.isawaitable(value):
        value = await value
    if not isinstance(value, dict):
        raise ValueError("ContextTrace extractor must return a dictionary.")
    return value


def _decode_json(body: bytes) -> Any:
    if not body:
        return None
    try:
        return json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None


def _first_string(data: dict[str, Any], *keys: str) -> Optional[str]:
    for key in keys:
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return None


def _citations(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    citations = []
    for citation in value:
        if not isinstance(citation, dict):
            continue
        claim = citation.get("claim")
        source_chunk_id = citation.get("source_chunk_id") or citation.get("chunk_id") or citation.get("source")
        if claim and source_chunk_id:
            citations.append({"claim": str(claim), "source_chunk_id": str(source_chunk_id)})
    return citations


def _http_metadata(
    request: dict[str, Any],
    response: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    metadata = {
        "method": request.get("method"),
        "path": request.get("path"),
    }
    if response is not None:
        metadata["status_code"] = response.get("status_code")
        metadata["latency_ms"] = response.get("latency_ms")
    return metadata


def _elapsed_ms(start_time: float) -> int:
    return int((time.perf_counter() - start_time) * 1000)
