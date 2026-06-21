# SOTA Readiness

This document keeps ContextTrace's public positioning tied to reproducible
evidence. The goal is to become a credible state-of-the-art product/library
without making claims before the benchmark support exists.

## Reality Check: Not SOTA Yet

As of June 20, 2026, ContextTrace has a credible benchmark and release-evidence
pipeline, but it is not yet defensible as a broad state-of-the-art RAG
evaluation product.

The reason is external validity. The verifier is strong on the built-in
500-case benchmark and the 150-case public holdout, but the latest 200-case
RAGTruth assisted run is still calibration-only:

- Failure macro-F1: `0.425`
- Root-cause accuracy: `0.565`
- Dangerous false-green rate: `0.005`
- Evidence-span overlap: `0.578`
- Claim-verdict macro-F1: `0.164` where claim-level overrides exist

That is not SOTA. It is useful evidence that the harness, review workflow, and
error-analysis path work, but the product still needs material verifier-quality
work on external datasets before public SOTA positioning is honest.

## SOTA Gate

Do not claim broad SOTA until all of these are true:

- At least two external datasets are scored end to end with documented adapters,
  frozen inputs, and reproducible commands.
- The primary external run is independently reviewed, not only assisted.
- RAGTruth or equivalent external failure macro-F1 is at least `0.75`.
- External dangerous false-green rate is at most `0.01`.
- Root-cause accuracy on external labeled failures is at least `0.70`.
- Evidence-span overlap on independently reviewed source spans is at least
  `0.70`.
- Full competitor rows are scored on the same IDs, with unsupported diagnostic
  fields shown as `N/A`.

Until then, the correct claim is benchmarked and local-first, not SOTA.

## Next Milestone: External Accuracy Sprint

Stop prioritizing new wrappers unless they unblock a publishable external run.
The next engineering milestone is to make the RAGTruth 200-case sample a strong
calibration target:

1. Triage the latest RAGTruth error-analysis rows by expected label and root
   cause.
2. Fix the largest false-green and wrong-taxonomy clusters first.
3. Add focused tests that reproduce each corrected external miss in the local
   verifier.
4. Rerun the same deterministic RAGTruth release workflow.
5. Promote the result only if failure macro-F1 and root-cause accuracy move
   materially without regressing the public holdout gates.

Immediate targets from the latest error analysis:

- `no_failure_detected -> answer_overreach`: 48 cases. The verifier is
  over-flagging many supported RAGTruth rows, especially answer-level rows with
  no hallucination span.
- `no_failure_detected -> conflicting_contexts`: 18 cases. Conflict detection is
  too eager on some supported rows.
- `conflicting_contexts -> answer_overreach`: 10 cases, concentrated in
  Data2txt/Yelp. These are contradicted-answer misses.
- `answer_overreach -> conflicting_contexts`: 10 cases. These are
  partial-support misses being treated as contradictions.
- Source-span localization misses: 44 cases, mostly Data2txt/Yelp conflict
  rows.

The first implementation pass should target these clusters in that order. The
single dangerous false green, `ragtruth_16056`, should stay tracked, but it does
not dominate the current quality gap.

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
- `BASELINES.md` defines how to collect publishable RAGAS, DeepEval, RAGChecker,
  local-judge, Phoenix, and TruLens rows.
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
- ContextTrace-Diag-150 now has a machine-checkable audit packet generator:
  `benchmarks/contexttrace_bench/audit_diag150.py`. It emits reviewer-ready
  JSON/Markdown packets, a human-review template, and validator output for case
  counts, source URL presence, evidence-span grounding, candidate-input leakage,
  artifact alignment, and independent sign-off completeness.
- The same audit command can generate a reproducible release bundle with copied
  artifacts, `manifest.json`, SHA256 checksums, and a bundle README. Bundles are
  marked `review_pending`, `freeze_ready`, or `validation_failed` based on audit
  validation and human sign-off state.
- `benchmarks/contexttrace_bench/diag150_release_workflow.py` now runs the
  Diag-150 evidence path end to end: public-holdout regeneration, available
  candidate-row scoring, audit artifact refresh, release bundle generation, and
  final status reporting.
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
  include deterministic source-span suggestions.
- A 200-case deterministic RAGTruth test-split sample now runs through
  `ragtruth_workflow.py` end to end: case pack, review queue, review packet,
  manifest, reviewed-case-pack application, and scored outputs.
