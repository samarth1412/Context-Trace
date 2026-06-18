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

## ContextTrace-Bench

Use `benchmarks/contexttrace_bench/` when you need to measure the verifier itself
rather than a retrieval strategy. It runs labeled cases across real ContextTrace
docs, release artifacts, external OSS docs, public issue examples, and
deterministic generated variants derived from those traces.

Before using these results publicly, read:

- [ContextTrace-Bench methodology](../benchmarks/contexttrace_bench/METHODOLOGY.md)
- [Baseline comparison runbook](../benchmarks/contexttrace_bench/BASELINES.md)
- [ContextTrace-Diag-150 tracker](../benchmarks/contexttrace_bench/DIAG150.md)
- [ContextTrace-Diag-150 audit checklist](../benchmarks/contexttrace_bench/AUDIT.md)
- [SOTA readiness checklist](sota-readiness.md)

The benchmark is a reproducible verifier-readiness benchmark. Passing its gates
means the current verifier did not regress on the current labeled cases; it is
not a general RAG-system state-of-the-art claim by itself.

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

Current holdout status: ContextTrace scores `1.000` failure macro-F1, `1.000`
claim-verdict macro-F1, `1.000` root-cause accuracy, and `1.000` citation
error F1 on 150 public-doc cases with 149 span-labeled cases. The OpenAI
diagnostic judge `gpt-4.1-mini` row scores `0.931` failure macro-F1, `0.953`
root-cause accuracy, `1.000` citation error F1, and `0.921` evidence-span
overlap on the same split. This holdout has reached the 150-case
ContextTrace-Diag-150 target and is intentionally excluded from the default
500-case `all` run; call it frozen only after the human audit checklist is
complete.

Generate the Diag-150 audit packet after the holdout run:

```bash
python benchmarks/contexttrace_bench/audit_diag150.py \
  --output-dir benchmarks/contexttrace_bench/out/public_holdout
```

The audit packet is the reviewer handoff for frozen-split sign-off. It includes
case-level labels, root causes, evidence spans, source URLs, benchmark
predictions, blank human-review fields, and a JSON validator report for
candidate-input leakage and artifact consistency.

After an independent reviewer fills the generated
`diag150_human_review_template.json`, enforce sign-off completeness:

```bash
python benchmarks/contexttrace_bench/audit_diag150.py \
  --output-dir benchmarks/contexttrace_bench/out/public_holdout \
  --review-file benchmarks/contexttrace_bench/out/public_holdout/diag150_human_review_template.json \
  --require-human-signoff
```

Create a bundle for reviewer handoff or launch evidence:

```bash
python benchmarks/contexttrace_bench/audit_diag150.py \
  --output-dir benchmarks/contexttrace_bench/out/public_holdout \
  --bundle-dir benchmarks/contexttrace_bench/out/diag150_release_bundle
```

The bundle includes copied artifacts, `manifest.json`, SHA256 checksums, and a
bundle README. It is marked `review_pending` until the completed human-review
file passes the strict sign-off gate.

Run the full Diag-150 release evidence workflow in one command:

```bash
python benchmarks/contexttrace_bench/diag150_release_workflow.py \
  --output-dir benchmarks/contexttrace_bench/out/public_holdout \
  --bundle-dir benchmarks/contexttrace_bench/out/diag150_release_bundle
```

The workflow regenerates the public holdout, scores available candidate
prediction files in the output directory, refreshes audit artifacts, writes the
release bundle, and prints `review_pending`, `freeze_ready`, or
`validation_failed`.

Core metrics:

- `failure_label_macro_f1`
- `claim_verdict_macro_f1`
- `root_cause_accuracy`
- `citation_error_f1`
- `evidence_span_overlap`
- `dangerous_false_green_rate`
- `latency_p95_ms`
- `cost_per_100_traces_usd`

Outputs:

- `contexttrace_bench_results.json`
- `results.md`
- `leaderboard.md`
- `report.html`
- `error_analysis.json`
- `error_analysis.md`
- `candidate_inputs.jsonl`

The JSON, Markdown, and HTML reports include deterministic 95% case-bootstrap
confidence intervals and a per-label precision/recall/F1 breakdown for the
headline verifier metrics. The error-analysis artifacts add confusion pairs,
root-cause confusion, false-positive labels, dangerous false greens, and the
highest-priority cases to inspect.

External evaluators can be compared by supplying candidate prediction JSON files
with `--candidate`. This produces leaderboard rows only after the competitor
predictions have been scored against the same case IDs and labels.

Candidate rows should cover the full benchmark, record model/package versions,
and keep unsupported diagnostic fields as `N/A` rather than zero.

Normalize evaluator output into candidate JSON:

```bash
python benchmarks/contexttrace_bench/adapt_candidate.py \
  --input evaluator_results.json \
  --output candidate_predictions.json \
  --system "External evaluator" \
  --id-field id \
  --labels-field predicted_labels
```

