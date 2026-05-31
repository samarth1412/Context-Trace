from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, Optional

import httpx

from contexttrace.client import ContextTrace

UNSUPPORTED_VERDICTS = {"unsupported", "contradicted", "not_enough_info"}
NO_FAILURE = "no_failure_detected"


@dataclass
class EvalQuestion:
    question: str
    id: Optional[str] = None
    expected_answer: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass
class EvalThresholds:
    min_citation_support: float = 0.8
    max_unsupported_claim_rate: float = 0.1
    max_failure_rate: float = 0.0


@dataclass
class EvalResult:
    question: EvalQuestion
    trace_id: Optional[str]
    citation_support: float
    unsupported_claim_rate: float
    failure_type: str
    token_usage: dict[str, Any]
    latency_ms: float
    error: Optional[str] = None


@dataclass
class EvalRunSummary:
    results: list[EvalResult]
    thresholds: EvalThresholds
    markdown: str

    @property
    def avg_citation_support(self) -> float:
        if not self.results:
            return 0.0
        return round(
            sum(result.citation_support for result in self.results) / len(self.results),
            3,
        )

    @property
    def unsupported_claim_rate(self) -> float:
        if not self.results:
            return 1.0
        return round(
            sum(result.unsupported_claim_rate for result in self.results) / len(self.results),
            3,
        )

    @property
    def failure_rate(self) -> float:
        if not self.results:
            return 1.0
        failures = [
            result
            for result in self.results
            if result.error or result.failure_type != NO_FAILURE
        ]
        return round(len(failures) / len(self.results), 3)

    @property
    def failed(self) -> bool:
        return (
            self.avg_citation_support < self.thresholds.min_citation_support
            or self.unsupported_claim_rate > self.thresholds.max_unsupported_claim_rate
            or self.failure_rate > self.thresholds.max_failure_rate
        )


EndpointCaller = Callable[[str, EvalQuestion, float, Dict[str, str]], Dict[str, Any]]


def load_dataset(path: str) -> list[EvalQuestion]:
    with open(path, "r", encoding="utf-8") as handle:
        data = json.load(handle)

    if isinstance(data, dict):
        raw_questions = data.get("questions")
    else:
        raw_questions = data

    if not isinstance(raw_questions, list):
        raise ValueError("Dataset must be a JSON list or an object with a questions list.")

    questions = []
    for index, item in enumerate(raw_questions):
        questions.append(_normalize_question(item, index=index))
    return questions


def run_evaluation(
    *,
    dataset_path: str,
    endpoint: str,
    api_key: str,
    project: str,
    base_url: str,
    thresholds: EvalThresholds,
    summary_path: Optional[str] = None,
    timeout: float = 30.0,
    endpoint_headers: Optional[dict[str, str]] = None,
    endpoint_caller: Optional[EndpointCaller] = None,
    contexttrace: Optional[ContextTrace] = None,
) -> EvalRunSummary:
    questions = load_dataset(dataset_path)
    caller = endpoint_caller or call_rag_endpoint
    ct = contexttrace or ContextTrace(
        api_key=api_key,
        project=project,
        base_url=base_url,
        timeout=timeout,
    )

    results: list[EvalResult] = []
    try:
        for question in questions:
            results.append(
                _evaluate_question(
                    contexttrace=ct,
                    question=question,
                    endpoint=endpoint,
                    timeout=timeout,
                    endpoint_headers=endpoint_headers or {},
                    endpoint_caller=caller,
                    dataset_path=dataset_path,
                )
            )
    finally:
        if contexttrace is None:
            ct.close()

    summary = EvalRunSummary(
        results=results,
        thresholds=thresholds,
        markdown="",
    )
    summary.markdown = render_markdown_summary(summary)
    write_summary(summary.markdown, summary_path=summary_path)
    return summary


def call_rag_endpoint(
    endpoint: str,
    question: EvalQuestion,
    timeout: float,
    headers: dict[str, str],
) -> dict[str, Any]:
    payload = question.payload or {
        "query": question.question,
        "question": question.question,
        "metadata": question.metadata,
    }
    if question.expected_answer is not None:
        payload["expected_answer"] = question.expected_answer

    with httpx.Client(timeout=timeout) as client:
        response = client.post(endpoint, json=payload, headers=headers)
        response.raise_for_status()
        return response.json()


