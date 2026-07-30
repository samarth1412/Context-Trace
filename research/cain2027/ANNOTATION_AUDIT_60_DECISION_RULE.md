# ContextTrace 60-case annotation-audit decision rule

Frozen before independent annotations exist: 2026-07-30

This is a recovery decision after the invalid LLM-first gold was disclosed. It
is not a preregistered confirmatory hypothesis and cannot restore untouched
status.

## Required integrity

The audit is usable only if:

- Pul and Sid both complete all 60 production cases;
- both sign the annotation attestation;
- neither uses an LLM, system predictions, Phase 6 results, web search, or the
  other submission before both originals are hashed;
- both original submissions are preserved;
- field-level agreement is reported before consensus;
- every disagreement is resolved by Pul/Sid consensus or marked unresolved;
- no implementation or threshold change occurs before audit scoring.

## Go/no-go rule

Collect a new untouched corpus only if the frozen `semantic_core_v2` reaches
all four feasibility points against the consensus labels:

| Endpoint | Feasibility point |
| --- | ---: |
| Failure-label macro-F1 improvement over frozen v1 | at least +0.10 |
| Root-cause accuracy | at least 0.60 |
| Unverifiable F1 | at least 0.40 |
| Dangerous false-green rate | at most 0.05 |

Also report each domain and the temporal subset. A domain dangerous
false-green rate above 0.10 blocks a safety claim even if pooled results meet
the points.

These thresholds decide whether another expensive untouched collection is
worthwhile. They are not paper success gates and do not replace the original
frozen gates.

## Outcomes

- If every feasibility point is met: acquire a genuinely new untouched corpus,
  freeze it before candidate execution, and use independent annotation
  from the start.
- If any point is missed: do not collect another test corpus yet. Diagnose and
  improve only on a separate development corpus, then freeze a new verifier
  version before new evaluation.
- Regardless of outcome: never tune using these 60 audit cases or their
  case-level errors.
