# ContextTrace-Bench

ContextTrace-Bench is the reproducible benchmark harness for measuring claim-level
failure attribution quality.

It wraps the bundled verification benchmark cases, adds deterministic adversarial
variants derived from those real traces, and reports product-facing metrics that
are useful for comparing local verifier modes and future baselines:

- `claim_verdict_macro_f1`
- `failure_label_macro_f1`
- `root_cause_accuracy`
- `citation_error_precision`
- `citation_error_recall`
- `evidence_span_overlap`
- `latency_p50_ms`
- `latency_p95_ms`
- `cost_per_100_traces_usd`
- `dangerous_false_green_rate`

Read [BENCHMARK_CARD.md](BENCHMARK_CARD.md) and [METHODOLOGY.md](METHODOLOGY.md)
before using results in launch material.
It documents label sources, generated-case limits, metrics, quality gates, and
the public claim policy. Use [BASELINES.md](BASELINES.md) to collect publishable
RAGAS, DeepEval, RAGChecker, local-judge, Phoenix, or TruLens comparison rows. The
`public_holdout` track is documented in [DIAG150.md](DIAG150.md), and the
required human audit pass is tracked in [AUDIT.md](AUDIT.md). The official CRAG
download, normalization, comparability boundary, and review process are in
[CRAG.md](CRAG.md).

Run it from the repo root:

```bash
python benchmarks/contexttrace_bench/run_contexttrace.py --mode semantic --case-set all
```

Outputs are written to `benchmarks/contexttrace_bench/out/` by default:

- `contexttrace_bench_results.json`
- `results.md`
- `leaderboard.md`
- `report.html`
- `error_analysis.json`
- `error_analysis.md`
- `candidate_inputs.jsonl`

`contexttrace_bench_results.json`, `results.md`, and `report.html` include
deterministic 95% case-bootstrap confidence intervals for the headline quality
metrics plus a per-label precision/recall/F1 breakdown. `error_analysis.md` and
`error_analysis.json` summarize confusion pairs, root-cause confusion,
false-positive labels, dangerous false greens, and cases to inspect. Use the
interval lower bound, not only the point estimate, when deciding whether a result
is ready for public SOTA positioning.

The default run targets 500 total cases. Use `--no-generated-cases` to inspect
only the curated source cases, or `--target-cases 750` to generate a larger
derived benchmark.

Passing the default gates means the verifier did not regress on the current
labeled benchmark. It does not, by itself, justify a broad public
state-of-the-art claim; publish competitor rows and independent external dataset
results before using that language.

Run the separate public-doc holdout without generated variants:

```bash
python benchmarks/contexttrace_bench/run_contexttrace.py \
  --mode semantic \
  --case-set public_holdout \
  --no-generated-cases \
  --output-dir benchmarks/contexttrace_bench/out/public_holdout
```

Current holdout status: ContextTrace semantic verifier scores `1.000` failure
macro-F1, `1.000` claim-verdict macro-F1, `1.000` root-cause accuracy,
`1.000` citation error F1, and `0.950` span overlap on 150 public-doc cases with
149 span-labeled cases. An OpenAI diagnostic judge baseline using
`gpt-4.1-mini` scores `0.931` failure macro-F1, `0.953` root-cause accuracy,
`1.000` citation error F1, and `0.921` span overlap on the same split. The
holdout has reached the 150-case ContextTrace-Diag-150 target and is
intentionally not included in `--case-set all`; call it frozen only after the
human audit checklist is complete.

Generate the machine-checkable Diag-150 audit packet:

```bash
python benchmarks/contexttrace_bench/audit_diag150.py \
  --output-dir benchmarks/contexttrace_bench/out/public_holdout
```

This writes `diag150_audit_packet.json`, `diag150_audit_packet.md`,
`diag150_human_review_template.json`, `diag150_audit_validation.json`, and an
artifact-local `AUDIT_REPORT.md`. Use the Markdown packet for case-level
sign-off and the validation JSON to prove the candidate input export has not
leaked labels.

