from __future__ import annotations

import argparse
import json
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
from baseline_common import load_candidate_inputs, load_raw_rows, response, retrieved_contexts, trace_payload, user_input, write_json  # noqa: E402


DEFAULT_INPUT = SCRIPT_DIR / "out" / "candidate_inputs.jsonl"
DEFAULT_RAW_OUTPUT = SCRIPT_DIR / "out" / "local_judge_raw_results.json"
DEFAULT_CANDIDATE_OUTPUT = SCRIPT_DIR / "out" / "local_judge_predictions.json"
DEFAULT_BASE_URL = "http://localhost:11434/v1"
DEFAULT_MODEL = "llama3.1:8b"
_JUDGE_THREAD_LOCAL = threading.local()
FAILURE_LABELS = [
    "no_failure_detected",
    "unsupported_answer",
    "contradicted_answer",
    "partial_support",
    "should_have_abstained",
    "citation_mismatch",
    "insufficient_context",
    "source_conflict",
    "stale_source",
    "stale_context_used",
    "low_authority_source",
]
ROOT_CAUSES = [
    "no_failure_detected",
    "answer_overreach",
    "conflicting_contexts",
    "partial_context",
    "should_have_abstained",
    "missing_cited_source",
    "wrong_source_cited",
    "stale_context",
    "low_authority_source",
]
CITATION_STATUSES = [
    "citation_ok",
    "cited_source_missing",
    "cited_source_does_not_support_claim",
    "claim_supported_by_different_source",
]


def run_local_judge_baseline(
    candidate_inputs: list[dict[str, Any]],
    *,
    model: str,
    base_url: str,
    api_key: str,
    system: str = "OpenAI-compatible judge",
    request_timeout: float = 60.0,
    existing_rows: list[dict[str, Any]] | None = None,
    max_workers: int = 1,
    progress_callback: Callable[[list[dict[str, Any]], int, int], None] | None = None,
) -> dict[str, Any]:
    total = len(candidate_inputs)
    outputs: list[dict[str, Any] | None] = [None] * total
    completed_by_id = {
        str(row.get("id")): row
        for row in (existing_rows or [])
        if row.get("id") and not row.get("error")
    }
    pending: list[tuple[int, dict[str, Any]]] = []
    for index, row in enumerate(candidate_inputs):
        existing = completed_by_id.get(str(row.get("id") or ""))
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
            outputs[index] = _score_judge_row(
                row,
                model=model,
                api_key=api_key,
                base_url=base_url,
                request_timeout=request_timeout,
            )
            completed += 1
            if progress_callback:
                progress_callback(_completed_rows(outputs), completed, total)
    else:
        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            futures = {
                executor.submit(
                    _score_judge_row,
                    row,
                    model=model,
                    api_key=api_key,
                    base_url=base_url,
                    request_timeout=request_timeout,
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
        system=system,
        version=model,
        preset="generic",
        id_field="id",
    )
    return {
        "system": system,
        "model": model,
        "base_url": base_url,
        "rows": rows,
        "candidate": candidate,
        "notes": [
            "This runner uses an OpenAI-compatible chat-completions endpoint.",
            "Default base URL targets Ollama's local OpenAI-compatible endpoint.",
        ],
    }


def _completed_rows(rows: list[dict[str, Any] | None]) -> list[dict[str, Any]]:
    return [row for row in rows if row is not None]


def _score_judge_row(
    row: dict[str, Any],
    *,
    model: str,
    api_key: str,
    base_url: str,
    request_timeout: float,
) -> dict[str, Any]:
    started = time.perf_counter()
    output: dict[str, Any] = {
        "id": str(row.get("id") or ""),
        "retrieved_context_count": len(retrieved_contexts(row)),
    }
    try:
        client = _thread_local_client(api_key=api_key, base_url=base_url, timeout=request_timeout)
        judged = _judge_row(client, row, model=model)
        output.update(_normalize_judge_output(judged))
    except Exception as exc:  # pragma: no cover - depends on optional package/provider behavior
        output["error"] = str(exc)
    output["latency_ms"] = round((time.perf_counter() - started) * 1000, 3)
    return output


def _thread_local_client(*, api_key: str, base_url: str, timeout: float) -> Any:
    key = (api_key, base_url, timeout)
    cached_key = getattr(_JUDGE_THREAD_LOCAL, "key", None)
    client = getattr(_JUDGE_THREAD_LOCAL, "client", None)
    if client is None or cached_key != key:
        client = _openai_client(api_key=api_key, base_url=base_url, timeout=timeout)
        _JUDGE_THREAD_LOCAL.key = key
        _JUDGE_THREAD_LOCAL.client = client
    return client


def _openai_client(*, api_key: str, base_url: str, timeout: float) -> Any:
    from openai import OpenAI

    return OpenAI(api_key=api_key, base_url=base_url, timeout=timeout)


def _judge_row(client: Any, row: dict[str, Any], *, model: str) -> dict[str, Any]:
    completion = client.chat.completions.create(
        model=model,
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a strict RAG evidence judge. Return only JSON. "
                    "Use the provided allowed labels and do not invent labels."
                ),
            },
            {"role": "user", "content": _judge_prompt(row)},
        ],
    )
    content = completion.choices[0].message.content or "{}"
    return _parse_json_object(content)