Presets for `ragas`, `deepeval`, `phoenix`, and `trulens` provide common score
field names, but the adapter remains dependency-free. It does not claim a
leaderboard result until the resulting candidate JSON is scored by the benchmark
harness.

Optional direct runners are available for RAGAS and DeepEval:

```bash
python benchmarks/contexttrace_bench/run_ragas.py \
  --input benchmarks/contexttrace_bench/out/candidate_inputs.jsonl \
  --candidate-output benchmarks/contexttrace_bench/out/ragas_predictions.json \
  --model gpt-4.1-mini

python benchmarks/contexttrace_bench/run_deepeval.py \
  --input benchmarks/contexttrace_bench/out/candidate_inputs.jsonl \
  --candidate-output benchmarks/contexttrace_bench/out/deepeval_predictions.json \
  --model gpt-4.1-mini
```

These scripts intentionally stay outside package dependencies. Install and
configure the external evaluator separately, then feed the produced candidate JSON
back into `run_contexttrace.py --candidate`.

OpenAI, RAGAS, and DeepEval are comparison-only paths. The verifier and benchmark
harness remain local-first; remote evaluator APIs are used only when you decide to
publish competitor rows. Use the pinned optional requirement files in separate
temporary venvs because the current RAGAS and DeepEval dependency graphs are not
identical:

Diagnostic metrics are scored only when a candidate reports them. Generic
faithfulness evaluators should show `N/A` for root cause, citation status, and
evidence spans rather than `0.0`.

RAGTruth external validation starts with a case-pack adapter:

```bash
python benchmarks/contexttrace_bench/ragtruth_adapter.py \
  --response path/to/response.jsonl \
  --source-info path/to/source_info.jsonl \
  --output benchmarks/contexttrace_bench/out/ragtruth_case_pack.json \
  --split test
```

For larger review rounds, use deterministic stratified sampling instead of the
first rows from the export:

```bash
python benchmarks/contexttrace_bench/ragtruth_adapter.py \
  --response benchmarks/contexttrace_bench/out/ragtruth_official/response.jsonl \
  --source-info benchmarks/contexttrace_bench/out/ragtruth_official/source_info.jsonl \
  --output benchmarks/contexttrace_bench/out/ragtruth_case_pack_test200_stratified.json \
  --split test \
  --quality good \
  --sample-size 200 \
  --sample-seed 13 \
  --stratify-by task_type,source,expected_label,model
```

The workflow wrapper creates the sampled case pack, review queue, packet, and
manifest together:

```bash
python benchmarks/contexttrace_bench/ragtruth_workflow.py \
  --response benchmarks/contexttrace_bench/out/ragtruth_official/response.jsonl \
  --source-info benchmarks/contexttrace_bench/out/ragtruth_official/source_info.jsonl \
  --output-dir benchmarks/contexttrace_bench/out/ragtruth_test200_review \
  --split test \
  --quality good \
  --sample-size 200 \
  --sample-seed 13 \
  --stratify-by task_type,source,expected_label,model
```

After review, rerun the wrapper with the reviewed JSONL so validation,
application, scoring, and the manifest stay together. Use
`--allow-missing-source-spans` only for reviewed rows where no fair source-side
span exists:

```bash
python benchmarks/contexttrace_bench/ragtruth_workflow.py \
  --response benchmarks/contexttrace_bench/out/ragtruth_official/response.jsonl \
  --source-info benchmarks/contexttrace_bench/out/ragtruth_official/source_info.jsonl \
  --output-dir benchmarks/contexttrace_bench/out/ragtruth_test200_review \
  --split test \
  --quality good \
  --sample-size 200 \
  --sample-seed 13 \
  --stratify-by task_type,source,expected_label,model \
  --review benchmarks/contexttrace_bench/out/ragtruth_test200_review/ragtruth_reviewed.jsonl \
  --allow-missing-source-spans
```

Create the RAGTruth release bundle after review:

```bash
python benchmarks/contexttrace_bench/ragtruth_release_workflow.py \
  --response benchmarks/contexttrace_bench/out/ragtruth_official/response.jsonl \
  --source-info benchmarks/contexttrace_bench/out/ragtruth_official/source_info.jsonl \
  --output-dir benchmarks/contexttrace_bench/out/ragtruth_release \
  --bundle-dir benchmarks/contexttrace_bench/out/ragtruth_release_bundle \
  --review benchmarks/contexttrace_bench/out/ragtruth_release/ragtruth_reviewed.jsonl \
  --allow-missing-source-spans
```

The bundle status is conservative:

- `review_pending`: source-evidence review has not been applied.
- `calibration_only`: reviewed/scored, but not strict independent external
  validation, for example assisted review or intentionally missing source spans.
- `publishable`: strict independent review, source-span requirements, scoring,
  and artifact validation passed.
- `validation_failed`: review, scoring, or artifact checks failed.

