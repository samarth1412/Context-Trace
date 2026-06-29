from __future__ import annotations

import argparse
import os
import sys
import threading
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
DEFAULT_RAW_OUTPUT = SCRIPT_DIR / "out" / "ragas_raw_results.json"
DEFAULT_CANDIDATE_OUTPUT = SCRIPT_DIR / "out" / "ragas_predictions.json"
_RAGAS_THREAD_LOCAL = threading.local()


def build_ragas_rows(candidate_inputs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "id": str(row.get("id") or ""),
            "user_input": user_input(row),
            "response": response(row),
            "retrieved_contexts": retrieved_contexts(row),
        }
        for row in candidate_inputs
    ]


def run_ragas_baseline(
    candidate_inputs: list[dict[str, Any]],
    *,
    model: str | None = None,
    max_output_tokens: int | None = None,
    include_context_recall: bool = False,
    use_response_as_reference: bool = False,
    faithfulness_threshold: float = 0.75,
    context_recall_threshold: float = 0.50,
    existing_rows: list[dict[str, Any]] | None = None,
    max_workers: int = 1,
    progress_callback: Callable[[list[dict[str, Any]], int, int], None] | None = None,
) -> dict[str, Any]:
    input_rows = build_ragas_rows(candidate_inputs)
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
            outputs[index] = _score_ragas_row(
                row,
                model=model,
                max_output_tokens=max_output_tokens,
                include_context_recall=include_context_recall,
                use_response_as_reference=use_response_as_reference,
            )
            completed += 1
            if progress_callback:
                progress_callback(_completed_rows(outputs), completed, total)
    else:
        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            futures = {
                executor.submit(
                    _score_ragas_row,
                    row,
                    model=model,
                    max_output_tokens=max_output_tokens,
                    include_context_recall=include_context_recall,
                    use_response_as_reference=use_response_as_reference,
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
        system="RAGAS",
        version=_evaluator_version(model, max_output_tokens=max_output_tokens),
        preset="ragas",
        faithfulness_threshold=faithfulness_threshold,
        context_recall_threshold=context_recall_threshold,
    )
    return {
        "system": "RAGAS",
        "model": model or "",
        "max_output_tokens": max_output_tokens,
        "rows": rows,
        "candidate": candidate,
        "notes": [
            "RAGAS faithfulness evaluates whether each response is supported by retrieved contexts.",
            "Context recall is emitted only when explicitly requested; ContextTrace-Bench does not ship hidden references to baseline runners.",
        ],
    }


def _evaluator_version(model: str | None, *, max_output_tokens: int | None) -> str:
    version = model or "configured"
    if max_output_tokens is not None:
        return "%s max_output_tokens=%s" % (version, max(1, int(max_output_tokens)))
    return version


def _completed_rows(rows: list[dict[str, Any] | None]) -> list[dict[str, Any]]:
    return [row for row in rows if row is not None]


def _score_ragas_row(
    row: dict[str, Any],
    *,
    model: str | None,
    max_output_tokens: int | None,
    include_context_recall: bool,
    use_response_as_reference: bool,
) -> dict[str, Any]:
    started = time.perf_counter()
    output: dict[str, Any] = {
        "id": row["id"],
        "retrieved_context_count": len(row["retrieved_contexts"]),
    }
    try:
        if not row["retrieved_contexts"]:
            output["faithfulness"] = 0.0
            output["context_recall"] = 0.0
            output["reason"] = "No retrieved contexts were supplied."
        else:
            scorer = _thread_local_scorer(model, max_output_tokens=max_output_tokens)
            faithfulness, reason = _score_faithfulness(scorer, row)
            output["faithfulness"] = faithfulness
            output["reason"] = reason
            if include_context_recall:
                output["context_recall"] = faithfulness if use_response_as_reference else None
    except Exception as exc:  # pragma: no cover - depends on optional package/provider behavior
        output["error"] = str(exc)
    output["latency_ms"] = round((time.perf_counter() - started) * 1000, 3)
    return output


def _thread_local_scorer(model: str | None, *, max_output_tokens: int | None = None) -> Any:
    cache_key = (model, max_output_tokens)
    cached_model = getattr(_RAGAS_THREAD_LOCAL, "model", None)
    scorer = getattr(_RAGAS_THREAD_LOCAL, "scorer", None)
    if scorer is None or cached_model != cache_key:
        scorer = _build_faithfulness_scorer(model, max_output_tokens=max_output_tokens)
        _RAGAS_THREAD_LOCAL.model = cache_key
        _RAGAS_THREAD_LOCAL.scorer = scorer
    return scorer


def _build_faithfulness_scorer(model: str | None, *, max_output_tokens: int | None = None) -> Any:
    try:
        from ragas.metrics.collections import Faithfulness
    except ImportError:
        from ragas.metrics import Faithfulness  # type: ignore

    if not model:
        return Faithfulness()

    try:
        from ragas.llms import llm_factory
    except ImportError:
        return Faithfulness()
    try:
        from openai import AsyncOpenAI

        client_kwargs: dict[str, str] = {}
        model_kwargs: dict[str, int] = {}
        if max_output_tokens is not None:
            model_kwargs["max_tokens"] = max(1, int(max_output_tokens))
        api_key = os.environ.get("OPENAI_API_KEY") or os.environ.get("CONTEXTTRACE_JUDGE_API_KEY")
        if api_key:
            client_kwargs["api_key"] = api_key
        base_url = os.environ.get("OPENAI_BASE_URL") or os.environ.get("CONTEXTTRACE_JUDGE_BASE_URL")
        if base_url:
            client_kwargs["base_url"] = base_url
        return Faithfulness(llm=llm_factory(model, client=AsyncOpenAI(**client_kwargs), **model_kwargs))
    except TypeError:
        return Faithfulness(llm=llm_factory(model, **model_kwargs))


def _score_faithfulness(scorer: Any, row: dict[str, Any]) -> tuple[float | None, str]:
    if hasattr(scorer, "score"):
        result = scorer.score(
            user_input=row["user_input"],
            response=row["response"],
            retrieved_contexts=row["retrieved_contexts"],
        )
        return score_value(result), metric_reason(scorer, result)

    try:
        from ragas.dataset_schema import SingleTurnSample
    except ImportError as exc:
        raise RuntimeError("Installed RAGAS package does not expose a supported faithfulness API.") from exc

    sample = SingleTurnSample(
        user_input=row["user_input"],
        response=row["response"],
        retrieved_contexts=row["retrieved_contexts"],
    )
    if hasattr(scorer, "single_turn_score"):
        result = scorer.single_turn_score(sample)
    elif hasattr(scorer, "single_turn_ascore"):
        import asyncio

        result = asyncio.run(scorer.single_turn_ascore(sample))
    else:
        raise RuntimeError("Installed RAGAS Faithfulness scorer has no supported scoring method.")
    return score_value(result), metric_reason(scorer, result)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run a RAGAS baseline over ContextTrace-Bench inputs.")
    parser.add_argument("--input", default=str(DEFAULT_INPUT), help="ContextTrace-Bench candidate_inputs.jsonl.")
    parser.add_argument("--raw-output", default=str(DEFAULT_RAW_OUTPUT), help="Raw RAGAS result JSON.")
    parser.add_argument("--candidate-output", default=str(DEFAULT_CANDIDATE_OUTPUT), help="Candidate JSON for leaderboard scoring.")
    parser.add_argument("--model", default=None, help="Optional RAGAS evaluator model name.")
    parser.add_argument("--max-output-tokens", default=None, type=int, help="Optional evaluator output-token cap for long responses.")
    parser.add_argument("--limit", default=None, type=int, help="Limit cases for debugging.")
    parser.add_argument("--include-context-recall", action="store_true", help="Emit context_recall when references are available.")
    parser.add_argument("--use-response-as-reference", action="store_true", help="Use actual response as a proxy reference for context recall.")
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
            system="RAGAS",
            version=_evaluator_version(args.model, max_output_tokens=args.max_output_tokens),
            preset="ragas",
            faithfulness_threshold=args.faithfulness_threshold,
            context_recall_threshold=args.context_recall_threshold,
        )
        write_json(
            {
                "system": "RAGAS",
                "model": args.model or "",
                "max_output_tokens": args.max_output_tokens,
                "rows": rows,
                "notes": [
                    "Partial progress may be present while the runner is still active.",
                    "RAGAS faithfulness evaluates whether each response is supported by retrieved contexts.",
                ],
            },
            args.raw_output,
        )
        write_candidate(candidate, args.candidate_output)
        print("RAGAS progress: %s/%s" % (completed, total), flush=True)

    result = run_ragas_baseline(
        load_candidate_inputs(args.input, limit=args.limit),
        model=args.model,
        max_output_tokens=args.max_output_tokens,
        include_context_recall=args.include_context_recall,
        use_response_as_reference=args.use_response_as_reference,
        faithfulness_threshold=args.faithfulness_threshold,
        context_recall_threshold=args.context_recall_threshold,
        existing_rows=load_raw_rows(args.raw_output) if args.resume else None,
        max_workers=args.max_workers,
        progress_callback=write_progress,
    )
    raw_path = write_json({key: value for key, value in result.items() if key != "candidate"}, args.raw_output)
    candidate_path = write_candidate(result["candidate"], args.candidate_output)
    print("Raw RAGAS results: %s" % raw_path)
    print("Candidate predictions: %s" % candidate_path)
    print("Rows: %s" % len(result["rows"]))
    errored = [row for row in result["rows"] if row.get("error")]
    if errored:
        print("Rows with errors: %s" % len(errored), file=sys.stderr)
    return 1 if errored else 0


if __name__ == "__main__":
    raise SystemExit(main())
