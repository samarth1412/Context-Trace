# V20 transfer-failure audit

V20 diagnoses the failed V19 confirmation run using the now-consumed V19 data.
It does not train a model, select a threshold, change a policy, or create new
confirmation evidence. The committed artifact contains hashes, identifiers,
probabilities, and derived signals without claim or evidence text.

## Findings

The failure is distributed across the learned relation, verdict, and
completeness layers rather than being caused mainly by the V17 rescue.

| Finding | Result |
|---|---:|
| False supports | 22 |
| False supports produced by V15 | 21 |
| V15 false supports with completeness probability at least 0.8 | 21 |
| False supports produced by the V17 rescue | 1 |
| Correct contradictions | 5 of 25 |
| Contradictions incorrectly supported | 7 |
| `unverifiable` predictions | 0 |
| Mean V14 `unverifiable` probability | 0.0043 |

The false supports comprise seven contradicted, seven unverifiable, four
unsupported, and four partially supported cases. Four false supports have a
visible relation contradiction probability of at least 0.5. This shows that
the completeness layer can override a strong conflict signal.

Three cases contain at least one decomposed requirement for which the local
selector found no span, and all three are errors. This is a real
evidence/decomposition risk, but it is too small to explain the overall 96
errors.

## Threshold diagnostic

V20 tests a post-hoc contradiction cap only to determine whether a simple guard
could repair V19. No tested cap passes all five gates. The best cap satisfying
the 5% false-support limit and zero contradiction false supports reaches only
12% support recall. It is not a selected policy.

The result rules out another threshold-only iteration. The next candidate needs
domain-diverse learning for contradictions, insufficient evidence, and mixed
evidence, plus an explicit cross-span conflict guard.

## Jev boundary

Existing Jev evidence remains useful but does not establish a V19 solution. On
the separate 72-case RAGTruth sentence extension held-out set, Jev 1.13.0
reached 75% accuracy and 0.7668 macro-F1 over the three observed labels, with
an 8.33% false-support rate. The frozen cascade reduced false supports to 2.08%
and reached 79.17% support recall, but made a remote call for 95.83% of cases.

Those results use another dataset and label scope. They support continued
evaluation of Jev as an optional review-path signal; they do not justify making
it the default or treating it as a substitute for local quality.

## Decision

Do not tune the V18 thresholds or release the candidate. Build a new local
development candidate from data disjoint from any future confirmation source.
The candidate must preserve the existing privacy and safety boundary: remote
providers remain explicit opt-ins, and `local_only` makes zero network calls.

The machine-readable audit is
[`results/v20_transfer_failure_audit.json`](results/v20_transfer_failure_audit.json).

## Reproduce

```bash
PYTHONPATH=packages/contexttrace:. .venv/bin/python \
  -m benchmarks.requirement_alignment.v20_transfer_failure_audit \
  --dataset /private/tmp/contexttrace_external_data/v19_confirmation.json \
  --relation-scores /private/tmp/contexttrace_external_data/v19_relation_scores.json \
  --atomic-scores /private/tmp/contexttrace_external_data/v19_atomic_scores.json \
  --multispan-scores /private/tmp/contexttrace_external_data/v19_multispan_scores.json \
  --confirmation-result benchmarks/requirement_alignment/results/v19_confirmation_result.json \
  --output benchmarks/requirement_alignment/results/v20_transfer_failure_audit.json
```
