from __future__ import annotations

import time
from typing import Any, Callable, Dict, Iterable, Optional

from contexttrace.client import ContextTrace

try:
    from llama_index.core.callbacks.base_handler import BaseCallbackHandler
except Exception:  # pragma: no cover - exercised when llama-index-core is not installed
    BaseCallbackHandler = object  # type: ignore[assignment]


QueryExtractor = Callable[[Any], Optional[str]]
ResponseExtractor = Callable[[Any], Optional[str]]
NodeConverter = Callable[[Any, int], Dict[str, Any]]


class ContextTraceLlamaIndexCallbackHandler(BaseCallbackHandler):  # type: ignore[misc]
    def __init__(
        self,
        *,
        project: Optional[str] = None,
        api_key: Optional[str] = None,
        base_url: str = "http://localhost:8000",
        client: Optional[ContextTrace] = None,
        trace_metadata: Optional[dict[str, Any]] = None,
        selected_context_limit: Optional[int] = None,
        query_extractor: Optional[QueryExtractor] = None,
        response_extractor: Optional[ResponseExtractor] = None,
        node_converter: Optional[NodeConverter] = None,
    ) -> None:
        try:
            super().__init__(event_starts_to_ignore=[], event_ends_to_ignore=[])
        except TypeError:
            try:
                super().__init__()
            except TypeError:
                pass

        self.event_starts_to_ignore = []
        self.event_ends_to_ignore = []

        if client is None:
            kwargs: dict[str, Any] = {"project": project or "default"}
            if api_key:
                kwargs.update({"api_key": api_key, "base_url": base_url, "mode": "hosted"})
            client = ContextTrace(**kwargs)

        self.client = client
        self.trace_metadata = trace_metadata or {}
        self.selected_context_limit = selected_context_limit
        self.query_extractor = query_extractor or _extract_query
        self.response_extractor = response_extractor or _extract_response_text
        self.node_converter = node_converter or llamaindex_node_to_chunk
        self.trace = None
        self.query: Optional[str] = None
        self.start_time: Optional[float] = None
        self.retrieve_start_time: Optional[float] = None
        self.retrieved_chunks: list[dict[str, Any]] = []
        self.source_chunks: list[dict[str, Any]] = []
        self.answer_logged = False

    def start_trace(self, trace_id: Optional[str] = None) -> None:
        return None

    def end_trace(
        self,
        trace_id: Optional[str] = None,
        trace_map: Optional[dict[str, list[str]]] = None,
    ) -> None:
        return None

    def on_event_start(
        self,
        event_type: Any,
        payload: Optional[dict[str, Any]] = None,
        event_id: str = "",
        parent_id: str = "",
        **kwargs: Any,
    ) -> str:
        if _event_matches(event_type, "query"):
            query = self.query_extractor(payload)
            if query:
                self._ensure_trace(
                    query=query,
                    event="query_start",
                    metadata=_event_metadata(event_type, payload, event_id, parent_id, kwargs),
                )
        if _event_matches(event_type, "retrieve", "retriever"):
            self.retrieve_start_time = time.perf_counter()
        return event_id

    def on_event_end(
        self,
        event_type: Any,
        payload: Optional[dict[str, Any]] = None,
        event_id: str = "",
        **kwargs: Any,
    ) -> None:
        if _event_matches(event_type, "retrieve", "retriever"):
            self._handle_retrieval_end(event_type, payload, event_id, kwargs)
            return

        if _event_matches(event_type, "query", "synthesize", "response"):
            self._handle_response_end(event_type, payload, event_id, kwargs)

    def trace_query(self, query: str, *, metadata: Optional[dict[str, Any]] = None) -> None:
        self._ensure_trace(query=query, event="manual_query", metadata=metadata or {})

    def trace_retrieved_nodes(self, nodes: Iterable[Any], *, metadata: Optional[dict[str, Any]] = None) -> None:
        self._log_retrieved_nodes(nodes, metadata=metadata or {})

    def trace_response(self, response: Any, *, metadata: Optional[dict[str, Any]] = None) -> None:
        self._log_response(response, metadata=metadata or {})

    def _handle_retrieval_end(
        self,
        event_type: Any,
        payload: Optional[dict[str, Any]],
        event_id: str,
        kwargs: dict[str, Any],
    ) -> None:
        nodes = _extract_nodes(payload, keys=("nodes", "source_nodes", "documents"))
        metadata = _event_metadata(event_type, payload, event_id, None, kwargs)
        self._log_retrieved_nodes(nodes, metadata=metadata)

    def _handle_response_end(
        self,
        event_type: Any,
        payload: Optional[dict[str, Any]],
        event_id: str,
        kwargs: dict[str, Any],
    ) -> None:
        response = _payload_get(payload, "response", "output", "result")
        if response is None and payload:
            response = payload
        metadata = _event_metadata(event_type, payload, event_id, None, kwargs)
        self._log_response(response, metadata=metadata)

    def _log_retrieved_nodes(self, nodes: Iterable[Any], *, metadata: dict[str, Any]) -> None:
        chunks = [self.node_converter(node, index) for index, node in enumerate(nodes or [])]
        self.retrieved_chunks = chunks

        if self.trace is None:
            self._ensure_trace(
                query=self.query or "unknown query",
                event="retrieve_end",
                metadata=metadata,
            )

        if self.trace is None or not chunks:
            return

        self.trace.log_retrieval(
            chunks,
            retriever_name="llamaindex_retriever",
            metadata={
                **metadata,
                "latency_ms": _elapsed_ms(self.retrieve_start_time),
            },
        )

    def _log_response(self, response: Any, *, metadata: dict[str, Any]) -> None:
        answer = self.response_extractor(response)
        source_nodes = _extract_source_nodes(response)
        source_chunks = [
            self.node_converter(node, index) for index, node in enumerate(source_nodes)
        ]
        self.source_chunks = source_chunks

        if self.trace is None:
            self._ensure_trace(
                query=self.query or self.query_extractor(response) or "unknown query",
                event="response_end",
                metadata=metadata,
            )

        if self.trace is None:
            return

        selected_chunks = source_chunks or self.retrieved_chunks
        if self.selected_context_limit:
            selected_chunks = selected_chunks[: self.selected_context_limit]
        if selected_chunks:
            self.trace.log_context(
                selected_chunks,
                metadata={
                    "source": "llamaindex_source_nodes" if source_chunks else "llamaindex_retrieved_nodes",
                    "source_node_count": len(source_chunks),
                    "retrieved_node_count": len(self.retrieved_chunks),
                },
            )

        if answer and not self.answer_logged:
            answer_metadata = dict(metadata)
            answer_metadata.update(
                {
                    "latency_ms": self._latency_ms(),
                    "source_node_count": len(source_chunks),
                    "retrieved_node_count": len(self.retrieved_chunks),
                }
            )
            self.trace.log_answer(
                answer,
                metadata=answer_metadata,
            )
            self.answer_logged = True

    def _ensure_trace(
        self,
        *,
        query: str,
        event: str,
        metadata: dict[str, Any],
    ) -> None:
        if self.trace is not None:
            return

        self.query = query
        self.start_time = time.perf_counter()
        trace_metadata = dict(self.trace_metadata)
        trace_metadata.update(
            {
                "integration": "llamaindex",
                "start_event": event,
                "llamaindex": metadata,
            }
        )
        self.trace = self.client.trace(query=query, metadata=trace_metadata).__enter__()

    def _latency_ms(self) -> int:
        if self.start_time is None:
            return 0
        return int((time.perf_counter() - self.start_time) * 1000)


