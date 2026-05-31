from __future__ import annotations

import time
from typing import Any, Iterable, Optional

from contexttrace.client import ContextTrace

try:
    from langchain_core.callbacks import BaseCallbackHandler
except Exception:  # pragma: no cover - exercised when langchain is not installed
    BaseCallbackHandler = object  # type: ignore[assignment]


class ContextTraceCallbackHandler(BaseCallbackHandler):  # type: ignore[misc]
    def __init__(
        self,
        *,
        project: Optional[str] = None,
        api_key: Optional[str] = None,
        base_url: str = "http://localhost:8000",
        client: Optional[ContextTrace] = None,
        trace_metadata: Optional[dict[str, Any]] = None,
        selected_context_limit: Optional[int] = None,
    ) -> None:
        if client is None:
            if not api_key:
                raise ValueError("api_key is required when client is not provided.")
            if not project:
                raise ValueError("project is required when client is not provided.")
            client = ContextTrace(api_key=api_key, project=project, base_url=base_url)

        self.client = client
        self.trace_metadata = trace_metadata or {}
        self.selected_context_limit = selected_context_limit
        self.trace = None
        self.query: Optional[str] = None
        self.retrieved_chunks: list[dict[str, Any]] = []
        self.start_time: Optional[float] = None
        self.llm_model: Optional[str] = None
        self.llm_usage: dict[str, Any] = {}
        self.answer_logged = False

    def on_chain_start(
        self,
        serialized: dict[str, Any],
        inputs: Any,
        **kwargs: Any,
    ) -> None:
        query = _extract_query(inputs)
        if query:
            self._ensure_trace(
                query=query,
                event="chain_start",
                metadata=_event_metadata(serialized, kwargs),
            )

    def on_retriever_start(
        self,
        serialized: dict[str, Any],
        query: str,
        **kwargs: Any,
    ) -> None:
        self._ensure_trace(
            query=query,
            event="retriever_start",
            metadata=_event_metadata(serialized, kwargs),
        )

    def on_retriever_end(self, documents: Iterable[Any], **kwargs: Any) -> None:
        chunks = [langchain_document_to_chunk(document, index) for index, document in enumerate(documents)]
        self.retrieved_chunks = chunks

        if self.trace is None:
            self._ensure_trace(
                query=self.query or "unknown query",
                event="retriever_end",
                metadata=_event_metadata(None, kwargs),
            )

        if not chunks or self.trace is None:
            return

        self.trace.log_retrieval(
            chunks,
            retriever_name=_serialized_name(kwargs.get("serialized")) or "langchain_retriever",
            metadata=_event_metadata(None, kwargs),
        )
        selected = chunks[: self.selected_context_limit] if self.selected_context_limit else chunks
        self.trace.log_context(
            selected,
            metadata={
                "source": "langchain_retriever_end",
                "selected_context_limit": self.selected_context_limit,
            },
        )

    def on_llm_end(self, response: Any, **kwargs: Any) -> None:
        self.llm_usage = _extract_token_usage(response)
        self.llm_model = _extract_model(response)

    def on_chain_end(self, outputs: Any, **kwargs: Any) -> None:
        answer = _extract_answer(outputs)
        if not answer:
            return

        if self.trace is None:
            self._ensure_trace(
                query=self.query or "unknown query",
                event="chain_end",
                metadata=_event_metadata(None, kwargs),
            )

        if self.trace is None or self.answer_logged:
            return

        self.trace.log_answer(
            answer,
            model=self.llm_model,
            usage=self.llm_usage,
            metadata={
                "latency_ms": self._latency_ms(),
                "langchain_output_keys": list(outputs.keys()) if isinstance(outputs, dict) else [],
            },
        )
        self.answer_logged = True

    def on_chain_error(self, error: BaseException, **kwargs: Any) -> None:
        if self.trace is not None and not self.answer_logged:
            self.trace.log_answer(
                "LangChain run failed before producing an answer.",
                metadata={
                    "latency_ms": self._latency_ms(),
                    "error": str(error),
                    "error_type": error.__class__.__name__,
                },
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
                "integration": "langchain",
                "start_event": event,
                "langchain": metadata,
            }
        )
        self.trace = self.client.trace(query=query, metadata=trace_metadata).__enter__()

    def _latency_ms(self) -> int:
        if self.start_time is None:
            return 0
        return int((time.perf_counter() - self.start_time) * 1000)


