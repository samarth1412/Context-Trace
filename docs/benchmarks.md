# Benchmarks

ContextTrace includes a local benchmark command for comparing RAG strategies and producing reproducible report artifacts.

```bash
contexttrace benchmark --dataset datasets/demo/refund_policy
```

Supported strategy labels:

- `dense_top_k`
- `bm25`
- `hybrid`
- `hybrid_rerank`
- `corrective`
- `adaptive`

If your full retrieval stack is not available in CI, use endpoint eval mode instead:

```bash
contexttrace eval \
  --dataset evals/questions.json \
  --endpoint http://localhost:8000/query
```

Benchmark metrics:

- `failure_rate`
- `citation_support`
- `unsupported_claim_rate`
- `retrieval_miss_rate`
- `latency_ms`
- `token_count`
- `cost_usd`

Outputs:

- `benchmark_results.json`
- `benchmark_summary.md`
- `benchmark_report.html`

Use thresholds to fail CI:

```bash
contexttrace benchmark \
  --dataset datasets/demo/refund_policy \
  --fail-on "failure_rate>0.25" \
  --fail-on "citation_support<0.80"
```

The report is static HTML and can be used for GitHub artifacts, screenshots, and launch posts.
