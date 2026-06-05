# Regression Testing

Use ContextTrace as a local RAG regression test before merging retrieval, prompt, chunking, or reranking changes.

## Replay Saved RAG Failures

Turn a saved portable trace into a regression case:

```bash
contexttrace suite create traces/refund_failure.json \
  --name refund-suite \
  --out .contexttrace/suites/refund-suite.json
```

Replay the case against your current RAG endpoint:

```bash
contexttrace suite run .contexttrace/suites/refund-suite.json \
  --endpoint http://localhost:8000/query \
  --answer-path $.answer \
  --contexts-path $.contexts \
  --citations-path $.citations \
  --report
```

The suite run exits non-zero when:

- a saved failure still has unsupported or unverifiable claims
- a previously supported case regresses
- citation mismatches appear
- the current answer should have abstained
- the endpoint response cannot be converted into a portable trace

Generate a report from a saved result:

```bash
contexttrace suite report .contexttrace/suites/refund-suite_results.json
```

## Manage Suite Cases

Add new saved failures as they appear:

```bash
contexttrace suite add .contexttrace/suites/refund-suite.json traces/new_failure.json
```

Inspect the suite:

```bash
contexttrace suite list .contexttrace/suites/refund-suite.json
contexttrace suite list .contexttrace/suites/refund-suite.json --json
```

Remove a case directly:

```bash
contexttrace suite remove .contexttrace/suites/refund-suite.json refund_processing_failure
```

Prune cases by status from a saved suite run:

```bash
contexttrace suite prune .contexttrace/suites/refund-suite.json \
  --results .contexttrace/suites/refund-suite_results.json \
  --status passed
```

## GitHub Actions

Use `examples/contexttrace-suite-ci.yml` as a starter workflow. The expected CI loop is:

```text
start local RAG app -> run contexttrace suite -> upload JSON and HTML report
```

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
