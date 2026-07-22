from __future__ import annotations

import inspect
import time
from contextvars import ContextVar
from dataclasses import dataclass, field
from functools import wraps
from typing import Any, Callable, Optional

from contexttrace.client import ContextTrace, TraceSession


@dataclass
class _RunState:
    trace: Optional[TraceSession] = None
    query: Optional[str] = None
    node_starts: dict[str, float] = field(default_factory=dict)


class ContextTraceLangGraphTracer:
    """Beta LangGraph adapter for logging graph nodes, tools, memory, and errors."""

    def __init__(
        self,
        *,
        project: Optional[str] = None,
        api_key: Optional[str] = None,
        base_url: str = "http://localhost:8000",
        client: Optional[ContextTrace] = None,
        trace_metadata: Optional[dict[str, Any]] = None,
    ) -> None:
        if client is None:
            kwargs: dict[str, Any] = {"project": project or "default"}
            if api_key:
                kwargs.update({"api_key": api_key, "base_url": base_url, "mode": "hosted"})
            client = ContextTrace(**kwargs)
        self.client = client
        self.trace_metadata = trace_metadata or {}
        self._default_state = _RunState()
        self._current_state: ContextVar[_RunState | None] = ContextVar(
            "contexttrace_langgraph_run_state", default=None
        )
        self._run_states: dict[str, _RunState] = {}

    def start_trace(
        self,
        query: str,
        *,
        metadata: Optional[dict[str, Any]] = None,
        run_id: str | None = None,
    ) -> TraceSession:
        state = self._activate(run_id, create=True)
        if self.trace is not None:
            return self.trace
        self.query = query
        trace_metadata = {
            **self.trace_metadata,
            **(metadata or {}),
            "integration": "langgraph",
        }
        self.trace = self.client.trace(query=query, metadata=trace_metadata).__enter__()
        if run_id:
            self._run_states[str(run_id)] = state
        return self.trace

    def end_trace(
        self,
        *,
        answer: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
        run_id: str | None = None,
    ) -> Optional[TraceSession]:
        state = self._activate(run_id)
        if self.trace is None:
            return None
        if answer:
            self.trace.log_answer(answer, metadata=metadata or {})
            self.trace.log_agent_event(
                event_type="final_answer",
                name="final_answer",
                output_json={"answer": answer},
                metadata=metadata or {},
            )
        trace = self.trace
        self.trace = None
        self._release_state(state)
        return trace

    def on_node_start(
        self,
        name: str,
        input_json: Any = None,
        *,
        event_type: str = "planner_step",
        metadata: Optional[dict[str, Any]] = None,
        run_id: str | None = None,
    ) -> None:
        self._activate(run_id)
        trace = self._ensure_trace(input_json)
        self._node_starts[name] = time.perf_counter()
        trace.log_agent_event(
            event_type=event_type,
            name=name,
            input_json=input_json,
            metadata={"phase": "start", **(metadata or {})},
        )

    def on_node_end(
        self,
        name: str,
        output_json: Any = None,
        *,
        event_type: str = "planner_step",
        metadata: Optional[dict[str, Any]] = None,
        run_id: str | None = None,
    ) -> None:
        self._activate(run_id)
        trace = self._ensure_trace(output_json)
        trace.log_agent_event(
            event_type=event_type,
            name=name,
            output_json=output_json,
            metadata={"phase": "end", **(metadata or {})},
            latency_ms=_elapsed_ms(self._node_starts.get(name)),
        )

    def on_tool_start(
        self,
        name: str,
        input_json: Any = None,
        *,
        metadata: Optional[dict[str, Any]] = None,
        run_id: str | None = None,
    ) -> None:
        self._activate(run_id)
        self._node_starts[name] = time.perf_counter()
        self._ensure_trace(input_json).log_tool_call(name, input_json=input_json, metadata=metadata)

    def on_tool_end(
        self,
        name: str,
        output_json: Any = None,
        *,
        input_json: Any = None,
        metadata: Optional[dict[str, Any]] = None,
        run_id: str | None = None,
    ) -> None:
        self._activate(run_id)
        self._ensure_trace(output_json).log_tool_result(
            name,
            input_json=input_json,
            output_json=output_json,
            metadata=metadata,
            latency_ms=_elapsed_ms(self._node_starts.get(name)),
        )

    def on_error(
        self,
        name: str,
        error: BaseException,
        *,
        input_json: Any = None,
        run_id: str | None = None,
    ) -> None:
        self._activate(run_id)
        self._ensure_trace(input_json).log_agent_error(
            str(error),
            name=name,
            input_json=input_json,
            metadata={"error_type": error.__class__.__name__},
            latency_ms=_elapsed_ms(self._node_starts.get(name)),
        )

    def wrap_node(
        self,
        name: str,
        func: Callable[..., Any],
        *,
        event_type: str = "planner_step",
    ) -> Callable[..., Any]:
        if inspect.iscoroutinefunction(func):

            @wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                input_json = {"args": _json_safe(args), "kwargs": _json_safe(kwargs)}
                self.on_node_start(name, input_json, event_type=event_type)
                try:
                    output = await func(*args, **kwargs)
                    self.on_node_end(name, _json_safe(output), event_type=event_type)
                    return output
                except BaseException as exc:
                    self.on_error(name, exc, input_json=input_json)
                    raise

            return async_wrapper

        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            input_json = {"args": _json_safe(args), "kwargs": _json_safe(kwargs)}
            self.on_node_start(name, input_json, event_type=event_type)
            try:
                output = func(*args, **kwargs)
                self.on_node_end(name, _json_safe(output), event_type=event_type)
                return output
            except BaseException as exc:
                self.on_error(name, exc, input_json=input_json)
                raise

        return wrapper

    def _ensure_trace(self, value: Any = None) -> TraceSession:
        if self.trace is not None:
            return self.trace
        query = _query_from_value(value) or self.query or "langgraph run"
        return self.start_trace(query)

    def _activate(self, run_id: str | None, *, create: bool = False) -> _RunState:
        key = str(run_id) if run_id else ""
        state = self._run_states.get(key) if key else None
        current = self._current_state.get()
        if state is None and create and (
            key or current is None or (current.trace is None and current.query is not None)
        ):
            state = _RunState()
        if state is None:
            state = current or self._default_state
        if key:
            self._run_states[key] = state
        self._current_state.set(state)
        return state

    def _release_state(self, state: _RunState) -> None:
        for run_id in [key for key, value in self._run_states.items() if value is state]:
            self._run_states.pop(run_id, None)

    def _state(self) -> _RunState:
        return self._current_state.get() or self._default_state

    @property
    def trace(self) -> Optional[TraceSession]:
        return self._state().trace

    @trace.setter
    def trace(self, value: Optional[TraceSession]) -> None:
        self._state().trace = value

    @property
    def query(self) -> Optional[str]:
        return self._state().query

    @query.setter
    def query(self, value: Optional[str]) -> None:
        self._state().query = value

    @property
    def _node_starts(self) -> dict[str, float]:
        return self._state().node_starts


def _elapsed_ms(start_time: Optional[float]) -> Optional[int]:
    if start_time is None:
        return None
    return int((time.perf_counter() - start_time) * 1000)


def _query_from_value(value: Any) -> Optional[str]:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        for key in ("query", "question", "input", "prompt"):
            candidate = value.get(key)
            if isinstance(candidate, str) and candidate.strip():
                return candidate
    return None


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    return str(value)