After independent review, validate the completed sign-off file:

```bash
python benchmarks/contexttrace_bench/audit_diag150.py \
  --output-dir benchmarks/contexttrace_bench/out/public_holdout \
  --review-file benchmarks/contexttrace_bench/out/public_holdout/diag150_human_review_template.json \
  --require-human-signoff
```

Create a release bundle for reviewers or launch evidence:

```bash
python benchmarks/contexttrace_bench/audit_diag150.py \
  --output-dir benchmarks/contexttrace_bench/out/public_holdout \
  --bundle-dir benchmarks/contexttrace_bench/out/diag150_release_bundle
```

The bundle copies the benchmark report, leaderboard, audit packet, validation
JSON, candidate inputs, and audit report into one folder with `manifest.json`,
SHA256 checksums, and a bundle README. It is marked `review_pending` until a
completed independent review file passes `--require-human-signoff`; only then is
the bundle marked `freeze_ready`.

Run the complete release evidence workflow in one command:

```bash
python benchmarks/contexttrace_bench/diag150_release_workflow.py \
  --output-dir benchmarks/contexttrace_bench/out/public_holdout \
  --bundle-dir benchmarks/contexttrace_bench/out/diag150_release_bundle
```

This regenerates the holdout benchmark, scores any known candidate prediction
files already present in the output directory, refreshes the audit packet, writes
the release bundle, and prints the final status. Add `--review-file ...` and
`--require-human-signoff` after independent review to make frozen-split
readiness a hard gate.

Enforce the internal verifier regression gates:

```bash
python benchmarks/contexttrace_bench/run_contexttrace.py \
  --mode semantic \
  --case-set all \
  --enforce-sota-gates
```

Default gates:

- `failure_label_macro_f1 >= 0.95`
- `claim_verdict_macro_f1 >= 0.95`
- `root_cause_accuracy >= 0.90`
- `citation_error_f1 >= 0.90`
- `evidence_span_overlap >= 0.75`
- `dangerous_false_green_rate <= 0.01`

These checks apply to one benchmark result. They do not verify independent
review, external dataset count, release-bundle integrity, or same-ID competitor
coverage. Run the fail-closed project-level evidence gate for broad-SOTA claim
readiness:

```bash
python benchmarks/contexttrace_bench/sota_gate.py
```

The command validates bundle checksums, documented external tracks, the primary
RAGTruth thresholds and confidence intervals, independent-review status,
same-ID competitor coverage, and Diag-150 freeze status. It returns nonzero
until every gate passes. Use `--allow-not-ready` only to refresh the JSON and
Markdown status reports while blockers remain.

## Candidate Baselines

Competitor or internal evaluator rows are scored from candidate prediction JSON
files. This keeps the leaderboard reproducible without requiring optional RAGAS,
DeepEval, RAGChecker, Phoenix, or TruLens dependencies in the benchmark harness.

`candidate_inputs.jsonl` contains the case IDs and trace payloads external
systems should evaluate. It intentionally omits expected labels.

```json
{
  "system": "RAGAS",
  "version": "custom-adapter",
  "estimated_cost_per_trace_usd": 0.002,
  "predictions": [
    {
      "id": "case-id",
      "predicted": ["unsupported_answer"],
      "predicted_verdict_counts": {"unsupported": 1},
      "predicted_citation_statuses": ["citation_ok"],
      "predicted_primary_root_cause": "answer_overreach",
      "predicted_evidence_spans": ["closest evidence text"],
      "latency_ms": 125.0
    }
  ]
}
```

Score one or more candidates:

```bash
python benchmarks/contexttrace_bench/run_contexttrace.py \
  --mode semantic \
  --case-set all \
  --candidate ragas_predictions.json \
  --candidate deepeval_predictions.json \
  --candidate ragchecker_predictions.json
```

Normalize generic evaluator output into candidate JSON:

```bash
python benchmarks/contexttrace_bench/adapt_candidate.py \
  --input evaluator_results.json \
  --output ragas_predictions.json \
  --system RAGAS \
  --preset ragas \
  --id-field id
```

