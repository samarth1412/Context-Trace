# Complete-support development study

## Decision

The complete-support branch did not meet its prespecified development gate and
stopped before held-out evaluation. No completeness policy should be added to
`JevJudge`, and no product default should change.

The final fresh 60-case development extension produced 10% supported recall,
90% partially-supported recall, zero partial-to-supported errors, 50% accuracy,
and 41.2% macro F1. The required supported recall was at least 50%. Although the
ranking AUC was 0.7567, the score distributions did not support a threshold that
was both safe and useful.

## Prespecified gate

The policy had to satisfy all four conditions on development validation before
any held-out pack could be created or queried:

- supported recall at least 50%;
- partially-supported recall at least 70%;
- partially-supported claims marked `supported` at most 5%;
- macro F1 above the base Jev verdict.

The initial pack contained 120 unused WiCE development claims, balanced 60/60,
with 80 cases for calibration and 40 for validation. After those validation
labels had been inspected, a new disjoint extension was frozen with 30 unused
claims per class. Its case-pack SHA-256 is
`50221d95206d3f477ad462cb1d8a7e2f9696a1d7d19cbf22878eb46b47afec7c`.
All 120 earlier cases were then treated as calibration and the fresh 60-case
extension was used for the final stopping decision.

## Inputs and privacy

Each Jev request contained only the claim and up to eight locally selected
evidence items. It did not contain the query, expected label, upstream label,
supporting-sentence annotations, case metadata, explanations, matched facts, or
generated evidence spans. Every request recorded the full typed probability
distributions, confidence, resolved model, latency, and token usage.

Jev remained explicitly remote and opt-in. `local_only` continued to reject
remote use, and the stable verifier and default provider were unchanged. The
MiniLM embedding baseline and fine-tuned classifier ran fully offline.

## Development results

| Variant | Validation set | Accuracy | Macro F1 | Supported recall | Partial recall | Partial→supported | Result |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| Base Jev, lexical selector | 40 | 62.5% | 56.4% | 25% | 100% | 0% | baseline |
| Typed Jev coverage gate | 40 | 65.0% | 60.1% | 30% | 100% | 0% | failed recall gate |
| Frozen-embedding fusion | 40 | 65.0% | 60.1% | 30% | 100% | 0% | failed recall gate |
| Fine-tuned MiniLM fusion | 40 | 62.5% | 58.1% | 30% | 95% | 5% | failed recall gate |
| Semantic selector + Jev | 40 | 62.5% | 58.1% | 30% | 95% | 5% | failed recall gate |
| Semantic selector + fine-tuned fusion | 40 | 60.0% | 54.4% | 25% | 95% | 5% | failed recall gate |
| Final sequential policy | fresh 60 | 50.0% | 41.2% | 10% | 90% | 0% | stopped |

The final fresh-extension base Jev result was 55.0% accuracy, 52.5% macro F1,
26.7% supported recall, 83.3% partial recall, and 6.67% partial-to-supported
errors. The safety-constrained gate reduced the error rate to zero by moving
supported predictions into `partially_supported`, lowering both accuracy and
supported recall.

## What the ablations show

The seven typed completeness judgments and the direct typed
`complete_support`/`partial_support` choice were directionally informative, but
Jev remained strongly conservative. On the first 40-case validation split it
called only 3/20 truly supported cases complete while rejecting all 20 partial
cases as incomplete.

The frozen MiniLM embedding classifier did not learn the task: five-fold
out-of-fold ROC AUC was 0.5395. Fine-tuning all six MiniLM layers also failed to
transfer, with a best internal WiCE-training validation ROC AUC of 0.5588. Its
fusion did not improve the external development gate.

Evidence selection explains part, but not all, of the problem. The lexical
selector retrieved a complete upstream supporting group for 9/20 supported
cases in the original validation partition. Label-blind MiniLM semantic ranking
raised this to 12/20 and raised the Jev-plus-feature ranking AUC from 0.7500 to
0.8075, but safe supported recall remained 30%.

The study made 420 development-only Jev requests across four planned
iterations and used 800,418 tokens. No held-out completeness request was made.

## Research implication

Complete support is not a threshold-calibration problem in the current design.
An explicit local atomic-coverage prototype was subsequently implemented: it
splits a claim into material requirements, retrieves evidence separately for
each requirement, and requires every local NLI alignment to pass before
returning `supported`. On the fresh 60-case extension it reached only 6.67%
supported recall and also missed the false-support cap. The architecture is now
available as a structured experimental scaffold, but the frozen generic NLI
model is not adequate for the task. `ATOMIC_COVERAGE_RESULTS.md` records the
full protocol and stopping decision.

The positive ambiguity gate remains valid and separate. This negative study
does not change its frozen policy or second-confirmation result.
