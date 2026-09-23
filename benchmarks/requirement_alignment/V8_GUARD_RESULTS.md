# V8 contradiction-aware guard results

## Decision

V8 is a real safety improvement, but it is not ready for the ContextTrace 1.3
default verifier. On SciFact development it reduced the optional cascade's false
positive rate from 8.33% to 0.56%, eliminated all contradiction false supports,
raised accuracy from 80.74% to 83.70%, and reduced remote routing from 68.89% to
56.67%. It met every quality gate but missed the predeclared 30% remote-call
ceiling.

The frozen policy also removed four of five V7 false supports on the previously
consumed SciFact evaluation split, including both contradiction errors. That
post-hoc result is useful regression evidence, but it is not a fresh holdout and
cannot authorize promotion. Stable verifier behavior remains unchanged; Jev
remains optional, explicitly enabled, and blocked by `local_only`.

## Protocol

- Policy selection used only the 270 balanced SciFact training-derived
  development cases: 90 entailments, 90 contradictions, and 90 not-mentioned
  cases.
- The 180 SciFact development-derived evaluation cases were excluded from
  candidate generation and policy selection.
- The two verified local artifacts scored the same claim and selected evidence.
  V8 uses both models' full relation probabilities and adds a deterministic
  contradiction veto.
- Jev scored every development case once so all 600 deterministic policy
  candidates could be compared without route-dependent missing judgments.
- Jev received only `claim` and `selected_evidence`. Targets, source relations,
  query text, split names, and metadata were not sent.
- Every remote row records the five verdict probabilities, confidence, resolved
  model, request latency, and token usage. Explanations and fact spans remain
  empty rather than being invented.

## Frozen development policy

Policy ID:
`81aa19260e97f04e15c2c3b75c1da86b6f093dead216a33cb521f221720d37cb`

1. Accept local support only when both entailment probabilities are at least
   `0.875` and neither contradiction probability exceeds `0.04`.
2. Accept local missing only when both entailment probabilities are at most
   `0.70`.
3. In `local_only`, abstain on every remaining case with zero network calls.
4. With explicit remote opt-in, route remaining cases to Jev and accept support
   only when Jev selects `supported` with probability at least `0.50`.
5. Require review for every supported result and every Jev result below `0.80`
   confidence.

## Development results

| System | Accuracy | Macro F1 | Support recall | False-positive rate | Contradiction false supports | Remote calls |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| V3 at 0.90 | 66.30% | 53.66% | 21.11% | 11.11% | not separated | 0 |
| V5 at 0.90 | 74.81% | 65.91% | 35.56% | 5.56% | not separated | 0 |
| Frozen V6 + optional Jev | 80.74% | 76.74% | 58.89% | 8.33% | 12 | 186/270 (68.89%) |
| V8 guard + optional Jev | **83.70%** | **78.59%** | 52.22% | **0.56%** | **0** | **153/270 (56.67%)** |

V8 traded 6.67 percentage points of recall for a 7.77-point false-positive
reduction and removed every contradiction false support. Local-only automatic
coverage rose from 31.11% to 43.33%, automatic accuracy rose from 78.57% to
85.47%, and its false-positive rate fell from 25.93% to 1.15%.

Sixteen of 600 candidates met all quality gates. No candidate also met the 30%
remote-call target, so the release gate failed.

For the selected route, Jev used 106,503 tokens (96,762 input and 9,741 output),
with 345.374 ms mean latency and 635.090 ms p95 latency. The all-case development
artifact used 192,139 tokens. All 270 responses resolved to `jev-1.13.0`; 133
were below the 0.80 review-confidence threshold.

## Post-hoc V7 regression check

The frozen V8 policy was applied once to the already-consumed V7 evaluation.
Eighty-five existing Jev judgments were reused after their selected-evidence
hashes were verified, and ten newly routed cases were judged. This check was not
used to change the policy.

| System | Accuracy | Macro F1 | Support recall | False-positive rate | False supports | Remote calls |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Frozen V6 + optional Jev | 76.67% | 68.42% | 38.33% | 4.17% | 5 | 124/180 (68.89%) |
| Frozen V8 + optional Jev | **77.78%** | 68.42% | 35.00% | **0.83%** | **1** | **95/180 (52.78%)** |

V8 eliminated four existing false supports and introduced none. Both
contradiction false supports disappeared. The remaining false support is a
not-mentioned case accepted by the local branch. Local-only automatic coverage
rose to 47.22%, accuracy rose to 85.88%, and false-positive rate fell to 1.45%.

The post-hoc split still fails the 50% support-recall gate and the 30% remote-call
gate. Because the split had already been inspected in V7, these numbers are a
diagnostic rather than unbiased release evidence.

## Next gate

The next experiment should freeze a new external holdout before running V8. It
must confirm zero contradiction false supports, at most 5% overall and local
false-positive rates, at least 50% support recall, and no more than 30% remote
routing. If routing remains high, the next model change should improve local
negative confidence or add a separate local contradiction detector; thresholds
must not be tuned on the consumed SciFact evaluation.
