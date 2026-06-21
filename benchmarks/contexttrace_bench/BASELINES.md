# Baseline Comparison Runbook

This file tracks competitor and reference baseline work for ContextTrace-Bench.
Rows should only be described as publishable after they cover the full benchmark
case set and are scored by `run_contexttrace.py --candidate`.

## Current Status

| System | Runner or Adapter | Status | Publishable | Notes |
| --- | --- | --- | --- | --- |
| ContextTrace semantic verifier | `run_contexttrace.py --mode semantic` | Ready | Yes | Local-first product path. CI enforces default quality gates. |
| RAGAS | `run_ragas.py` | Full OpenAI-backed candidate scored | Yes | `gpt-4.1-mini`, 500/500 rows, zero row errors. Faithfulness-only baseline; diagnostic fields are `N/A`. |
| DeepEval | `run_deepeval.py` | Full OpenAI-backed candidate scored | Yes | `gpt-4.1-mini`, 500/500 rows, zero row errors. Faithfulness-only baseline; diagnostic fields are `N/A`. |
| RAGChecker | `run_ragchecker.py`, `adapt_candidate.py --preset ragchecker` | 50-row OpenAI proxy smoke scored; reference sidecar ready | No | Requires Python 3.9+ and `gt_answer` per row. The `--use-response-as-gt` smoke verified runner/checkpointing but is not publishable; publishable runs should use `--reference-file`. |
| OpenAI diagnostic judge | `run_local_judge.py` | Expanded public holdout and RAGTruth smoke candidates scored | Holdout only | `gpt-4.1-mini`, 150/150 public-holdout rows and 50/50 RAGTruth smoke rows, zero row errors. The RAGTruth smoke is calibration-only because it has high dangerous false-green rate. |
| OpenAI-compatible local judge | `run_local_judge.py` | Smoke run completed | No | Ollama `phi3:latest` produced 5 predictions. It is parseable but slow on this machine, so full 500-case execution is a multi-hour run. |
| Phoenix | `adapt_candidate.py --preset phoenix` | Adapter ready | No | Requires exported Phoenix evaluator results. |
| TruLens | `adapt_candidate.py --preset trulens` | Adapter ready | No | Requires exported TruLens evaluator results. |
| RAGTruth external validation | `ragtruth_adapter.py`, `ragtruth_review.py`, `ragtruth_workflow.py`, `run_contexttrace.py --case-pack` | 200-case stratified assisted workflow scored | No | Deterministic test-split sample scored with 88 GPT-5.1-assisted review rows; 76 rows have source evidence spans and 12 are intentionally source-less. Requires independent human sign-off and calibration before publishable external-dataset claims. |

Latest scored leaderboard:

| System | Cases | Failure Macro-F1 | Diagnostic Coverage |
| --- | ---: | ---: | --- |
| ContextTrace semantic verifier | 500 | 1.000 | Root cause, citation status, and evidence-span localization reported where supported. |
| RAGAS `gpt-4.1-mini` | 500 | 0.200 | Faithfulness labels only; root cause, citation status, and spans are `N/A`. |
| DeepEval `gpt-4.1-mini` | 500 | 0.069 | Faithfulness labels only; root cause, citation status, and spans are `N/A`. |

Latest RAGChecker proxy smoke:

| System | Cases | Failure Macro-F1 | Dangerous False Green | Notes |
| --- | ---: | ---: | ---: | --- |
| RAGChecker `openai/gpt-4.1-mini` response-as-gt proxy | 50 | 0.038 | 0.860 | Checkpointed chunks completed with zero runner errors. This is setup/calibration evidence only because `gt_answer` was proxied from the response. |

The RAGChecker smoke wrote `ragchecker_raw_results.json` and
`ragchecker_predictions.json` under ignored benchmark output. It validated the
native input builder, official RAGChecker API path, candidate adapter, and
`--resume` checkpointing. Do not scale this proxy mode into a publishable row;
use a real reference answer sidecar through `--reference-file` before spending
on a full 500-case RAGChecker comparison.

Latest public holdout:

| System | Cases | Failure Macro-F1 | Root Cause Accuracy | Citation Error F1 | Span Overlap |
| --- | ---: | ---: | ---: | ---: | ---: |
| ContextTrace semantic verifier | 150 | 1.000 | 1.000 | 1.000 | 0.950 |
| OpenAI diagnostic judge `gpt-4.1-mini` | 150 | 0.931 | 0.953 | 1.000 | 0.921 |

