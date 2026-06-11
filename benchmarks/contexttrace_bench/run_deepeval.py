from __future__ import annotations

import argparse
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Callable

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from adapt_candidate import adapt_candidate_rows, write_candidate  # noqa: E402
from baseline_common import (  # noqa: E402
    load_raw_rows,
    load_candidate_inputs,
    metric_reason,
    response,
    retrieved_contexts,
    score_value,
    user_input,
    write_json,
)


DEFAULT_INPUT = SCRIPT_DIR / "out" / "candidate_inputs.jsonl"
DEFAULT_RAW_OUTPUT = SCRIPT_DIR / "out" / "deepeval_raw_results.json"
DEFAULT_CANDIDATE_OUTPUT = SCRIPT_DIR / "out" / "deepeval_predictions.json"


def build_deepeval_rows(candidate_inputs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "id": str(row.get("id") or ""),
            "input": user_input(row),
            "actual_output": response(row),
            "retrieval_context": retrieved_contexts(row),
        }
        for row in candidate_inputs
    ]


def run_deepeval_baseline(
    candidate_inputs: list[dict[str, Any]],
    *,
    model: str | None = None,
    include_contextual_recall: bool = False,
    use_response_as_expected: bool = False,
    faithfulness_threshold: float = 0.75,
    context_recall_threshold: float = 0.50,
    existing_rows: list[dict[str, Any]] | None = None,
    max_workers: int = 1,
    progress_callback: Callable[[list[dict[str, Any]], int, int], None] | None = None,
) -> dict[str, Any]:
    input_rows = build_deepeval_rows(candidate_inputs)
    total = len(input_rows)
    outputs: list[dict[str, Any] | None] = [None] * total
    completed_by_id = {
        str(row.get("id")): row
        for row in (existing_rows or [])
        if row.get("id") and not row.get("error")
    }
    pending: list[tuple[int, dict[str, Any]]] = []

    for index, row in enumerate(input_rows):
        existing = completed_by_id.get(row["id"])
        if existing is None:
            pending.append((index, row))
        else:
            outputs[index] = existing

    completed = total - len(pending)
    if progress_callback and completed:
        progress_callback(_completed_rows(outputs), completed, total)

    worker_count = max(1, int(max_workers or 1))
    if worker_count == 1:
        for index, row in pending:
            outputs[index] = _score_deepeval_row(
                row,
                model=model,
                include_contextual_recall=include_contextual_recall,
                use_response_as_expected=use_response_as_expected,
                faithfulness_threshold=faithfulness_threshold,
                context_recall_threshold=context_recall_threshold,
            )
            completed += 1
            if progress_callback:
                progress_callback(_completed_rows(outputs), completed, total)
    else:
        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            futures = {
                executor.submit(
                    _score_deepeval_row,
                    row,
                    model=model,
                    include_contextual_recall=include_contextual_recall,
                    use_response_as_expected=use_response_as_expected,
                    faithfulness_threshold=faithfulness_threshold,
                    context_recall_threshold=context_recall_threshold,
                ): index
                for index, row in pending
            }
            for future in as_completed(futures):
                index = futures[future]
                outputs[index] = future.result()
                completed += 1
                if progress_callback:
                    progress_callback(_completed_rows(outputs), completed, total)

    rows = _completed_rows(outputs)

    candidate = adapt_candidate_rows(
        rows,
        system="DeepEval",
        version=model or "configured",
        preset="deepeval",
        faithfulness_threshold=faithfulness_threshold,
        context_recall_threshold=context_recall_threshold,
    )
    return {
        "system": "DeepEval",
        "model": model or "",
        "rows": rows,
        "candidate": candidate,
        "notes": [
            "DeepEval FaithfulnessMetric evaluates whether actual_output aligns with retrieval_context.",
            "ContextualRecallMetric requires expected_output; this runner only uses it when explicitly enabled.",
        ],
    }


def _completed_rows(rows: list[dict[str, Any] | None]) -> list[dict[str, Any]]:
    return [row for row in rows if row is not None]


def _score_deepeval_row(
    row: dict[str, Any],
    *,
    model: str | None,
    include_contextual_recall: bool,
    use_response_as_expected: bool,
    faithfulness_threshold: float,
    context_recall_threshold: float,
) -> dict[str, Any]:
    started = time.perf_counter()
    output: dict[str, Any] = {
        "id": row["id"],
        "retrieved_context_count": len(row["retrieval_context"]),
    }
    try:
        if not row["retrieval_context"]:
            output["faithfulness_score"] = 0.0
            output["contextual_recall"] = 0.0
            output["reason"] = "No retrieved contexts were supplied."
        else:
            test_case = _build_test_case(row, expected_output=row["actual_output"] if use_response_as_expected else None)
            faithfulness_metric = _build_faithfulness_metric(model=model, threshold=faithfulness_threshold)
            faithfulness_metric.measure(test_case)
            output["faithfulness_score"] = score_value(faithfulness_metric)
            output["reason"] = metric_reason(faithfulness_metric)
            if include_contextual_recall:
                if not use_response_as_expected:
                    output["contextual_recall"] = None
                else:
                    recall_metric = _build_contextual_recall_metric(model=model, threshold=context_recall_threshold)
                    recall_metric.measure(test_case)
                    output["contextual_recall"] = score_value(recall_metric)
                    output["contextual_recall_reason"] = metric_reason(recall_metric)
    except Exception as exc:  # pragma: no cover - depends on optional package/provider behavior
        output["error"] = str(exc)
    output["latency_ms"] = round((time.perf_counter() - started) * 1000, 3)
    return output


