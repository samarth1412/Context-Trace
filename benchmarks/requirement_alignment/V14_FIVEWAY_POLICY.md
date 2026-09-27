# V14 development-only five-way policy

V14 tests whether a local policy can turn frozen V11 relation probabilities
into all five ContextTrace verdicts. It uses only the 125-case V13 development
split. The consumed V13 held-out split is never loaded.

## Method

The experiment derives 54 label-blind features from:

- distributions of V11 entailment, contradiction, and neutral probabilities;
- same-span and cross-span relation interactions; and
- deterministic lexical overlap, negation, number, and length signals.

Dataset identity and evaluation labels are excluded. Thirty-three multinomial
logistic, extra-trees, and histogram-boosting candidates produce five-fold
stratified out-of-fold probabilities. Each candidate then evaluates 4,096
support-safety policies. Candidate selection prioritizes passing every gate,
then five-way macro-F1 and support recall.

## Result

The selected three-leaf histogram classifier achieved the following
out-of-fold results:

| Measure | Direct classifier | Safety policy |
|---|---:|---:|
| Accuracy | 0.6160 | 0.6720 |
| Macro-F1 | 0.6158 | 0.6549 |
| Support recall | 0.3200 | 0.2000 |
| Contradiction recall | 0.9200 | 0.9200 |
| Partial-support recall | 0.4000 | 0.7200 |
| Unsupported recall | 0.5600 | 0.6400 |
| Unverifiable recall | 0.8800 | 0.8800 |

The policy reduced development false supports from V11's 41% transfer result
to 2%, with zero contradicted claims marked supported. It also routed 82% of
partial or ambiguous cases to the corresponding review outcomes. These are
meaningful improvements.

No candidate met all release gates. The selected policy recovered only 20% of
supported cases and routed 53.6% of all cases to partial-support or
unverifiable outcomes. A separate Pareto audit found no threshold combination
that reached the 50% support-recall requirement while preserving the remaining
safety and review-budget constraints.

## Decision

V14 is not eligible for release and no model artifact is retained. Its result
shows that local five-way aggregation fixes much of V11's contradiction and
ambiguity failure, but the current V11 representation does not separate fully
supported from partially supported evidence well enough.

The next experiment should target complete-support discrimination directly,
using atomic claim requirements and coverage features on development data.
Only after a candidate clears development gates should ContextTrace freeze a
new untouched confirmation pack. Stable defaults remain unchanged,
`local_only` makes zero network calls, and no remote provider is enabled by
default.