The adapter preserves RAGTruth answer-side hallucination spans, but publishable
span-localization claims still require human mapping to source evidence spans.

Score the adapted case pack through the same report path:

```bash
python benchmarks/contexttrace_bench/run_contexttrace.py \
  --mode semantic \
  --case-pack benchmarks/contexttrace_bench/out/ragtruth_case_pack.json \
  --output-dir benchmarks/contexttrace_bench/out/ragtruth
```

Create and apply the human review queue before using source-span metrics:

```bash
python benchmarks/contexttrace_bench/ragtruth_review.py build-queue \
  --case-pack benchmarks/contexttrace_bench/out/ragtruth_case_pack.json \
  --output benchmarks/contexttrace_bench/out/ragtruth_review_queue.jsonl \
  --suggest-source-spans \
  --max-suggestions 3

python benchmarks/contexttrace_bench/ragtruth_review.py build-packet \
  --review-queue benchmarks/contexttrace_bench/out/ragtruth_review_queue.jsonl \
  --output benchmarks/contexttrace_bench/out/ragtruth_review_packet.md

python benchmarks/contexttrace_bench/ragtruth_review.py validate \
  --case-pack benchmarks/contexttrace_bench/out/ragtruth_case_pack.json \
  --review benchmarks/contexttrace_bench/out/ragtruth_reviewed.jsonl \
  --output benchmarks/contexttrace_bench/out/ragtruth_review_validation.json \
  --require-reviewed \
  --require-source-spans

python benchmarks/contexttrace_bench/ragtruth_review.py apply \
  --case-pack benchmarks/contexttrace_bench/out/ragtruth_case_pack.json \
  --review benchmarks/contexttrace_bench/out/ragtruth_reviewed.jsonl \
  --output benchmarks/contexttrace_bench/out/ragtruth_reviewed_case_pack.json \
  --require-reviewed
```

Omit `--require-source-spans` only when reviewed notes explain that no fair
source-side span exists; those rows are reviewed but excluded from
evidence-span-overlap labels.

For full runs, prefer the resumable checkpointed path:

```powershell
$env:OPENAI_API_KEY = "<your OpenAI API key>"
.\benchmarks\contexttrace_bench\run_openai_baselines.ps1 -Resume -MaxWorkers 4
```

For a low-cost smoke test, use `-Limit 5`. Limited runs write candidate files but
do not score a full leaderboard row.

Latest full OpenAI-backed faithfulness rows used `gpt-4.1-mini` across all 500
cases. RAGAS scored `0.200` failure macro-F1 and DeepEval scored `0.069`
failure macro-F1. Both are faithfulness-only baselines, so diagnostic
attribution fields are `N/A`.

```powershell
$ragasVenv = Join-Path $env:TEMP "contexttrace-ragas"
py -3.11 -m venv $ragasVenv
& "$ragasVenv\Scripts\python.exe" -m pip install -r benchmarks/contexttrace_bench/requirements-ragas.txt
$env:OPENAI_API_KEY = "<your OpenAI API key>"
& "$ragasVenv\Scripts\python.exe" benchmarks/contexttrace_bench/run_ragas.py `
  --input benchmarks/contexttrace_bench/out/candidate_inputs.jsonl `
  --candidate-output benchmarks/contexttrace_bench/out/ragas_predictions.json `
  --model gpt-4.1-mini `
  --resume `
  --max-workers 4 `
  --progress-every 25

$deepevalVenv = Join-Path $env:TEMP "contexttrace-deepeval"
py -3.11 -m venv $deepevalVenv
& "$deepevalVenv\Scripts\python.exe" -m pip install -r benchmarks/contexttrace_bench/requirements-deepeval.txt
$env:OPENAI_API_KEY = "<your OpenAI API key>"
& "$deepevalVenv\Scripts\python.exe" benchmarks/contexttrace_bench/run_deepeval.py `
  --input benchmarks/contexttrace_bench/out/candidate_inputs.jsonl `
  --candidate-output benchmarks/contexttrace_bench/out/deepeval_predictions.json `
  --model gpt-4.1-mini `
  --resume `
  --max-workers 4 `
  --progress-every 25
```

Local evaluator baseline:

```powershell
$judgeVenv = Join-Path $env:TEMP "contexttrace-local-judge"
py -3.11 -m venv $judgeVenv
& "$judgeVenv\Scripts\python.exe" -m pip install -r benchmarks/contexttrace_bench/requirements-local-judge.txt
& "$judgeVenv\Scripts\python.exe" benchmarks/contexttrace_bench/run_local_judge.py `
  --input benchmarks/contexttrace_bench/out/candidate_inputs.jsonl `
  --candidate-output benchmarks/contexttrace_bench/out/local_judge_predictions.json `
  --base-url http://localhost:11434/v1 `
  --model llama3.1:8b
```

Phoenix and TruLens comparison rows can be adapted from their exported evaluator
results with `--preset phoenix` and `--preset trulens`.
