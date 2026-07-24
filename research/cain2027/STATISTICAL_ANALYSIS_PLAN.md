# ContextTrace CAIN 2027 statistical analysis plan

Plan version: 1.0  
Status: internally frozen before data collection  
Freeze date: 2026-07-24  
Random seed: `20271030`

## Analysis populations

### Untouched eligible population

All cases in the hash-verified frozen manifest that pass pre-generation
eligibility and whose gold records pass the frozen annotation schema. Cases are
not excluded because of system behavior, label difficulty, or unfavorable
results.

### Track populations

- Natural OOD
- Temporal/source condition

Overall estimates are reported only when the endpoint has the same
interpretation in both tracks. Both track-specific estimates remain mandatory.

### Claim populations

- all adjudicated propositional claims;
- citation-eligible claims, excluding `not_applicable`;
- evidence-span-eligible claims with at least one adjudicated non-empty span;
- root-cause-eligible claims, excluding gold `none` but retaining
  `not_observable` as a class;
- selective-diagnosis claims with a frozen confidence value or abstention.

Population counts are reported before metrics.

## Estimands

The primary comparison estimand is the paired difference between
`semantic_core_v2` and `semantic_v1_calibrated` on identical eligible claims.
Absolute performance estimands describe `semantic_core_v2` on the frozen
untouched population.

The four confirmatory estimands are:

1. failure-label macro-F1 difference, v2 minus v1;
2. v2 root-cause accuracy;
3. v2 unverifiable-class F1;
4. v2 dangerous false-green rate.

Definitions are fixed in `METRIC_DEFINITIONS.md`.

## Clustering and resampling

Claims are nested in traces, traces in source documents or snapshot pairs, and
documents in source families. The source family is the primary independent
cluster. All nested observations remain bundled.

Confidence intervals use 10,000 hierarchical cluster-bootstrap replicates:

1. stratify by track and domain;
2. sample source families with replacement within each stratum;
3. retain all documents, traces, and claims belonging to each selected family;
4. preserve paired predictions from every system;
5. compute the endpoint and paired difference.

The default interval is the 2.5th and 97.5th percentile of valid replicates.
The number of invalid replicates, usually caused by absent rare classes, is
reported. If fewer than 9,500 replicates are valid, the interval is marked
unstable and the endpoint is inconclusive; no alternate interval is substituted
post hoc.

For latency, memory, and throughput, the resampling unit is the independently
repeated benchmark operation or run block as defined by the frozen operational
runner. Quantile intervals use a run-block bootstrap rather than treating
within-process timing samples as fully independent.

## Hypothesis tests

Where a paired endpoint admits system-label exchange, use a two-sided paired
cluster-randomization test:

1. compute the observed paired difference;
2. for each of 100,000 deterministic permutations, swap complete v1/v2 output
   bundles within source-family clusters with probability 0.5;
3. recompute the difference;
4. calculate the plus-one corrected two-sided p-value.

Absolute threshold hypotheses H2a, H4a, and H4b are evaluated primarily by
point estimate and 95% interval relative to their gates; they are not converted
into arbitrary null-hypothesis superiority tests. For multiplicity accounting,
their prespecified one-sample exact or cluster-bootstrap tail probabilities are
reported where meaningful.

The four confirmatory endpoint p-values form one family and receive Holm
correction at family-wise alpha 0.05. All other tests are secondary/exploratory
and are reported with unadjusted p-values plus effect sizes and intervals. No
claim of “statistical superiority” is based on an unadjusted secondary test.

## Gate interpretation

| Endpoint | Success gate | Strong support | Point-gate only | Does not support |
| --- | --- | --- | --- | --- |
| Failure macro-F1 delta | ≥ 0.15 | lower 95% CI > 0 and point ≥ 0.15 | point ≥ 0.15 but interval includes 0 | point < 0.15 |
| Root accuracy | ≥ 0.75 | lower 95% CI ≥ 0.75 | point ≥ 0.75 but lower CI < 0.75 | point < 0.75 |
| Unverifiable F1 | ≥ 0.60 | lower 95% CI ≥ 0.60 | point ≥ 0.60 but lower CI < 0.60 | point < 0.60 |
| Dangerous false green | ≤ 0.02 | upper 95% CI ≤ 0.02 | point ≤ 0.02 but upper CI > 0.02 | point > 0.02 |

The full confirmatory success claim requires all four point gates. “Strong
support” requires all four strong-support criteria plus no integrity failure.
Otherwise conclusions are endpoint-specific.

## Class support and rare outcomes

A confirmatory class needs at least 20 gold-positive claims across at least five
source families. Class counts may be computed by the custodian only after the
manifest is frozen and without disclosure to implementers.

- Zero-support classes are `N/A` and excluded from the macro average.
- Classes below the support rule remain in the fixed macro average when
  calculable, but their per-class interpretation is explicitly inconclusive.
- No class is merged, dropped, or redefined based on observed performance.
- If unverifiable lacks required support, H4a is inconclusive rather than
  replaced with a neighboring label.

## Missing and invalid system outputs

Every system has an availability endpoint. For primary diagnostic scoring:

- missing or schema-invalid predictions for a gold failure claim count as
  false negatives;
- missing predictions for a gold `none`/supported claim do not count as correct
  and enter an explicit `invalid_output` prediction category;
- an invalid output never counts as abstention unless the system emits a
  schema-valid abstention;
- timed-out operations retain their timeout latency and failure status;
- baseline fields that are structurally unsupported are `N/A`, not errors.

Primary paired comparisons use the union of cases for which the endpoint is a
declared capability of both systems, with invalid outputs scored
conservatively. A complete-case comparison is reported only as a sensitivity
analysis and cannot replace the primary result.