def _build_test_case(row: dict[str, Any], *, expected_output: str | None) -> Any:
    from deepeval.test_case import LLMTestCase

    kwargs = {
        "input": row["input"],
        "actual_output": row["actual_output"],
        "retrieval_context": row["retrieval_context"],
    }
    if expected_output is not None:
        kwargs["expected_output"] = expected_output
    return LLMTestCase(**kwargs)


def _build_faithfulness_metric(*, model: str | None, threshold: float) -> Any:
    from deepeval.metrics import FaithfulnessMetric

    kwargs: dict[str, Any] = {
        "threshold": threshold,
        "include_reason": True,
        "async_mode": False,
    }
    if model:
        kwargs["model"] = model
    return FaithfulnessMetric(**kwargs)


def _build_contextual_recall_metric(*, model: str | None, threshold: float) -> Any:
    from deepeval.metrics import ContextualRecallMetric

    kwargs: dict[str, Any] = {
        "threshold": threshold,
        "include_reason": True,
        "async_mode": False,
    }
    if model:
        kwargs["model"] = model
    return ContextualRecallMetric(**kwargs)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run a DeepEval baseline over ContextTrace-Bench inputs.")
    parser.add_argument("--input", default=str(DEFAULT_INPUT), help="ContextTrace-Bench candidate_inputs.jsonl.")
    parser.add_argument("--raw-output", default=str(DEFAULT_RAW_OUTPUT), help="Raw DeepEval result JSON.")
    parser.add_argument("--candidate-output", default=str(DEFAULT_CANDIDATE_OUTPUT), help="Candidate JSON for leaderboard scoring.")
    parser.add_argument("--model", default=None, help="Optional DeepEval evaluator model name.")
    parser.add_argument("--limit", default=None, type=int, help="Limit cases for debugging.")
    parser.add_argument("--include-contextual-recall", action="store_true", help="Run ContextualRecallMetric when expected output is available.")
    parser.add_argument("--use-response-as-expected", action="store_true", help="Use actual output as a proxy expected output for contextual recall.")
    parser.add_argument("--faithfulness-threshold", default=0.75, type=float)
    parser.add_argument("--context-recall-threshold", default=0.50, type=float)
    parser.add_argument("--max-workers", default=1, type=int, help="Concurrent evaluator calls. Keep low to avoid rate limits.")
    parser.add_argument("--progress-every", default=25, type=int, help="Write partial raw/candidate outputs every N completed rows.")
    parser.add_argument("--resume", action="store_true", help="Reuse completed rows from --raw-output.")
    args = parser.parse_args(argv)

    last_written = 0

    def write_progress(rows: list[dict[str, Any]], completed: int, total: int) -> None:
        nonlocal last_written
        if args.progress_every <= 0:
            return
        if completed != total and completed - last_written < args.progress_every:
            return
        last_written = completed
        candidate = adapt_candidate_rows(
            rows,
            system="DeepEval",
            version=args.model or "configured",
            preset="deepeval",
            faithfulness_threshold=args.faithfulness_threshold,
            context_recall_threshold=args.context_recall_threshold,
        )
        write_json(
            {
                "system": "DeepEval",
                "model": args.model or "",
                "rows": rows,
                "notes": [
                    "Partial progress may be present while the runner is still active.",
                    "DeepEval FaithfulnessMetric evaluates whether actual_output aligns with retrieval_context.",
                ],
            },
            args.raw_output,
        )
        write_candidate(candidate, args.candidate_output)
        print("DeepEval progress: %s/%s" % (completed, total), flush=True)

    result = run_deepeval_baseline(
        load_candidate_inputs(args.input, limit=args.limit),
        model=args.model,
        include_contextual_recall=args.include_contextual_recall,
        use_response_as_expected=args.use_response_as_expected,
        faithfulness_threshold=args.faithfulness_threshold,
        context_recall_threshold=args.context_recall_threshold,
        existing_rows=load_raw_rows(args.raw_output) if args.resume else None,
        max_workers=args.max_workers,
        progress_callback=write_progress,
    )
    raw_path = write_json({key: value for key, value in result.items() if key != "candidate"}, args.raw_output)
    candidate_path = write_candidate(result["candidate"], args.candidate_output)
    print("Raw DeepEval results: %s" % raw_path)
    print("Candidate predictions: %s" % candidate_path)
    print("Rows: %s" % len(result["rows"]))
    errored = [row for row in result["rows"] if row.get("error")]
    if errored:
        print("Rows with errors: %s" % len(errored), file=sys.stderr)
    return 1 if errored else 0


if __name__ == "__main__":
    raise SystemExit(main())
