from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Callable

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from adapt_candidate import adapt_candidate_rows, write_candidate  # noqa: E402
from baseline_common import (  # noqa: E402
    load_candidate_inputs,
    load_raw_rows,
    response,
    trace_payload,
    user_input,
    write_json,
)


DEFAULT_INPUT = SCRIPT_DIR / "out" / "candidate_inputs.jsonl"
DEFAULT_RAGCHECKER_INPUT = SCRIPT_DIR / "out" / "ragchecker_input.json"
DEFAULT_RAW_OUTPUT = SCRIPT_DIR / "out" / "ragchecker_raw_results.json"
DEFAULT_CANDIDATE_OUTPUT = SCRIPT_DIR / "out" / "ragchecker_predictions.json"


def build_ragchecker_rows(
    candidate_inputs: list[dict[str, Any]],
    *,
    gt_answer_field: str | None = None,
    use_response_as_gt: bool = False,
) -> list[dict[str, Any]]:
    return [
        {
            "query_id": str(row.get("id") or ""),
            "query": user_input(row),
            "gt_answer": _reference_answer(
                row,
                gt_answer_field=gt_answer_field,
                use_response_as_gt=use_response_as_gt,
            ),
            "response": response(row),
            "retrieved_context": _retrieved_context(row),
        }
        for row in candidate_inputs
    ]


def adapt_ragchecker_result_rows(
    rows: list[dict[str, Any]],
    *,
    version: str = "",
    faithfulness_threshold: float = 0.75,
    context_recall_threshold: float = 0.50,
) -> dict[str, Any]:
    return adapt_candidate_rows(
        rows,
        system="RAGChecker",
        version=version,
        preset="ragchecker",
        faithfulness_threshold=faithfulness_threshold,
        context_recall_threshold=context_recall_threshold,
    )


def run_ragchecker_baseline(
    candidate_inputs: list[dict[str, Any]],
    *,
    extractor_name: str,
    checker_name: str,
    metrics: str = "all_metrics",
    gt_answer_field: str | None = None,
    use_response_as_gt: bool = False,
    batch_size_extractor: int = 32,
    batch_size_checker: int = 32,
    faithfulness_threshold: float = 0.75,
    context_recall_threshold: float = 0.50,
    existing_rows: list[dict[str, Any]] | None = None,
    chunk_size: int = 0,
    progress_callback: Callable[[list[dict[str, Any]], int, int], None] | None = None,
) -> dict[str, Any]:
    input_rows = build_ragchecker_rows(
        candidate_inputs,
        gt_answer_field=gt_answer_field,
        use_response_as_gt=use_response_as_gt,
    )
    missing_gt = _missing_gt_answer_count(input_rows)
    if missing_gt:
        raise ValueError(
            "RAGChecker requires gt_answer for every row. Missing %s gt_answer values; "
            "provide --gt-answer-field or use --use-response-as-gt for a comparison-only proxy."
            % missing_gt
        )

    total = len(input_rows)
    outputs: list[dict[str, Any] | None] = [None] * total
    completed_by_id = {
        str(row.get("query_id") or row.get("id")): row
        for row in (existing_rows or [])
        if (row.get("query_id") or row.get("id")) and not row.get("error")
    }
    pending: list[tuple[int, dict[str, Any]]] = []
    for index, row in enumerate(input_rows):
        existing = completed_by_id.get(row["query_id"])
        if existing is None:
            pending.append((index, row))
        else:
            outputs[index] = existing

    completed = total - len(pending)
    if progress_callback and completed:
        progress_callback(_completed_rows(outputs), completed, total)

    started = time.perf_counter()
    raw_outputs: list[dict[str, Any]] = []
    run_chunk_size = max(1, int(chunk_size or len(pending) or 1))
    for chunk in _chunks(pending, run_chunk_size):
        chunk_started = time.perf_counter()
        raw_payload = _evaluate_ragchecker_rows(
            [row for _, row in chunk],
            extractor_name=extractor_name,
            checker_name=checker_name,
            metrics=metrics,
            batch_size_extractor=batch_size_extractor,
            batch_size_checker=batch_size_checker,
        )
        raw_outputs.append(raw_payload)
        by_query_id = {
            str(row.get("query_id") or row.get("id")): row
            for row in _ragchecker_result_rows(raw_payload)
            if row.get("query_id") or row.get("id")
        }
        chunk_latency_ms = round((time.perf_counter() - chunk_started) * 1000, 3)
        for index, input_row in chunk:
            output = by_query_id.get(input_row["query_id"])
            if output is None:
                output = {
                    "query_id": input_row["query_id"],
                    "error": "RAGChecker did not return a row for this query_id.",
                }
            output.setdefault("latency_ms", None)
            output["chunk_latency_ms"] = chunk_latency_ms
            outputs[index] = output
            completed += 1
        if progress_callback:
            progress_callback(_completed_rows(outputs), completed, total)

    rows = _completed_rows(outputs)
    raw_payload = raw_outputs[0] if len(raw_outputs) == 1 else _aggregate_ragchecker_payload(rows)
    candidate = adapt_ragchecker_result_rows(
        rows,
        version=_version_label(extractor_name=extractor_name, checker_name=checker_name),
        faithfulness_threshold=faithfulness_threshold,
        context_recall_threshold=context_recall_threshold,
    )
    return {
        "system": "RAGChecker",
        "extractor_name": extractor_name,
        "checker_name": checker_name,
        "metrics": metrics,
        "elapsed_ms": round((time.perf_counter() - started) * 1000, 3),
        "rows": rows,
        "ragchecker_input": {"results": input_rows},
        "ragchecker_output": raw_payload,
        "ragchecker_outputs": raw_outputs,
        "candidate": candidate,
        "notes": [
            "RAGChecker reports per-case metrics under each result.metrics object.",
            (
                "ContextTrace-Bench maps metrics.faithfulness to unsupported_answer "
                "and metrics.claim_recall to should_have_abstained."
            ),
            "Chunked runs report aggregate metrics as mean per-row percentages.",
        ],
    }


