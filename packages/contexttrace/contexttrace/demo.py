from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from contexttrace.client import ContextTrace
from contexttrace.demo_data import load_demo_dataset
from contexttrace.report import ReportGenerator


STRATEGY_TOP_K = {
    "dense_top_k": 2,
    "bm25": 2,
    "bm25_top_k": 2,
    "hybrid": 3,
    "hybrid_rerank": 4,
    "corrective": 4,
    "corrective_rag": 4,
    "adaptive": 4,
    "contexttrace_adaptive": 4,
}


@dataclass(frozen=True)
class DemoRun:
    dataset: str
    eval_run_id: str | None
    trace_ids: list[str]
    report_path: str
    summary: dict[str, Any]


def run_demo_dataset(
    *,
    dataset: str,
    contexttrace: ContextTrace,
    strategy: str = "adaptive",
    report_path: str | None = None,
    max_questions: int | None = None,
) -> DemoRun:
    loaded = load_demo_dataset(dataset)
    chunks = _document_chunks(loaded["documents"])
    questions = list(loaded["questions"])
    if max_questions is not None:
        questions = questions[:max_questions]

    trace_ids: list[str] = []
    traces: list[dict[str, Any]] = []
    for index, question in enumerate(questions):
        trace_id = _run_question(
            contexttrace=contexttrace,
            dataset_name=loaded["name"],
            question=question,
            expected_answer=loaded["expected_answers"].get(question["id"], ""),
            expected_sources=list(loaded["expected_sources"].get(question["id"], [])),
            chunks=chunks,
            strategy=strategy,
            position=index,
        )
        trace_ids.append(trace_id)
        traces.append(contexttrace.get_trace(trace_id))

    summary = aggregate_trace_metrics(traces)
    store = getattr(getattr(contexttrace, "_transport", None), "store", None)
    eval_run_id = None
    if store is not None:
        eval_run_id = store.create_eval_run(dataset=loaded["name"], endpoint="contexttrace-demo", summary=summary)
        for index, question in enumerate(questions):
            store.add_eval_question(
                eval_run_id=eval_run_id,
                question=question,
                trace_id=trace_ids[index],
                position=index,
            )

    if report_path is None:
        report_path = str(Path(".contexttrace") / "reports" / ("%s_demo.html" % loaded["name"]))
    ReportGenerator().generate_eval_report(
        {
            "id": eval_run_id or "%s-demo" % loaded["name"],
            "dataset": loaded["name"],
            "endpoint": "contexttrace-demo",
            "summary": summary,
        },
        traces,
        path=report_path,
    )
    return DemoRun(
        dataset=loaded["name"],
        eval_run_id=eval_run_id,
        trace_ids=trace_ids,
        report_path=report_path,
        summary=summary,
    )


def aggregate_trace_metrics(traces: Iterable[dict[str, Any]]) -> dict[str, Any]:
    rows = list(traces)
    count = len(rows)
    if not rows:
        return {
            "questions_tested": 0,
            "reliability_score": 0.0,
            "failure_rate": 0.0,
            "citation_support": 0.0,
            "unsupported_claim_rate": 0.0,
            "retrieval_miss_rate": 0.0,
            "latency_ms": 0.0,
            "token_count": 0.0,
            "cost_usd": 0.0,
            "top_failures": [],
        }

    failures: list[str] = []
    citation_support: list[float] = []
    unsupported: list[float] = []
    retrieval_misses = 0
    reliability_scores: list[float] = []
    latency: list[float] = []
    tokens: list[float] = []
    for trace in rows:
        evaluation = trace.get("evaluation") or {}
        failure = evaluation.get("failure") or {}
        scores = evaluation.get("scores") or {}
        failure_type = failure.get("failure_type") or "unknown"
        if failure_type != "no_failure_detected":
            failures.append(failure_type)
        if failure_type == "retrieval_miss":
            retrieval_misses += 1
        citation_support.append(float(scores.get("citation_support") or 0.0))
        unsupported.append(float(scores.get("unsupported_claim_rate") or 0.0))
        reliability_scores.append(float((evaluation.get("reliability") or {}).get("score") or 0.0))
        answer = trace.get("answer") or {}
        usage = answer.get("usage") or {}
        metadata = answer.get("metadata") or {}
        if "latency_ms" in metadata:
            latency.append(float(metadata["latency_ms"]))
        if "total_tokens" in usage:
            tokens.append(float(usage["total_tokens"]))
    avg_tokens = _avg(tokens)
    return {
        "questions_tested": count,
        "reliability_score": _avg(reliability_scores),
        "failure_rate": round(len(failures) / count, 3),
        "citation_support": _avg(citation_support),
        "avg_citation_support": _avg(citation_support),
        "unsupported_claim_rate": _avg(unsupported),
        "retrieval_miss_rate": round(retrieval_misses / count, 3),
        "latency_ms": _avg(latency),
        "token_count": avg_tokens,
        "cost_usd": round(avg_tokens * 0.000001, 6),
        "top_failures": _top_failures(failures),
    }


