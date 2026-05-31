# ContextTrace Benchmarks

The benchmark pipeline produces deterministic RAG strategy comparisons for the website, launch posts, and regression discussions. It does not call a hosted LLM by default, so the same dataset and code produce stable scores.

## Run a Benchmark

```bash
python benchmarks/run_benchmark.py --dataset datasets/refund_policy
```

The dataset path may be either a real path or a path relative to `benchmarks/`. The command writes:

- `benchmarks/results/<dataset>/benchmark_results.json`
- `benchmarks/results/<dataset>/benchmark_summary.md`
- `benchmarks/results/<dataset>/charts/*.svg`
- `apps/web/lib/benchmark-results.json`
- `apps/web/public/benchmarks/<dataset>/*.svg`

## Datasets

Each dataset lives under `benchmarks/datasets/<name>` and includes:

- `documents/` with Markdown source documents
- `questions.json`
- `expected_answers.json`
- `expected_sources.json`

Current sample datasets:

- `employee_handbook`
- `refund_policy`
- `ai_paper_qa`

## Strategies

The runner compares:

- `dense_top_k`
- `bm25_top_k`
- `hybrid`
- `hybrid_rerank`
- `corrective_rag`
- `contexttrace_adaptive`

The implementation is intentionally local and deterministic. It uses token overlap, lightweight synonym expansion, and strategy-specific cost and latency modeling to create stable public-report fixtures. Live provider benchmarks can be layered on later, but public numbers should clearly disclose which runner produced them.

## Metrics

The summary reports:

- `citation_support`
- `unsupported_claim_rate`
- `failure_rate`
- `retrieval_miss_rate`
- `average_tokens`
- `average_latency_ms`
- `average_cost_usd`

`benchmark_summary.md` includes tradeoff notes so the report does not imply that one strategy wins every dimension.

## Website Export

The dashboard benchmark page reads `apps/web/lib/benchmark-results.json` and chart SVGs copied to `apps/web/public/benchmarks/<dataset>`. Re-run the benchmark command after editing datasets or strategy scoring.

