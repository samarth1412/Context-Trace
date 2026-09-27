# V10 four-way local verifier screen

V10 tests whether frozen local verifier signals can distinguish support,
refutation, insufficient evidence, and disputed evidence on the new
Climate-FEVER development partition. It does not reuse the consumed V9
holdout, change stable product defaults, or make a remote call.

## Frozen-feature result

The selected standardized multinomial logistic candidate uses `C=0.01`. On
the balanced 60-case development set it reached **0.4000 accuracy** and
**0.3931 macro-F1**.

| Gold label | Precision | Recall | F1 |
|---|---:|---:|---:|
| Disputed | 0.5000 | 0.4000 | 0.4444 |
| Insufficient evidence | 0.4286 | 0.4000 | 0.4138 |
| Refutation | 0.4286 | 0.6000 | 0.5000 |
| Support | 0.2308 | 0.2000 | 0.2143 |

No one of the 73,036 threshold and review-budget combinations met every
promotion gate. The best safety-eligible diagnostic used all 18 review slots
and achieved 0.3333 support recall, 0.0444 false-support rate, zero refutation
false supports, and 0.4667 disputed-review coverage. It failed the 0.50 support
recall and 0.90 disputed-review targets.

## Bounded architecture checks

Two local follow-ups tested whether the failure was specific to linear frozen
features. These are development diagnostics, not promoted artifacts.

- A six-layer pinned NLI model adapted for three epochs on the 1,500
  evidence-level training annotations improved direct four-way accuracy to
  0.5500 and macro-F1 to 0.5389. Its best diagnostic policy reached 0.6667
  support recall and 0.6667 disputed-review coverage, but its false-support
  rate was 0.1778.
- A joint four-class claim model peaked at 0.4167 accuracy and 0.3613 macro-F1.
  It did not learn a reliable disputed class.
- Nonlinear tree and kernel aggregators over the adapted span scores peaked at
  0.5167 accuracy and 0.5042 macro-F1. None met all gates.

The evidence-level adaptation is the strongest direction, but it is not safe
enough for ContextTrace 1.3. The next experiment should improve evidence-level
relation supervision and explicit conflict aggregation, then freeze a policy
before evaluating once on a different dataset. V9 and V10 development results
cannot serve as that confirmation.

## Product decision

The V10 candidates are rejected for release. The stable verifier remains
unchanged, `local_only` still makes zero network calls, and no remote provider
is enabled by default.