The expanded public holdout has reached the 150-case ContextTrace-Diag-150
target. It passes all labeled gates for the local semantic verifier across 150
cases and 149 evidence-span labels. The OpenAI diagnostic judge reported all
150 rows with zero row errors, with root-cause coverage on 150/150 rows,
citation-status coverage on 103/150 rows, and evidence-span coverage on 149/150
rows.

Latest RAGTruth assisted review pilot:

| System | Cases | Reviewed Span Rows | Failure Macro-F1 | Root Cause Accuracy | Dangerous False Green | Citation Error F1 | Span Overlap |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| ContextTrace semantic verifier on RAGTruth stratified test sample | 200 | 76 | 0.491 | 0.670 | 0.005 | 1.000 | 0.589 |
| ContextTrace semantic verifier on RAGTruth test-split smoke | 50 | 15 | 0.181 | 0.400 | 0.000 | 1.000 | 0.883 |
| OpenAI diagnostic judge `gpt-4.1-mini` on RAGTruth test-split smoke | 50 | 15 | 0.272 | 0.660 | 0.260 | 1.000 | 0.592 |

These pilots use official RAGTruth `response.jsonl` and `source_info.jsonl`
files stored outside the repo under ignored benchmark output. The latest
200-case row uses `sample_size=200`, `sample_seed=13`, and
`stratify_by=task_type,source,expected_label,model`; it reviewed all 88
hallucination rows with a GPT-5.1-assisted source pass, validated with zero
errors, and allowed 12 rows with no fair source-side evidence span. These are
assisted review artifacts, not independent human sign-off. Treat the result as
workflow and calibration evidence: it proves the adapter, review queue, apply
step, manifest, and source-span scoring path work end to end, while the low
failure macro-F1 and root-cause accuracy show the RAGTruth taxonomy
mapping/calibration still needs work before any SOTA claim. The latest
ContextTrace row includes verifier calibration for common news-summary
paraphrases, generated summary prefixes, QA boilerplate/list markers, multi-span
QA list/procedural evidence, source-availability boilerplate,
relation/appositive evidence variants, strict death-count identity checks,
negated structured parking lists, and structured JSON evidence attributes such
as Wi-Fi, reservations, parking, ambience flags, categories, ratings, hours
ranges, day-specific schedules, structured review aggregation, explicit
structured-data absence claims, mixed-polarity parking claims, and plural
structured list-item matching. The latest pass also tightens negation scope
across `but`/`though` clauses, supports structured variable closing hours, and
maps bounded Yelp review paraphrases for cash/ATM wording, small salad bars,
friendly staff, menu changes, wrong sandwiches, high prices, and busy golf-event
days. The current row further expands review-domain cue detection and bounded
paraphrases for environmental straw/dockage concerns, not-welcoming wording,
pier/waterfront views, menu item lists, beer selection, hidden-gem wording,
mixed sentiment subfacts, and food/service sentiment. The latest calibration
also guards fact-level semantic support for preventive negation paraphrases,
first-time-since negative wording, critical-condition medical paraphrases,
outsourced-service contrast clauses, quoted conditional negation, and pronoun
relation paraphrases while preserving swapped-entity and reversed-relation
contradiction tests. The current row additionally improves answerability/list
calibration with relation-support precedence, numbered visit/call/fill/submit
list parsing, optional `with or without` list handling, broader supporting-span
recall, URL/website and city-list paraphrases, and targeted
attribution/closed-list contradiction guards.
RAGTruth rows use answer-level verdict scope by default; claim-count metrics
apply only to rows with explicit reviewer taxonomy overrides. The OpenAI judge is
useful as a contrastive calibration target, but its 50-row smoke labeled 46/50
rows as `no_failure_detected`, so its `0.260` dangerous false-green rate blocks
any publishable claim from that smoke.

## Full ContextTrace Run

```bash
python benchmarks/contexttrace_bench/run_contexttrace.py \
  --mode semantic \
  --case-set all \
  --output-dir benchmarks/contexttrace_bench/out \
  --enforce-sota-gates
```

Expected artifacts:

- `benchmarks/contexttrace_bench/out/contexttrace_bench_results.json`
- `benchmarks/contexttrace_bench/out/results.md`
- `benchmarks/contexttrace_bench/out/leaderboard.md`
- `benchmarks/contexttrace_bench/out/report.html`
- `benchmarks/contexttrace_bench/out/error_analysis.json`
- `benchmarks/contexttrace_bench/out/error_analysis.md`
- `benchmarks/contexttrace_bench/out/candidate_inputs.jsonl`

## Remote RAGAS And DeepEval Runs

