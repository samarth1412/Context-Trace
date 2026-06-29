# Benchmarks

ContextTrace has two distinct benchmark surfaces: product evaluation for a RAG
system and ContextTrace-Bench for the verifier itself.

## Evaluate A RAG System

Compare retrieval strategies on a local dataset:

```bash
contexttrace benchmark \
  --dataset datasets/demo/refund_policy \
  --fail-on "failure_rate>0.25" \
  --fail-on "citation_support<0.80"
```

Use endpoint evaluation when the retrieval stack is not installed locally:

```bash
contexttrace eval \
  --dataset evals/questions.json \
  --endpoint http://localhost:8000/query
```

Product reports include failure rate, citation support, unsupported-claim rate,
retrieval-miss rate, latency, token count, and cost.

## Evaluate ContextTrace

Run the local verifier benchmark from the repository root:

```bash
python benchmarks/contexttrace_bench/run_contexttrace.py \
  --mode semantic \
  --case-set all \
  --enforce-sota-gates
```

Run the separate public-doc holdout:

```bash
python benchmarks/contexttrace_bench/run_contexttrace.py \
  --mode semantic \
  --case-set public_holdout \
  --no-generated-cases \
  --output-dir benchmarks/contexttrace_bench/out/public_holdout
```

Generated outputs include JSON results, Markdown summaries, an HTML report,
confidence intervals, per-label metrics, error analysis, and evaluator-ready
candidate inputs. The `out/` directory is intentionally ignored by Git.

## Evidence Policy

Passing the built-in regression gates does not justify a general RAG evaluation
SOTA claim. Run the separate fail-closed claim gate after restoring the
versioned evidence archive from the matching GitHub release:

```bash
python benchmarks/contexttrace_bench/sota_gate.py --allow-not-ready
```

The current gate passes `8/10` checks. Independent RAGTruth review and
ContextTrace-Diag-150 sign-off remain open, so current metrics are
dataset-specific calibration evidence.

## Canonical Runbooks

- [Benchmark card](../benchmarks/contexttrace_bench/BENCHMARK_CARD.md)
- [Methodology and claim policy](../benchmarks/contexttrace_bench/METHODOLOGY.md)
- [Baseline comparison runbook](../benchmarks/contexttrace_bench/BASELINES.md)
- [ContextTrace-Diag-150](../benchmarks/contexttrace_bench/DIAG150.md)
- [Human audit checklist](../benchmarks/contexttrace_bench/AUDIT.md)
- [CRAG track](../benchmarks/contexttrace_bench/CRAG.md)
- [Current SOTA gate snapshot](../benchmarks/contexttrace_bench/SOTA_STATUS.md)
- [Evidence and claim readiness](sota-readiness.md)

These runbooks contain the exact RAGTruth, ARES, CRAG, RAGAS, DeepEval, and
RAGChecker adapter commands. Keep unsupported competitor diagnostics as `N/A`
and compare systems only on identical case IDs.
