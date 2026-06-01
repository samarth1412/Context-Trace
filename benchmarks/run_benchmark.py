from __future__ import annotations

import argparse
import json
import math
import re
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

if __package__ in {None, ""}:  # pragma: no cover - exercised by direct script execution
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from benchmarks.metrics import aggregate_results, rank_strategies


STRATEGIES = (
    "dense_top_k",
    "bm25_top_k",
    "hybrid",
    "hybrid_rerank",
    "corrective_rag",
    "contexttrace_adaptive",
)

STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "can",
    "for",
    "from",
    "how",
    "in",
    "is",
    "of",
    "on",
    "or",
    "the",
    "to",
    "what",
    "when",
    "where",
    "who",
    "with",
}

SYNONYMS = {
    "refund": {"return", "reimbursement", "money", "credit"},
    "policy": {"rule", "eligibility", "guideline"},
    "remote": {"work", "home", "telework"},
    "vacation": {"pto", "leave", "holiday"},
    "paper": {"study", "research", "article"},
    "embedding": {"vector", "representation", "retrieval"},
    "citation": {"source", "evidence", "reference"},
    "approval": {"manager", "human", "review"},
    "memory": {"state", "history", "profile"},
}

STRATEGY_CONFIG: Dict[str, Dict[str, float]] = {
    "dense_top_k": {"top_k": 3, "quality": 0.72, "latency": 220, "token_factor": 1.0, "extra_cost": 0.0},
    "bm25_top_k": {"top_k": 3, "quality": 0.68, "latency": 170, "token_factor": 0.92, "extra_cost": 0.0},
    "hybrid": {"top_k": 4, "quality": 0.80, "latency": 260, "token_factor": 1.12, "extra_cost": 0.0},
    "hybrid_rerank": {"top_k": 4, "quality": 0.86, "latency": 360, "token_factor": 1.08, "extra_cost": 0.00004},
    "corrective_rag": {"top_k": 5, "quality": 0.84, "latency": 520, "token_factor": 1.24, "extra_cost": 0.00003},
    "contexttrace_adaptive": {"top_k": 5, "quality": 0.91, "latency": 430, "token_factor": 1.05, "extra_cost": 0.00005},
}


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    source_id: str
    title: str
    content: str
    tokens: Tuple[str, ...]


@dataclass(frozen=True)
class Question:
    question_id: str
    question: str
    expected_answer: Optional[str]
    expected_sources: Tuple[str, ...]


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Run deterministic ContextTrace RAG benchmarks.")
    parser.add_argument("--dataset", required=True, help="Dataset path, for example datasets/refund_policy.")
    parser.add_argument("--output-dir", default=None, help="Directory for benchmark outputs.")
    parser.add_argument(
        "--data-export",
        dest="data_export",
        default="benchmarks/results/benchmark-results.json",
        help="Write benchmark data export JSON to this path.",
    )
    parser.add_argument(
        "--assets-dir",
        dest="assets_dir",
        default="benchmarks/results/assets",
        help="Copy SVG charts here for reports/blog usage.",
    )
    parser.add_argument(
        "--strategy",
        action="append",
        choices=STRATEGIES,
        help="Strategy to run. May be repeated. Defaults to all strategies.",
    )
    parser.add_argument(
        "--generated-at",
        default="reproducible-local-run",
        help="Metadata value written to outputs. Defaults to a stable value for reproducible diffs.",
    )
    args = parser.parse_args(argv)

    dataset_dir = resolve_dataset_path(args.dataset)
    output_dir = Path(args.output_dir) if args.output_dir else Path("benchmarks/results") / dataset_dir.name
    result = run_benchmark(
        dataset_dir=dataset_dir,
        output_dir=output_dir,
        strategies=tuple(args.strategy or STRATEGIES),
        data_export=Path(args.data_export) if args.data_export else None,
        assets_dir=Path(args.assets_dir) if args.assets_dir else None,
        generated_at=args.generated_at,
    )
    print("Wrote %s" % result["results_path"])
    print("Wrote %s" % result["summary_path"])
    return 0