def langchain_document_to_chunk(document: Any, index: int = 0) -> dict[str, Any]:
    metadata = getattr(document, "metadata", None) or {}
    if not isinstance(metadata, dict):
        metadata = {"metadata": metadata}

    content = (
        getattr(document, "page_content", None)
        or getattr(document, "content", None)
        or getattr(document, "text", None)
    )
    if content is None and isinstance(document, dict):
        content = document.get("page_content") or document.get("content") or document.get("text")
        metadata = document.get("metadata") or metadata

    if content is None:
        raise ValueError("LangChain document must include page_content, content, or text.")

    chunk_id = (
        metadata.get("chunk_id")
        or metadata.get("id")
        or metadata.get("doc_id")
        or getattr(document, "id", None)
        or f"langchain_doc_{index}"
    )
    source = metadata.get("source") or metadata.get("url") or metadata.get("path")
    relevance_score = (
        metadata.get("relevance_score")
        or metadata.get("score")
        or getattr(document, "score", None)
    )

    return {
        "chunk_id": str(chunk_id),
        "content": str(content),
        "source": source,
        "metadata": metadata,
        "relevance_score": relevance_score,
    }


def _extract_query(inputs: Any) -> Optional[str]:
    if isinstance(inputs, str):
        return inputs
    if not isinstance(inputs, dict):
        return None

    for key in ("query", "question", "input", "prompt"):
        value = inputs.get(key)
        if isinstance(value, str) and value.strip():
            return value

    for value in inputs.values():
        if isinstance(value, str) and value.strip():
            return value
    return None


def _extract_answer(outputs: Any) -> Optional[str]:
    if isinstance(outputs, str):
        return outputs
    if not isinstance(outputs, dict):
        return None

    for key in ("answer", "output", "result", "text", "response"):
        value = outputs.get(key)
        if isinstance(value, str) and value.strip():
            return value

    for value in outputs.values():
        if isinstance(value, str) and value.strip():
            return value
    return None


def _extract_token_usage(response: Any) -> dict[str, Any]:
    llm_output = getattr(response, "llm_output", None) or {}
    if isinstance(llm_output, dict):
        token_usage = llm_output.get("token_usage") or llm_output.get("usage")
        if isinstance(token_usage, dict):
            return token_usage
    return {}


def _extract_model(response: Any) -> Optional[str]:
    llm_output = getattr(response, "llm_output", None) or {}
    if isinstance(llm_output, dict):
        model = llm_output.get("model_name") or llm_output.get("model")
        if isinstance(model, str):
            return model
    return None


def _event_metadata(serialized: Any, kwargs: dict[str, Any]) -> dict[str, Any]:
    metadata: dict[str, Any] = {}
    name = _serialized_name(serialized)
    if name:
        metadata["serialized_name"] = name

    callback_metadata = kwargs.get("metadata")
    if isinstance(callback_metadata, dict):
        metadata["metadata"] = callback_metadata

    tags = kwargs.get("tags")
    if tags:
        metadata["tags"] = list(tags)

    run_id = kwargs.get("run_id")
    if run_id is not None:
        metadata["run_id"] = str(run_id)

    parent_run_id = kwargs.get("parent_run_id")
    if parent_run_id is not None:
        metadata["parent_run_id"] = str(parent_run_id)

    return metadata


def _serialized_name(serialized: Any) -> Optional[str]:
    if not isinstance(serialized, dict):
        return None
    name = serialized.get("name")
    if isinstance(name, str):
        return name
    serialized_id = serialized.get("id")
    if isinstance(serialized_id, list) and serialized_id:
        return str(serialized_id[-1])
    if isinstance(serialized_id, str):
        return serialized_id
    return None
