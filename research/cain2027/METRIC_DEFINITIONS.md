# ContextTrace CAIN 2027 metric definitions

Metric contract version: 1.0  
Status: Phase 1 definition; implementation to be frozen before evaluation  
Freeze date: 2026-07-24

Let \(G\) be adjudicated gold claims and \(P_s\) predictions from system \(s\)
after the frozen one-to-one claim alignment. Metrics are calculated on the
eligible population named for each metric. Report numerators, denominators, and
support counts with every aggregate.

## Classification metrics

### Per-class precision, recall, and F1

For class \(k\):

\[
P_k = \frac{TP_k}{TP_k + FP_k},\quad
R_k = \frac{TP_k}{TP_k + FN_k},\quad
F1_k = \frac{2 P_k R_k}{P_k + R_k}.
\]

When a denominator is zero, the corresponding value is undefined rather than
silently set to one. A class with gold support but no predictions has recall and
F1 zero. Zero-gold-support classes are `N/A`.

### Macro-F1

Unweighted mean of \(F1_k\) over predefined classes with gold support.
Failure-label macro-F1 uses the fixed failure taxonomy in `CLAIM_POLICY.md`.
Report the included class list and support for each class.

### Micro-F1

Compute precision and recall after summing TP, FP, and FN across eligible
classes. It is secondary because common labels can dominate it.

### Root-cause accuracy

Number of exact primary-root-cause matches divided by root-cause-eligible gold
claims. Gold `none` is excluded; `not_observable` is a valid class. A
schema-valid candidate abstention is incorrect for exact root-cause accuracy
but remains distinguishable from a forced wrong cause.

### Unverifiable F1

Binary F1 with gold claim verdict `unverifiable` as positive and every other
claim verdict as negative.

## Citation metrics

A citation error is positive when citation state is `partial`, `wrong_source`,
`missing`, or `malformed`. `correct` is negative and `not_applicable` is
excluded. Report precision, recall, F1, the six-way confusion matrix, and
resolvable-citation rate.

## Dangerous false-green metrics

Gold dangerous cases follow `CLAIM_POLICY.md`.

\[
\text{DFGR} =
\frac{\text{dangerous gold claims predicted green}}
     {\text{all dangerous gold claims}}.
\]

“Green” requires a schema-valid, non-abstained, unqualified positive output at
or above the frozen green threshold with no failure, citation, source-condition,
or insufficiency warning.

Trace-level DFGR is the fraction of traces containing at least one dangerous
false green among traces containing at least one dangerous gold claim.

Report the claim and trace numerators and denominators, plus false greens by
domain, track, route, and failure family.

## Abstention metrics

Gold-positive abstention is `must_abstain`. A predicted positive is a
schema-valid final abstention.

- abstention precision: required abstentions divided by predicted abstentions;
- abstention recall: predicted abstentions divided by required abstentions;
- abstention F1: harmonic mean;
- diagnostic coverage: eligible claims receiving a non-abstained prediction;
- unnecessary abstention rate: predicted abstentions among `must_answer`
  claims.

`may_answer_with_qualification` is reported separately and is not forced into
the binary primary abstention metric.

## Evidence-span metrics

### Character intersection-over-union

For source-matched predicted character set \(A\) and gold set \(B\):

\[
IoU = \frac{|A \cap B|}{|A \cup B|}.
\]

Wrong-source spans score zero. Multiple spans are combined after frozen
one-to-one maximum-overlap matching; unmatched spans contribute union mass.

### Token F1

Apply the frozen Unicode tokenizer to exact source substrings. Token precision
is overlapping predicted token mass divided by predicted token mass; recall is
overlapping token mass divided by gold token mass. Use multiset counts so
repeated tokens do not receive extra credit. The claim score is the harmonic
mean.

Report claim-macro, source-family-macro, exact-offset accuracy, and
wrong-source rate. Empty-gold-span claims are excluded and counted separately.

## Selective prediction metrics

### Risk and coverage

At threshold \(t\):

\[
\text{coverage}(t) =
\frac{\#\{\text{non-abstained predictions with score}\ge t\}}{N}
\]

and risk is the mean frozen 0/1 diagnostic loss over covered claims. Confidence
ties enter together.

### AURC

Area under the empirical risk-coverage curve using right-continuous step
integration over attainable coverage values. Lower is better. Do not
interpolate through tied-confidence blocks.

### Coverage at fixed error

Maximum attainable coverage whose empirical risk does not exceed 0.01, 0.02,
0.05, or 0.10. If no nonzero coverage meets a bound, report zero.

## Calibration metrics

These metrics apply only to confidence with a frozen probabilistic meaning.

### Brier score

\[
\text{Brier} = \frac{1}{N}\sum_i (p_i-y_i)^2,
\]

where \(y_i=1\) for a correct field-level diagnosis.

### Expected calibration error

Use 15 equal-mass confidence bins:

\[
\text{ECE} =
\sum_b \frac{n_b}{N}
\left|\operatorname{accuracy}(b)-\operatorname{confidence}(b)\right|.
\]

Report every bin; ECE alone may hide local miscalibration.

## Model-route metrics

- NLI invocation rate: claims routed to NLI divided by route-eligible claims.
- unresolved-disagreement rate: deterministic/NLI disagreements ending in
  abstention divided by claims evaluated by both routes.
- route failure rate: NLI runtime/schema failures divided by attempted NLI
  calls.
- model-call rate: local and remote model calls separately per claim and trace.

Cached calls count as invocations for routing but are reported separately for
latency/cost.

## Availability and validity

- prediction availability: schema-valid outputs divided by requested outputs;
- case completeness: cases with every required system output divided by frozen
  cases;
- invalid-output rate: schema-invalid outputs divided by requested outputs;
- timeout and provider-failure rates reported separately.

Unsupported baseline capabilities are excluded from availability denominators
only when declared `N/A` before execution.

## Operational metrics

- latency p50/p95/p99: empirical wall-clock quantiles for measured operations
  after fixed warm-up;
- capture overhead: paired elapsed time with capture enabled minus disabled,
  reported in milliseconds and percent;
- throughput: successfully completed operations divided by measured wall time;
- peak memory: maximum resident set size above the recorded pre-run baseline;
- storage: persisted bytes per trace and cumulative bytes;
- rejection rate: explicitly rejected operations divided by submitted
  operations;
- dropped-trace rate: silently or explicitly lost traces divided by submitted
  traces; silence is treated as a failure;
- truncation frequency: traces with any configured truncation divided by
  accepted traces;
- concurrency isolation failure: operations with cross-run state leakage,
  misattribution, or corrupted association divided by concurrent operations;
- queue saturation behavior: accepted, rejected, timed out, and completed
  counts at each offered load.

Hardware, software, model warm state, batch size, concurrency, payload tier, and
privacy/persistence mode accompany every result.

## Paired differences and uncertainty

For a metric \(M\), paired difference is:

\[
\Delta M = M(P_{\mathrm{v2}},G) - M(P_{\mathrm{v1}},G).
\]

For metrics where lower is better, tables explicitly reverse the improvement
direction rather than silently negating values. Confidence intervals follow the
hierarchical bootstrap in `STATISTICAL_ANALYSIS_PLAN.md`.

## Reporting contract

Every metric table includes:

- exact system, taxonomy, schema, and scorer versions;
- population and eligibility rule;
- numerator, denominator, class supports, and invalid count;
- point estimate and 95% interval;
- absolute paired difference when applicable;
- adjusted p-value only for confirmatory tests;
- `N/A`, insufficient-support, or unstable-interval flags;
- track/domain breakdown for headline endpoints.
