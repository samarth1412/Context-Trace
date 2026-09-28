# V24 explicit support-risk heads

V24 tests the next hypothesis from V23: a five-way classifier may be the wrong
objective for the high-cost `supported` decision. It trains three separate
binary heads for support, contradiction risk, and review risk on the same V21
features and five out-of-fold splits. The rejected V23 classifier supplies
only the routing probabilities for non-support verdicts.

## Result

The selected `logistic_c_0.03` policy has:

| Metric | Result | Gate |
|---|---:|---:|
| Accuracy | 42.6% | — |
| Macro-F1 | 0.3894 | — |
| Supported recall | 7.0% | at least 50% |
| False-support rate | 0.25% | at most 5% |
| Contradiction false supports | 0 | exactly 0 |
| Partial/ambiguous review recall | 77.5% | at least 80% |
| Review rate | 49.6% | at most 50% |

No estimator and threshold combination passes all gates. The dedicated risk
heads improve safe supported recall from V23's 1% to 7%, while keeping zero
contradiction false supports and only one false support among 400 non-support
cases. The remaining gap to 50% is too large to promote or confirm.

This result closes the threshold and classical-head path for the current
feature family. The next experiment needs new claim-evidence representations
or training examples that distinguish complete entailment from plausible but
insufficient evidence. Another search over these probabilities is unlikely to
change the release decision.

The machine-readable artifact is
[`results/v24_support_risk.json`](results/v24_support_risk.json). It retains
case identifiers, labels, predictions, and probabilities without raw claim or
evidence text. Remote inference, default-provider changes, and network calls
remain zero.

## Reproduce

```bash
PYTHONPATH=packages/contexttrace:. .venv/bin/python \
  -m benchmarks.requirement_alignment.v24_support_risk \
  --development /private/tmp/contexttrace_external_data/v21_development.json \
  --relation-scores /private/tmp/contexttrace_external_data/v23_relation_scores.json \
  --atomic-scores /private/tmp/contexttrace_external_data/v23_atomic_scores.json \
  --multispan-scores /private/tmp/contexttrace_external_data/v21_multispan_scores.json \
  --routing-result benchmarks/requirement_alignment/results/v23_stronger_nli_atomic_screen.json \
  --output benchmarks/requirement_alignment/results/v24_support_risk.json
```
