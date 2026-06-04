from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Iterable as CollectionsIterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from contexttrace.client import ContextTrace
from contexttrace.report import ReportGenerator


EndpointCaller = Callable[[str, str, Dict[str, str], Optional[Dict[str, Any]], float], Dict[str, Any]]


@dataclass(frozen=True)
class EndpointEvalResult:
    eval_run_id: str | None
    trace_ids: list[str]
    questions_tested: int
    reliability_score: float
    failure_rate: float
    avg_citation_support: float
    unsupported_claim_rate: float
    top_failures: list[str]
    report_path: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "eval_run_id": self.eval_run_id,
            "trace_ids": self.trace_ids,
            "questions_tested": self.questions_tested,
            "reliability_score": self.reliability_score,
            "failure_rate": self.failure_rate,
            "avg_citation_support": self.avg_citation_support,
            "unsupported_claim_rate": self.unsupported_claim_rate,
            "top_failures": self.top_failures,
            "report_path": self.report_path,
        }


def run_endpoint_eval(
    *,
    dataset_path: str,
    endpoint: str,
    contexttrace: ContextTrace,
    method: str = "POST",
    headers: Optional[dict[str, str]] = None,
    body_template: Optional[dict[str, Any]] = None,
    input_key: str = "question",
    answer_path: str = "$.answer",
    contexts_path: str = "$.contexts",
    citations_path: str = "$.citations",
    timeout: float = 30.0,
    caller: EndpointCaller | None = None,
    generate_report: bool = True,
    report_path: str | None = None,
) -> EndpointEvalResult:
    questions = _load_dataset(dataset_path)
    headers = headers or {}
    method = method.upper()
    trace_ids: list[str] = []
    failures: list[str] = []
    supports: list[float] = []
    unsupported_rates: list[float] = []
    reliability_scores: list[float] = []
    eval_run_id: str | None = None
    question_records: list[dict[str, Any]] = []

    for index, question in enumerate(questions):
        query = str(question.get("query") or question.get("question") or "")
        if not query:
            continue
        body = _render_body(body_template, query=query) if body_template is not None else {input_key: query}
        start = time.perf_counter()
        response = (caller or _default_caller)(endpoint, method, headers, body, timeout)
        latency_ms = round((time.perf_counter() - start) * 1000, 2)

        answer = _extract(response, answer_path) or ""
        raw_contexts = _extract(response, contexts_path) or _extract(response, "$.retrieved_chunks") or []
        raw_citations = _extract(response, citations_path) or []
        chunks = _normalize_chunks(raw_contexts)
        citations = _normalize_citations(raw_citations, answer=answer, chunks=chunks)

        with contexttrace.trace(
            query=query,
            metadata={
                "source": "byo_rag_endpoint",
                "dataset_id": question.get("id"),
                "endpoint": endpoint,
                "latency_ms": latency_ms,
            },
        ) as trace:
            if chunks:
                trace.log_retrieval(chunks, metadata={"endpoint": endpoint})
                trace.log_context(chunks)
            trace.log_answer(
                str(answer),
                model=str(response.get("model") or "external-rag-endpoint"),
                usage=response.get("usage") or {},
                metadata={"latency_ms": latency_ms},
            )
            if citations:
                trace.log_citations(citations)
            evaluation = trace.evaluate()
            trace_ids.append(str(trace.trace_id))

        scores = evaluation.get("scores") or {}
        failure = evaluation.get("failure") or {}
        reliability = evaluation.get("reliability") or {}
        failure_type = failure.get("failure_type") or failure.get("type") or "unknown"
        if failure_type != "no_failure_detected":
            failures.append(str(failure_type))
        supports.append(float(scores.get("citation_support") or 0.0))
        unsupported_rates.append(float(scores.get("unsupported_claim_rate") or 0.0))
        reliability_scores.append(float(reliability.get("score") or 0.0))
        question_records.append({"question": question, "trace_id": trace.trace_id, "position": index})

    store = getattr(getattr(contexttrace, "_transport", None), "store", None)
    if store is not None:
        summary = {
            "questions_tested": len(trace_ids),
            "failure_rate": _rate(len(failures), len(trace_ids)),
            "avg_citation_support": _avg(supports),
            "unsupported_claim_rate": _avg(unsupported_rates),
            "reliability_score": _avg(reliability_scores),
            "top_failures": _top_failures(failures),
        }
        eval_run_id = store.create_eval_run(dataset=dataset_path, endpoint=endpoint, summary=summary)
        for record in question_records:
            store.add_eval_question(
                eval_run_id=eval_run_id,
                question=record["question"],
                trace_id=record["trace_id"],
                position=record["position"],
            )

    output_path = report_path
    if generate_report and trace_ids:
        if output_path is None:
            output_path = str(Path(".contexttrace") / "reports" / ("eval_%s.html" % (eval_run_id or trace_ids[-1])))
        traces = [contexttrace.get_trace(trace_id) for trace_id in trace_ids]
        ReportGenerator().generate_eval_report(
            {
                "id": eval_run_id or "local-eval",
                "dataset": dataset_path,
                "endpoint": endpoint,
                "summary": {
                    "questions_tested": len(trace_ids),
                    "failure_rate": _rate(len(failures), len(trace_ids)),
                    "avg_citation_support": _avg(supports),
                    "unsupported_claim_rate": _avg(unsupported_rates),
                    "reliability_score": _avg(reliability_scores),
                    "top_failures": _top_failures(failures),
                },
            },
            traces,
            path=output_path,
        )

    return EndpointEvalResult(
        eval_run_id=eval_run_id,
        trace_ids=trace_ids,
        questions_tested=len(trace_ids),
        reliability_score=_avg(reliability_scores),
        failure_rate=_rate(len(failures), len(trace_ids)),
        avg_citation_support=_avg(supports),
        unsupported_claim_rate=_avg(unsupported_rates),
        top_failures=_top_failures(failures),
        report_path=output_path,
    )


