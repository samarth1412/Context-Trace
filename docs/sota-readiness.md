# SOTA Readiness

This document keeps ContextTrace's public positioning tied to reproducible
evidence. The goal is to become a credible state-of-the-art product/library
without making claims before the benchmark support exists.

## Week 1: Credibility Foundation

Week 1 is about making the current verifier benchmark reproducible, publishable,
and honest.

Completed in the repo:

- ContextTrace-Bench runs as a CI-gated verifier benchmark.
- Benchmark artifacts are generated under `benchmarks/contexttrace_bench/out/`.
- CI uploads result JSON, Markdown summary, leaderboard, HTML report, candidate
  inputs, methodology, and baseline runbook.
- `METHODOLOGY.md` defines case sets, labels, metrics, quality gates,
  limitations, and public claim policy.
- `BASELINES.md` defines how to collect publishable RAGAS, DeepEval, local-judge,
  Phoenix, and TruLens rows.
- Full OpenAI-backed RAGAS and DeepEval baseline rows were collected with
  `gpt-4.1-mini` across all 500 benchmark cases.
- A separate `public_holdout` case set was added and expanded to 75 cases from
  OpenTelemetry, Weaviate, LlamaIndex, Milvus, LangChain, Haystack, Qdrant,
  Pinecone, Chroma, RAGAS, and DeepEval public docs. It is excluded from `all`
  by design and is the first 75/150 milestone for ContextTrace-Diag-150.
- A richer OpenAI diagnostic judge baseline was run on the public holdout with
  `gpt-4.1-mini`.
- The remote baseline runners now support resumable checkpoints and bounded
  evaluator concurrency.
- Documentation links now point reviewers to methodology and baseline status.

Still pending for Week 1:

- Run a full local/OpenAI-compatible judge baseline if local runtime is
  acceptable.
- Review generated `leaderboard.md` and `report.html` before using them in public
  material.

Current baseline status:

- ContextTrace semantic verifier: 500 cases, failure macro-F1 `1.000`,
  root-cause accuracy `1.000`, citation error F1 `1.000`, evidence span
  overlap `0.863`.
- RAGAS with `gpt-4.1-mini`: 500 cases, zero row errors, failure macro-F1
  `0.200`. Diagnostic attribution fields are `N/A`.
- DeepEval with `gpt-4.1-mini`: 500 cases, zero row errors, failure macro-F1
  `0.069`. Diagnostic attribution fields are `N/A`.
- Public holdout, ContextTrace semantic verifier: 75 cases, failure macro-F1
  `1.000`, claim-verdict macro-F1 `1.000`, root-cause accuracy `1.000`,
  citation error F1 `1.000`, evidence span overlap `0.944` across 74
  span-labeled cases.
- Public holdout, OpenAI diagnostic judge with `gpt-4.1-mini`: 75 cases, zero
  row errors, failure macro-F1 `0.869`, root-cause accuracy `0.973`, citation
  error F1 `1.000`, evidence span overlap `0.905`.
- Ollama is reachable locally and `phi3:latest` completed a 5-case local-judge
  smoke run. The smoke took about 155 seconds, making a full 500-case run a
  multi-hour local job on this machine.

## Allowed Claim This Week

Use:

> ContextTrace provides a local-first benchmarked verifier for claim-level RAG
> failure attribution, citation-error detection, root-cause diagnosis, and
> evidence-span localization.

Avoid:

> ContextTrace is the state-of-the-art RAG evaluation framework.

That broader claim needs independent public datasets, frozen holdout splits,
confidence intervals, and full competitor rows.

## Week 1 Verification Commands

```bash
python -m pytest benchmarks/tests/test_contexttrace_bench.py packages/contexttrace/tests/test_verify.py -q
python benchmarks/contexttrace_bench/run_contexttrace.py --mode semantic --case-set all --enforce-sota-gates
python benchmarks/contexttrace_bench/run_contexttrace.py --mode semantic --case-set public_holdout --no-generated-cases --output-dir benchmarks/contexttrace_bench/out/public_holdout
```

Remote baseline smoke test:

```powershell
$env:OPENAI_API_KEY = "<your evaluator key>"
.\benchmarks\contexttrace_bench\run_openai_baselines.ps1 -Limit 5
```

Full baseline run:

```powershell
$env:OPENAI_API_KEY = "<your evaluator key>"
.\benchmarks\contexttrace_bench\run_openai_baselines.ps1 -Resume -MaxWorkers 4
```

## Week 1 Exit Criteria

- CI is green.
- Current ContextTrace-Bench artifacts are available.
- Public docs include methodology and limitations.
- At least one full competitor row is scored, or the baseline status explicitly
  says why it is pending.
- No public copy makes a broad SOTA claim without the evidence above.

No version bump or release branch is required for Week 1 readiness work.