- A GPT-5.1-assisted source-evidence review mapped all 88 hallucination rows in
  that 200-case sample. It validated with zero errors; 76 rows have source
  evidence spans, and 12 rows are intentionally source-less because no fair
  source-side span exists. This is assisted review, not independent human
  sign-off.
- RAGTruth now has a release workflow,
  `benchmarks/contexttrace_bench/ragtruth_release_workflow.py`, that adapts the
  dataset, validates/applies reviewed source-evidence mappings, scores
  ContextTrace, optionally scores existing candidate rows, and writes a
  checksummed release bundle. Bundle statuses are `review_pending`,
  `calibration_only`, `publishable`, or `validation_failed`.
- RAGTruth scored bundles now include `ragtruth_error_analysis.json` and
  `ragtruth_error_analysis.md`, which convert the assisted run into concrete
  calibration targets by task, source dataset, model, label type, expected
  label, root-cause confusion, and source-span localization quality.
- RAGTruth scoring now treats verdict counts as answer-level by default instead
  of inventing one expected claim verdict from each answer-level label.
  Claim-count metrics are scored only for explicit reviewer taxonomy overrides;
  on the 200-case assisted run this reduced error-analysis misses from `199` to
  `164` without changing the conservative `calibration_only` status.
- The semantic verifier now handles common news-summary paraphrases, generated
  summary prefixes, QA boilerplate/list markers, multi-span QA list/procedural
  evidence, source-availability boilerplate, relation/appositive evidence
  variants, strict death-count identity checks, negated structured parking
  lists, and structured JSON evidence for clear attributes such as Wi-Fi,
  reservations, parking, ambience flags, categories, ratings, hours ranges, and
  day-specific schedules. This moved the 200-case RAGTruth assisted sample from
  failure macro-F1 `0.270` to `0.425` and root-cause accuracy `0.360` to
  `0.565` while holding dangerous false-green rate at `0.005`.
- The current semantic verifier scores failure macro-F1 `0.425`, root-cause
  accuracy `0.565`, dangerous false-green rate `0.005`, and evidence span
  overlap `0.578` on that 200-case RAGTruth sample, so RAGTruth is now a
  concrete calibration target rather than a publishable external benchmark
  claim.
- Documentation links now point reviewers to methodology and baseline status.

Still pending for Week 1:

- Broaden judge baselines beyond the current public-holdout and RAGTruth smoke
  runs if local runtime is acceptable.
- Use the RAGTruth error-analysis report to prioritize taxonomy mapping,
  partial-support handling, contradicted-answer handling, and source-span
  localization before rerunning external validation.
- Get independent human sign-off for the 200-case RAGTruth source-evidence
  mappings before using it for publishable span-localization or
  external-dataset claims. Until then, the RAGTruth release bundle should remain
  `calibration_only`. This is tracked in GitHub issue #7.
- Create full external dataset validation tracks for RAGTruth, RAGChecker, CRAG,
  and ARES before making broad SOTA claims. RAGChecker, CRAG, and ARES follow-up
  work is tracked in GitHub issues #3, #4, and #5.
- Complete human audit sign-off for ContextTrace-Diag-150 before using
  frozen-split language. Use `audit_diag150.py` to generate the reviewer packet
  and validation artifacts before the independent review, then rerun it with
  `--review-file` and `--require-human-signoff`.
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
- RAGTruth assisted review pilot, ContextTrace semantic verifier: 200 official
  test-split stratified cases, 88 assisted-reviewed hallucination rows, 76
  rows with source evidence spans, failure macro-F1 `0.425`, root-cause
  accuracy `0.565`, citation error F1 `1.000`, evidence span overlap `0.578`,
  and dangerous false-green rate `0.005`. This is not publishable without
  independent sign-off and calibration.
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
python benchmarks/contexttrace_bench/audit_diag150.py --output-dir benchmarks/contexttrace_bench/out/public_holdout
python benchmarks/contexttrace_bench/audit_diag150.py --output-dir benchmarks/contexttrace_bench/out/public_holdout --review-file benchmarks/contexttrace_bench/out/public_holdout/diag150_human_review_template.json --require-human-signoff
python benchmarks/contexttrace_bench/audit_diag150.py --output-dir benchmarks/contexttrace_bench/out/public_holdout --bundle-dir benchmarks/contexttrace_bench/out/diag150_release_bundle
python benchmarks/contexttrace_bench/diag150_release_workflow.py --output-dir benchmarks/contexttrace_bench/out/public_holdout --bundle-dir benchmarks/contexttrace_bench/out/diag150_release_bundle
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
