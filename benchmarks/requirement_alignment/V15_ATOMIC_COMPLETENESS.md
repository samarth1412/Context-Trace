# V15 atomic completeness fusion

V15 targets V14's remaining failure: distinguishing fully supported claims
from partially supported claims without weakening contradiction and ambiguity
safety.

## Method

The existing deterministic atomic-coverage component decomposed the 125 V13
development claims into 153 requirements. Each requirement was evaluated by
the frozen V11 relation model against only the already-selected evidence. Raw
text remained in the external dataset; score artifacts retain hashes,
probabilities, statuses, latency, and the verified model identifier.

V15 combines three feature families:

- V14 out-of-fold five-way probabilities;
- V11 full-claim relation and lexical features; and
- V11 atomic-requirement score distributions and coverage summaries.

Sixty candidate combinations across three feature sets use the same five
stratified out-of-fold partitions as V14. Binary completeness models train only
on supported and partially-supported rows within each training fold, while
producing probabilities for every validation row. The fusion layer evaluates
4,096 safety policies per candidate. Evaluation labels are targets only and
never enter model features.

## Result

| Measure | V14 | V15 |
|---|---:|---:|
| Accuracy | 0.6720 | 0.7040 |
| Macro-F1 | 0.6549 | 0.7005 |
| Support recall | 0.2000 | 0.4000 |
| False-support rate | 0.0200 | 0.0400 |
| Contradiction false supports | 0 | 0 |
| Partial/ambiguous review recall | 0.8200 | 0.8000 |
| Review rate | 0.5360 | 0.4800 |

V15 doubles support recall, improves macro-F1 by 4.56 percentage points, keeps
all contradicted cases out of the supported class, and brings review volume
under its 50% cap. Contradiction and ambiguity recall remain 92% and 88%.

Four of five promotion gates pass. Support recall reaches 10 of 25 cases, three
short of the required 13. An exact-threshold Pareto audit also found no policy
that reached 50% support recall while preserving all other safety and review
constraints.

The selected binary completeness model has only 0.6528 ROC-AUC across the 50
supported/partial cases. Raw minimum atomic entailment ranks the boundary at
0.7208 ROC-AUC, but its safe threshold recovers only 28% of supported cases.
The limitation is therefore not just policy thresholding: requirement
decomposition and complete-support representation remain weak.

## Decision

V15 is a positive development result but is not eligible for release. No model
artifact is retained and the consumed V13 held-out set remains inaccessible.
The next experiment should improve atomic decomposition coverage before adding
another classifier. Stable defaults remain unchanged, `local_only` makes zero
network calls, and no remote provider is enabled by default.
