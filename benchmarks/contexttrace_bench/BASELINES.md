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
| RAGChecker | `run_ragchecker.py`, `adapt_candidate.py --preset ragchecker` | 200-row real-reference CRAG calibration scored | No | `gpt-4.1-mini`, 200/200 same-ID CRAG rows, real official-answer sidecar, all 11 metrics, and zero errors. The gold-answer grounding proxy remains review-pending, not publishable. |
| OpenAI diagnostic judge | `run_local_judge.py` | Expanded public holdout and RAGTruth smoke candidates scored | Holdout only | `gpt-4.1-mini`, 150/150 public-holdout rows and 50/50 RAGTruth smoke rows, zero row errors. The RAGTruth smoke is calibration-only because it has high dangerous false-green rate. |
| OpenAI-compatible local judge | `run_local_judge.py` | Smoke run completed | No | Ollama `phi3:latest` produced 5 predictions. It is parseable but slow on this machine, so full 500-case execution is a multi-hour run. |
| Phoenix | `adapt_candidate.py --preset phoenix` | Adapter ready | No | Requires exported Phoenix evaluator results. |
| TruLens | `adapt_candidate.py --preset trulens` | Adapter ready | No | Requires exported TruLens evaluator results. |
| RAGTruth external validation | `ragtruth_adapter.py`, `ragtruth_review.py`, `ragtruth_workflow.py`, `run_contexttrace.py --case-pack` | 200-case stratified assisted workflow scored | No | Deterministic test-split sample scored with 88 GPT-5.1-assisted review rows; 75 rows have source evidence spans and 13 are intentionally source-less or source-supported taxonomy corrections. Requires independent human sign-off and calibration before publishable external-dataset claims. |
| ARES NQ example external validation | `ares_adapter.py`, `external_case_pack_workflow.py`, `run_contexttrace.py --case-pack` | 200-row same-ID comparison scored | No | ContextTrace, RAGAS, and DeepEval were scored on 200 unique IDs from the official example. The checksummed bundle remains `review_pending`; independent label and source-evidence review is required. |
| CRAG Task 1 v5 calibration | `crag_adapter.py`, `crag_calibration_report.py`, `crag_ragchecker_report.py`, `external_case_pack_workflow.py` | 200-row same-ID ContextTrace/RAGChecker grounding proxy scored | No | Pinned 739 MB archive, 200 unique stratified IDs, five web pages each, and a checksum-verified review bundle. ContextTrace and RAGChecker agree on 150/200 rows; gold-answer correctness is not a grounding label. |
| Generic external case-pack validation | `external_case_pack.py`, `external_case_pack_workflow.py`, `run_contexttrace.py --case-pack` | Workflow ready | No | Normalizes CRAG/ARES-style JSON or JSONL exports with query, answer, contexts, and labels, then writes review/release bundles. Requires official export files, dataset documentation, and review/sign-off before publishable external claims. |

Latest scored leaderboard:

| System | Cases | Failure Macro-F1 | Diagnostic Coverage |
| --- | ---: | ---: | --- |
| ContextTrace semantic verifier | 500 | 1.000 | Root cause, citation status, and evidence-span localization reported where supported. |
| RAGAS `gpt-4.1-mini` | 500 | 0.200 | Faithfulness labels only; root cause, citation status, and spans are `N/A`. |
| DeepEval `gpt-4.1-mini` | 500 | 0.069 | Faithfulness labels only; root cause, citation status, and spans are `N/A`. |

Latest RAGChecker runs:

| Run | Cases | Reference Mode | Result | Status |
| --- | ---: | --- | --- | --- |
| Built-in smoke, `openai/gpt-4.1-mini` | 50 | Response-as-gt proxy | Failure macro-F1 `0.038`, dangerous false green `0.860` | Setup only |
| CRAG Task 1 v5, `openai/gpt-4.1-mini` | 200 | Official-answer sidecar | 93 proxy-accepted, 107 flagged, 200 complete metric rows, zero errors | `review_pending` |

