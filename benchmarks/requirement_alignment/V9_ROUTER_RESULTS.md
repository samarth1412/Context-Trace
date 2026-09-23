# V9 local meta-router development result

V9 adds a development-only local routing candidate before the frozen
Climate-FEVER confirmation run. It does not change ContextTrace's stable
verifier, enable a remote provider by default, or access the V9 holdout.

## Design

The candidate preserves the frozen V8 supported and missing decisions. For V8
uncertainty it adds two stages:

1. The already pinned `cross-encoder/nli-deberta-v3-small` model may return
   local support only when entailment is at least `0.98` and contradiction is at
   most `0.01`.
2. A 48-feature logistic router ranks the remaining cases for optional Jev.
   Its inputs contain only local v3/v5 probabilities, pinned-NLI probabilities,
   sentence aggregates, and deterministic lexical measurements. Gold labels
   are training targets only and are never model inputs or Jev inputs.

Router estimates are five-fold out-of-fold predictions grouped by SciFact
document ID. This prevents evidence from the same document appearing in both a
router training fold and its validation fold. The search considered nine
regularization values and every remote-call count from 0 through the
predeclared 30% cap. It selected the smallest call count at the best recall and
macro F1, then preferred stronger regularization.

## Development result

| Candidate | Accuracy | Macro F1 | Support recall | False-positive rate | Contradiction false supports | Jev calls |
|---|---:|---:|---:|---:|---:|---:|
| V8 guarded cascade | 0.8370 | 0.7859 | 0.5222 | 0.0056 | 0 | 153/270 (56.67%) |
| V9 grouped-OOF router | **0.8444** | **0.7975** | **0.5444** | **0.0056** | **0** | **77/270 (28.52%)** |

The pinned-NLI gate accepted 9 additional supported claims and produced no
false supports on this development set. The complete candidate produced one
false support, a NotMentioned case already accepted locally by V8; it produced
no contradiction false supports. Compared with V8, V9 cut simulated Jev calls
by 49.7% while improving recall, accuracy, and macro F1.

With `local_only=true`, all 77 router-selected remote cases abstain and make no
network calls. The remaining 193 cases have 71.48% automatic coverage, 86.01%
accuracy, a 0.69% false-positive rate, and zero contradiction false supports.

## Decision

This is a positive development result and a valid candidate for the frozen
Climate-FEVER holdout. It is not release evidence: the pinned-NLI thresholds,
router hyperparameters, and remote threshold were selected on SciFact
development, and the final serialized router is trained on all development
routes. The Climate-FEVER binary and disputed subsets remain unscored. V9 must
meet every gate in `V9_HOLDOUT_PROTOCOL.md` before any product integration or
1.3 release decision.

The result also carries a runtime tradeoff. Auxiliary local scoring evaluates
v3, v5, and pinned NLI at both group and sentence level. Holdout reporting must
include end-to-end local latency and memory, not only the reduced remote-call
count.