Run optional baseline adapters directly:

```bash
python benchmarks/contexttrace_bench/run_ragas.py \
  --input benchmarks/contexttrace_bench/out/candidate_inputs.jsonl \
  --candidate-output benchmarks/contexttrace_bench/out/ragas_predictions.json \
  --model gpt-4.1-mini \
  --resume \
  --max-workers 4 \
  --progress-every 25

python benchmarks/contexttrace_bench/run_deepeval.py \
  --input benchmarks/contexttrace_bench/out/candidate_inputs.jsonl \
  --candidate-output benchmarks/contexttrace_bench/out/deepeval_predictions.json \
  --model gpt-4.1-mini \
  --resume \
  --max-workers 4 \
  --progress-every 25

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

Then score the candidates:

```bash
python benchmarks/contexttrace_bench/run_contexttrace.py \
  --mode semantic \
  --case-set all \
  --candidate benchmarks/contexttrace_bench/out/ragas_predictions.json \
  --candidate benchmarks/contexttrace_bench/out/deepeval_predictions.json \
  --candidate benchmarks/contexttrace_bench/out/ragchecker_predictions.json
```

The RAGAS, DeepEval, and RAGChecker runners require those packages and a
configured evaluator LLM. By default they emit faithfulness-style predictions;
root-cause, citation, and evidence-span fields remain unreported unless the
candidate JSON explicitly provides them. RAGChecker also requires `gt_answer`;
publishable rows should pass `--reference-file` with rows like
`{"id": "case-id", "gt_answer": "reference answer"}`. Use
`--use-response-as-gt` only for comparison-only smoke/proxy rows. The pinned
RAGChecker package requires Python 3.9 or newer; the examples use an isolated
Python 3.11 venv.

Leaderboard diagnostic metrics use `N/A` when a candidate does not report that
field. Those fields are not counted as attempted failures; the separate
diagnostic coverage table shows whether each system reports root cause, citation
status, and evidence spans.

Run a local/OpenAI-compatible judge baseline against Ollama, LM Studio, vLLM, or
a remote OpenAI-compatible endpoint:

```powershell
$judgeVenv = Join-Path $env:TEMP "contexttrace-local-judge"
py -3.11 -m venv $judgeVenv
& "$judgeVenv\Scripts\python.exe" -m pip install -r benchmarks/contexttrace_bench/requirements-local-judge.txt
& "$judgeVenv\Scripts\python.exe" benchmarks/contexttrace_bench/run_local_judge.py `
  --input benchmarks/contexttrace_bench/out/candidate_inputs.jsonl `
  --candidate-output benchmarks/contexttrace_bench/out/local_judge_predictions.json `
  --base-url http://localhost:11434/v1 `
  --model llama3.1:8b

python benchmarks/contexttrace_bench/run_contexttrace.py `
  --mode semantic `
  --case-set all `
  --candidate benchmarks/contexttrace_bench/out/local_judge_predictions.json
```

For the public holdout, score the richer OpenAI diagnostic judge row:

```powershell
$env:OPENAI_API_KEY = "<your OpenAI API key>"
$judgeVenv = Join-Path $env:TEMP "contexttrace-local-judge"
py -3.11 -m venv $judgeVenv
& "$judgeVenv\Scripts\python.exe" -m pip install -r benchmarks/contexttrace_bench/requirements-local-judge.txt
& "$judgeVenv\Scripts\python.exe" benchmarks/contexttrace_bench/run_local_judge.py `
  --input benchmarks/contexttrace_bench/out/public_holdout/candidate_inputs.jsonl `
  --raw-output benchmarks/contexttrace_bench/out/public_holdout/openai_diagnostic_judge_raw_results.json `
  --candidate-output benchmarks/contexttrace_bench/out/public_holdout/openai_diagnostic_judge_predictions.json `
  --base-url https://api.openai.com/v1 `
  --model gpt-4.1-mini `
  --system "OpenAI diagnostic judge" `
  --max-workers 4 `
  --progress-every 3
```

