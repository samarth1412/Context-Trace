# V9 Climate-FEVER holdout result

The frozen V9 router was evaluated once on the 240-case Climate-FEVER holdout.
The policy ID was
`718b3e848ea6998387400b88f6851bb751e4dba638010a4b19724c8fe0f475c6`.
No threshold, feature, prompt, or gate changed after observing these results.

## Result

| Measure | Frozen gate | Result | Pass |
|---|---:|---:|:---:|
| Support recall | at least 50% | **10.00%** | No |
| Overall false-positive rate | at most 5% | **0.00%** | Yes |
| Local-only false-positive rate | at most 5% | **0.00%** | Yes |
| Contradiction false supports | zero | **0** | Yes |
| Primary Jev call rate | at most 30% | **6.67%** | Yes |
| Disputed automatic supports | zero | **0** | Yes |
| Disputed review/abstain coverage | at least 90% | **8.33%** | No |

The 180-case primary result has 70.00% accuracy and 0.4991 macro F1. It
correctly rejects all 60 contradictions and all 60 insufficient-evidence
claims, but accepts only 6 of 60 supported claims. The candidate therefore
fails the release gates despite perfect observed false-support safety.

The local-only path abstains on 12 primary cases and makes zero network calls.
Its 93.33% automatic coverage is misleading in isolation: it accepts only 1 of
50 automatically decided supported claims, for 2.00% positive recall.

## Failure analysis

The failure is routing transfer, not evidence minimization or the Jev support
gate. The frozen V8 stage marked 21 of 60 supported claims uncertain. The V9
router retained only 10 of those for Jev, accepted one claim locally, and
classified the remaining 49 as missing. Jev accepted support for 5 of the 10
routed supported claims; the other 5 were classified partially supported.

Across all 240 cases, the router made 17 Jev calls (7.08%). Every request sent
only the claim and its five selected evidence items. Jev resolved to
`jev-1.13.0`, used 14,876 tokens, and had 240.762 ms mean request latency. One
insufficient-evidence case received a Jev `supported` choice, but its supported
probability did not meet the frozen 0.50 gate, preventing a false support.

The disputed challenge exposes the same conservative behavior. The router sent
only 5 of 60 disputed cases to Jev and classified 55 locally as missing. All
five routed cases required review, producing only 8.33% review coverage against
the frozen 90% target.

## Decision

The V9 router is not eligible for ContextTrace 1.3 or optional `JevJudge`
product integration. Stable behavior remains unchanged, Jev remains disabled
by default, and `local_only` remains fully offline.

This holdout is now consumed and cannot be used to tune a replacement while
remaining fresh release evidence. The next experiment should create a separate,
heterogeneous development collection with climate/scientific paraphrases and
explicit disputed-evidence examples. It should train routing for recall under
the existing false-support cap, freeze a new policy, and confirm it on a new
untouched holdout.