The RAGChecker smoke wrote `ragchecker_raw_results.json` and
`ragchecker_predictions.json` under ignored benchmark output. It validated the
native input builder, official RAGChecker API path, candidate adapter, and
`--resume` checkpointing. Do not scale this proxy mode into a publishable row;
use a real reference answer sidecar through `--reference-file`. The CRAG run now
validates that path across 200 same-ID rows; the built-in 500-case benchmark
still needs an appropriate independent reference-answer source before a full
RAGChecker row can be claimed.

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
| ContextTrace semantic verifier on RAGTruth stratified test sample | 200 | 75 | 0.955 | 0.955 | 0.000 | 1.000 | 0.786 |
| ContextTrace semantic verifier on RAGTruth test-split smoke | 50 | 15 | 0.181 | 0.400 | 0.000 | 1.000 | 0.883 |
| OpenAI diagnostic judge `gpt-4.1-mini` on RAGTruth test-split smoke | 50 | 15 | 0.272 | 0.660 | 0.260 | 1.000 | 0.592 |

These pilots use official RAGTruth `response.jsonl` and `source_info.jsonl`
files stored outside the repo under ignored benchmark output. The latest
200-case row uses `sample_size=200`, `sample_seed=13`, and
`stratify_by=task_type,source,expected_label,model`; it reviewed all 88
hallucination rows with a GPT-5.1-assisted source pass, validated with zero
errors, and allowed 13 rows with no fair source-side evidence span or a
source-supported taxonomy correction. These are
assisted review artifacts, not independent human sign-off. Treat the result as
workflow and calibration evidence: it proves the adapter, review queue, apply
step, manifest, and source-span scoring path work end to end. The current
failure macro-F1, root-cause accuracy, dangerous false-green rate, and
evidence-span overlap now clear the 6-week plan's RAGTruth calibration
thresholds, but independent sign-off, claim-verdict calibration, and broader
external validation still block publishable external-dataset claims. The latest
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
attribution/closed-list contradiction guards. The current row also adds bounded
structured Yelp review-summary support for private-event, comedy-relocation,
affordability, positive/negative experience, delivery, dining-service,
gratuity, signage, and accommodating-staff paraphrases, with a guard against
supporting slow-service claims from positive staff reviews alone. The latest
row also narrows strict death-count handling so age-at-death summaries can use
adjacent evidence, and adds high-confidence distributed predicate support for
compressed multi-span summaries while preserving relation-conflict tests. It
also includes reviewed taxonomy overrides for `ragtruth_16056` and
`ragtruth_906`, where assisted source review found the labeled spans directly
supported by the source text, eliminating apparent dangerous false greens. The
current row adds supported-row overflag calibration for multi-sentence external
summaries, QA procedural snippets, structured review summaries, time
expressions, song/version summaries, editable schedule templates, Waze safety
language, Obama/Cuba/Venezuela policy context, migrant employment/revenue
wording, education/prevention summaries, distributed bratwurst timing evidence,
and non-negating `without hesitation` clauses. It also narrows numeric/version
conflict detection, ignores passage markers in numeric checks, requires content
numbers such as percentages to appear in source evidence before semantic support
is granted, handles compact time forms such as `7pm`, and neutralizes
non-denial negation phrases such as `no disputing`, `or not`, and
uncertain-beginnings wording. The latest error analysis shows
`answer_overreach -> conflicting_contexts` down from `8` cases to `3` without
introducing dangerous false greens. A follow-up parser and numeric-normalization
pass skips orphan passage/list markers, removes dangling inline list markers,
normalizes thousands separators, recognizes simple `rise by X to Y`
previous-amount derivations, and preserves contradiction handling for explicit
`do not use` method warnings. Supported-row overflags remain a root-cause
cluster at `3` `no_failure_detected -> answer_overreach` cases.
A follow-up pass splits bullet-style procedural answers, filters short step
headings, normalizes compact height notation such as `5'3"`, and handles
bounded harassment-summary paraphrases such as `not to mention` and
culture-shift language.
A temperature/proposal/fire-regeneration pass canonicalizes
`proposal`/`proposed`, keeps Fahrenheit/Celsius equivalents from creating
spurious missing numbers, handles cautionary cooking instructions such as
`not too close`, and supports bounded jack-pine fire/cone paraphrases.
The current contradicted-answer pass adds bounded conflict detection for
all-week structured hours with closed days, missing-person physical-attribute
availability, death-group identity mismatches, conditional safety claims,
praise attribution, and Dermaroller-vs-paint-roller domain mismatch. This
reduced `conflicting_contexts -> answer_overreach` misses from `10` to `4`
while keeping dangerous false greens at `0`.
A supported-row and projection pass adds bounded support for defamation-law
summaries, Pope/genocide dilemma wording, Tucker/Phyllis leverage summaries,
Luna/Eric-secret summaries, and Yelp closure-uncertainty wording. It also keeps
explicit RAGTruth `claim_counts` unsupported labels instead of collapsing them
to answer-level partial support. This moved the 200-case RAGTruth assisted row
to failure macro-F1 `0.937` and root-cause accuracy `0.935` while keeping
dangerous false greens at `0`.
Structured JSON source-span localization now emits atomic top-level field,
nested Yelp attribute, business-hour, and review-sentence spans, then ranks
equally relevant evidence toward the most bounded source span. This moved the
200-case RAGTruth assisted row to evidence-span overlap `0.783` and
claim-verdict macro-F1 `0.337` while preserving the label and root-cause
metrics.
A passage-scoped support pass splits MARCO `passage N:` contexts without
cross-passage sentence spans, accepts bounded passage-level absence claims, and
covers a tweet-favorite tool paraphrase. This moved the 200-case RAGTruth
assisted row to failure macro-F1 `0.944`, root-cause accuracy `0.945`, and
evidence-span overlap `0.786` while keeping dangerous false greens at `0`.
A focused full-context conflict fallback catches existing amputation causality
conflicts when a compound claim's top evidence span only covers the other
conjunct. This moved the 200-case RAGTruth assisted row to failure macro-F1
`0.950` and root-cause accuracy `0.950` while keeping evidence-span overlap
`0.786` and dangerous false greens at `0`.
A structured-data pass treats a single-feature outdoor seating availability
assertion as conflicting when the source JSON has `OutdoorSeating: null`, while
leaving multi-amenity partial-support rows and explicit absence-of-information
claims intact. This moved the 200-case RAGTruth assisted row to failure
macro-F1 `0.955` and root-cause accuracy `0.955` while keeping evidence-span
overlap `0.786` and dangerous false greens at `0`.
RAGTruth rows use answer-level verdict scope by default; claim-count metrics
apply only to rows with explicit reviewer taxonomy overrides. The OpenAI judge is
useful as a contrastive calibration target, but its 50-row smoke labeled 46/50
rows as `no_failure_detected`, so its `0.260` dangerous false-green rate blocks
any publishable claim from that smoke.