RAGChecker, Phoenix, and TruLens outputs can be normalized with the built-in
adapter presets:

```bash
python benchmarks/contexttrace_bench/adapt_candidate.py \
  --input ragchecker_output.json \
  --output benchmarks/contexttrace_bench/out/ragchecker_predictions.json \
  --system RAGChecker \
  --preset ragchecker
```

```bash
python benchmarks/contexttrace_bench/adapt_candidate.py \
  --input phoenix_results.json \
  --output benchmarks/contexttrace_bench/out/phoenix_predictions.json \
  --system Phoenix \
  --preset phoenix \
  --id-field id

python benchmarks/contexttrace_bench/adapt_candidate.py \
  --input trulens_results.json \
  --output benchmarks/contexttrace_bench/out/trulens_predictions.json \
  --system TruLens \
  --preset trulens \
  --id-field id
```

For remote OpenAI comparison runs, keep the product path local and isolate the
optional evaluator dependencies in a temporary environment. RAGAS, DeepEval, and
RAGChecker currently have different transitive dependency constraints, so
install them in separate venvs when collecting publishable comparison rows.

## External Dataset Scaffolding

For CRAG, ARES, or another external export that already has query, answer,
context, and label fields, first normalize it into a ContextTrace case pack:

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
```

The generic adapter accepts JSON or JSONL rows. Contexts may be strings or
objects with `text`, `content`, `passage`, or `document` fields. Use
`--id-field`, `--root-cause-field`, and `--evidence-spans-field` when the
export provides those columns under different names. Rows without answer text
or contexts are skipped because they cannot be fairly verified. The generated
case pack records skipped counts and sampling metadata under `stats`.

Score the adapted pack with the normal external report path:

```bash
python benchmarks/contexttrace_bench/run_contexttrace.py \
  --mode semantic \
  --case-pack benchmarks/contexttrace_bench/out/ares_case_pack.json \
  --output-dir benchmarks/contexttrace_bench/out/ares
```

Treat generic external packs as a documented bridge, not a publishable result by
themselves. Public claims still need the upstream dataset citation, frozen input
file, exact adapter command, independent review where labels or source spans
are ambiguous, and competitor rows scored on the same IDs.

For the full reviewable workflow, use the wrapper. It adapts the rows, writes a
review template and Markdown packet, scores ContextTrace, and creates a
checksummed release bundle:

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

The bundle remains `review_pending` until a completed review JSONL is supplied.
After independent review, rerun the workflow with `--review` and
`--review-kind independent`:

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
  --stratify-by split,label \
  --review benchmarks/contexttrace_bench/out/ares_release/external_review_completed.jsonl \
  --review-kind independent
```

The official ARES NQ example TSV can be normalized first:

```bash
python benchmarks/contexttrace_bench/ares_adapter.py \
  --download-example labeled \
  --download-dir benchmarks/contexttrace_bench/out/ares_nq_example \
  --output benchmarks/contexttrace_bench/out/ares_nq_example/ares_nq_labeled_rows.jsonl \
  --dataset ARES-NQ-example \
  --source-name "ARES/NQ labeled example"
```

Then score a deterministic 200-row stratified smoke:

