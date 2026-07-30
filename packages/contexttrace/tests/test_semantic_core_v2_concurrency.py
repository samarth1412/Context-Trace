from __future__ import annotations

import time

import pytest

from contexttrace.verify.schema import RAGTrace, TraceContext
from contexttrace.verify.semantic_core_v2 import (
    DETERMINISTIC_ONLY_V2_PROFILE,
    verify_trace_v2,
    verify_traces_v2,
)


def _trace(index: int) -> RAGTrace:
    text = f"Policy {index} permits returns within 30 days."
    return RAGTrace(
        query=f"What does policy {index} permit?",
        answer=text,
        contexts=[
            TraceContext(
                id=f"context-{index}",
                text=text,
                metadata={"canonical": True, "current": True},
            )
        ],
        metadata={"case_id": f"case-{index}", "private": f"secret-{index}"},
    )


def test_bounded_concurrent_results_preserve_order_and_isolation() -> None:
    traces = [_trace(index) for index in range(24)]
    results = verify_traces_v2(
        traces,
        profile=DETERMINISTIC_ONLY_V2_PROFILE,
        max_workers=4,
    )
    assert [result["input_identity"]["metadata"]["case_id"] for result in results] == [
        f"case-{index}" for index in range(24)
    ]
    for index, result in enumerate(results):
        serialized = str(result)
        assert f"secret-{index}" not in serialized
        assert result["claims"][0]["evidence_context_ids"] == [f"context-{index}"]


def test_concurrent_and_serial_predictions_are_identical() -> None:
    traces = [_trace(index) for index in range(8)]
    serial = verify_traces_v2(
        traces,
        profile=DETERMINISTIC_ONLY_V2_PROFILE,
        max_workers=1,
    )
    parallel = verify_traces_v2(
        traces,
        profile=DETERMINISTIC_ONLY_V2_PROFILE,
        max_workers=4,
    )
    assert serial == parallel


def test_single_trace_deterministic_output_is_stable() -> None:
    trace = _trace(1)
    first = verify_trace_v2(trace, profile=DETERMINISTIC_ONLY_V2_PROFILE)
    second = verify_trace_v2(trace, profile=DETERMINISTIC_ONLY_V2_PROFILE)
    assert first == second


@pytest.mark.parametrize("workers", [0, 9])
def test_worker_bound_fails_closed(workers: int) -> None:
    with pytest.raises(ValueError, match="between 1 and 8"):
        verify_traces_v2([_trace(1)], max_workers=workers)


def test_deterministic_small_batch_performance_guard() -> None:
    traces = [_trace(index) for index in range(32)]
    started = time.perf_counter()
    results = verify_traces_v2(
        traces,
        profile=DETERMINISTIC_ONLY_V2_PROFILE,
        max_workers=4,
    )
    elapsed = time.perf_counter() - started
    assert len(results) == 32
    assert elapsed < 10.0