Gold records failing schema validation trigger an integrity review before
scoring. If correction exposes labels or changes outcomes after the test is run,
the original remains preserved and confirmatory status is reassessed under the
deviation policy.

## Confidence and calibration

Calibration metrics are computed only if the frozen system documentation gives
confidence a probabilistic interpretation. Otherwise confidence is treated as a
ranking score and only risk-coverage analysis is reported.

When probabilistic:

- Brier score uses the binary correctness target defined per output field;
- ECE uses 15 equal-mass bins fixed before evaluation;
- bin boundaries are computed from candidate confidence ranks without labels;
- each bin reports count, mean confidence, empirical accuracy, and a
  cluster-bootstrap interval;
- adaptive relabeling or post-hoc temperature scaling on untouched data is
  prohibited.

## Selective-risk analysis

Risk is diagnostic error under the field-specific 0/1 loss; coverage is the
fraction receiving a non-abstained prediction at or above a threshold.
Thresholds are swept over the frozen confidence ranking only to draw the curve,
not to choose a deployment threshold.

Report:

- AURC;
- coverage at error thresholds 0.01, 0.02, 0.05, and 0.10;
- risk at coverage 0.50, 0.60, 0.70, 0.80, and 0.90;
- the operating point from the frozen implementation;
- results for v2 and the forced-classification ablation.

If confidence ties occur, tied claims enter coverage together. Linear
interpolation across ties is prohibited.

## Evidence localization

Compute token F1 and character IoU per eligible claim, then macro-average over
claims and source families. Tokens are Unicode word/punctuation tokens produced
by the frozen scorer. Multiple predicted and gold spans are compared using
maximum-weight one-to-one matching; unmatched span mass contributes zero.

Source identifiers must match before textual overlap receives credit. A span in
the wrong source scores zero even if its text is duplicated. Both exact-offset
and overlap results are reported.

## Prespecified subgroup analyses

Report descriptive estimates and cluster-bootstrap intervals by:

- track;
- three top-level domains;
- retrieval family: lexical, dense, hybrid;
- reranking enabled/disabled;
- generator model/family;
- chunk-size band;
- answer-length band;
- citation format;
- source-condition category;
- claim verdict and failure family;
- deterministic versus NLI-routed claims;
- trace-size tier.

A subgroup needs at least 30 claims, five source families, and both outcome
classes for binary metrics. Otherwise counts are shown and the estimate is
marked insufficient. Subgroup analyses are not confirmatory and must not be used
to rescue failed overall hypotheses.

## Sensitivity analyses

Prespecified sensitivity analyses:

- trace-level instead of claim-level dangerous false-green rate;
- exact claim-boundary matches only;
- single-annotation versus double-annotation/adjudicated subset;
- excluding `not_observable` from root-cause macro-F1 while retaining it in
  accuracy reporting;
- Natural OOD only;
- temporal/source condition only;
- complete-case system outputs;
- source-family macro-average rather than pooled claims;
- alternative confidence interpretation omitted when confidence is not
  probabilistic.

These remain secondary and cannot redefine primary conclusions.

## Agreement analysis boundary

Human inter-annotator agreement belongs to Phase 3 but its reporting rules are
prespecified:

- claim boundaries: exact match and overlap F1;
- categorical fields: raw agreement, class prevalence, Cohen’s kappa for two
  annotators, and Krippendorff’s alpha when assignment is incomplete;
- evidence spans: token F1 and character IoU;
- every field reported separately;
- adjudicated labels never substituted into pre-adjudication agreement.

No combined kappa is permitted.

## Operational analysis

For each frozen workload/configuration report:

- p50, p95, p99 latency with run-block bootstrap intervals;
- throughput and completed/rejected/dropped counts;
- peak resident memory and CPU time where supported;
- stored bytes per trace and cumulative storage growth;
- truncation, timeout, persistence, isolation, and privacy-test failures;
- queue depth and behavior at saturation;
- NLI invocation and model-failure rates.

Warm-up samples are excluded by rule. Failed measured operations remain in
reliability denominators. Hardware and software strata are not pooled unless
the execution environment is identical.

## Failure analysis and researcher degrees of freedom

The error-review sample is defined in `EXPERIMENT_PROTOCOL.md`. Error review
begins only after metrics and tables are immutable. Review notes can explain
failure modes but cannot modify gold, predictions, eligibility, hypotheses, or
the metric implementation.

Unexpected analyses are labeled post hoc with an explicit rationale. They do
not appear in abstracts or contribution lists as preregistered evidence.

## Negative, null, and inconclusive findings

- A missed point gate is reported as not supporting that hypothesis.
- A point gate met with an interval crossing the relevant boundary is reported
  as point-gate support with material uncertainty.
- Too little class or cluster support is inconclusive, never a pass.
- An unavailable baseline is an availability limitation, never evidence of
  superiority.
- Mixed domain outcomes are reported without averaging away a safety-critical
  regression.
- A higher macro-F1 accompanied by a false-green regression is not described as
  safer or better overall.
- RQ5 is omitted if approvals or real participants are unavailable.

All denominators, exclusions, invalid outputs, and deviations appear in the
paper artifact.

## Reproducibility requirements

The scoring package must have unit tests for:

- every confusion-matrix mapping;
- macro-F1 with absent and rare classes;
- dangerous false-green edge cases;
- abstention and invalid-output handling;
- claim alignment;
- multi-span matching;
- cluster bootstrap determinism;
- Holm correction;
- risk-coverage ties and AURC;
- subgroup sufficiency;
- paired baseline identity and case-order invariance.

The final metric output records the scorer source hash, configuration hash,
random seed, manifest hash, gold hash, prediction hashes, Python/runtime
versions, and command line.