def render_markdown_summary(summary: EvalRunSummary) -> str:
    status = "failed" if summary.failed else "passed"
    lines = [
        "# ContextTrace RAG Evaluation",
        "",
        f"Status: **{status}**",
        "",
        "| Metric | Value | Threshold |",
        "| --- | ---: | ---: |",
        (
            "| Average citation support | %.3f | >= %.3f |"
            % (summary.avg_citation_support, summary.thresholds.min_citation_support)
        ),
        (
            "| Unsupported claim rate | %.3f | <= %.3f |"
            % (summary.unsupported_claim_rate, summary.thresholds.max_unsupported_claim_rate)
        ),
        (
            "| Failure rate | %.3f | <= %.3f |"
            % (summary.failure_rate, summary.thresholds.max_failure_rate)
        ),
        "",
        "| Question | Trace | Citation support | Unsupported claims | Failure | Tokens | Latency |",
        "| --- | --- | ---: | ---: | --- | ---: | ---: |",
    ]
    for result in summary.results:
        token_usage = result.token_usage.get("total_tokens", "")
        trace = result.trace_id or ""
        if trace:
            trace = "`%s`" % trace
        failure = result.error or result.failure_type
        lines.append(
            "| %s | %s | %.3f | %.3f | %s | %s | %.1f ms |"
            % (
                _escape_table(result.question.question),
                trace,
                result.citation_support,
                result.unsupported_claim_rate,
                _escape_table(failure),
                token_usage,
                result.latency_ms,
            )
        )
    return "\n".join(lines) + "\n"


def write_summary(markdown: str, *, summary_path: Optional[str]) -> None:
    output_path = summary_path or "contexttrace-eval-summary.md"
    Path(output_path).write_text(markdown, encoding="utf-8")

    github_summary = os.getenv("GITHUB_STEP_SUMMARY")
    if github_summary:
        with open(github_summary, "a", encoding="utf-8") as handle:
            handle.write(markdown)


def _evaluate_question(
    *,
    contexttrace: ContextTrace,
    question: EvalQuestion,
    endpoint: str,
    timeout: float,
    endpoint_headers: dict[str, str],
    endpoint_caller: EndpointCaller,
    dataset_path: str,
) -> EvalResult:
    started_at = time.perf_counter()
    error = None
    response: dict[str, Any] = {}

    try:
        response = endpoint_caller(endpoint, question, timeout, endpoint_headers)
    except Exception as exc:  # pragma: no cover - exact httpx exception surface varies
        error = str(exc)

    latency_ms = round((time.perf_counter() - started_at) * 1000, 2)
    chunks = _normalize_chunks(response)
    selected_context = _normalize_selected_context(response, chunks)
    answer = _extract_answer(response, error=error)
    citations = _normalize_citations(response)
    usage = _extract_usage(response)
    model = _extract_model(response)

    with contexttrace.trace(
        query=question.question,
        metadata={
            "source": "contexttrace_cli_eval",
            "dataset": dataset_path,
            "question_id": question.id,
            "expected_answer": question.expected_answer,
            **question.metadata,
        },
    ) as trace:
        trace.log_retrieval(chunks, retriever_name="contexttrace-cli-eval")
        trace.log_context(selected_context)
        trace.log_answer(
            answer,
            model=model,
            usage=usage,
            metadata={"endpoint": endpoint, "latency_ms": latency_ms, "error": error},
        )
        trace.log_citations(citations)
        evaluation = trace.evaluate()

    citation_support, unsupported_claim_rate = _score_evaluation(evaluation)
    failure_type = evaluation.get("failure", {}).get("failure_type", "unknown")
    if error:
        failure_type = "endpoint_error"

    return EvalResult(
        question=question,
        trace_id=trace.trace_id,
        citation_support=citation_support,
        unsupported_claim_rate=unsupported_claim_rate,
        failure_type=failure_type,
        token_usage=usage,
        latency_ms=latency_ms,
        error=error,
    )


