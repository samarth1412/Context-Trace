# Regression Testing

Use ContextTrace as a local RAG regression test before merging retrieval, prompt, chunking, or reranking changes.

## Benchmark A Demo Dataset

```bash
contexttrace benchmark --dataset datasets/demo/refund_policy
```

Outputs:

- `.contexttrace/benchmarks/benchmark_results.json`
- `.contexttrace/benchmarks/benchmark_summary.md`
- `.contexttrace/benchmarks/benchmark_report.html`

## Fail On Thresholds

```bash
contexttrace benchmark \
  --dataset datasets/demo/refund_policy \
  --fail-on "failure_rate>0.25" \
  --fail-on "citation_support<0.80" \
  --fail-on "unsupported_claim_rate>0.15"
```

The command exits non-zero when any threshold fails.

Supported threshold metrics:

- `failure_rate`
- `citation_support`
- `unsupported_claim_rate`
- `retrieval_miss_rate`
- `latency_ms`
- `token_count`
- `cost_usd`
- `reliability_score`

## Evaluate Your Endpoint

```bash
contexttrace eval \
  --dataset evals/questions.json \
  --endpoint http://localhost:8000/query \
  --answer-path $.answer \
  --contexts-path $.contexts \
  --citations-path $.citations \
  --fail-on "failure_rate>0.25"
```

This is useful when your RAG app is already running locally and you do not want to add SDK instrumentation yet.