def _load_dataset(path: str) -> list[dict[str, Any]]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(data, list):
        raw_questions = data
    elif isinstance(data, dict):
        raw_questions = data.get("questions") or []
    else:
        raw_questions = []

    questions: list[dict[str, Any]] = []
    for index, item in enumerate(raw_questions):
        if isinstance(item, str):
            questions.append({"id": "q%s" % (index + 1), "query": item})
        elif isinstance(item, dict):
            questions.append(dict(item))
    return questions


def _default_caller(
    endpoint: str,
    method: str,
    headers: dict[str, str],
    body: dict[str, Any] | None,
    timeout: float,
) -> dict[str, Any]:
    request_headers = {"Content-Type": "application/json", **headers}
    url = endpoint
    data = None
    if method == "GET":
        query = urllib.parse.urlencode(body or {})
        separator = "&" if "?" in endpoint else "?"
        url = endpoint + (separator + query if query else "")
    else:
        data = json.dumps(body or {}).encode("utf-8")
    request = urllib.request.Request(url, data=data, headers=request_headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        raise RuntimeError("RAG endpoint request failed: %s" % exc) from exc


def _render_body(template: Any, *, query: str) -> Any:
    if isinstance(template, str):
        return template.replace("{{query}}", query)
    if isinstance(template, list):
        return [_render_body(value, query=query) for value in template]
    if isinstance(template, dict):
        return {key: _render_body(value, query=query) for key, value in template.items()}
    return template


def _extract(payload: Any, path: str) -> Any:
    if path in {"", "$"}:
        return payload
    if not path.startswith("$."):
        return None
    value = payload
    for part in path[2:].split("."):
        if value is None:
            return None
        if "[" in part and part.endswith("]"):
            name, raw_index = part[:-1].split("[", 1)
            value = value.get(name) if isinstance(value, dict) else None
            try:
                value = value[int(raw_index)]
            except (TypeError, ValueError, IndexError):
                return None
        elif isinstance(value, dict):
            value = value.get(part)
        else:
            return None
    return value


def _normalize_chunks(raw_contexts: Any) -> list[dict[str, Any]]:
    if raw_contexts is None:
        return []
    if isinstance(raw_contexts, (str, dict)):
        raw_contexts = [raw_contexts]
    chunks = []
    for index, item in enumerate(raw_contexts if isinstance(raw_contexts, CollectionsIterable) else []):
        if isinstance(item, str):
            chunks.append({"chunk_id": "chunk_%s" % (index + 1), "content": item})
        elif isinstance(item, dict):
            chunks.append(
                {
                    "chunk_id": str(item.get("chunk_id") or item.get("id") or "chunk_%s" % (index + 1)),
                    "content": str(item.get("content") or item.get("text") or item.get("page_content") or ""),
                    "source": item.get("source"),
                    "metadata": item.get("metadata") or {},
                    "relevance_score": item.get("relevance_score") or item.get("score"),
                }
            )
    return [chunk for chunk in chunks if chunk.get("content")]


def _normalize_citations(
    raw_citations: Any,
    *,
    answer: Any,
    chunks: list[dict[str, Any]],
    default_to_first_chunk: bool = True,
) -> list[dict[str, Any]]:
    if raw_citations is None:
        raw_citations = []
    if isinstance(raw_citations, dict):
        raw_citations = [raw_citations]
    citations = []
    for item in raw_citations if isinstance(raw_citations, CollectionsIterable) and not isinstance(raw_citations, str) else []:
        if isinstance(item, dict):
            source_chunk_id = item.get("source_id") or item.get("source_chunk_id") or item.get("chunk_id") or item.get("id")
            if source_chunk_id is None and item.get("source") and chunks:
                source_chunk_id = chunks[0]["chunk_id"]
            citations.append(
                {
                    "claim": str(item.get("claim") or item.get("text") or answer or ""),
                    "source_chunk_id": str(source_chunk_id or (chunks[0]["chunk_id"] if chunks else "")),
                }
            )
        elif isinstance(item, str) and chunks:
            citations.append({"claim": item, "source_chunk_id": chunks[0]["chunk_id"]})
    if default_to_first_chunk and not citations and answer and chunks:
        citations.append({"claim": str(answer), "source_chunk_id": chunks[0]["chunk_id"]})
    return [citation for citation in citations if citation["claim"] and citation["source_chunk_id"]]


def _avg(values: list[float]) -> float:
    return round(sum(values) / len(values), 3) if values else 0.0


def _rate(count: int, total: int) -> float:
    return round(count / total, 3) if total else 0.0


def _top_failures(failures: list[str]) -> list[str]:
    counts = {failure: failures.count(failure) for failure in set(failures)}
    return [name for name, _ in sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:5]]
