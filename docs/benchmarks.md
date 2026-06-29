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

Presets for `ragas`, `deepeval`, `ragchecker`, `phoenix`, and `trulens` provide
common score field names, but the adapter remains dependency-free. It does not
claim a leaderboard result until the resulting candidate JSON is scored by the
benchmark harness.

Optional direct runners are available for RAGAS, DeepEval, and RAGChecker:

```bash
python benchmarks/contexttrace_bench/run_ragas.py \
  --input benchmarks/contexttrace_bench/out/candidate_inputs.jsonl \
  --candidate-output benchmarks/contexttrace_bench/out/ragas_predictions.json \
  --model gpt-4.1-mini

python benchmarks/contexttrace_bench/run_deepeval.py \
  --input benchmarks/contexttrace_bench/out/candidate_inputs.jsonl \
  --candidate-output benchmarks/contexttrace_bench/out/deepeval_predictions.json \
  --model gpt-4.1-mini

python benchmarks/contexttrace_bench/run_ragchecker.py \
  --input benchmarks/contexttrace_bench/out/candidate_inputs.jsonl \
  --reference-file path/to/reference_answers.jsonl \
  --reference-id-field id \
  --reference-answer-field gt_answer \
  --ragchecker-input-output benchmarks/contexttrace_bench/out/ragchecker_input.json \
  --candidate-output benchmarks/contexttrace_bench/out/ragchecker_predictions.json \
  --extractor-name openai/gpt-4.1-mini \
  --checker-name openai/gpt-4.1-mini \
  --chunk-size 25 \
  --resume \
  --progress-every 25
```

These scripts intentionally stay outside package dependencies. Install and
configure the external evaluator separately, then feed the produced candidate JSON
back into `run_contexttrace.py --candidate`.

RAGChecker requires `gt_answer` for each row. ContextTrace candidate inputs hide
benchmark answers, so publishable RAGChecker rows should use `--reference-file`
with rows like `{"id": "case-id", "gt_answer": "reference answer"}`.
`--use-response-as-gt` is only a comparison-only proxy for setup and smoke runs.
The pinned RAGChecker package requires Python 3.9 or newer; the examples use an
isolated Python 3.11 venv.

OpenAI, RAGAS, DeepEval, and RAGChecker are comparison-only paths. The verifier
and benchmark harness remain local-first; remote evaluator APIs are used only
when you decide to publish competitor rows. Use the pinned optional requirement
files in separate temporary venvs because these evaluator dependency graphs are
not identical:

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
RAGTruth cases use `expected_verdict_scope: answer_label` by default because the
dataset does not provide claim-level verdict counts. Claim-verdict metrics are
scored only for rows where a reviewer explicitly supplies
`taxonomy_override.expected_verdict_counts`.
When scoring completes, the release bundle also includes
`scored/ragtruth_error_analysis.json` and
`scored/ragtruth_error_analysis.md`. These reports group misses by task type,
source dataset, model, RAGTruth label type, expected label, root-cause
confusion, and span-localization quality so calibration work can target the
largest blockers before any publishable external-validation claim.

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

$ragcheckerVenv = Join-Path $env:TEMP "contexttrace-ragchecker"
py -3.11 -m venv $ragcheckerVenv
& "$ragcheckerVenv\Scripts\python.exe" -m pip install -r benchmarks/contexttrace_bench/requirements-ragchecker.txt
& "$ragcheckerVenv\Scripts\python.exe" -m spacy download en_core_web_sm
$env:OPENAI_API_KEY = "<your OpenAI API key>"
& "$ragcheckerVenv\Scripts\python.exe" benchmarks/contexttrace_bench/run_ragchecker.py `
  --input benchmarks/contexttrace_bench/out/candidate_inputs.jsonl `
  --reference-file path/to/reference_answers.jsonl `
  --reference-id-field id `
  --reference-answer-field gt_answer `
  --ragchecker-input-output benchmarks/contexttrace_bench/out/ragchecker_input.json `
  --candidate-output benchmarks/contexttrace_bench/out/ragchecker_predictions.json `
  --extractor-name openai/gpt-4.1-mini `
  --checker-name openai/gpt-4.1-mini `
  --chunk-size 25 `
  --resume `
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

RAGChecker, Phoenix, and TruLens comparison rows can be adapted from exported
evaluator results with `--preset ragchecker`, `--preset phoenix`, and
`--preset trulens`.

Generic external datasets with query, answer, contexts, and labels can be
normalized into the same case-pack format:

```bash
python benchmarks/contexttrace_bench/external_case_pack.py \
  --input path/to/external_rows.jsonl \
  --output benchmarks/contexttrace_bench/out/ares_case_pack.json \
  --dataset ARES \
  --query-field question \
  --answer-field response \
  --contexts-field retrieved_context \
  --label-field label \
  --sample-size 200 \
  --sample-seed 13 \
  --stratify-by split,label

python benchmarks/contexttrace_bench/run_contexttrace.py \
  --mode semantic \
  --case-pack benchmarks/contexttrace_bench/out/ares_case_pack.json \
  --output-dir benchmarks/contexttrace_bench/out/ares