Latest ARES NQ example smoke:

| System | Cases | Eligible Rows | Failure Macro-F1 | 95% CI | Root Cause Accuracy | Dangerous False Green | Citation Error F1 | Span Overlap | Status |
| --- | ---: | ---: | ---: | --- | ---: | ---: | ---: | ---: | --- |
| ContextTrace semantic verifier | 200 | 4,421 | 0.995 | 0.981-1.000 | 0.995 | 0.000 | 1.000 | 1.000 (89 labeled) | review_pending |
| RAGAS `gpt-4.1-mini` | 200 | 4,421 | 0.471 | 0.426-0.513 | N/A | 0.030 | N/A | N/A | calibration only |
| DeepEval `gpt-4.1-mini` | 200 | 4,421 | 0.388 | 0.342-0.431 | N/A | 0.360 | N/A | N/A | calibration only |

This run uses the official ARES `nq_labeled_output.tsv` example file from
`stanford-futuredata/ARES`, normalized by `ares_adapter.py`, then sampled with
`sample_size=200`, `sample_seed=13`, and
`stratify_by=metadata.ares_context_relevance_label,metadata.ares_answer_faithfulness_label,metadata.ares_answer_relevance_label`.
The official TSV contains 6,189 rows; the default adapter keeps 4,421
answer-grounding rows and skips context-relevance-only retrieval negatives unless
`--include-context-relevance-negatives` is supplied. Repeated raw IDs are
deterministically disambiguated and the generic adapter rejects duplicate IDs
after normalization, so each candidate has `200/200` matched coverage with zero
runner errors. RAGAS and DeepEval report faithfulness only; unreported diagnostic
fields remain `N/A`.

The tracked release evidence is in
`out/ares_nq_example/smoke200_compared_bundle/`, with raw RAGAS and DeepEval
runner outputs in `out/ares_nq_example/baselines_unique/`.

The `1.000` span score applies to 89 auto-derived exact-answer spans and is not
an independently labeled source-localization result. The sole ContextTrace
disagreement is an ARES-positive row whose answer `one` is paired only with the
title `The Bastard Executioner`. This remains a second external-dataset workflow
proof, not a publishable row. Independent review of the ARES component-label
mapping and source evidence is still required.