Use the helper script for full publishable rows:

```powershell
$env:OPENAI_API_KEY = "<your evaluator key>"
.\benchmarks\contexttrace_bench\run_openai_baselines.ps1
```

Use a limited smoke run only to verify setup:

```powershell
$env:OPENAI_API_KEY = "<your evaluator key>"
.\benchmarks\contexttrace_bench\run_openai_baselines.ps1 -Limit 5
```

Limited runs are not publishable because they do not cover all case IDs.

The helper supports resumable checkpointed runs:

```powershell
.\benchmarks\contexttrace_bench\run_openai_baselines.ps1 `
  -Resume `
  -MaxWorkers 4 `
  -ProgressEvery 25 `
  -SkipInstall
```

`-Resume` reuses completed rows from the raw output files and retries missing or
errored rows. `-MaxWorkers` controls concurrent evaluator calls; keep it low
unless provider rate limits are known.

Manual RAGAS run:

```powershell
$ragasVenv = Join-Path $env:TEMP "contexttrace-ragas"
py -3.11 -m venv $ragasVenv
& "$ragasVenv\Scripts\python.exe" -m pip install -r benchmarks/contexttrace_bench/requirements-ragas.txt
& "$ragasVenv\Scripts\python.exe" benchmarks/contexttrace_bench/run_ragas.py `
  --input benchmarks/contexttrace_bench/out/candidate_inputs.jsonl `
  --candidate-output benchmarks/contexttrace_bench/out/ragas_predictions.json `
  --model gpt-4.1-mini `
  --resume `
  --max-workers 4 `
  --progress-every 25
```

Manual DeepEval run:

```powershell
$deepevalVenv = Join-Path $env:TEMP "contexttrace-deepeval"
py -3.11 -m venv $deepevalVenv
& "$deepevalVenv\Scripts\python.exe" -m pip install -r benchmarks/contexttrace_bench/requirements-deepeval.txt
& "$deepevalVenv\Scripts\python.exe" benchmarks/contexttrace_bench/run_deepeval.py `
  --input benchmarks/contexttrace_bench/out/candidate_inputs.jsonl `
  --candidate-output benchmarks/contexttrace_bench/out/deepeval_predictions.json `
  --model gpt-4.1-mini `
  --resume `
  --max-workers 4 `
  --progress-every 25
```

Manual RAGChecker run:

```powershell
$ragcheckerVenv = Join-Path $env:TEMP "contexttrace-ragchecker"
py -3.11 -m venv $ragcheckerVenv
& "$ragcheckerVenv\Scripts\python.exe" -m pip install -r benchmarks/contexttrace_bench/requirements-ragchecker.txt
& "$ragcheckerVenv\Scripts\python.exe" -m spacy download en_core_web_sm
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

`--use-response-as-gt` makes a setup/proxy row only. Publishable RAGChecker
comparisons need a real reference answer sidecar supplied with
`--reference-file` or an official RAGChecker output adapted with
`--from-ragchecker-output`.

Score full candidate rows:

```bash
python benchmarks/contexttrace_bench/run_contexttrace.py \
  --mode semantic \
  --case-set all \
  --candidate benchmarks/contexttrace_bench/out/ragas_predictions.json \
  --candidate benchmarks/contexttrace_bench/out/deepeval_predictions.json \
  --candidate benchmarks/contexttrace_bench/out/ragchecker_predictions.json
```

## Local Judge Baseline

Run against an OpenAI-compatible endpoint:

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

Then score it:

```bash
python benchmarks/contexttrace_bench/run_contexttrace.py \
  --mode semantic \
  --case-set all \
  --candidate benchmarks/contexttrace_bench/out/local_judge_predictions.json
```

Run the richer OpenAI diagnostic judge on the public holdout:

```powershell
$env:OPENAI_API_KEY = "<your evaluator key>"
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
  --progress-every 3 `
  --request-timeout 90

python benchmarks/contexttrace_bench/run_contexttrace.py `
  --mode semantic `
  --case-set public_holdout `
  --no-generated-cases `
  --output-dir benchmarks/contexttrace_bench/out/public_holdout `
  --candidate benchmarks/contexttrace_bench/out/public_holdout/openai_diagnostic_judge_predictions.json
```

Current local smoke result:

```bash
python benchmarks/contexttrace_bench/run_contexttrace.py \
  --mode semantic \
  --case-set all \
  --candidate benchmarks/contexttrace_bench/out/local_judge_phi3_smoke_predictions.json