def llamaindex_node_to_chunk(node_or_node_with_score: Any, index: int = 0) -> dict[str, Any]:
    node = getattr(node_or_node_with_score, "node", node_or_node_with_score)
    score = getattr(node_or_node_with_score, "score", None)
    metadata = _node_metadata(node)
    content = _node_content(node)
    if content is None:
        raise ValueError("LlamaIndex node must include text, content, or get_content().")

    chunk_id = (
        metadata.get("chunk_id")
        or metadata.get("id")
        or metadata.get("doc_id")
        or getattr(node, "node_id", None)
        or getattr(node, "id_", None)
        or getattr(node, "id", None)
        or f"llamaindex_node_{index}"
    )
    source = metadata.get("source") or metadata.get("url") or metadata.get("path") or metadata.get("file_name")
    relevance_score = (
        score
        if score is not None
        else metadata.get("relevance_score") or metadata.get("score")
    )

    return {
        "chunk_id": str(chunk_id),
        "content": str(content),
        "source": source,
        "metadata": metadata,
        "relevance_score": relevance_score,
    }


def _node_metadata(node: Any) -> dict[str, Any]:
    metadata = getattr(node, "metadata", None)
    if metadata is None:
        metadata = getattr(node, "extra_info", None)
    if isinstance(node, dict):
        metadata = node.get("metadata") or node.get("extra_info") or metadata
    if not isinstance(metadata, dict):
        return {"metadata": metadata} if metadata is not None else {}
    return metadata


