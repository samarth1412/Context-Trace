# External five-way confirmation results

## Verdict

Jev is a useful optional verifier, but this run does not justify promoting Jev
or the frozen cascade to an automatic default and does not support a SOTA claim.
Jev makes a statistically significant improvement over the stable verifier on
the frozen 125-case set. Its 53.6% five-way accuracy, 32% supported recall, 4%
unverifiable recall, and 12% false-support rate still leave large gaps.

The result preserves ContextTrace's product contract: the stable provider and
default behavior are unchanged, Jev remains explicitly opt-in and remote, and
`local_only` continues to block remote inference.

A subsequent development-only ambiguity study found a useful composition: a
local logistic meta-gate over one Jev verdict distribution and five typed Jev
ambiguity judgments. On a second, disjoint, frozen 35-case confirmation set,
the gate improved Jev from 45.7% to 57.1% accuracy and from 39.1% to 54.9%
macro F1. This is encouraging independent evidence, but the set has only seven
cases per verdict and the paired result is not statistically significant.

## Frozen design

- 125 public test cases, balanced at 25 per ContextTrace verdict.
- 125 unique normalized claims and no exact claim, case-ID, or normalized-input
  overlap with the prior Jev experiment packs.
- WiCE supplies `supported`, `partially_supported`, and `unsupported` cases;
  real-revision VitaminC cases supply `contradicted`; AmbiEnt pairs with two or
  more linguist-validated readings supply `unverifiable`.
- The case pack was frozen before any verifier ran. The freeze manifest SHA-256
  is `cc73e3909c00f05ff64b05c2bd9941bd283cb4443e7863133ab18c2738a66b78`.
- Every system received the same claim and label-blind selected evidence. No
  expected label, upstream label, diagnostic evidence annotation, or
  disambiguation was sent.

## Main results

| System | Five-way accuracy | Macro F1 | Supported recall | Unverifiable recall | False support |
| --- | ---: | ---: | ---: | ---: | ---: |
| Stable semantic | 33.6% | 30.6% | 16% | 8% | 17/100 (17%) |
| Local deterministic + pinned NLI | 14.4% | 10.2% | 8% | 4% | 15/100 (15%) |
| Jev 1.13.0 | 53.6% | 48.3% | 32% | 4% | 12/100 (12%) |
| Frozen stable + Jev cascade | 54.4% | 49.5% | 28% | — | 10/100 (10%) |

Jev's accuracy 95% Wilson interval is 44.9–62.1%; stable's is 25.9–42.3%.
The paired exact McNemar comparison has 33 Jev-only correct cases and 8
stable-only correct cases (`p = 0.000112`). Jev's gain is real on this sample.

The cascade changes only nine Jev decisions. It gains three cases and loses two,
so the 0.8-point accuracy increase is not significant (`p = 1.0`). Its 10%
false-support rate exceeds the 5% development safety constraint used when the
policy was selected. The external result therefore fails to confirm that frozen
cascade policy.

## What worked

- Jev improves contradiction recall from 24% to 68%.
- Jev improves partial-support recall from 28% to 84%.
- Jev retains useful unsupported performance: 20/25 correct, and it marks none
  of the 25 WiCE `unsupported` cases as `supported`.
- Jev improves overall five-way accuracy by 20 percentage points over stable.
- The remote run resolves to `jev-1.13.0`, with mean latency 231 ms (p50 221 ms,
  p95 333 ms) and 109,595 total tokens for 125 cases.

## What failed

Ambiguity is the clearest blocker. Jev predicts `unverifiable` for only one of
25 AmbiEnt examples. It incorrectly marks eight ambiguous cases as fully
supported, including several with high supported probability. Stable has the
same structural weakness and marks 14 ambiguous cases supported.

Complete support is the second blocker. Jev recognizes only 8/25 fully
supported WiCE claims and moves 17 into `partially_supported`. This conservative
bias helps avoid unsupported false positives, but it makes the five-way verdict
unreliable for positive claims.

Jev's 12 false-support errors consist of eight `unverifiable`, two
`contradicted`, and two `partially_supported` cases. There are zero
`unsupported` → `supported` errors. The frozen cascade reduces the total to ten
but still produces nine ambiguity-related false supports.

The pinned local NLI path does not transfer to this task. At 14.4% accuracy it
is worse than the stable verifier, so adding generic NLI alone is not the route
to SOTA-quality ContextTrace verification.

## Product and research decision

Keep `JevJudge` optional. It provides a meaningful quality lift, records typed
probabilities and operational metadata, and is useful for explicit remote
verification. Require review for every supported verdict and treat ambiguity as
a separate gate. Do not market the current verifier or cascade as SOTA.

The completed development track shows that independently thresholding holistic
or decomposed ambiguity judgments is ineffective. A learned combination of the
five ambiguity judgments and the base verdict probabilities is substantially
better. It is still a research policy and must not change the product default.

## Learned ambiguity follow-up

The follow-up used 125 upstream development cases: 75 for fitting and threshold
selection and 50 for validation. It made one typed Jev request per case. The
request contained only the claim and selected evidence and returned the
five-way verdict distribution plus lexical, reference, structural/scope,
pragmatic, and verdict-instability judgments. Evaluation labels were never
included in a request.

