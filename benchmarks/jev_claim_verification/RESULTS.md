# Jev claim-verification results

Run date: 2026-09-20

The development split was run first. The held-out split was then run once with the same evidence selector, TypeSafe `Choice` question, label criteria, requested `jev-latest` model, and no threshold or prompt changes. TypeSafe resolved both runs to `jev-1.13.0`.

## Summary

| Split | Cases | Stable correct | Jev correct | Stable accuracy | Jev accuracy | False supported |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Development | 5 | 2 | 4 | 0.40 | 0.80 | 0 |
| Held-out | 5 | 1 | 4 | 0.20 | 0.80 | 0 |
| Combined | 10 | 3 | 8 | 0.30 | 0.80 | 0 |

`False supported` counts every case whose expected label was not `supported` but Jev returned `supported`. The narrower unsupported-to-supported count was also zero on both splits. Jev assigned probability `0.0` to `supported` for all eight non-supported cases in this diagnostic set.

## Case results

| Case | Expected | Stable | Jev | Jev confidence |
| --- | --- | --- | --- | ---: |
| `dev_supported_refund_window` | supported | supported | supported | 1.00 |
| `dev_unsupported_refund_speed` | unsupported | unverifiable | unsupported | 0.93 |
| `dev_contradicted_refund_window` | contradicted | contradicted | contradicted | 1.00 |
| `dev_partial_refund_shipping` | partially_supported | supported | partially_supported | 0.99 |
| `dev_ambiguous_priority_support` | unverifiable | partially_supported | contradicted | 0.48 |
| `heldout_supported_leave` | supported | supported | supported | 0.99 |
| `heldout_unsupported_backup_schedule` | unsupported | unverifiable | unsupported | 0.99 |
| `heldout_contradicted_remote_days` | contradicted | supported | contradicted | 1.00 |
| `heldout_partial_travel_approval` | partially_supported | contradicted | partially_supported | 0.99 |
| `heldout_ambiguous_beta_access` | unverifiable | partially_supported | contradicted | 0.74 |

There were seven baseline/Jev disagreements. Jev corrected five baseline errors: both unsupported additions, both partial-support cases, and the held-out numeric contradiction. On the other two disagreements, neither provider matched the expected `unverifiable` label. Jev interpreted qualified evidence such as “may be available for some plans” and “enabled gradually for eligible paid accounts” as contradicting an absolute “every/all” claim. Under this experiment's label policy, that evidence remains too ambiguous to prove the universal claim false.

## Confidence, latency, and usage

Both Jev errors had confidence below `0.8` (`0.48` and `0.74`). Every correct verdict had confidence of at least `0.93`. A provisional `0.8` human-review gate would therefore accept 8/10 cases, refer both errors, and make no wrong automatic decisions on this sample. This threshold was observed after the held-out run and must be calibrated on a larger development set before production use.

| Split | Mean request latency | Input tokens | Output tokens | Total tokens |
| --- | ---: | ---: | ---: | ---: |
| Development | 309.527 ms | 2,835 | 319 | 3,154 |
| Held-out | 263.925 ms | 2,783 | 319 | 3,102 |
| Combined | 286.726 ms | 5,618 | 638 | 6,256 |

Per-case latency, token usage, confidence, full probability distributions, resolved model version, and evidence-input hashes are preserved in `results/jev_development.json` and `results/jev_heldout.json`.

## Recommendation

The result justifies implementing Jev as an optional, explicitly remote `JevJudge` behind the existing `ClaimJudge` contract. It should remain disabled by default, preserve the `local_only` block, receive only ContextTrace-selected evidence, and send verdicts below a calibrated confidence threshold to review or the stable fallback. It should not replace the stable verifier based on ten hand-authored cases.

Before claiming a general quality improvement, run a larger frozen held-out set, repeat requests to measure model stability, calibrate the confidence gate, and add more difficult unsupported additions and ambiguous universal/qualified statements. The current evidence supports an experimental optional provider; it does not support a SOTA or production-default claim.