```

- Candidate: `Ollama phi3 local judge`
- Model: `phi3:latest`
- Coverage: 5 submitted predictions out of 500 cases
- Status: smoke only, not publishable
- Observed smoke runtime: about 155 seconds for 5 cases

Installed Ollama chat models at the time of the smoke run were `phi3:latest`,
`llama3:latest`, and `mistral:latest`. Larger local models are expected to be
slower unless hardware or serving settings change.

## Phoenix And TruLens Exports

Normalize Phoenix output:

```bash
python benchmarks/contexttrace_bench/adapt_candidate.py \
  --input phoenix_results.json \
  --output benchmarks/contexttrace_bench/out/phoenix_predictions.json \
  --system Phoenix \
  --preset phoenix \
  --id-field id
```

Normalize TruLens output:

```bash
python benchmarks/contexttrace_bench/adapt_candidate.py \
  --input trulens_results.json \
  --output benchmarks/contexttrace_bench/out/trulens_predictions.json \
  --system TruLens \
  --preset trulens \
  --id-field id
```

## RAGTruth External Validation

Build the first external dataset case pack from RAGTruth exports:

```bash
python benchmarks/contexttrace_bench/ragtruth_adapter.py \
  --response path/to/response.jsonl \
  --source-info path/to/source_info.jsonl \
  --output benchmarks/contexttrace_bench/out/ragtruth_case_pack.json \
  --split test
```

For the next broader review round, build a deterministic stratified sample and
record the sampling metadata from `stats.sampling`:

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

Or build the sampled case pack, review queue, review packet, and manifest in one
workflow run:

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

Score the adapted case pack:

```bash
python benchmarks/contexttrace_bench/run_contexttrace.py \
  --mode semantic \
  --case-pack benchmarks/contexttrace_bench/out/ragtruth_case_pack.json \
  --output-dir benchmarks/contexttrace_bench/out/ragtruth
```

Prepare the human evidence-span review queue and apply reviewed mappings:

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

RAGTruth labels answer-side hallucination spans. The adapter maps no-span rows
to `no_failure_detected`, evident conflict spans to `contradicted_answer`, and
other hallucination spans to `partial_support`, while preserving the original
spans in `ragtruth_metadata.answer_hallucination_spans`. A publishable external
validation run still needs human mapping from those answer spans to source-side
evidence spans before using evidence-span overlap.

Run the OpenAI diagnostic judge on a reviewed RAGTruth smoke pack for calibration
only:

```powershell
$env:OPENAI_API_KEY = "<your evaluator key>"
$judgeVenv = Join-Path $env:TEMP "contexttrace-openai-judge"
py -3.11 -m venv $judgeVenv
& "$judgeVenv\Scripts\python.exe" -m pip install -r benchmarks/contexttrace_bench/requirements-local-judge.txt
& "$judgeVenv\Scripts\python.exe" benchmarks/contexttrace_bench/run_local_judge.py `
  --input benchmarks/contexttrace_bench/out/ragtruth_official/reviewed_assisted_test50_calibrated/candidate_inputs.jsonl `
  --raw-output benchmarks/contexttrace_bench/out/ragtruth_official/openai_judge_test50_raw_results.json `
  --candidate-output benchmarks/contexttrace_bench/out/ragtruth_official/openai_judge_test50_predictions.json `
  --base-url https://api.openai.com/v1 `
  --model gpt-4.1-mini `
  --system "OpenAI diagnostic judge on RAGTruth assisted pilot" `
  --max-workers 4 `
  --progress-every 10 `
  --request-timeout 90 `
  --resume

python benchmarks/contexttrace_bench/run_contexttrace.py `
  --mode semantic `
  --case-pack benchmarks/contexttrace_bench/out/ragtruth_official/ragtruth_reviewed_case_pack_test50_assisted.json `
  --output-dir benchmarks/contexttrace_bench/out/ragtruth_official/openai_judge_test50_scored `
  --bootstrap-samples 100 `
  --candidate benchmarks/contexttrace_bench/out/ragtruth_official/openai_judge_test50_predictions.json
```

## Publishability Checklist

For every public baseline row, record:

- Runner or adapter command.
- Python version, package versions, model name, and provider.
- Full-case coverage, not a `-Limit` smoke run.
- Candidate JSON path.
- Scored leaderboard artifact path.
- Known missing diagnostic fields shown as `N/A`.
- Any estimated cost assumptions.

Do not compare a faithfulness-only evaluator against root-cause, citation, or
span-localization metrics as if those fields were attempted. Use the diagnostic
coverage table for that distinction.