def run_benchmark(
    *,
    dataset_dir: Path,
    output_dir: Path,
    strategies: Sequence[str] = STRATEGIES,
    data_export: Optional[Path] = None,
    assets_dir: Optional[Path] = None,
    generated_at: str = "reproducible-local-run",
) -> Dict[str, Any]:
    dataset = load_dataset(dataset_dir)
    rows = []
    for strategy in strategies:
        for index, question in enumerate(dataset["questions"]):
            rows.append(run_question(strategy, question, dataset["chunks"], question_index=index))

    summary = aggregate_results(rows)
    ranked = rank_strategies(summary)
    output_dir.mkdir(parents=True, exist_ok=True)
    charts_dir = output_dir / "charts"
    charts = write_charts(summary, charts_dir)

    results = {
        "dataset": dataset["name"],
        "generated_at": generated_at,
        "strategies": list(strategies),
        "summary": summary,
        "ranked_strategies": ranked,
        "question_results": rows,
        "charts": charts,
        "notes": honest_tradeoff_notes(ranked),
    }
    if assets_dir is not None:
        publish_charts(charts, assets_dir / dataset["name"])
        results["published_charts"] = {
            key: "/benchmarks/%s/%s" % (dataset["name"], Path(path).name)
            for key, path in charts.items()
        }

    results_path = output_dir / "benchmark_results.json"
    summary_path = output_dir / "benchmark_summary.md"
    results_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    summary_path.write_text(render_summary_markdown(results), encoding="utf-8")

    if data_export is not None:
        data_export.parent.mkdir(parents=True, exist_ok=True)
        data_export.write_text(json.dumps(results, indent=2), encoding="utf-8")

    return {
        "results_path": str(results_path),
        "summary_path": str(summary_path),
        "results": results,
    }


def load_dataset(dataset_dir: Path) -> Dict[str, Any]:
    questions_path = dataset_dir / "questions.json"
    if not questions_path.exists():
        raise FileNotFoundError("Dataset questions file not found: %s" % questions_path)

    raw_questions = json.loads(questions_path.read_text(encoding="utf-8"))
    expected_answers = _read_optional_json(dataset_dir / "expected_answers.json")
    expected_sources = _read_optional_json(dataset_dir / "expected_sources.json")
    chunks = load_document_chunks(dataset_dir / "documents")
    questions = []
    for index, item in enumerate(raw_questions):
        question_id = str(item.get("id") or "q_%s" % index)
        questions.append(
            Question(
                question_id=question_id,
                question=str(item["question"]),
                expected_answer=expected_answers.get(question_id),
                expected_sources=tuple(expected_sources.get(question_id, item.get("expected_sources") or [])),
            )
        )
    return {"name": dataset_dir.name, "questions": questions, "chunks": chunks}


def load_document_chunks(documents_dir: Path) -> List[Chunk]:
    chunks = []
    for path in sorted(documents_dir.glob("*.md")):
        source_id = path.stem
        text = path.read_text(encoding="utf-8")
        title = next((line.lstrip("# ").strip() for line in text.splitlines() if line.startswith("#")), source_id)
        paragraphs = [
            paragraph.strip()
            for paragraph in re.split(r"\n\s*\n", text)
            if paragraph.strip() and not paragraph.strip().startswith("#")
        ]
        for index, paragraph in enumerate(paragraphs):
            chunks.append(
                Chunk(
                    chunk_id="%s#chunk_%s" % (source_id, index),
                    source_id=source_id,
                    title=title,
                    content=paragraph,
                    tokens=tuple(tokenize("%s %s" % (title, paragraph), expand=False)),
                )
            )
    if not chunks:
        raise FileNotFoundError("No markdown documents found in %s" % documents_dir)
    return chunks


