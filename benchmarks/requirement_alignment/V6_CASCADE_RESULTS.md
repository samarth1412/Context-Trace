# V6 local-first uncertainty cascade results

## Decision

V6 validates a safe, low-remote-call uncertainty route, but it does not improve
over v3 on the separate evaluation partition. It remains a research result and
must not replace the stable verifier or change ContextTrace defaults.

The frozen optional-Jev cascade reaches **50.00% supported recall**, **0.00%
false-support rate**, **0.8333 accuracy**, and **0.7778 macro F1** on 90
evaluation cases. V3 alone at its existing 0.90 threshold reaches **53.33%
recall**, **0.00% false-support rate**, **0.8444 accuracy**, and **0.7956 macro
F1**. V6 therefore passes the absolute 50% recall and 5% FPR limits but fails
the predeclared non-regression requirement against v3.

## Isolated data

The builder selected two disjoint 90-case partitions from ContractNLI train,
each balanced across 30 entailments, 30 contradictions, and 30 not-mentioned
relations. Every selected claim-evidence pair is excluded from the 2,100
ContractNLI examples used to train v3 and v5. Calibration and evaluation IDs
are disjoint, and ContractNLI development and test were not accessed.

This is internal evidence rather than an untouched benchmark result. All 148
selected source documents overlap documents represented during training, and
the same 17 legal hypotheses recur. The split tests unseen pairs and a frozen
routing policy, not fully unseen documents or tasks.

## Frozen policy

The policy was selected from calibration only:

1. score the same selected evidence with v3 and v5 locally;
2. accept `supported` locally when both entailment probabilities are at least
   0.80;
3. accept `missing` locally when both probabilities are at most 0.50;
4. under `local_only`, abstain on every remaining case with zero network calls;
5. with explicit remote opt-in, route only those cases to one TypeSafe Jev
   five-way `Choice` judgment;
6. accept routed support only when Jev selects `supported` with supported
   probability at least 0.50;
7. require review for every supported result and every Jev result below 0.80
   confidence.

The exact content-hashed policy is in `results/v6_cascade_policy.json`. The
evaluation runner rejects Jev rows that do not exactly match the cases routed
by that frozen policy.

## Calibration and evaluation

| Split | System | Accuracy | Macro F1 | Supported recall | False-support rate | Jev calls |
|---|---|---:|---:|---:|---:|---:|
| Calibration | V3, threshold 0.90 | 0.8111 | 0.7403 | 0.4333 | 0.0000 | 0/90 |
| Calibration | Frozen cascade | **0.8556** | **0.8128** | **0.5667** | **0.0000** | 20/90 |
| Evaluation | V3, threshold 0.90 | **0.8444** | **0.7956** | **0.5333** | **0.0000** | 0/90 |
| Evaluation | V5, threshold 0.90 | 0.8000 | 0.7293 | 0.4333 | 0.0167 | 0/90 |
| Evaluation | Frozen cascade | 0.8333 | 0.7778 | 0.5000 | 0.0000 | **13/90** |

The calibration improvement did not transfer. On evaluation, the 13 routed
cases contain eight entailments and five not-mentioned cases. Jev recovers one
of the eight entailments, rejects seven, and correctly rejects all five
not-mentioned cases. The cascade produces no false support, but it loses one
supported case relative to v3 overall.

## Local-only behavior

| Split | Automatic coverage | Automatic accuracy | Automatic false support | Abstentions | Network calls |
|---|---:|---:|---:|---:|---:|
| Calibration | 0.7778 | 0.9143 | 0 | 20 | 0 |
| Evaluation | **0.8556** | **0.8961** | **0** | 13 | **0** |

This is the strongest product-relevant result from v6: model disagreement can
support an explicit abstention mode with useful coverage and no observed false
support. It does not justify packaging both large model artifacts as the
default local runtime, especially because v3 alone is more accurate on this
evaluation.

## Remote input and cost

Jev received only `claim` and the selected evidence IDs/text. Query, context
metadata, split, relation, and evaluation targets were absent. Every result
records the complete five-label distribution, confidence, resolved model,
latency, and token usage. Explanation and fact fields remain empty. All calls
resolved to `jev-1.13.0`.

The one-time all-case calibration run used 66,035 tokens over 90 calls. The
frozen policy would have routed 20 of those cases and used 14,937 tokens. The
separate evaluation made 13 calls, used 9,418 tokens, and measured 277.923 ms
mean and 388.445 ms p95 Jev latency. Local v3 and v5 scoring took 8.498 seconds
for the 90 evaluation cases on this CPU.

## Conclusion

V6 shows that v3/v5 disagreement is a useful abstention signal and that a
strictly optional Jev route can preserve zero observed false support with a
14.44% remote-call rate. It does not show a quality improvement over v3 in this
legal requirement task, so no `JevJudge` cascade should be promoted from this
result.

The next semantic experiment should change the verifier signal rather than
retune these thresholds. A reasonable candidate is a decomposed optional Jev
check for complete support, direct conflict, and evidence sufficiency, composed
in code and developed on a newly frozen set. The local-only branch should keep
the validated abstention behavior. ContractNLI test must remain reserved until
a candidate beats v3 on a separate development evaluation.
