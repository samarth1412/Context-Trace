# V16 support-failure audit

V16 diagnoses the remaining V15 support-recall failure before another model is
trained. It uses only the already-consumed V13 development split. The held-out
split is neither loaded nor used.

## Method

The audit compares V14 routing, V15 completeness probabilities, frozen V11
relation scores, deterministic atomic requirements, and lexical coverage for
the same 125 development cases. It examines all 15 supported claims missed by
V15 and retains the four existing false supports as guard cases.

The diagnostic categories are deterministic hypotheses rather than causal
labels. They use label-blind signals; evaluation verdicts are used only to
identify errors and calculate metrics. Source text remains in external local
artifacts. The committed report contains case identifiers, hashes, scores, and
derived signals, but no claim or evidence text.

V16 also enumerates every observed combination of completeness, contradiction,
and ambiguity thresholds: 140,608 policies in total. This is a post-hoc
diagnostic frontier, not model training or a policy selected for release.

## Findings

V15 correctly supports 10 of 25 supported cases and misses 15. It already uses
four of the five false-support cases allowed by the 5% cap. Reaching the 50%
support-recall gate requires 13 correct supports, so the next mechanism must
promote at least three correct cases while adding at most one false support.
That requires at least 75% precision among newly promoted cases.

| Primary diagnostic hypothesis | Missed cases |
|---|---:|
| V14 routed outside the support/partial boundary | 4 |
| Selected-evidence coverage risk | 4 |
| Atomic under-decomposition candidate | 3 |
| Completeness-ranker false negative | 2 |
| Relation-scoring false-negative candidate | 2 |

The supporting signals show a broader representation problem. Eleven of the
15 missed cases have low best-span lexical coverage, eleven have a minimum
atomic entailment below 0.70, and fourteen fall below V15's completeness
threshold. Four complex claims are represented as only one requirement. These
counts overlap and should not be interpreted as independent causes.

Threshold changes alone cannot close the gap. No enumerated policy passes all
five release gates. The best policy preserving the other four gates remains at
40% support recall, with 3% false supports, 82% partial/ambiguous review recall,
and a 48.8% review rate. The lowest-false-support policy that reaches 52%
support recall raises false supports to 9%, incorrectly supports one
contradiction, and lowers partial/ambiguous review recall to 74%.

## Decision

Do not promote V15 or tune another threshold over the same signals. V17 should
improve deterministic decomposition for materially coordinated claims and
score requirements over combinations of selected evidence spans. It should
retain V14's contradiction and ambiguity guards and must achieve at least 75%
precision on any newly promoted support cases.

Stable verifier behavior is unchanged. The audit uses no remote inference,
enables no remote provider, and preserves zero network calls in `local_only`
mode.