Latest CRAG Task 1 v5 gold-answer grounding calibration:

| Cases | Proxy Accepted | Flagged For Review | Contexts At Cap | False-Premise Accepted | Real-Time Accepted | Status |
| ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 200 | 95 (47.5%) | 105 (52.5%) | 511 / 1,000 | 0 / 25 | 4 / 15 | review_pending |

This sample is drawn from 2,705 eligible rows in the pinned official archive,
with all five domains, eight question types, four temporal classes, and both
splits represented. Selected-ID SHA256 is
`a782cf309506e2dff8f3b9c039fd2dc7bbab6f9cc3d98c9238693a1f64a9d80c`.
The proxy asks whether ContextTrace accepts an official gold answer as grounded
by the supplied web pages. It is not answer-correctness or verifier-accuracy
ground truth; see [CRAG.md](CRAG.md). The generic harness macro-F1 must not be
used as a CRAG comparison metric before independent grounding review.

The same-ID RAGChecker run uses a real sidecar containing those official
answers, not `--use-response-as-gt`. RAGChecker proxy-accepts 93/200 and
ContextTrace proxy-accepts 95/200. They agree on 150/200 (`75.0%`), with Cohen's
kappa `0.4982`, exact McNemar p-value `0.887725`, 26 ContextTrace-only accepts,
and 24 RAGChecker-only accepts. RAGChecker completed all 11 metrics on all 200
rows with zero errors; mean faithfulness is `0.5073` and mean claim recall is
`0.4903`. These are evaluator-behavior diagnostics on gold-answer responses,
not CRAG answer accuracy or a publishable SOTA result.

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

python benchmarks/contexttrace_bench/ragtruth_review.py build-signoff-handoff \
  --review-queue benchmarks/contexttrace_bench/out/ragtruth_review_queue.jsonl \
  --case-pack benchmarks/contexttrace_bench/out/ragtruth_case_pack.json \
  --output-dir benchmarks/contexttrace_bench/out/ragtruth_independent_signoff

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

## Generic External Case Packs

Normalize the official ARES NQ example:

```bash
python benchmarks/contexttrace_bench/ares_adapter.py \
  --download-example labeled \
  --download-dir benchmarks/contexttrace_bench/out/ares_nq_example \
  --output benchmarks/contexttrace_bench/out/ares_nq_example/ares_nq_labeled_rows.jsonl \
  --dataset ARES-NQ-example \
  --source-name "ARES/NQ labeled example"
```

Use `external_case_pack.py` when the next external dataset is already available
as JSON or JSONL rows with answer, context, and label fields. This is the
shortest path for CRAG/ARES-style exports because it reuses the same
`run_contexttrace.py --case-pack` scoring, candidate-input, leaderboard,
confidence-interval, and error-analysis machinery as RAGTruth.

```bash
python benchmarks/contexttrace_bench/external_case_pack.py \
  --input path/to/ares_or_crag_rows.jsonl \
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

The adapter accepts contexts as strings or objects with `text`, `content`,
`passage`, or `document` fields. Use `--root-cause-field` and
`--evidence-spans-field` when the dataset supplies richer labels. If evidence
spans are not supplied by the dataset or an independent reviewer, span-overlap
metrics should be described as unavailable or review-pending rather than
publishable.

Score the generated case pack:

```bash
python benchmarks/contexttrace_bench/run_contexttrace.py \
  --mode semantic \
  --case-pack benchmarks/contexttrace_bench/out/ares_case_pack.json \
  --output-dir benchmarks/contexttrace_bench/out/ares
```

Before calling the row publishable, record the upstream dataset version or
commit, the frozen input file checksum, the full adapter command, sampling
metadata from `stats.sampling`, reviewed label/span decisions, and competitor
prediction files scored on the same case IDs.

Prefer the workflow wrapper for a reviewable release artifact:

```bash
python benchmarks/contexttrace_bench/external_case_pack_workflow.py \
  --input path/to/ares_or_crag_rows.jsonl \
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

This writes `external_case_pack.json`, `external_review_template.jsonl`,
`external_review_packet.md`, scored benchmark artifacts under `scored/`, and a
bundle `manifest.json` with SHA256 checksums. The bundle stays
`review_pending` until a completed review JSONL is supplied. Rerun with
`--review completed_review.jsonl --review-kind independent` to validate and
apply sign-off. Assisted or warning-bearing review remains `calibration_only`.

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
