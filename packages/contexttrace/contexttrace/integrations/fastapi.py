from __future__ import annotations

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

    The middleware buffers JSON request and response bodies, extracts RAG fields, and logs a
    ContextTrace trace after the endpoint completes. Custom extractors can return:
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

    async def __call__(
        self,
        scope: dict[str, Any],
        receive: Callable[[], Awaitable[dict[str, Any]]],
        send: Callable[[dict[str, Any]], Awaitable[None]],
    ) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        request_body, request_messages = await _read_request_body(receive)
        request_info = _request_info(scope, request_body)
        if self.should_trace and not self.should_trace(request_info):
            await self.app(scope, _replay_receive(request_messages), send)
            return

        start_time = time.perf_counter()
        response_messages: list[dict[str, Any]] = []

        async def capture_send(message: dict[str, Any]) -> None:
            response_messages.append(message)

        try:
            await self.app(scope, _replay_receive(request_messages), capture_send)
        except BaseException as exc:
            await self._log_exception(request_info, exc, start_time)
            raise

        response_info = _response_info(response_messages, start_time)
        await self._log_trace(request_info, response_info)

        for message in response_messages:
            await send(message)

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


async def _read_request_body(
    receive: Callable[[], Awaitable[dict[str, Any]]],
) -> tuple[bytes, list[dict[str, Any]]]:
    body_parts: list[bytes] = []
    messages: list[dict[str, Any]] = []
    while True:
        message = await receive()
        messages.append(message)
        if message.get("type") != "http.request":
            break
        body_parts.append(message.get("body", b""))
        if not message.get("more_body", False):
            break
    return b"".join(body_parts), messages


def _replay_receive(messages: list[dict[str, Any]]) -> Callable[[], Awaitable[dict[str, Any]]]:
    pending = list(messages)

    async def receive() -> dict[str, Any]:
        if pending:
            return pending.pop(0)
        return {"type": "http.request", "body": b"", "more_body": False}

    return receive


def _request_info(scope: dict[str, Any], body: bytes) -> dict[str, Any]:
    headers = {
        key.decode("latin1").lower(): value.decode("latin1")
        for key, value in scope.get("headers", [])
    }
    return {
        "method": scope.get("method"),
        "path": scope.get("path"),
        "headers": headers,
        "body": body,
        "json": _decode_json(body),
        "scope": scope,
    }


def _response_info(messages: list[dict[str, Any]], start_time: float) -> dict[str, Any]:
    status_code = None
    headers: dict[str, str] = {}
    body_parts: list[bytes] = []
    for message in messages:
        if message.get("type") == "http.response.start":
            status_code = message.get("status")
            headers = {
                key.decode("latin1").lower(): value.decode("latin1")
                for key, value in message.get("headers", [])
            }
        if message.get("type") == "http.response.body":
            body_parts.append(message.get("body", b""))
    body = b"".join(body_parts)
    return {
        "status_code": status_code,
        "headers": headers,
        "body": body,
        "json": _decode_json(body),
        "latency_ms": _elapsed_ms(start_time),
    }


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