def _run_question(
    *,
    contexttrace: ContextTrace,
    dataset_name: str,
    question: dict[str, Any],
    expected_answer: str,
    expected_sources: list[str],
    chunks: list[dict[str, Any]],
    strategy: str,
    position: int,
) -> str:
    query = str(question["query"])
    retrieved = _retrieve(query, chunks, top_k=STRATEGY_TOP_K.get(strategy, 3))
    expected_failure = question.get("expected_failure")
    if expected_sources and expected_failure in {None, "citation_mismatch"}:
        retrieved = _force_expected_sources(chunks, expected_sources, retrieved)
        retrieved = [
            chunk
            for chunk in retrieved
            if (chunk["source"] in expected_sources or (chunk.get("metadata") or {}).get("stance") != "archived")
        ]
    if expected_failure == "retrieval_miss":
        retrieved = [chunk for chunk in retrieved if chunk["source"] not in expected_sources]
        if not retrieved:
            retrieved = [chunk for chunk in chunks if chunk["source"] not in expected_sources][:2]
    if expected_failure == "conflicting_sources":
        retrieved = _force_expected_sources(chunks, expected_sources, retrieved)
    selected = retrieved[: max(1, min(len(retrieved), STRATEGY_TOP_K.get(strategy, 3)))]
    answer = _demo_answer(question, expected_answer)
    citations = _demo_citations(question, answer, selected, chunks, expected_sources)
    latency_ms = 35 + (position * 7) + len(selected) * 12
    token_count = 80 + len(answer.split()) + sum(len(chunk["content"].split()) for chunk in selected)

    with contexttrace.trace(
        query=query,
        metadata={
            "dataset": dataset_name,
            "question_id": question["id"],
            "question_type": question.get("type"),
            "expected_sources": expected_sources,
            "expected_failure": expected_failure or "no_failure_detected",
            "strategy": strategy,
        },
    ) as trace:
        trace.log_retrieval(retrieved, metadata={"strategy": strategy})
        trace.log_context(selected)
        trace.log_answer(
            answer,
            model="contexttrace-demo-rag",
            usage={"total_tokens": token_count},
            metadata={"latency_ms": latency_ms, "strategy": strategy},
        )
        if citations:
            trace.log_citations(citations)
        trace.evaluate()
        return str(trace.trace_id)


def _document_chunks(documents: dict[str, str]) -> list[dict[str, Any]]:
    chunks: list[dict[str, Any]] = []
    for source, text in documents.items():
        sections = [section.strip() for section in re.split(r"\n##\s+", text) if section.strip()]
        for index, section in enumerate(sections):
            content = re.sub(r"^#\s+", "", section).strip()
            if not content:
                continue
            if len(content.split()) <= 4 and Path(source).stem.replace("_", " ").lower() in content.lower():
                continue
            chunks.append(
                {
                    "chunk_id": "%s_%s" % (Path(source).stem, index + 1),
                    "content": content,
                    "source": source,
                    "metadata": {
                        "section": content.splitlines()[0][:80],
                        "stance": _stance(source, content),
                    },
                    "relevance_score": 0.0,
                }
            )
    return chunks


def _retrieve(query: str, chunks: list[dict[str, Any]], *, top_k: int) -> list[dict[str, Any]]:
    query_terms = _terms(query)
    scored = []
    for chunk in chunks:
        score = len(query_terms & _terms(chunk["content"])) / max(len(query_terms), 1)
        scored.append({**chunk, "relevance_score": round(score, 3)})
    return sorted(scored, key=lambda chunk: (-float(chunk["relevance_score"]), chunk["source"]))[:top_k]


def _force_expected_sources(
    chunks: list[dict[str, Any]],
    expected_sources: list[str],
    retrieved: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    forced = [chunk for chunk in chunks if chunk["source"] in expected_sources]
    seen = {chunk["chunk_id"] for chunk in forced}
    return forced + [chunk for chunk in retrieved if chunk["chunk_id"] not in seen]


def _demo_answer(question: dict[str, Any], expected_answer: str) -> str:
    failure = question.get("expected_failure")
    if failure == "should_have_abstained":
        return "Yes, the documents say this exception is available to eligible employees or customers."
    if failure == "unsupported_answer":
        return "Yes, the policy gives a special exception that is not limited by the documented rules."
    return expected_answer


def _demo_citations(
    question: dict[str, Any],
    answer: str,
    selected: list[dict[str, Any]],
    chunks: list[dict[str, Any]],
    expected_sources: list[str],
) -> list[dict[str, Any]]:
    if not answer or not selected:
        return []
    failure = question.get("expected_failure")
    claim = answer.split(".")[0].strip() + "."
    if failure == "citation_mismatch":
        wrong = next((chunk for chunk in selected if chunk["source"] not in expected_sources), None)
        if wrong is None:
            wrong = next((chunk for chunk in chunks if chunk["source"] not in expected_sources), selected[0])
        return [{"claim": claim, "source_chunk_id": wrong["chunk_id"]}]
    return [{"claim": claim, "source_chunk_id": selected[0]["chunk_id"]}]


def _stance(source: str, content: str) -> str:
    lowered = (source + " " + content).lower()
    if "archived" in lowered or "old_" in lowered or "legacy" in lowered:
        return "archived"
    if "current" in lowered or "policy" in lowered:
        return "current"
    return "neutral"


def _terms(text: str) -> set[str]:
    return {
        token.strip(".,:;!?()[]{}\"'").lower().rstrip("s")
        for token in text.split()
        if len(token.strip(".,:;!?()[]{}\"'")) > 2
    }


def _avg(values: list[float]) -> float:
    return round(sum(values) / len(values), 3) if values else 0.0


def _top_failures(failures: list[str]) -> list[str]:
    counts = {failure: failures.count(failure) for failure in set(failures)}
    return [name for name, _ in sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:5]]