```bash
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

Current ARES example status: the official example TSV contains 6,189 rows. The
default adapter path keeps the 4,421 answer-grounding rows and skips
context-relevance-only retrieval negatives unless
`--include-context-relevance-negatives` is supplied. Repeated upstream IDs are
disambiguated deterministically, and duplicate normalized case IDs are rejected.
The corrected stratified sample therefore contains 200 unique IDs.

ContextTrace scores failure macro-F1 `0.995` (95% CI `0.981-1.000`), root-cause
accuracy `0.995`, dangerous false-green rate `0.000`, citation error F1 `1.000`,
and evidence span overlap `1.000` on the 89 rows with auto-derived exact-answer
spans. Same-ID `gpt-4.1-mini` runs completed without row errors: RAGAS scores
failure macro-F1 `0.471` (95% CI `0.426-0.513`) and DeepEval scores `0.388`
(95% CI `0.342-0.431`). Their diagnostic attribution fields are `N/A`.

The bundle is still `review_pending`. Its exact-answer spans are synthetic, and
the sole ContextTrace disagreement is an ARES-positive row whose answer `one`
has only `The Bastard Executioner` as context. Independent review of the ARES
component-label mapping and source evidence is required before these calibration
results can support external-validation claims.

The RAGTruth adapter creates a ContextTrace-style case pack from the official
`response.jsonl` and `source_info.jsonl` exports:

```bash
python benchmarks/contexttrace_bench/ragtruth_adapter.py \
  --response path/to/response.jsonl \
  --source-info path/to/source_info.jsonl \
  --output benchmarks/contexttrace_bench/out/ragtruth_case_pack.json \
  --split test
```

For larger review packets, use deterministic stratified sampling and record the
sampling metadata from the generated case pack:

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

The workflow wrapper creates the sampled case pack, JSONL review queue, Markdown
review packet, and manifest in one reproducible run:

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

After review, rerun the same wrapper with the reviewed JSONL to validate,
apply, score, and update the manifest. Use `--allow-missing-source-spans` only
when reviewed rows explain that no fair source-side span exists:

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

Create the RAGTruth release bundle in one command:

```bash
python benchmarks/contexttrace_bench/ragtruth_release_workflow.py \
  --response benchmarks/contexttrace_bench/out/ragtruth_official/response.jsonl \
  --source-info benchmarks/contexttrace_bench/out/ragtruth_official/source_info.jsonl \
  --output-dir benchmarks/contexttrace_bench/out/ragtruth_release \
  --bundle-dir benchmarks/contexttrace_bench/out/ragtruth_release_bundle \
  --review benchmarks/contexttrace_bench/out/ragtruth_release/ragtruth_reviewed.jsonl \
  --allow-missing-source-spans
```

Bundle statuses are intentionally conservative: `review_pending` means source
evidence review is not applied, `calibration_only` means the run is reviewed and
scored but not strict independent external validation, `publishable` means
strict independent review and scoring passed for RAGTruth-specific claims, and
`validation_failed` means review, scoring, or artifact checks failed.

RAGTruth rows use `expected_verdict_scope: answer_label` unless a reviewer
explicitly supplies `taxonomy_override.expected_verdict_counts`. This avoids
inventing claim-level verdict counts from answer-side hallucination labels while
still allowing strict claim-count checks for curated overrides.

Scored RAGTruth bundles include `scored/ragtruth_error_analysis.json` and
`scored/ragtruth_error_analysis.md`. The reports rank dangerous false greens,
partial-support misses, contradicted-answer misses, source-span localization
misses, and root-cause misses, then group them by task/source/model/label
facets for calibration planning.

Run the same-ID RAGAS faithfulness baseline on the release candidate inputs:

```powershell
& ".tmp-ragas-venv\Scripts\python.exe" benchmarks/contexttrace_bench/run_ragas.py `
  --input benchmarks/contexttrace_bench/out/ragtruth_release_bundle/scored/candidate_inputs.jsonl `
  --raw-output benchmarks/contexttrace_bench/out/ragtruth_release/ragas_raw_results.json `
  --candidate-output benchmarks/contexttrace_bench/out/ragtruth_release/ragas_predictions.json `
  --model gpt-4.1-mini `
  --max-output-tokens 32768 `
  --max-workers 4 `
  --progress-every 10 `
  --resume
```

The canonical row covers 200/200 IDs with zero errors and scores failure
macro-F1 `0.152`. Root-cause, citation, and evidence-span diagnostics are `N/A`.
The release workflow auto-discovers `ragas_predictions.json` in its output
directory and includes `baseline_results.json` in the bundle.

Score the adapted pack with the same benchmark reports:

```bash
python benchmarks/contexttrace_bench/run_contexttrace.py \
  --mode semantic \
  --case-pack benchmarks/contexttrace_bench/out/ragtruth_case_pack.json \
  --output-dir benchmarks/contexttrace_bench/out/ragtruth