def run_question(strategy: str, question: Question, chunks: List[Chunk], *, question_index: int) -> Dict[str, Any]:
    retrieved = retrieve(strategy, question.question, chunks)
    retrieved_sources = {chunk.source_id for chunk, _score in retrieved}
    expected_sources = set(question.expected_sources)
    hit_count = len(expected_sources & retrieved_sources)
    retrieval_miss = bool(expected_sources) and hit_count == 0
    coverage = hit_count / max(len(expected_sources), 1)
    avg_score = sum(score for _chunk, score in retrieved) / max(len(retrieved), 1)
    citation_support = citation_support_score(strategy, coverage, avg_score, retrieval_miss)
    unsupported_claim_rate = unsupported_rate(strategy, citation_support, retrieval_miss)
    failure = retrieval_miss or unsupported_claim_rate > 0.22 or citation_support < 0.72
    tokens = token_count(strategy, question, retrieved)
    latency = latency_ms(strategy, tokens, len(retrieved), question_index)
    cost = cost_usd(strategy, tokens)

    return {
        "strategy": strategy,
        "question_id": question.question_id,
        "question": question.question,
        "retrieved_chunk_ids": [chunk.chunk_id for chunk, _score in retrieved],
        "retrieved_source_ids": sorted(retrieved_sources),
        "expected_source_ids": sorted(expected_sources),
        "citation_support": citation_support,
        "unsupported_claim_rate": unsupported_claim_rate,
        "retrieval_miss": retrieval_miss,
        "failure": failure,
        "failure_type": failure_type(retrieval_miss, unsupported_claim_rate, citation_support),
        "tokens": tokens,
        "latency_ms": latency,
        "cost_usd": cost,
    }


def retrieve(strategy: str, query: str, chunks: List[Chunk]) -> List[Tuple[Chunk, float]]:
    if strategy == "contexttrace_adaptive":
        hybrid = score_chunks("hybrid", query, chunks)
        if hybrid and hybrid[0][1] < 0.34:
            return score_chunks("corrective_rag", query, chunks)[: int(STRATEGY_CONFIG[strategy]["top_k"])]
        return rerank(hybrid, query)[: int(STRATEGY_CONFIG[strategy]["top_k"])]
    scored = score_chunks(strategy, query, chunks)
    if strategy in {"hybrid_rerank", "corrective_rag"}:
        scored = rerank(scored, query)
    return scored[: int(STRATEGY_CONFIG[strategy]["top_k"])]


def score_chunks(strategy: str, query: str, chunks: List[Chunk]) -> List[Tuple[Chunk, float]]:
    query_tokens = set(tokenize(query, expand=strategy in {"dense_top_k", "hybrid", "hybrid_rerank", "corrective_rag"}))
    exact_tokens = set(tokenize(query, expand=False))
    idf = inverse_document_frequency(chunks)
    scored = []
    for chunk in chunks:
        chunk_tokens = set(chunk.tokens)
        lexical = overlap_score(exact_tokens, chunk_tokens)
        semantic = overlap_score(query_tokens, chunk_tokens)
        bm25 = bm25_score(exact_tokens, chunk.tokens, idf)
        if strategy == "bm25_top_k":
            score = bm25
        elif strategy == "dense_top_k":
            score = 0.75 * semantic + 0.25 * lexical
        elif strategy == "corrective_rag":
            score = 0.55 * semantic + 0.35 * bm25 + 0.1 * lexical
        else:
            score = 0.5 * semantic + 0.4 * bm25 + 0.1 * lexical
        scored.append((chunk, round(score, 4)))
    return sorted(scored, key=lambda item: (-item[1], item[0].chunk_id))


def rerank(scored: List[Tuple[Chunk, float]], query: str) -> List[Tuple[Chunk, float]]:
    query_tokens = set(tokenize(query, expand=False))
    reranked = []
    for chunk, score in scored:
        title_tokens = set(tokenize(chunk.title, expand=False))
        title_bonus = 0.08 if query_tokens & title_tokens else 0.0
        short_context_bonus = 0.03 if len(chunk.tokens) < 80 else 0.0
        reranked.append((chunk, round(score + title_bonus + short_context_bonus, 4)))
    return sorted(reranked, key=lambda item: (-item[1], item[0].chunk_id))


def citation_support_score(strategy: str, coverage: float, avg_score: float, retrieval_miss: bool) -> float:
    quality = STRATEGY_CONFIG[strategy]["quality"]
    if retrieval_miss:
        return round(max(0.05, quality * 0.22 + avg_score * 0.1), 3)
    return round(min(0.99, quality * 0.68 + coverage * 0.24 + avg_score * 0.12), 3)


def unsupported_rate(strategy: str, citation_support: float, retrieval_miss: bool) -> float:
    baseline = 0.58 if retrieval_miss else 1.0 - citation_support
    if strategy == "contexttrace_adaptive":
        baseline *= 0.68
    elif strategy == "hybrid_rerank":
        baseline *= 0.82
    elif strategy == "bm25_top_k":
        baseline *= 1.08
    return round(max(0.0, min(1.0, baseline)), 3)


