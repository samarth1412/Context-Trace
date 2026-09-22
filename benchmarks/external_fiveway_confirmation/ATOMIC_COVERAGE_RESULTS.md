# Experimental local atomic-coverage study

## Decision

The local atomic-coverage prototype did not meet its prespecified development
gate. It must remain experimental and must not be wired into provider
selection, product defaults, or a held-out evaluation.

At the threshold selected on 120 calibration cases, the fresh disjoint 60-case
development extension produced 50.0% accuracy, 38.4% macro F1, 6.67% supported
recall, 93.33% partially-supported recall, and a 6.67% partial-to-supported
error rate. The gate required at least 50% supported recall, at least 70%
partial recall, and at most 5% partial-to-supported errors.

## Implementation and protocol

`AtomicCoverageJudge` is a reusable, explicitly experimental local verifier.
It decomposes a claim into deterministic claim substrings, performs label-blind
local evidence selection for each requirement, runs the frozen local NLI model
on only those selected spans, and records each exact requirement, evidence ID,
evidence text, and three-way NLI distribution. Its aggregate result requires
every requirement to pass before returning `supported`.

The verifier accepts only a local NLI provider and records `local_only: true`
and `remote_inference: false`. It does not make a TypeSafe/Jev call, download a
model, or use evaluation labels during inference. The stable verifier, provider
selection, and default behavior are unchanged.

The experiment used the earlier 120-case WiCE development pack only for
threshold selection. The 60-case extension, frozen with SHA-256
`50221d95206d3f477ad462cb1d8a7e2f9696a1d7d19cbf22878eb46b47afec7c`,
was kept as the final validation cohort. No held-out pack was created or
queried.

## Results

| System | Cohort | Accuracy | Macro F1 | Supported recall | Partial recall | Partial→supported |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Atomic coverage, threshold 0.15 | calibration 120 | 61.67% | 56.87% | 28.33% | 95.0% | 5.0% |
| Base Jev | fresh validation 60 | 55.0% | 52.47% | 26.67% | 83.33% | 6.67% |
| Atomic coverage, threshold 0.15 | fresh validation 60 | 50.0% | 38.44% | 6.67% | 93.33% | 6.67% |

The atomic system disagreed with base Jev on 14 of 60 validation cases. It was
correct on five disagreements and Jev was correct on eight; the remaining
disagreement was wrong for both. The two partial claims incorrectly accepted
as supported were `wice_dev02670` and `wice_dev02905`. The extension contained
no `unsupported` class because this study specifically tests complete versus
partial support.

The local verifier's mean latency on the fresh extension was 71.0 ms per claim
(median 56.6 ms, maximum 329.6 ms). It created one requirement for 39 cases,
two for 18 cases, and three for three cases.

## Interpretation

The architecture exposes the missing-coverage state that the earlier holistic
approaches lacked, but generic NLI scores do not separate complete from partial
support on unseen claims. Calibration chose a very low 0.15 entailment
threshold and still recovered only two of 30 fully supported validation claims.
Adding the atomic NLI summaries to the prior Jev signal model also reduced the
fresh-extension ranking ROC AUC from 0.7567 to 0.6833 in the development probe.

This result rules out thresholding the current frozen NLI model as the next
quality improvement. A credible next experiment needs supervision at the
claim-requirement/evidence alignment level: a trained requirement
representation, group-aware retrieval, and an NLI or reranker trained on
complete-versus-missing requirement pairs. The current prototype is useful as
the evaluation and tracing scaffold for that work.

The subsequent gold-evidence audit confirms this diagnosis. Of 28 supported
false negatives, 15 still failed with a complete gold evidence group, eight
were retrieval misses, and five routed available evidence to the wrong
requirement. `ATOMIC_FAILURE_AUDIT.md` contains the training-data specification
and exact failure cohorts.