def _judge_prompt(row: dict[str, Any]) -> str:
    trace = trace_payload(row)
    contexts = trace.get("contexts") or []
    context_blocks = [
        {
            "index": index,
            "id": str(context.get("id") or index),
            "text": str(context.get("text") or ""),
        }
        for index, context in enumerate(contexts)
        if isinstance(context, dict) and str(context.get("text") or "").strip()
    ]
    citation_blocks = [
        {
            "claim": str(citation.get("claim") or ""),
            "source_id": str(citation.get("source_id") or ""),
        }
        for citation in (trace.get("citations") or [])
        if isinstance(citation, dict)
    ]
    return json.dumps(
        {
            "task": "Classify whether the answer is grounded in the retrieved contexts.",
            "taxonomy_rules": [
                "Use citation_mismatch when a cited source is missing, the cited source does not support the cited claim, or another retrieved source supports the claim but the cited source does not.",
                "Use partial_support when the answer mixes supported details with unsupported extra details. Prefer predicted_verdict_counts.partially_supported=1 for a single mixed claim.",
                "Use unsupported_answer when the answer has factual claims that no retrieved context supports.",
                "Use contradicted_answer when retrieved context directly conflicts with the answer. Also include should_have_abstained for direct contradiction.",
                "Use should_have_abstained when no retrieved context supports the answer or the available context contradicts the answer.",
                "If no contexts are provided and the answer makes a factual claim, use unsupported_answer and should_have_abstained.",
                "Use root cause answer_overreach for unsupported additions or partial support, conflicting_contexts for contradiction, wrong_source_cited for wrong cited source, missing_cited_source for absent cited source, and should_have_abstained for no usable context.",
            ],
            "allowed_failure_labels": FAILURE_LABELS,
            "allowed_root_causes": ROOT_CAUSES,
            "allowed_citation_statuses": CITATION_STATUSES,
            "required_json_schema": {
                "predicted": ["one or more allowed_failure_labels"],
                "predicted_verdict_counts": {
                    "supported": "integer",
                    "partially_supported": "integer",
                    "unsupported": "integer",
                    "contradicted": "integer",
                    "unverifiable": "integer",
                },
                "predicted_primary_root_cause": "one allowed_root_causes value",
                "predicted_citation_statuses": ["one allowed_citation_statuses value per cited claim"],
                "predicted_evidence_spans": ["short exact supporting snippets from contexts"],
            },
            "query": user_input(row),
            "answer": response(row),
            "contexts": context_blocks,
            "citations": citation_blocks,
        },
        ensure_ascii=True,
    )