```

Build a human-review queue for source evidence mapping:

```bash
python benchmarks/contexttrace_bench/ragtruth_review.py build-queue \
  --case-pack benchmarks/contexttrace_bench/out/ragtruth_case_pack.json \
  --output benchmarks/contexttrace_bench/out/ragtruth_review_queue.jsonl \
  --suggest-source-spans \
  --max-suggestions 3
```

Build a reviewer-facing Markdown packet for independent sign-off:

```bash
python benchmarks/contexttrace_bench/ragtruth_review.py build-packet \
  --review-queue benchmarks/contexttrace_bench/out/ragtruth_review_queue.jsonl \
  --output benchmarks/contexttrace_bench/out/ragtruth_review_packet.md
```

Or build the independent-review handoff in one step. This writes a blank
signoff template, Markdown packet, README, and status JSON; prior assisted
review fields are intentionally cleared.

```bash
python benchmarks/contexttrace_bench/ragtruth_review.py build-signoff-handoff \
  --review-queue benchmarks/contexttrace_bench/out/ragtruth_review_queue.jsonl \
  --case-pack benchmarks/contexttrace_bench/out/ragtruth_case_pack.json \
  --output-dir benchmarks/contexttrace_bench/out/ragtruth_independent_signoff
```

Validate reviewed rows before applying them:

```bash
python benchmarks/contexttrace_bench/ragtruth_review.py validate \
  --case-pack benchmarks/contexttrace_bench/out/ragtruth_case_pack.json \
  --review benchmarks/contexttrace_bench/out/ragtruth_reviewed.jsonl \
  --output benchmarks/contexttrace_bench/out/ragtruth_review_validation.json \
  --require-reviewed \
  --require-source-spans
```

Omit `--require-source-spans` only for reviewed rows whose notes explain that no
fair source-side span exists; those rows stay reviewed but are excluded from
source-span-overlap labels.

After review, apply rows marked `reviewed`, `accepted`, or `approved` with
`source_evidence_spans` filled:

```bash
python benchmarks/contexttrace_bench/ragtruth_review.py apply \
  --case-pack benchmarks/contexttrace_bench/out/ragtruth_case_pack.json \
  --review benchmarks/contexttrace_bench/out/ragtruth_reviewed.jsonl \
  --output benchmarks/contexttrace_bench/out/ragtruth_reviewed_case_pack.json \
  --require-reviewed
```

RAGTruth labels answer-side hallucination spans. The adapter preserves those
spans in metadata and maps answer-level labels into the ContextTrace taxonomy,
but it leaves `expected_evidence_spans` empty until a human curator maps the
answer-side spans to source evidence. Treat this as external-validation
scaffolding, not a publishable leaderboard row by itself.

The helper script below builds the optional temp venvs, runs both remote
evaluators, and scores the full leaderboard. It reads `OPENAI_API_KEY` from the
current shell environment, Windows user/machine environment, or repo `.env`.

```powershell
$env:OPENAI_API_KEY = "<your OpenAI API key>"
.\benchmarks\contexttrace_bench\run_openai_baselines.ps1 -Resume -MaxWorkers 4
```

Use a limited smoke run before spending on the full comparison:

```powershell
$env:OPENAI_API_KEY = "<your OpenAI API key>"
.\benchmarks\contexttrace_bench\run_openai_baselines.ps1 -Limit 5
```

Latest full OpenAI-backed comparison rows were collected with `gpt-4.1-mini`
across all 500 cases: RAGAS scored `0.200` failure macro-F1 and DeepEval scored
`0.069` failure macro-F1. Both are faithfulness-only rows, so root-cause,
citation-status, and span-localization fields correctly appear as `N/A`.

Manual equivalent:

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

The default benchmark now meets the 500-case bar. Publish full competitor rows
and keep diagnostic N/A reporting before making a broad public
state-of-the-art claim.
