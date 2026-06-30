# ARR Pre-Review Experiment Snapshot

Status: `pre_review_paper_candidate`

Paper result eligible: `False`. Broad SOTA claim allowed: `False`.

These are frozen pre-review results. Independent Diag-150 and RAGTruth review must pass before paper-result claims; broad state-of-the-art language remains blocked.

Source commit: `15cf09f9f9d7bfdd6285dae2603edad12d8a3ff9`; bootstrap samples: `400`; ablation case-ID SHA-256: `3d32bd4f1c1e64f97e52d2f5eb4a814878c02301856d093d3e45b51626496fbb`.
Class-sensitive intervals retain at least 95% of requested draws; always-defined ablation intervals retain all 400.

## External Results

| Dataset | Review status | Cases | Failure F1 [95% CI] | Claim F1 | Root cause | Citation F1 | Span overlap | False green [95% CI] |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| RAGTruth | assisted_review_pending_independent | 200 | 0.955 [0.912, 0.977] | 0.337 | 0.955 | 1.000 | 0.786 | 0.000 [0.000, 0.000] |
| ContextTrace-Diag-150 | pending_independent | 150 | 1.000 [1.000, 1.000] | 1.000 | 1.000 | 1.000 | 0.950 | 0.000 [0.000, 0.000] |

## Cumulative Ablations

| Profile | Availability | Cases | Failure F1 [95% CI] | Claim F1 | Citation F1 | Root cause | Span overlap | False green [95% CI] |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Full ContextTrace | available | 500 | 1.000 [1.000, 1.000] | 1.000 | 1.000 | 1.000 | 0.862 | 0.000 [0.000, 0.000] |
| Lexical-only verifier | available | 500 | 0.419 [0.355, 0.443] | 0.971 | N/A | N/A | N/A | 0.232 [0.194, 0.270] |
| Semantic-only verifier | available | 500 | 0.419 [0.355, 0.443] | 0.971 | N/A | N/A | N/A | 0.232 [0.194, 0.270] |
| No citation module | available | 500 | 0.831 [0.808, 0.841] | 1.000 | N/A | 0.878 | 0.862 | 0.122 [0.094, 0.150] |
| No contradiction checks | available | 500 | 0.812 [0.746, 0.851] | 0.706 | 1.000 | 0.980 | 0.862 | 0.008 [0.002, 0.016] |
| No abstention logic | available | 500 | 0.875 [0.857, 0.875] | 1.000 | 1.000 | 0.372 | 0.862 | 0.000 [0.000, 0.000] |
| No root-cause classifier | available | 500 | 1.000 [1.000, 1.000] | 1.000 | 1.000 | N/A | 0.862 | 0.000 [0.000, 0.000] |
| No source trust/freshness | available | 500 | 0.708 [0.670, 0.718] | 1.000 | 1.000 | 0.888 | 0.862 | 0.112 [0.086, 0.142] |
| No evidence-span localization | available | 500 | 0.982 [0.925, 1.000] | 0.971 | 1.000 | 0.998 | N/A | 0.000 [0.000, 0.000] |
| NLI-only mode | not_available | None | N/A | N/A | N/A | N/A | N/A | N/A |
| Judge-only mode | not_available | None | N/A | N/A | N/A | N/A | N/A | N/A |

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