| Development-validation system | Accuracy | Macro F1 | Unverifiable recall | False support |
| --- | ---: | ---: | ---: | ---: |
| Jev base verdict | 52.0% | 45.7% | 0% | 3/40 (7.5%) |
| Independent threshold gate | 30.0% | 27.4% | 70% | 2/40 (5.0%) |
| Frozen learned meta-gate | 62.0% | 58.2% | 70% | 0/40 (0%) |

The logistic gate uses a fixed L2 model (`C=1`, balanced class weights) trained
on the 75 calibration cases. Its threshold of 0.60 was selected only on that
calibration partition under a 5% false-support constraint. The validation
ambiguity ROC AUC is 0.8975. The serialized policy ID is
`bfd4d056c919748265d41fddef44c5dc8ac54c4affa89e848409781350bc2163`.
Scoring is local and adds no remote request.

The second confirmation pack was frozen after excluding case IDs, normalized
claims, and normalized inputs from six prior experiment packs. It contains 35
cases, seven per verdict; the small size is forced by the seven unused WiCE
test `not_supported` cases. Its final freeze-manifest SHA-256 is
`5cecde4352707e4ac1252f5d570d736fec70fbc5c2da431d95e6ee871f4f4985`.

| Disjoint frozen system | Accuracy | Macro F1 | Supported recall | Unverifiable recall | False support |
| --- | ---: | ---: | ---: | ---: | ---: |
| Jev 1.13.0 base verdict | 45.7% | 39.1% | 14.3% | 0% | 2/28 (7.14%) |
| Frozen learned meta-gate | 57.1% | 54.9% | 14.3% | 57.1% | 1/28 (3.57%) |

The gate made six overrides. Four corrected AmbiEnt cases; two changed one
wrong non-ambiguous verdict into another wrong verdict; and it harmed no
previously correct prediction. The paired table is four gate-only correct and
zero Jev-only correct (`p = 0.125`, exact two-sided McNemar), so the direction
is positive but the set is too small for a significance claim. Neither system
marked an `unsupported` case as `supported`. The remaining false support is one
ambiguous case marked supported.

The confirmation run resolved to Jev 1.13.0, used 48,083 tokens, and had mean
latency 244 ms (p50 223 ms, p95 355 ms). The local meta-gate made no additional
remote calls. An initial execution stopped after one API response because of a
held-out metadata-field bug; it wrote no prediction row and no prediction was
inspected. `CONFIRMATION_V2_EXECUTION_LOG.md` records the incident and the new
freeze made before the successful run.

These results justify continuing the optional Jev research path and testing the
learned ambiguity gate on a larger independently labeled RAG corpus. They do
not justify a SOTA claim or enabling Jev by default. Fully supported recall
remains the largest quality problem: both systems identify only one of seven
supported claims in the second confirmation set.

## Complete-support follow-up

The next development study targeted that supported-recall failure with typed
coverage judgments, a direct complete-versus-partial choice, a frozen embedding
classifier, a task-fine-tuned local MiniLM model, and a semantic evidence
selector. None met the prespecified requirement of at least 50% supported
recall while keeping partial-to-supported errors at or below 5%.

On a fresh disjoint 60-case development extension, the final policy achieved
10% supported recall, 90% partial recall, 0% partial-to-supported errors, 50%
accuracy, and 41.2% macro F1. The branch therefore stopped without creating or
querying a held-out completeness pack. `COMPLETENESS_RESULTS.md` contains the
full protocol, ablations, privacy audit, and stopping decision.

## Local atomic-coverage follow-up

The next experiment implemented a reusable local requirement-coverage judge.
It decomposes claims, selects evidence separately for each requirement, and
records exact selected evidence plus the frozen NLI model's full three-way
probabilities. It is experimental, local-only, and absent from provider
selection and defaults.

The 120-case calibration cohort selected an entailment threshold of 0.15 under
the 5% false-support constraint. On the same fresh 60-case extension used only
for final validation, atomic coverage reached 50.0% accuracy, 38.4% macro F1,
6.67% supported recall, 93.33% partial recall, and 6.67% partial-to-supported
errors. It therefore failed both the supported-recall and false-support gates
and performed below base Jev. No held-out evaluation was opened.

This rules out generic local NLI thresholding as the next route to a quality
gain. The code remains a useful tracing and evaluation scaffold for training a
requirement-level alignment model. `ATOMIC_COVERAGE_RESULTS.md` contains the
complete result and error analysis.

A post-prediction audit then ran the same frozen NLI model on WiCE's annotated
gold evidence groups. Gold evidence raised the supported diagnostic pass rate
from 2/30 to 15/30. Among the 28 normal-path supported false negatives, 15
still failed with gold evidence, eight lacked a complete selected evidence
group, and five had the group available but routed it to the wrong requirement.
The audit also found and fixed five non-source decomposition outputs; every
requirement now retains exact claim provenance, without changing the negative
validation outcome. `ATOMIC_FAILURE_AUDIT.md` defines the resulting supervised
requirement-alignment training plan.
