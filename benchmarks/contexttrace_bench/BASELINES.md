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
| OpenAI diagnostic judge | `run_local_judge.py` | Expanded public holdout and RAGTruth smoke candidates scored | Holdout only | `gpt-4.1-mini`, 150/150 public-holdout rows and 50/50 RAGTruth smoke rows, zero row errors. The RAGTruth smoke is calibration-only because it has high dangerous false-green rate. |
| OpenAI-compatible local judge | `run_local_judge.py` | Smoke run completed | No | Ollama `phi3:latest` produced 5 predictions. It is parseable but slow on this machine, so full 500-case execution is a multi-hour run. |
| Phoenix | `adapt_candidate.py --preset phoenix` | Adapter ready | No | Requires exported Phoenix evaluator results. |
| TruLens | `adapt_candidate.py --preset trulens` | Adapter ready | No | Requires exported TruLens evaluator results. |
| RAGTruth external validation | `ragtruth_adapter.py`, `ragtruth_review.py`, `run_contexttrace.py --case-pack` | Official raw-file assisted pilot scored | No | 50-row test-split smoke builds, scores, and maps the 15 hallucination rows with assisted source-span review. Requires independent human sign-off and broader coverage before publishable external-dataset claims. |

Latest scored leaderboard:

| System | Cases | Failure Macro-F1 | Diagnostic Coverage |
| --- | ---: | ---: | --- |
| ContextTrace semantic verifier | 500 | 1.000 | Root cause, citation status, and evidence-span localization reported where supported. |
| RAGAS `gpt-4.1-mini` | 500 | 0.200 | Faithfulness labels only; root cause, citation status, and spans are `N/A`. |
| DeepEval `gpt-4.1-mini` | 500 | 0.069 | Faithfulness labels only; root cause, citation status, and spans are `N/A`. |

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
| ContextTrace semantic verifier on RAGTruth test-split smoke | 50 | 15 | 0.181 | 0.400 | 0.000 | 1.000 | 0.883 |
| OpenAI diagnostic judge `gpt-4.1-mini` on RAGTruth test-split smoke | 50 | 15 | 0.272 | 0.660 | 0.260 | 1.000 | 0.592 |

This pilot uses official RAGTruth `response.jsonl` and `source_info.jsonl`
files stored outside the repo under ignored benchmark output. The 15 reviewed
rows are an assisted source-evidence mapping pass, not independent human
sign-off. Treat the result as a workflow validation artifact: it proves the
adapter, review queue, apply step, and source-span scoring path work end to end,
while the low failure macro-F1 and root-cause accuracy show the RAGTruth
taxonomy mapping/calibration still needs work before any SOTA claim. The OpenAI
judge is useful as a contrastive calibration target, but it labeled 46/50 rows
as `no_failure_detected`, so its `0.260` dangerous false-green rate blocks any
publishable claim from this smoke.

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

Score full candidate rows:

```bash
python benchmarks/contexttrace_bench/run_contexttrace.py \
  --mode semantic \
  --case-set all \
  --candidate benchmarks/contexttrace_bench/out/ragas_predictions.json \
  --candidate benchmarks/contexttrace_bench/out/deepeval_predictions.json
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

python benchmarks/contexttrace_bench/ragtruth_review.py apply \
  --case-pack benchmarks/contexttrace_bench/out/ragtruth_case_pack.json \
  --review benchmarks/contexttrace_bench/out/ragtruth_reviewed.jsonl \
  --output benchmarks/contexttrace_bench/out/ragtruth_reviewed_case_pack.json \
  --require-reviewed
```

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
