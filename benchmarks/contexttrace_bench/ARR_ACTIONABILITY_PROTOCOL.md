# ARR Diagnosis-Actionability Protocol

Status: preregistered implementation protocol for RQ4. This study is separate
from blinded ground-truth annotation.

## Question And Contrast

RQ4 asks whether evidence-chain diagnoses help humans identify a concrete repair.
The paired contrast holds the trace, semantic matcher, and claim-verdict logic
constant:

- `evidence_chain`: full ContextTrace output with evidence spans, citation state,
  abstention, source assessment, root cause, reasons, and suggested fixes.
- `semantic_core`: claim verdicts and aggregate support scores with diagnostic
  modules disabled.

This is an ablation-based human study, not a comparison against a named external
product. It isolates the value of diagnostic structure from evaluator accuracy.

## Sampling And Blinding

The full study uses 40 deterministically sampled failure cases, stratified by
expected primary root cause. No-failure cases are excluded because there is no
repair decision to evaluate. A quick packet uses 12 cases only to validate the
harness and is never a paper result.

Cases are shuffled and assigned opaque `ACT-*` IDs. Outputs are named only
`option_1` and `option_2`. Evidence-chain placement alternates with a randomized
starting side, so option-order counts differ by at most one. The condition map,
original IDs, and expected labels remain only in the private key.

Content necessarily reveals that one output is richer. The study is therefore
condition-label blinded, not presentation-form blinded. This limitation must be
reported.

## Review Task

Reviewers inspect the query, answer, contexts, and both outputs. For each option
they record:

- `diagnosis_correct`: whether the output's assessment is supported by the trace.
- `repair_actionable`: whether it enables a concrete next engineering action.
- `repair_specificity`: 1 (generic) through 5 (specific and implementable).
- `evidence_sufficiency`: 1 (insufficient) through 5 (enough to verify the diagnosis).

They then choose `option_1`, `option_2`, `tie`, or `neither` as more useful for
repair, record total decision time in seconds, confidence from 1 through 5, and
an optional rationale. Reviewers must not access the private key or expected
labels.

## Review Target

Use at least three non-author reviewers for all 40 cases. Record reviewer role
and relevant RAG/debugging experience outside the anonymous response file. An
author pilot may use `review_kind=pilot_author`, but author ratings are excluded
from independent-result claims.

## Outcomes

The preregistered primary outcome is the evidence-chain preference rate among
decisive choices, with a 95% Wilson interval and two-sided exact binomial test
against 0.5. Report ties and neither choices separately.

Secondary outcomes are paired deltas for diagnosis correctness, repair
actionability, repair specificity, and evidence sufficiency. Report deterministic
case-bootstrap 95% intervals for each delta, option-order breakdowns, per-reviewer
results, and raw inter-reviewer preference agreement. Do not remove disagreements
or low-confidence cases after viewing results.

The unit of inference is the reviewer-case judgment. Because repeated judgments
from the same reviewer and case are not statistically independent, pooled results
are descriptive; paper claims should emphasize per-reviewer effects and use a
mixed-effects analysis if inferential claims go beyond the preregistered exact
preference test.

## Commands

Build a non-paper quick packet:

```bash
python benchmarks/contexttrace_bench/arr_actionability.py build \
  --quick \
  --case-set public_holdout \
  --output-dir benchmarks/contexttrace_bench/out/arr_actionability_quick
```

Score completed reviewer packets:

```bash
python benchmarks/contexttrace_bench/arr_actionability.py score \
  --key benchmarks/contexttrace_bench/out/arr_actionability/condition_key.private.json \
  --responses reviewer_a.json reviewer_b.json reviewer_c.json \
  --output-dir benchmarks/contexttrace_bench/out/arr_actionability/scored
```

Send only `actionability_packet.json` to reviewers. Never send
`condition_key.private.json`.
