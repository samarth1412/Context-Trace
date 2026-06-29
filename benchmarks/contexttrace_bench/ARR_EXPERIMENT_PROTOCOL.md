# ARR Experiment Protocol

Status: frozen on 2026-06-29 for the ARR August 2026 cycle.

Target submission date: 2026-08-03. The target is an eight-page long paper,
excluding the required limitations section and references.

## Research Claim

ContextTrace is a benchmarked, local-first evidence-chain forensics system for
claim-level RAG and agent failure diagnosis. The paper must not call ContextTrace
state of the art unless every evidence gate in `SOTA_STATUS.json` passes with
independent external evidence.

The machine-readable protocol is `ARR_EXPERIMENTS.json`. A protocol change after
the freeze date requires a dated changelog entry stating the reason and whether
the change was made before or after inspecting affected results.

## Research Questions

- RQ1: How accurately does ContextTrace detect claim-level RAG failures on
  externally sourced and public-document cases?
- RQ2: How accurately does it localize evidence spans, citation failures, and
  primary root causes?
- RQ3: Which stages contribute to diagnostic quality, latency, and coverage?
- RQ4: Are the resulting diagnoses correct and actionable to blinded humans?

RQ4 actionability is a separate system-output study. Ground-truth annotators do
not see ContextTrace predictions and are not asked to assess actionability.

## Evaluation Units

The primary evaluation unit is one query, answer, context set, and citation set.
Claim-level predictions are aggregated within a case before case-bootstrap
confidence intervals are calculated. Generated variants from ContextTrace-Bench
are engineering regression evidence, not independent validation data.

Dataset roles are fixed as follows:

| Dataset | Cases | Role |
| --- | ---: | --- |
| RAGTruth | 200 target | Primary external calibration; independent review pending |
| ContextTrace-Diag-150 | 150 | Primary public-document holdout; independent review pending |
| ARES | 200 target | Secondary calibration |
| CRAG | 200 target | Secondary grounding calibration |
| ContextTrace-Bench | 500 target | Engineering regression only |

No case may move from tuning or author calibration into an independent test
claim. Dataset versions, source hashes, selected IDs, and exclusion counts must
be recorded with each paper run.

## Frozen Ablations

All profiles run on identical ordered case IDs with the same bootstrap seed.
They are cumulative so each row has one interpretable addition.

| ID | Profile | Mode | Citations | Abstention | Root cause | Spans | Source state |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |
| A0 | Lexical core | lexical | off | off | off | off | off |
| A1 | + semantic matching | semantic | off | off | off | off | off |
| A2 | + citation alignment | semantic | on | off | off | off | off |
| A3 | + abstention and root cause | semantic | on | on | on | off | off |
| A4 | + evidence-span localization | semantic | on | on | on | on | off |
| A5 | Full ContextTrace | semantic | on | on | on | on | on |

NLI and judge modes are sensitivity studies, not replacements for the frozen
main ablation table.

## Metrics And Statistics

Failure-label macro-F1, claim-verdict macro-F1, dangerous false-green rate, and
latency are reported for every profile. Citation F1, root-cause accuracy, and
evidence-span overlap are reported only when that profile generates the relevant
output. Unsupported metrics are `N/A`; they are never copied from another row.

Paper runs use 400 deterministic paired case-bootstrap resamples and report 95%
confidence intervals, absolute effects, case counts, output coverage, p50/p95
latency, and cost assumptions. Quick runs use 50 resamples only to validate the
harness and are never paper results. Conclusions must account for interval width,
not only point estimates.

## Exclusions And Leakage

- Exclusions must be specified before a paper run and reported by reason.
- Labels, original IDs, benchmark notes, and predictions are absent from blinded
  annotation packets.
- The private annotation key is never sent to a reviewer.
- Prompt, threshold, or label changes after result inspection require a new
  experiment ID and cannot silently replace the frozen run.
- Author-only review is calibration evidence and is described as such.

## Claim Gates

A paper result requires a non-quick run, frozen case IDs, recorded commit and
environment, complete output artifacts, and the review status appropriate to the
claim. Broad superiority language additionally requires matched published
baselines and independent review. Until then, report scoped empirical findings.