def load_ragchecker_output(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if isinstance(payload, dict):
        return payload
    if isinstance(payload, list):
        return {"results": [row for row in payload if isinstance(row, dict)]}
    raise ValueError("Could not parse RAGChecker output from %s." % path)


def _completed_rows(rows: list[dict[str, Any] | None]) -> list[dict[str, Any]]:
    return [row for row in rows if row is not None]


def _chunks(items: list[tuple[int, dict[str, Any]]], size: int) -> list[list[tuple[int, dict[str, Any]]]]:
    return [items[index : index + size] for index in range(0, len(items), size)]


def _aggregate_ragchecker_payload(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "results": rows,
        "metrics": {
            "overall_metrics": {
                "precision": _mean_metric_percent(rows, "precision"),
                "recall": _mean_metric_percent(rows, "recall"),
                "f1": _mean_metric_percent(rows, "f1"),
            },
            "retriever_metrics": {
                "claim_recall": _mean_metric_percent(rows, "claim_recall"),
                "context_precision": _mean_metric_percent(rows, "context_precision"),
            },
            "generator_metrics": {
                "context_utilization": _mean_metric_percent(rows, "context_utilization"),
                "faithfulness": _mean_metric_percent(rows, "faithfulness"),
                "hallucination": _mean_metric_percent(rows, "hallucination"),
                "noise_sensitivity_in_irrelevant": _mean_metric_percent(
                    rows,
                    "noise_sensitivity_in_irrelevant",
                ),
                "noise_sensitivity_in_relevant": _mean_metric_percent(
                    rows,
                    "noise_sensitivity_in_relevant",
                ),
                "self_knowledge": _mean_metric_percent(rows, "self_knowledge"),
            },
        },
    }


def _mean_metric_percent(rows: list[dict[str, Any]], metric: str) -> float | None:
    values = []
    for row in rows:
        metrics = row.get("metrics") if isinstance(row.get("metrics"), dict) else {}
        value = metrics.get(metric)
        try:
            values.append(float(value))
        except (TypeError, ValueError):
            continue
    if not values:
        return None
    return round((sum(values) / len(values)) * 100, 1)


def _retrieved_context(row: dict[str, Any]) -> list[dict[str, str]]:
    contexts = trace_payload(row).get("contexts") or []
    output = []
    for index, context in enumerate(contexts):
        if not isinstance(context, dict):
            continue
        text = str(context.get("text") or "").strip()
        if not text:
            continue
        metadata = context.get("metadata") if isinstance(context.get("metadata"), dict) else {}
        doc_id = (
            context.get("id")
            or context.get("source_id")
            or metadata.get("source_id")
            or metadata.get("doc_id")
        )
        output.append(
            {
                "doc_id": str(doc_id or "context_%s" % (index + 1)),
                "text": text,
            }
        )
    return output


def _reference_answer(
    row: dict[str, Any],
    *,
    gt_answer_field: str | None,
    use_response_as_gt: bool,
) -> str:
    if gt_answer_field:
        value = _get_path(row, gt_answer_field)
        if value is not None and str(value).strip():
            return str(value)

    trace = trace_payload(row)
    for field in (
        "gt_answer",
        "ground_truth",
        "ground_truth_answer",
        "reference",
        "reference_answer",
        "expected_answer",
    ):
        for container in (row, trace):
            value = container.get(field) if isinstance(container, dict) else None
            if value is not None and str(value).strip():
                return str(value)

    return response(row) if use_response_as_gt else ""


def _missing_gt_answer_count(rows: list[dict[str, Any]]) -> int:
    return sum(1 for row in rows if not str(row.get("gt_answer") or "").strip())


def _evaluate_ragchecker_rows(
    rows: list[dict[str, Any]],
    *,
    extractor_name: str,
    checker_name: str,
    metrics: str,
    batch_size_extractor: int,
    batch_size_checker: int,
) -> dict[str, Any]:
    try:
        from ragchecker import RAGChecker, RAGResults
    except ImportError as exc:  # pragma: no cover - depends on optional package
        raise RuntimeError(
            "RAGChecker is not installed. Install benchmarks/contexttrace_bench/requirements-ragchecker.txt "
            "in an isolated venv, then rerun this command."
        ) from exc

    rag_results = RAGResults.from_json(json.dumps({"results": rows}))
    evaluator = RAGChecker(
        extractor_name=extractor_name,
        checker_name=checker_name,
        batch_size_extractor=batch_size_extractor,
        batch_size_checker=batch_size_checker,
    )
    evaluator.evaluate(rag_results, _metric_group(metrics))
    return _rag_results_payload(rag_results)


def _metric_group(name: str) -> Any:
    try:
        from ragchecker import metrics as ragchecker_metrics
    except ImportError:  # pragma: no cover - depends on package export style
        import ragchecker.metrics as ragchecker_metrics

    normalized = name.strip()
    for candidate in (normalized, normalized.lower()):
        if hasattr(ragchecker_metrics, candidate):
            return getattr(ragchecker_metrics, candidate)
    raise ValueError("Unknown RAGChecker metrics group %s." % name)


def _rag_results_payload(rag_results: Any) -> dict[str, Any]:
    for method_name in ("to_json", "json"):
        method = getattr(rag_results, method_name, None)
        if callable(method):
            value = method()
            if isinstance(value, str):
                return json.loads(value)
            if isinstance(value, dict):
                return value
    for method_name in ("to_dict", "dict", "model_dump"):
        method = getattr(rag_results, method_name, None)
        if callable(method):
            value = method()
            if isinstance(value, dict):
                return value
    try:
        return json.loads(str(rag_results))
    except json.JSONDecodeError as exc:  # pragma: no cover - optional package compatibility
        raise RuntimeError("Could not serialize RAGChecker results.") from exc


def _ragchecker_result_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("results")
    if not isinstance(rows, list):
        rows = payload.get("rows")
    if not isinstance(rows, list):
        raise ValueError("RAGChecker output must include a results list.")
    return [row for row in rows if isinstance(row, dict)]


def _get_path(row: dict[str, Any], field: str) -> Any:
    current: Any = row
    for part in field.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def _version_label(*, extractor_name: str, checker_name: str) -> str:
    return "extractor=%s checker=%s" % (extractor_name, checker_name)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build or run a RAGChecker baseline over ContextTrace-Bench inputs."
    )
    parser.add_argument("--input", default=str(DEFAULT_INPUT), help="ContextTrace-Bench candidate_inputs.jsonl.")
    parser.add_argument(
        "--ragchecker-input-output",
        default=str(DEFAULT_RAGCHECKER_INPUT),
        help="Native RAGChecker input JSON.",
    )
    parser.add_argument("--raw-output", default=str(DEFAULT_RAW_OUTPUT), help="Raw RAGChecker result JSON.")
    parser.add_argument(
        "--candidate-output",
        default=str(DEFAULT_CANDIDATE_OUTPUT),
        help="Candidate JSON for leaderboard scoring.",
    )
    parser.add_argument(
        "--from-ragchecker-output",
        default=None,
        help="Adapt an existing official RAGChecker output JSON without running RAGChecker.",
    )
    parser.add_argument("--input-only", action="store_true", help="Only write native RAGChecker input JSON.")
    parser.add_argument("--extractor-name", default=None, help="RAGChecker claim extractor model/provider name.")
    parser.add_argument("--checker-name", default=None, help="RAGChecker claim checker model/provider name.")
    parser.add_argument("--metrics", default="all_metrics", help="RAGChecker metrics group, for example all_metrics.")
    parser.add_argument("--gt-answer-field", default=None, help="Optional dotted field path for gt_answer.")
    parser.add_argument(
        "--use-response-as-gt",
        action="store_true",
        help="Use the response as a proxy gt_answer when candidate inputs do not include references.",
    )
    parser.add_argument("--limit", default=None, type=int, help="Limit cases for debugging.")
    parser.add_argument("--batch-size-extractor", default=32, type=int)
    parser.add_argument("--batch-size-checker", default=32, type=int)
    parser.add_argument("--faithfulness-threshold", default=0.75, type=float)
    parser.add_argument("--context-recall-threshold", default=0.50, type=float)
    parser.add_argument("--chunk-size", default=0, type=int, help="Evaluate rows in checkpointable chunks.")
    parser.add_argument("--progress-every", default=25, type=int, help="Write partial outputs every N completed rows.")
    parser.add_argument("--resume", action="store_true", help="Reuse completed rows from --raw-output.")
    args = parser.parse_args(argv)

    if args.from_ragchecker_output:
        payload = load_ragchecker_output(args.from_ragchecker_output)
        rows = _ragchecker_result_rows(payload)
        candidate = adapt_ragchecker_result_rows(
            rows,
            version="official-output",
            faithfulness_threshold=args.faithfulness_threshold,
            context_recall_threshold=args.context_recall_threshold,
        )
        raw_path = write_json(payload, args.raw_output)
        candidate_path = write_candidate(candidate, args.candidate_output)
        print("Raw RAGChecker results: %s" % raw_path)
        print("Candidate predictions: %s" % candidate_path)
        print("Rows: %s" % len(rows))
        return 0

    candidate_inputs = load_candidate_inputs(args.input, limit=args.limit)
    input_rows = build_ragchecker_rows(
        candidate_inputs,
        gt_answer_field=args.gt_answer_field,
        use_response_as_gt=args.use_response_as_gt,
    )
    input_path = write_json({"results": input_rows}, args.ragchecker_input_output)
    missing_gt = _missing_gt_answer_count(input_rows)
    if args.input_only:
        print("RAGChecker input: %s" % input_path)
        print("Rows: %s" % len(input_rows))
        if missing_gt:
            print("Rows missing gt_answer: %s" % missing_gt, file=sys.stderr)
        return 1 if missing_gt else 0

    if not args.extractor_name or not args.checker_name:
        print(
            "--extractor-name and --checker-name are required unless "
            "--input-only or --from-ragchecker-output is used.",
            file=sys.stderr,
        )
        return 2

    last_written = 0

    def write_progress(rows: list[dict[str, Any]], completed: int, total: int) -> None:
        nonlocal last_written
        if args.progress_every <= 0:
            return
        if completed != total and completed - last_written < args.progress_every:
            return
        last_written = completed
        candidate = adapt_ragchecker_result_rows(
            rows,
            version=_version_label(
                extractor_name=args.extractor_name,
                checker_name=args.checker_name,
            ),
            faithfulness_threshold=args.faithfulness_threshold,
            context_recall_threshold=args.context_recall_threshold,
        )
        write_json(
            {
                "system": "RAGChecker",
                "extractor_name": args.extractor_name,
                "checker_name": args.checker_name,
                "metrics": args.metrics,
                "rows": rows,
                "ragchecker_output": _aggregate_ragchecker_payload(rows),
                "notes": [
                    "Partial progress may be present while the runner is still active.",
                    "Chunked runs report aggregate metrics as mean per-row percentages.",
                ],
            },
            args.raw_output,
        )
        write_candidate(candidate, args.candidate_output)
        print("RAGChecker progress: %s/%s" % (completed, total), flush=True)

    result = run_ragchecker_baseline(
        candidate_inputs,
        extractor_name=args.extractor_name,
        checker_name=args.checker_name,
        metrics=args.metrics,
        gt_answer_field=args.gt_answer_field,
        use_response_as_gt=args.use_response_as_gt,
        batch_size_extractor=args.batch_size_extractor,
        batch_size_checker=args.batch_size_checker,
        faithfulness_threshold=args.faithfulness_threshold,
        context_recall_threshold=args.context_recall_threshold,
        existing_rows=load_raw_rows(args.raw_output) if args.resume else None,
        chunk_size=args.chunk_size,
        progress_callback=write_progress,
    )
    raw_path = write_json(
        {
            "system": result["system"],
            "extractor_name": result["extractor_name"],
            "checker_name": result["checker_name"],
            "metrics": result["metrics"],
            "elapsed_ms": result["elapsed_ms"],
            "rows": result["rows"],
            "ragchecker_output": result["ragchecker_output"],
            "notes": result["notes"],
        },
        args.raw_output,
    )
    candidate_path = write_candidate(result["candidate"], args.candidate_output)
    print("RAGChecker input: %s" % input_path)
    print("Raw RAGChecker results: %s" % raw_path)
    print("Candidate predictions: %s" % candidate_path)
    print("Rows: %s" % len(result["rows"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
