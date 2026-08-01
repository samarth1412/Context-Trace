# Verifier v2.1 development status

This document describes unreleased development work. It is not a release note,
and the stable ContextTrace verifier remains `semantic_v1_calibrated`.

## What changed

The opt-in `semantic_core_v2_1` profile keeps the v2 output schema while adding
two safety and accuracy policies:

1. A claim supported only by NLI after ambiguous deterministic evidence cannot
   become green. It remains supported-with-qualification.
2. Bounded evidence spans from the same source are recomposed in source order
   for NLI, with a bounded query cue. This preserves cross-sentence evidence and
   product/entity context without exposing the full trace.

The profile hash includes the guard, composition switches, and character
bounds. NLI continues to receive at most three selected spans, and the local
model artifact must match the existing model, revision, file hashes, and
manifest hash.

## Development-only results

On the visible 150-case public development holdout and 14 controlled safety
fixtures:

- controlled safety fixtures: 14/14;
- clean supported-answer detection: 97.26%;
- exact verdict-count match: 90.00%;
- selective NLI invocation rate: 24.57%;
- unresolved route rate: approximately 2%;
- p95 latency on the development machine: below 50 ms;
- dangerous false-green and dangerous safe-classification rates: 0%.

These numbers are for iterative engineering only. The cases and labels are
visible during development, so they are not untouched or confirmatory research
evidence.

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
