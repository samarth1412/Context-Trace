# V11 evidence-relation and conflict result

V11 expands local evidence-relation supervision after the V10 four-way screen
showed that frozen features could not reliably identify disputed evidence. It
keeps the fixed V10 development set, excludes every consumed V9 claim and every
training evidence component touching V10 development, and makes no remote
calls.

## Training data

The training builder selected all zero-entropy evidence annotations from the
eligible Climate-FEVER claims. Text-bearing data remains external.

| Item | Count |
|---|---:|
| Eligible claims | 1,210 |
| Selected evidence spans | 3,039 |
| Entailment spans | 1,345 |
| Contradiction spans | 388 |
| Neutral spans | 1,306 |
| Unique selected evidence texts | 2,357 |

Every selected annotation has zero upstream entropy. Exact evidence is
disjoint from V10 development, model outputs were not used for selection, and
labels remain outside model inputs.

## Selected result

The selected checkpoint is epoch 2 of a three-epoch CPU transfer run over the
pinned six-layer NLI model. The last two encoder layers, pooler, and
three-class head were trainable.

| Development measure | V10 best | V11 epoch 2 |
|---|---:|---:|
| Four-way accuracy | 0.5500 | **0.6000** |
| Four-way macro-F1 | 0.5389 | **0.5960** |
| Direct support recall | 0.7333 | **0.7333** |
| Direct disputed recall | 0.3333 | **0.4667** |

The evidence-level relation classifier reached 0.6167 accuracy and 0.5919
macro-F1 over the 300 development spans. Explicit aggregation then marked a
claim disputed only when support and contradiction evidence crossed their
selected thresholds.

The safety-compatible routing policy used cross-span conflict products and 16
of 60 review slots. It achieved 0.4000 support recall, 0.0444 false-support
rate, zero refutation false supports, and 0.6000 disputed-review coverage. No
policy met every promotion gate.

## Decision

V11 is a positive research result because it improves four-way macro-F1 by
0.0571 over the previous best local experiment. It is rejected for the
ContextTrace 1.3 release because the strict routed policy misses the 0.50
support-recall and 0.90 disputed-review targets.

The next experiment should improve contradiction supervision and conflict
ranking. The frozen V10 development split may guide that work, but release
confirmation must use a different untouched dataset. Stable defaults remain
unchanged, `local_only` makes zero network calls, and no provider is enabled by
default.
