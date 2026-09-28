# V18 frozen confirmation candidate

V18 converts the V14–V17 development experiments into one reproducible
candidate that can be applied to a new confirmation set without fitting or
selecting anything on confirmation data.

## Why this freeze is required

V14 and V15 reported five-fold out-of-fold results. Those predictions support
development model selection, but the selected estimators had not been fitted
on all development cases or stored for later inference. Evaluating a newly
trained or modified implementation after seeing confirmation labels would
invalidate a one-shot confirmation.

V18 therefore freezes the selected configuration before accessing a new test
set:

- V14: `hist_leaves_3_minimum_10`, trained on all 125 development cases with
  the existing 54 relation, interaction, and lexical features;
- V15: `hist_minimum_5`, trained on the 50 supported and partially-supported
  development cases with the selected 93-feature completeness representation;
- V14 and V15 policy thresholds copied exactly from their committed reports;
  and
- the V17 rescue restricted to V14 `supported` routes with minimum single-span
  entailment of at least 0.70.

The V15 stacking model trains with V14's existing out-of-fold development
probabilities. At confirmation time it receives probabilities from the V14
model fitted on all development cases, following the standard cross-fitted
stacking pattern.

## Reproduce the freeze

```bash
PYTHONPATH=packages/contexttrace:. LOKY_MAX_CPU_COUNT=8 .venv/bin/python \
  -m benchmarks.requirement_alignment.freeze_v18_candidate \
  --development /private/tmp/contexttrace_external_data/v13_development.json \
  --relation-scores /private/tmp/contexttrace_external_data/v13_development_scores.json \
  --v14-report benchmarks/requirement_alignment/results/v14_fiveway_policy.json \
  --atomic-scores /private/tmp/contexttrace_external_data/v15_atomic_scores.json \
  --v15-report benchmarks/requirement_alignment/results/v15_atomic_completeness.json \
  --v17-report benchmarks/requirement_alignment/results/v17_multispan_completeness.json \
  --artifact-output /private/tmp/contexttrace_external_data/v18_frozen_candidate.joblib \
  --manifest-output benchmarks/requirement_alignment/results/v18_frozen_candidate_manifest.json
```

The trusted local artifact is 139,768 bytes with SHA-256
`bcc5f0d2e66edbb5a400c5c54bb59a31a39ac1a6ce02ff38602b5f0af6288009`.
An independent rebuild produced identical bytes. The binary remains in
external local storage; the repository commits its complete manifest and the
code needed to rebuild and verify it.

## Protocol boundary

The full-development fit is not an evaluation result. Its in-sample outputs
must not be reported as evidence of quality. The V17 out-of-fold development
result remains the only candidate-selection result.

At this freeze point, no new confirmation data, labels, or predictions have
been loaded. The next stage must build and hash a disjoint confirmation set,
run the frozen artifact once, and report the result without retraining,
threshold changes, case removal, or another selection pass.

The artifact is local-only, uses no remote inference, changes no stable
verifier behavior, and enables no provider by default.