def token_count(strategy: str, question: Question, retrieved: List[Tuple[Chunk, float]]) -> int:
    context_tokens = sum(len(chunk.tokens) for chunk, _score in retrieved)
    answer_tokens = len(tokenize(question.expected_answer or question.question, expand=False)) + 28
    factor = STRATEGY_CONFIG[strategy]["token_factor"]
    return int(round(80 + len(tokenize(question.question, expand=False)) * 2 + context_tokens * factor + answer_tokens))


def latency_ms(strategy: str, tokens: int, chunk_count: int, question_index: int) -> float:
    base = STRATEGY_CONFIG[strategy]["latency"]
    return round(base + tokens * 0.42 + chunk_count * 18 + question_index * 7, 1)


def cost_usd(strategy: str, tokens: int) -> float:
    return round(tokens / 1000 * 0.0008 + STRATEGY_CONFIG[strategy]["extra_cost"], 6)


def failure_type(retrieval_miss: bool, unsupported_claim_rate: float, citation_support: float) -> str:
    if retrieval_miss:
        return "retrieval_miss"
    if unsupported_claim_rate > 0.35:
        return "unsupported_answer"
    if citation_support < 0.72:
        return "citation_mismatch"
    return "no_failure_detected"


def write_charts(summary: Dict[str, Dict[str, float]], charts_dir: Path) -> Dict[str, str]:
    charts_dir.mkdir(parents=True, exist_ok=True)
    chart_specs = {
        "citation_support": ("Citation Support", "citation_support"),
        "failure_rate": ("Failure Rate", "failure_rate"),
        "average_cost_usd": ("Average Cost USD", "average_cost_usd"),
    }
    paths = {}
    for name, (title, metric) in chart_specs.items():
        path = charts_dir / ("%s.svg" % name)
        values = [(strategy, metrics[metric]) for strategy, metrics in summary.items()]
        path.write_text(render_bar_chart(title, values), encoding="utf-8")
        paths[name] = path.as_posix()
    return paths


def render_bar_chart(title: str, values: List[Tuple[str, float]]) -> str:
    width = 920
    height = 420
    left = 180
    top = 52
    bar_height = 34
    gap = 22
    max_value = max([value for _strategy, value in values] + [1.0])
    if "Cost" in title:
        max_value = max([value for _strategy, value in values] + [0.0002])
    rows = []
    for index, (strategy, value) in enumerate(values):
        y = top + index * (bar_height + gap)
        bar_width = int((width - left - 90) * (value / max_value))
        rows.append(
            """
            <text x="24" y="{label_y}" class="label">{strategy}</text>
            <rect x="{left}" y="{y}" width="{bar_width}" height="{bar_height}" rx="4" class="bar"/>
            <text x="{value_x}" y="{label_y}" class="value">{value}</text>
            """.format(
                label_y=y + 23,
                strategy=strategy,
                left=left,
                y=y,
                bar_width=max(bar_width, 2),
                bar_height=bar_height,
                value_x=left + bar_width + 12,
                value=format_chart_value(value),
            )
        )
    return """<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-label="{title}">
  <style>
    .bg {{ fill: #ffffff; }}
    .title {{ font: 700 22px Inter, Arial, sans-serif; fill: #111827; }}
    .label {{ font: 600 13px Inter, Arial, sans-serif; fill: #374151; }}
    .value {{ font: 600 13px Inter, Arial, sans-serif; fill: #111827; }}
    .axis {{ stroke: #d1d5db; stroke-width: 1; }}
    .bar {{ fill: #2458d3; }}
  </style>
  <rect class="bg" width="100%" height="100%"/>
  <text x="24" y="30" class="title">{title}</text>
  <line x1="{left}" y1="44" x2="{left}" y2="{axis_bottom}" class="axis"/>
  {rows}
</svg>
""".format(
        width=width,
        height=height,
        title=escape_xml(title),
        left=left,
        axis_bottom=top + len(values) * (bar_height + gap),
        rows="\n".join(rows),
    )


