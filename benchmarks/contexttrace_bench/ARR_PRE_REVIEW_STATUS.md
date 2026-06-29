# ARR Pre-Review Experiment Snapshot

Status: `pre_review_paper_candidate`

Paper result eligible: `False`. Broad SOTA claim allowed: `False`.

These are frozen pre-review results. Independent Diag-150 and RAGTruth review must pass before paper-result claims; broad state-of-the-art language remains blocked.

Source commit: `2e0a26ea0cc5d6fb1c996f993277358fda05d04c`; bootstrap samples: `400`; ablation case-ID SHA-256: `3d32bd4f1c1e64f97e52d2f5eb4a814878c02301856d093d3e45b51626496fbb`.
Class-sensitive intervals retain at least 95% of requested draws; always-defined ablation intervals retain all 400.

## External Results

| Dataset | Review status | Cases | Failure F1 [95% CI] | Claim F1 | Root cause | Citation F1 | Span overlap | False green [95% CI] |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| RAGTruth | assisted_review_pending_independent | 200 | 0.955 [0.912, 0.977] | 0.337 | 0.955 | 1.000 | 0.786 | 0.000 [0.000, 0.000] |
| ContextTrace-Diag-150 | pending_independent | 150 | 1.000 [1.000, 1.000] | 1.000 | 1.000 | 1.000 | 0.950 | 0.000 [0.000, 0.000] |

## Cumulative Ablations

| Profile | Cases | Failure F1 [95% CI] | Claim F1 | Citation F1 | Root cause | Span overlap | False green [95% CI] |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Lexical core | 500 | 0.419 [0.355, 0.443] | 0.971 | N/A | N/A | N/A | 0.232 [0.194, 0.270] |
| + semantic matching | 500 | 0.419 [0.355, 0.443] | 0.971 | N/A | N/A | N/A | 0.232 [0.194, 0.270] |
| + citation alignment | 500 | 0.566 [0.512, 0.590] | 0.971 | 1.000 | N/A | N/A | 0.112 [0.086, 0.142] |
| + abstention and root cause | 500 | 0.691 [0.637, 0.715] | 0.971 | 1.000 | 0.886 | N/A | 0.112 [0.086, 0.142] |
| + evidence-span localization | 500 | 0.708 [0.670, 0.718] | 1.000 | 1.000 | 0.888 | 0.862 | 0.112 [0.086, 0.142] |
| Full ContextTrace | 500 | 1.000 [1.000, 1.000] | 1.000 | 1.000 | 1.000 | 0.862 | 0.000 [0.000, 0.000] |

## Same-ID Baseline

| System | Cases | Failure F1 [95% CI] | Claim F1 | Root cause | Citation F1 | Span overlap | False green [95% CI] |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| ContextTrace | 200 | 0.955 [0.912, 0.977] | 0.337 | 0.955 | 1.000 | 0.786 | 0.000 [0.000, 0.000] |
| RAGAS | 200 | 0.152 [0.143, 0.199] | 0.533 | N/A | N/A | N/A | 0.300 [0.240, 0.365] |

## Error Analysis

Cases: `200`; label misses: `9`; dangerous false greens: `0`.

## Remaining Gates

- `independent_diag150_review_complete`: `pending`
- `independent_ragtruth_review_complete`: `pending`
- `matched_external_baseline_available`: `passed`
- `non_quick_run`: `passed`
- `ragtruth_case_pack_available`: `passed`

The RAGTruth claim-verdict metric is lower than the matched RAGAS row; the systems expose different diagnostic coverage, so report overlapping outputs and `N/A` fields without a broad dominance claim.