def _node_content(node: Any) -> Optional[str]:
    get_content = getattr(node, "get_content", None)
    if callable(get_content):
        try:
            content = get_content()
            if content is not None:
                return str(content)
        except TypeError:
            pass

    for attr in ("text", "content", "page_content"):
        value = getattr(node, attr, None)
        if value is not None:
            return str(value)

    text_resource = getattr(node, "text_resource", None)
    value = getattr(text_resource, "text", None)
    if value is not None:
        return str(value)

    if isinstance(node, dict):
        for key in ("text", "content", "page_content"):
            value = node.get(key)
            if value is not None:
                return str(value)
    return None


def _event_matches(event_type: Any, *names: str) -> bool:
    event_name = _event_name(event_type)
    return event_name in names


def _event_name(event_type: Any) -> str:
    for attr in ("value", "name"):
        value = getattr(event_type, attr, None)
        if isinstance(value, str):
            return value.lower()
    text = str(event_type).lower()
    return text.rsplit(".", 1)[-1]


def _payload_get(payload: Any, *keys: str) -> Any:
    if not isinstance(payload, dict):
        return None

    normalized = {key.lower() for key in keys}
    for key, value in payload.items():
        variants = {str(key).lower()}
        name = getattr(key, "name", None)
        if isinstance(name, str):
            variants.add(name.lower())
        key_value = getattr(key, "value", None)
        if isinstance(key_value, str):
            variants.add(key_value.lower())
        if variants & normalized:
            return value
    return None


def _extract_query(value: Any) -> Optional[str]:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        result = _payload_get(value, "query_str", "query", "question", "input", "prompt")
        if isinstance(result, str) and result.strip():
            return result
    response = getattr(value, "query", None)
    if isinstance(response, str) and response.strip():
        return response
    return None


def _extract_nodes(payload: Any, *, keys: tuple[str, ...]) -> Iterable[Any]:
    nodes = _payload_get(payload, *keys)
    if nodes is None:
        return []
    return nodes


def _extract_response_text(response: Any) -> Optional[str]:
    if isinstance(response, str):
        return response
    if isinstance(response, dict):
        for key in ("response", "answer", "output", "result", "text"):
            value = response.get(key)
            if isinstance(value, str) and value.strip():
                return value
    for attr in ("response", "answer", "output", "text"):
        value = getattr(response, attr, None)
        if isinstance(value, str) and value.strip():
            return value
    if response is not None:
        text = str(response)
        return text if text and not text.startswith("<") else None
    return None


def _extract_source_nodes(response: Any) -> list[Any]:
    if isinstance(response, dict):
        nodes = response.get("source_nodes") or response.get("nodes")
        return list(nodes or [])
    nodes = getattr(response, "source_nodes", None)
    if nodes is None:
        nodes = getattr(response, "source_nodes_with_scores", None)
    return list(nodes or [])


def _elapsed_ms(start_time: Optional[float]) -> Optional[int]:
    if start_time is None:
        return None
    return int((time.perf_counter() - start_time) * 1000)


def _event_metadata(
    event_type: Any,
    payload: Optional[dict[str, Any]],
    event_id: Optional[str],
    parent_id: Optional[str],
    kwargs: dict[str, Any],
) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "event_type": _event_name(event_type),
    }
    if event_id:
        metadata["event_id"] = event_id
    if parent_id:
        metadata["parent_id"] = parent_id

    callback_metadata = kwargs.get("metadata")
    if isinstance(callback_metadata, dict):
        metadata["metadata"] = callback_metadata

    if payload:
        payload_keys = []
        for key in payload.keys():
            name = getattr(key, "name", None) or getattr(key, "value", None) or str(key)
            payload_keys.append(str(name))
        metadata["payload_keys"] = payload_keys

    return metadata