```

Use this for CRAG/ARES-style exports only after recording the upstream dataset
version, frozen input checksum, field mapping, sampling metadata, and any
independent review needed for labels or source evidence spans.

The official CRAG Task 1/2 v5 archive has a dedicated streaming adapter:

```bash
python benchmarks/contexttrace_bench/crag_adapter.py \
  --download-official \
  --download-dir benchmarks/contexttrace_bench/out/crag_official \
  --output benchmarks/contexttrace_bench/out/crag_official/crag_task1_v5_rows_200.jsonl \
  --manifest-output benchmarks/contexttrace_bench/out/crag_official/crag_task1_v5_adapter_manifest_200.json \
  --sample-size 200 \
  --sample-seed 13 \
  --stratify-by domain,question_type,static_or_dynamic,split
```

It pins the official repository commit and 739 MB archive SHA256, samples from
compressed JSONL without unpacking the corpus, extracts visible text from five
web pages per row, and writes a complete provenance manifest. CRAG gold answers
are correctness references rather than grounding labels, so adapter output is
marked `unreviewed_gold_answer_proxy` and remains review input. See
[`CRAG.md`](../benchmarks/contexttrace_bench/CRAG.md) for metric comparability,
license, limitations, and independent-review commands.

Current calibration: the pinned archive has 2,705 eligible rows after one
missing-value answer is excluded. The deterministic 200-row sample covers all
five domains, eight question types, four temporal classes, and both splits.
ContextTrace accepts 95 gold answers under the unreviewed proxy and flags 105
for source-grounding review; 511/1,000 extracted contexts reach the disclosed
12,000-character cap. These are review-load statistics, not failure accuracy.
The selected-ID SHA256 is
`a782cf309506e2dff8f3b9c039fd2dc7bbab6f9cc3d98c9238693a1f64a9d80c`.

For a complete review/release bundle, prefer the workflow wrapper:

```bash
python benchmarks/contexttrace_bench/external_case_pack_workflow.py \
  --input path/to/external_rows.jsonl \
  --dataset ARES \
  --output-dir benchmarks/contexttrace_bench/out/ares_release \
  --bundle-dir benchmarks/contexttrace_bench/out/ares_release_bundle \
  --query-field question \
  --answer-field response \
  --contexts-field retrieved_context \
  --label-field label \
  --sample-size 200 \
  --sample-seed 13 \
  --stratify-by split,label
```

It writes the case pack, review JSONL template, reviewer packet, scored
benchmark artifacts, and a checksummed bundle. Rerun it with
`--review completed_review.jsonl --review-kind independent` after review to move
from `review_pending` to a dataset-specific publishable bundle when validation
passes.

The official ARES NQ example TSV has a dedicated normalizer:

```bash
python benchmarks/contexttrace_bench/ares_adapter.py \
  --download-example labeled \
  --download-dir benchmarks/contexttrace_bench/out/ares_nq_example \
  --output benchmarks/contexttrace_bench/out/ares_nq_example/ares_nq_labeled_rows.jsonl \
  --dataset ARES-NQ-example \
  --source-name "ARES/NQ labeled example"

python benchmarks/contexttrace_bench/external_case_pack_workflow.py \
  --input benchmarks/contexttrace_bench/out/ares_nq_example/ares_nq_labeled_rows.jsonl \
  --dataset ARES-NQ-example \
  --output-dir benchmarks/contexttrace_bench/out/ares_nq_example/smoke200_release \
  --bundle-dir benchmarks/contexttrace_bench/out/ares_nq_example/smoke200_release_bundle \
  --sample-size 200 \
  --sample-seed 13 \
  --stratify-by metadata.ares_context_relevance_label,metadata.ares_answer_faithfulness_label,metadata.ares_answer_relevance_label \
  --bootstrap-samples 100 \
  --no-auto-candidates
```

Current ARES status: the official example TSV contains 6,189 rows. The default
adapter path keeps 4,421 answer-grounding rows and skips context-relevance-only
retrieval negatives unless `--include-context-relevance-negatives` is supplied.
Repeated upstream IDs are deterministically disambiguated, and the generic
adapter rejects any duplicate IDs that remain after normalization. The corrected
stratified sample therefore has 200 rows and 200 unique case IDs.

On those IDs, ContextTrace scores failure macro-F1 `0.995` (95% CI
`0.981-1.000`), root-cause accuracy `0.995`, dangerous false-green rate `0.000`,
citation error F1 `1.000`, and evidence span overlap `1.000` across 89 rows with
auto-derived exact-answer spans. RAGAS and DeepEval, both using
`gpt-4.1-mini`, completed the same 200 IDs with zero runner errors and score
failure macro-F1 `0.471` (95% CI `0.426-0.513`) and `0.388` (95% CI
`0.342-0.431`) respectively. Their root-cause, citation, and span fields are
`N/A` because the runners report faithfulness only.

The tracked evidence is under
`benchmarks/contexttrace_bench/out/ares_nq_example/smoke200_compared_bundle/`.
It contains the frozen case pack, candidate inputs and predictions,
machine-readable baseline scores, reports, review packet, manifest, and SHA256
checksums. Raw zero-error runner outputs are retained under
`benchmarks/contexttrace_bench/out/ares_nq_example/baselines_unique/`.

The checksummed bundle remains `review_pending`. The exact-answer spans are
synthetic localization labels, not independent evidence-span annotations, and
the sole ContextTrace disagreement is an ARES-positive row whose answer `one`
has only the title `The Bastard Executioner` as context. Treat all ARES numbers
as calibration evidence until independent review validates the component-label
mapping and source evidence.
