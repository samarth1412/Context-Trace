# V22 domain-diverse candidate

**V25 qualification:** [the input audit](V25_INPUT_AND_REPRESENTATION_RESULTS.md)
found question/answer fragmentation and inherited-label alignment risks. These
results remain reproducible but do not establish that the relation features
alone caused the failure.

V22 tests whether the existing local relation, atomic-completeness, and
multi-span signals can learn the five ContextTrace verdicts on the balanced
500-case V21 development set. It uses five-fold stratified out-of-fold
predictions and searches twelve deterministic classifier configurations. The
policy search uses development data only.

## Result

| Metric | Direct classifier | Selected safety policy |
|---|---:|---:|
| Accuracy | 41.4% | 41.2% |
| Macro-F1 | 0.4104 | 0.3668 |
| Supported recall | 32.0% | 0.0% |
| False-support rate | 16.0% | 0.0% |
| Partial/ambiguous review recall | — | 73.5% |
| Review rate | — | 49.6% |

No candidate passes all five promotion gates. The selected safe policy avoids
false support by declining every supported claim, and it also misses the 80%
review-recall floor. V22 is therefore rejected.

This is a useful failure: the old relation signals remain too entangled across
supported, contradicted, unsupported, and unverifiable examples for a policy
threshold to recover safe support. Stable verifier behavior is unchanged.

The machine-readable result is
[`results/v22_domain_candidate.json`](results/v22_domain_candidate.json). It
contains case identifiers, probabilities, predictions, metrics, and hashes,
without raw claim or evidence text.

## Reproduce

```bash
PYTHONPATH=packages/contexttrace:. .venv/bin/python \
  -m benchmarks.requirement_alignment.v22_domain_candidate \
  --development /private/tmp/contexttrace_external_data/v21_development.json \
  --relation-scores /private/tmp/contexttrace_external_data/v21_relation_scores.json \
  --atomic-scores /private/tmp/contexttrace_external_data/v21_atomic_scores.json \
  --multispan-scores /private/tmp/contexttrace_external_data/v21_multispan_scores.json \
  --output benchmarks/requirement_alignment/results/v22_domain_candidate.json
```