def _normalize_question(item: Any, *, index: int) -> EvalQuestion:
    if isinstance(item, str):
        return EvalQuestion(question=item, id=str(index))
    if not isinstance(item, dict):
        raise ValueError("Each dataset entry must be a string or object.")

    question = item.get("question") or item.get("query")
    if not question:
        raise ValueError("Each dataset entry must include question or query.")

    return EvalQuestion(
        question=str(question),
        id=str(item.get("id") or index),
        expected_answer=item.get("expected_answer"),
        metadata=item.get("metadata") or {},
        payload=item.get("payload") or {},
    )


def _normalize_chunks(response: dict[str, Any]) -> list[dict[str, Any]]:
    candidates = (
        response.get("retrieved_chunks")
        or response.get("chunks")
        or response.get("documents")
        or response.get("sources")
        or []
    )
    return [_normalize_chunk(chunk, index=index) for index, chunk in enumerate(candidates)]


def _normalize_selected_context(
    response: dict[str, Any],
    chunks: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    candidates = response.get("selected_context") or response.get("context")
    if not candidates:
        return chunks
    if isinstance(candidates, str):
        candidates = [candidates]
    return [_normalize_chunk(chunk, index=index) for index, chunk in enumerate(candidates)]


def _normalize_chunk(chunk: Any, *, index: int) -> dict[str, Any]:
    if isinstance(chunk, str):
        return {
            "chunk_id": "chunk_%s" % index,
            "content": chunk,
            "source": None,
            "metadata": {},
            "relevance_score": None,
        }
    if not isinstance(chunk, dict):
        content = getattr(chunk, "page_content", None) or getattr(chunk, "content", None)
        metadata = getattr(chunk, "metadata", None) or {}
        chunk_id = getattr(chunk, "id", None) or metadata.get("id") or "chunk_%s" % index
        return {
            "chunk_id": str(chunk_id),
            "content": str(content or ""),
            "source": metadata.get("source"),
            "metadata": metadata,
            "relevance_score": getattr(chunk, "score", None),
        }

    chunk_id = chunk.get("chunk_id") or chunk.get("id") or "chunk_%s" % index
    content = chunk.get("content") or chunk.get("text") or chunk.get("page_content") or ""
    return {
        "chunk_id": str(chunk_id),
        "content": str(content),
        "source": chunk.get("source"),
        "metadata": chunk.get("metadata") or {},
        "relevance_score": chunk.get("relevance_score") or chunk.get("score"),
    }


def _normalize_citations(response: dict[str, Any]) -> list[dict[str, Any]]:
    citations = response.get("citations") or []
    normalized = []
    for item in citations:
        if not isinstance(item, dict):
            continue
        claim = item.get("claim")
        source_chunk_id = item.get("source_chunk_id") or item.get("chunk_id") or item.get("source_id")
        if claim and source_chunk_id:
            normalized.append(
                {
                    "claim": str(claim),
                    "source_chunk_id": str(source_chunk_id),
                    "metadata": item.get("metadata") or {},
                }
            )
    return normalized


def _extract_answer(response: dict[str, Any], *, error: Optional[str]) -> str:
    if error:
        return "Endpoint request failed: %s" % error
    answer = response.get("answer") or response.get("output") or response.get("response")
    return str(answer or "No answer returned by endpoint.")


def _extract_usage(response: dict[str, Any]) -> dict[str, Any]:
    return response.get("usage") or response.get("token_usage") or {}


def _extract_model(response: dict[str, Any]) -> Optional[str]:
    model = response.get("model") or response.get("model_name")
    return str(model) if model else None


def _score_evaluation(evaluation: dict[str, Any]) -> tuple[float, float]:
    checks = evaluation.get("citation_checks") or []
    if not checks:
        return 0.0, 1.0
    support_scores = [float(check.get("support_score") or 0.0) for check in checks]
    unsupported = [
        check
        for check in checks
        if check.get("verdict") in UNSUPPORTED_VERDICTS
    ]
    return (
        round(sum(support_scores) / len(support_scores), 3),
        round(len(unsupported) / len(checks), 3),
    )


def _escape_table(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")
