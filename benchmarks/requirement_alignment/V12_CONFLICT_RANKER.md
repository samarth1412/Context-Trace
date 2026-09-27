# V12 disputed-evidence ranker result

V12 tests whether a dedicated local conflict ranker can improve the V11 review
policy. It uses the selected V11 relation model to score every evidence span,
then learns from all eligible Climate-FEVER claim groups. V9 remains consumed,
V10 development remains fixed, and all inference is local.

## Training and features

The V12 training partition contains 1,210 claims and 6,050 evidence spans,
including 78 disputed claims. Exact evidence is disjoint from the 60-case V10
development set.

Each ranker receives 143 deterministic features derived from:

- per-evidence V11 entailment, contradiction, and neutral probabilities;
- cross-span entailment and contradiction products;
- score distributions and threshold counts;
- lexical overlap, negation, and evidence-pair similarity.

Evaluation labels are targets only. No label is present in the V11 inputs or
ranker features.

## Result

The screen compared 146 logistic, extra-trees, random-forest, histogram
boosting, and kernel candidates. The selected extra-trees ranker achieved:

| Measure | Result |
|---|---:|
| Disputed hits in 18 review slots | 9/15 |
| Disputed recall at 18 | 0.6000 |
| Average precision | 0.3977 |
| ROC-AUC | 0.6726 |

This does not improve V11's 0.6000 disputed-review coverage. Its integrated
safety-compatible policy used 17 review slots and achieved 0.4000 support
recall, 0.0444 false-support rate, zero refutation false supports, and 0.6000
disputed-review coverage. No policy met all gates.

A separate pairwise cross-encoder used 141 unanimous conflict pairs and 705
model-selected hard negatives. Its best disputed recall at 18 was 0.4000 at
the untrained checkpoint; three training epochs reached at most 0.3333. The
pair model was rejected and its artifact was not retained.

## Decision

V12 is a useful negative result: classifier complexity and hard-negative pair
training do not solve the remaining error. V11 remains the strongest local
research candidate with 0.5960 four-way macro-F1, but it is still ineligible
for ContextTrace 1.3.

Further threshold or architecture tuning on V10 development would overfit the
same 60 cases. The next research cycle should create a new contradiction-rich
development resource, while reserving a separate dataset for one-time release
confirmation. Stable defaults remain unchanged, `local_only` makes zero
network calls, and no remote provider is enabled by default.
