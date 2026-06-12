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
- A separate `public_holdout` case set was added and expanded to 150 cases from
  OpenTelemetry, Weaviate, LlamaIndex, Milvus, LangChain, Haystack, Qdrant,
  Pinecone, Chroma, RAGAS, DeepEval, LangSmith, Phoenix, TruLens, DSPy,
  LanceDB, Elasticsearch, Redis, pgvector, OpenSearch, MongoDB Vector Search,
  Azure AI Search, Vespa, OpenAI Evals, and Guardrails public docs. It is
  excluded from `all` by design and has reached the ContextTrace-Diag-150 target.
- A richer OpenAI diagnostic judge baseline was run on the public holdout with
  `gpt-4.1-mini`.
- `benchmarks/contexttrace_bench/AUDIT.md` defines the human sign-off checklist
  required before calling the holdout frozen.
- The remote baseline runners now support resumable checkpoints and bounded
  evaluator concurrency.
- Benchmark artifacts now include deterministic 95% case-bootstrap confidence
  intervals, per-label breakdowns for the headline metrics, and error-analysis
  JSON/Markdown with confusion pairs and cases to inspect.
- A RAGTruth external-validation adapter scaffold can build a ContextTrace-style
  case pack from `response.jsonl` and `source_info.jsonl`, with answer-side
  hallucination spans preserved for human evidence-span mapping.
- External case packs can now be scored through `run_contexttrace.py --case-pack`
  and produce the same JSON, Markdown, HTML, confidence interval, and
  candidate-input artifacts as built-in benchmark runs.
- `ragtruth_review.py` can generate a human-review queue and apply reviewed
  source evidence spans back into a reviewed RAGTruth case pack.
- A 50-row official RAGTruth test-split smoke run was built, scored, and queued
  for review from the raw GitHub dataset files. The 15 hallucination review rows
  now include deterministic source-span suggestions. The result is smoke-only
  and not publishable until issue #7 evidence mapping is complete.
- An assisted source-evidence review pilot mapped those 15 RAGTruth
  hallucination rows and rescored the 50-row test-split smoke. Span overlap is
  now measurable at `0.882` across 15 reviewed rows. The current calibrated
  semantic verifier scores failure macro-F1 `0.172` and root-cause accuracy
  `0.340`, so this is workflow/calibration evidence, not a publishable external
  benchmark claim.
- Documentation links now point reviewers to methodology and baseline status.

Still pending for Week 1:

- Run a full local/OpenAI-compatible judge baseline if local runtime is
  acceptable.
- Get independent human sign-off for the RAGTruth source-evidence mappings and
  expand beyond the 50-row smoke before using it for publishable
  span-localization or external-dataset claims. This is tracked in GitHub issue
  #7.
- Create full external dataset validation tracks for RAGTruth, RAGChecker, CRAG,
  and ARES before making broad SOTA claims. RAGChecker, CRAG, and ARES follow-up
  work is tracked in GitHub issues #3, #4, and #5.
- Complete human audit sign-off for ContextTrace-Diag-150 before using
  frozen-split language.
- Review generated `leaderboard.md` and `report.html` before using them in public
  material.

Current baseline status:

- ContextTrace semantic verifier: 500 cases, failure macro-F1 `1.000`,
  root-cause accuracy `1.000`, citation error F1 `1.000`, evidence span
  overlap `0.862`.
- RAGAS with `gpt-4.1-mini`: 500 cases, zero row errors, failure macro-F1
  `0.200`. Diagnostic attribution fields are `N/A`.
- DeepEval with `gpt-4.1-mini`: 500 cases, zero row errors, failure macro-F1
  `0.069`. Diagnostic attribution fields are `N/A`.
- Public holdout, ContextTrace semantic verifier: 150 cases, failure macro-F1
  `1.000`, claim-verdict macro-F1 `1.000`, root-cause accuracy `1.000`,
  citation error F1 `1.000`, evidence span overlap `0.950` across 149
  span-labeled cases.
- Public holdout, OpenAI diagnostic judge with `gpt-4.1-mini`: 150 cases, zero
  row errors, failure macro-F1 `0.931`, root-cause accuracy `0.953`, citation
  error F1 `1.000`, evidence span overlap `0.921`.
- RAGTruth assisted review pilot, ContextTrace semantic verifier: 50 official
  test-split smoke cases, 15 assisted-reviewed source-evidence rows, failure
  macro-F1 `0.172`, root-cause accuracy `0.340`, citation error F1 `1.000`,
  evidence span overlap `0.882` across the 15 reviewed rows. This is not
  publishable without independent sign-off and broader coverage.
- RAGTruth assisted review pilot, OpenAI diagnostic judge with `gpt-4.1-mini`:
  50 official test-split smoke cases, zero row errors, failure macro-F1 `0.272`,
  root-cause accuracy `0.660`, citation error F1 `1.000`, evidence span overlap
  `0.592`, and dangerous false-green rate `0.260`. This is useful calibration
  evidence, but it is too under-sensitive to use as a publishable external row.
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

That broader claim still needs independent public datasets, audited frozen
holdout language, interval-aware reporting, and full competitor rows.

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
- Public docs link the ContextTrace-Diag-150 audit checklist and do not call the
  split frozen until sign-off is complete.
- At least one full competitor row is scored, or the baseline status explicitly
  says why it is pending.
- No public copy makes a broad SOTA claim without the evidence above.

No version bump or release branch is required for Week 1 readiness work.
