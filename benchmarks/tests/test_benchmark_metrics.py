from __future__ import annotations

import json
from pathlib import Path

import pytest

from benchmarks.metrics import aggregate_results, rank_strategies
from benchmarks.run_benchmark import run_benchmark


def test_aggregate_results_computes_strategy_metrics() -> None:
    records = [
        {
            "strategy": "dense_top_k",
            "citation_support": 0.8,
            "unsupported_claim_rate": 0.1,
            "failure": False,
            "retrieval_miss": False,
            "tokens": 100,
            "latency_ms": 200,
            "cost_usd": 0.0001,
        },
        {
            "strategy": "dense_top_k",
            "citation_support": 0.6,
            "unsupported_claim_rate": 0.4,
            "failure": True,
            "retrieval_miss": True,
            "tokens": 200,
            "latency_ms": 300,
            "cost_usd": 0.0002,
        },
        {
            "strategy": "hybrid",
            "citation_support": 0.9,
            "unsupported_claim_rate": 0.05,
            "failure": False,
            "retrieval_miss": False,
            "tokens": 160,
            "latency_ms": 260,
            "cost_usd": 0.00016,
        },
    ]

    summary = aggregate_results(records)

    assert summary["dense_top_k"]["citation_support"] == pytest.approx(0.7)
    assert summary["dense_top_k"]["unsupported_claim_rate"] == pytest.approx(0.25)
    assert summary["dense_top_k"]["failure_rate"] == pytest.approx(0.5)
    assert summary["dense_top_k"]["retrieval_miss_rate"] == pytest.approx(0.5)
    assert summary["dense_top_k"]["average_tokens"] == pytest.approx(150)
    assert summary["hybrid"]["failure_rate"] == pytest.approx(0)


def test_rank_strategies_prioritizes_reliability_then_cost() -> None:
    summary = {
        "cheap": {
            "citation_support": 0.8,
            "unsupported_claim_rate": 0.12,
            "failure_rate": 0.1,
            "retrieval_miss_rate": 0.0,
            "average_tokens": 100,
            "average_latency_ms": 120,
            "average_cost_usd": 0.00008,
        },
        "reliable": {
            "citation_support": 0.91,
            "unsupported_claim_rate": 0.08,
            "failure_rate": 0.0,
            "retrieval_miss_rate": 0.0,
            "average_tokens": 200,
            "average_latency_ms": 250,
            "average_cost_usd": 0.0002,
        },
    }

    ranked = rank_strategies(summary)

    assert [row["strategy"] for row in ranked] == ["reliable", "cheap"]


def test_run_benchmark_writes_reproducible_outputs(tmp_path: Path) -> None:
    dataset_dir = Path(__file__).resolve().parents[1] / "datasets" / "refund_policy"
    output_dir = tmp_path / "results"
    website_export = tmp_path / "web" / "benchmark-results.json"
    website_assets = tmp_path / "web" / "public" / "benchmarks"

    result = run_benchmark(
        dataset_dir=dataset_dir,
        output_dir=output_dir,
        strategies=("dense_top_k", "contexttrace_adaptive"),
        website_export=website_export,
        website_assets_dir=website_assets,
        generated_at="test-run",
    )

    results_path = Path(result["results_path"])
    summary_path = Path(result["summary_path"])
    payload = json.loads(results_path.read_text(encoding="utf-8"))
    website_payload = json.loads(website_export.read_text(encoding="utf-8"))

    assert results_path.exists()
    assert summary_path.exists()
    assert payload["generated_at"] == "test-run"
    assert len(payload["question_results"]) == 8
    assert "Honest Tradeoffs" in summary_path.read_text(encoding="utf-8")
    assert website_payload["website_charts"]["citation_support"].endswith("citation_support.svg")
    assert (website_assets / "refund_policy" / "citation_support.svg").exists()