def _normalize_judge_output(payload: dict[str, Any]) -> dict[str, Any]:
    labels = _allowed_list(payload.get("predicted"), FAILURE_LABELS) or ["no_failure_detected"]
    verdict_counts = payload.get("predicted_verdict_counts")
    if not isinstance(verdict_counts, dict):
        verdict_counts = {}
    normalized_counts = {
        "supported": int(verdict_counts.get("supported") or 0),
        "partially_supported": int(verdict_counts.get("partially_supported") or 0),
        "unsupported": int(verdict_counts.get("unsupported") or 0),
        "contradicted": int(verdict_counts.get("contradicted") or 0),
        "unverifiable": int(verdict_counts.get("unverifiable") or 0),
    }
    if not any(normalized_counts.values()):
        normalized_counts["supported" if labels == ["no_failure_detected"] else "unsupported"] = 1

    root = str(payload.get("predicted_primary_root_cause") or "")
    if root not in ROOT_CAUSES:
        root = "no_failure_detected" if labels == ["no_failure_detected"] else "answer_overreach"

    return {
        "predicted": labels,
        "predicted_verdict_counts": normalized_counts,
        "predicted_primary_root_cause": root,
        "predicted_citation_statuses": _allowed_list(payload.get("predicted_citation_statuses"), CITATION_STATUSES),
        "predicted_evidence_spans": _string_list(payload.get("predicted_evidence_spans")),
    }


def _allowed_list(value: Any, allowed: list[str]) -> list[str]:
    return [item for item in _string_list(value) if item in allowed]


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value.strip() else []
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    return [str(value)]


def _parse_json_object(value: str) -> dict[str, Any]:
    stripped = value.strip()
    if stripped.startswith("```"):
        stripped = stripped.strip("`")
        if stripped.lower().startswith("json"):
            stripped = stripped[4:].strip()
    parsed = json.loads(stripped)
    if not isinstance(parsed, dict):
        raise ValueError("Judge response was not a JSON object.")
    return parsed


def _api_key_from_env() -> str:
    return (
        os.environ.get("OPENAI_API_KEY")
        or os.environ.get("CONTEXTTRACE_JUDGE_API_KEY")
        or os.environ.get("OLLAMA_API_KEY")
        or "ollama"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run a local/OpenAI-compatible LLM judge baseline over ContextTrace-Bench inputs.")
    parser.add_argument("--input", default=str(DEFAULT_INPUT), help="ContextTrace-Bench candidate_inputs.jsonl.")
    parser.add_argument("--raw-output", default=str(DEFAULT_RAW_OUTPUT), help="Raw judge result JSON.")
    parser.add_argument("--candidate-output", default=str(DEFAULT_CANDIDATE_OUTPUT), help="Candidate JSON for leaderboard scoring.")
    parser.add_argument("--model", default=os.environ.get("CONTEXTTRACE_JUDGE_MODEL") or DEFAULT_MODEL)
    parser.add_argument("--base-url", default=os.environ.get("OPENAI_BASE_URL") or os.environ.get("CONTEXTTRACE_JUDGE_BASE_URL") or DEFAULT_BASE_URL)
    parser.add_argument("--system", default="OpenAI-compatible judge")
    parser.add_argument("--limit", default=None, type=int, help="Limit cases for debugging.")
    parser.add_argument("--request-timeout", default=60.0, type=float)
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
            system=args.system,
            version=args.model,
            preset="generic",
            id_field="id",
        )
        write_json(
            {
                "system": args.system,
                "model": args.model,
                "base_url": args.base_url,
                "rows": rows,
                "notes": [
                    "Partial progress may be present while the runner is still active.",
                    "This runner uses an OpenAI-compatible chat-completions endpoint.",
                ],
            },
            args.raw_output,
        )
        write_candidate(candidate, args.candidate_output)
        print("Judge progress: %s/%s" % (completed, total), flush=True)

    result = run_local_judge_baseline(
        load_candidate_inputs(args.input, limit=args.limit),
        model=args.model,
        base_url=args.base_url,
        api_key=_api_key_from_env(),
        system=args.system,
        request_timeout=args.request_timeout,
        existing_rows=load_raw_rows(args.raw_output) if args.resume else None,
        max_workers=args.max_workers,
        progress_callback=write_progress,
    )
    raw_path = write_json({key: value for key, value in result.items() if key != "candidate"}, args.raw_output)
    candidate_path = write_candidate(result["candidate"], args.candidate_output)
    print("Raw local judge results: %s" % raw_path)
    print("Candidate predictions: %s" % candidate_path)
    print("Rows: %s" % len(result["rows"]))
    errored = [row for row in result["rows"] if row.get("error")]
    if errored:
        print("Rows with errors: %s" % len(errored), file=sys.stderr)
    return 1 if errored else 0


if __name__ == "__main__":
    raise SystemExit(main())
