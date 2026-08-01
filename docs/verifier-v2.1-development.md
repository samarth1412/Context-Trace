# Verifier v2.1 development status

This document describes unreleased development work. It is not a release note,
and the stable ContextTrace verifier remains `semantic_v1_calibrated`.

## What changed

The opt-in `semantic_core_v2_1` profile keeps the v2 output schema while adding
six safety and accuracy policies:

1. A claim supported only by NLI after ambiguous deterministic evidence cannot
   become green. It remains supported-with-qualification.
2. Bounded evidence spans from the same source are recomposed in source order
   for NLI, with a bounded query cue. This preserves cross-sentence evidence and
   product/entity context without exposing the full trace.
3. Conservative atomic claim unitization separates coordinated facts only when
   both sides are independently verifiable, preserves exact answer offsets, and
   reconstructs shared subjects only from observable answer text. Frozen v2
   unitization remains unchanged.
4. A dedicated observable-conflict checker prevents generic NLI entailment from
   overriding explicit number, date, version, negation, identifier, path, status,
   relation, condition, scope, and boundary conflicts. It changes only accepted
   support decisions and records every intervention in the NLI provenance.
5. A hash-locked logistic support-risk gate calibrates accepted NLI decisions
   from NLI probabilities and observable conflict signals. It can reject or
   abstain only when a contradiction or omission signal is present; otherwise it
   records risk without changing the base verdict. The deterministic conflict
   checker remains the final safety fallback.
6. A relational source-condition reasoner gives hazardous observables precedence
   over inconsistent safe labels, parses typed boolean metadata, follows
   replacement links, compares versions and publication times only within a
   declared source lineage, and detects conflicts between authoritative sources.
   It emits bounded related-source provenance without copying source text.

The profile hash includes all safety guards, composition switches, the
source-condition reasoner switch, atomic-unitization switch, and character bounds. NLI continues to receive at
most three selected spans, and the local model artifact must match the existing
model, revision, file hashes, and manifest hash.

## Development-only results

On the visible 150-case public development holdout and 14 controlled safety
fixtures:

- controlled safety fixtures: 14/14;
- clean supported-answer detection: 97.26%;
- exact verdict-count match: 90.00%;
- selective NLI invocation rate: 23.89%;
- unresolved route rate: approximately 2%;
- p95 latency on the development machine: below 50 ms;
- dangerous false-green and dangerous safe-classification rates: 0%.

These numbers are for iterative engineering only. The cases and labels are
visible during development, so they are not untouched or confirmatory research
evidence.

The separate 24-pair synthetic hard-negative pack exposes three accepted false
entailments from generic NLI: scope omission, a numeric boundary error, and a
temporal boundary error. The dedicated conflict checker reduces accepted false
entailment from 25% to 0% on the 12 negative controls while retaining 100%
positive recall. This small synthetic result validates the mechanism only; it
is not evidence of generalization or SOTA performance.

The learned risk gate uses a generated 144-case development corpus with 96
training, 24 validation, and 24 held-out-development cases. Source families are
disjoint across the three splits, and all 12 mutation categories occur in each
split. On the held-out-development split, the pinned generic NLI baseline has
91.67% accuracy, 16.67% false entailment, 0.0796 ECE, and 0.0359 AURC. The
learned gate has 100% accuracy, 0% false entailment, 0.0176 ECE, and 0 AURC on
that small synthetic split. An earlier lexical-feature design was rejected
because it reduced clean-support performance; the packaged model uses only NLI
probabilities and observable signals. These are synthetic development metrics,
not external or untouched evidence.

A separate 54-case source-condition pack covers current canonical, current
noncanonical, stale, superseded, low-authority, conflicting-authority, and
unknown cases. Its 18-case held-out-development split uses disjoint source
families. On that templated split, frozen v2 has 0.1048 macro-F1 and a 42.86%
dangerous false-green rate; v2.1 has 1.0 macro-F1 and 0% dangerous false greens.
The perfect candidate score reflects direct coverage of the declared metadata
and relation rules. It is a regression result, not evidence of external
generalization.

## Opt-in CLI

Deterministic verification makes no model call:

```bash
contexttrace verify-v2 trace.json --profile deterministic --json
```

Selective verification requires the exact local pinned artifact:

```bash
contexttrace verify-v2 trace.json \
  --profile selective \
  --model-path /private/models/nli-deberta-v3-small \
  --output prediction-v2.json
```

`CONTEXTTRACE_NLI_MODEL_PATH` may replace `--model-path`. ContextTrace never
downloads the model automatically.

## Non-release boundary

This work does not change the package version, stable v1 CLI behavior, default
profile, schemas used by v1 traces, PyPI/TestPyPI state, tags, or GitHub release
state. Those decisions are intentionally deferred to the larger release plan.