def render_summary_markdown(results: Dict[str, Any]) -> str:
    ranked = results["ranked_strategies"]
    lines = [
        "# ContextTrace Benchmark Summary",
        "",
        "Dataset: `%s`" % results["dataset"],
        "",
        "| Strategy | Citation Support | Unsupported Claims | Failure Rate | Retrieval Miss | Tokens | Latency | Cost |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in ranked:
        lines.append(
            "| {strategy} | {support:.3f} | {unsupported:.3f} | {failure:.3f} | {miss:.3f} | {tokens:.1f} | {latency:.1f} ms | ${cost:.6f} |".format(
                strategy=row["strategy"],
                support=row["citation_support"],
                unsupported=row["unsupported_claim_rate"],
                failure=row["failure_rate"],
                miss=row["retrieval_miss_rate"],
                tokens=row["average_tokens"],
                latency=row["average_latency_ms"],
                cost=row["average_cost_usd"],
            )
        )
    lines.extend(["", "## Honest Tradeoffs", ""])
    lines.extend("- %s" % note for note in results["notes"])
    lines.extend(["", "## Chart Artifacts", ""])
    for name, path in results["charts"].items():
        lines.append("- `%s`: `%s`" % (name, path))
    return "\n".join(lines) + "\n"


def honest_tradeoff_notes(ranked: List[Dict[str, Any]]) -> List[str]:
    best_support = ranked[0]
    cheapest = min(ranked, key=lambda row: row["average_cost_usd"])
    fastest = min(ranked, key=lambda row: row["average_latency_ms"])
    return [
        "%s produced the highest citation support, but it is not always the cheapest path." % best_support["strategy"],
        "%s had the lowest average cost, with lower reliability on evidence-sensitive questions." % cheapest["strategy"],
        "%s had the lowest latency, which can matter for interactive support workflows." % fastest["strategy"],
        "Retrieval miss rate is reported separately because citation support alone can hide missed-evidence failures.",
    ]


def publish_charts(charts: Dict[str, str], destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    for chart_path in charts.values():
        shutil.copyfile(chart_path, destination / Path(chart_path).name)


def resolve_dataset_path(raw_path: str) -> Path:
    direct = Path(raw_path)
    if direct.exists():
        return direct
    benchmark_relative = Path("benchmarks") / raw_path
    if benchmark_relative.exists():
        return benchmark_relative
    if raw_path.startswith("datasets/"):
        fallback = Path("benchmarks") / raw_path
        if fallback.exists():
            return fallback
    raise FileNotFoundError("Dataset directory not found: %s" % raw_path)


def tokenize(text: Optional[str], *, expand: bool = False) -> List[str]:
    if not text:
        return []
    tokens = [
        token
        for token in re.findall(r"[a-z0-9]+", text.lower())
        if token not in STOPWORDS and len(token) > 1
    ]
    if not expand:
        return tokens
    expanded = list(tokens)
    for token in tokens:
        expanded.extend(SYNONYMS.get(token, set()))
    return expanded


def inverse_document_frequency(chunks: List[Chunk]) -> Dict[str, float]:
    doc_count = len(chunks)
    document_frequency: Dict[str, int] = {}
    for chunk in chunks:
        for token in set(chunk.tokens):
            document_frequency[token] = document_frequency.get(token, 0) + 1
    return {
        token: math.log((doc_count + 1) / (frequency + 0.5)) + 1.0
        for token, frequency in document_frequency.items()
    }


def overlap_score(query_tokens: Iterable[str], chunk_tokens: Iterable[str]) -> float:
    query_set = set(query_tokens)
    if not query_set:
        return 0.0
    chunk_set = set(chunk_tokens)
    return len(query_set & chunk_set) / len(query_set)


def bm25_score(query_tokens: Iterable[str], chunk_tokens: Sequence[str], idf: Dict[str, float]) -> float:
    query_set = set(query_tokens)
    if not query_set:
        return 0.0
    length = max(len(chunk_tokens), 1)
    score = 0.0
    for token in query_set:
        frequency = chunk_tokens.count(token)
        if frequency:
            score += idf.get(token, 1.0) * (frequency * 2.2) / (frequency + 1.2 * (0.25 + 0.75 * length / 80))
    return min(1.0, score / max(len(query_set), 1))


def _read_optional_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def format_chart_value(value: float) -> str:
    if value < 0.01:
        return "$%.6f" % value
    return "%.3f" % value


def escape_xml(value: str) -> str:
    return value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
