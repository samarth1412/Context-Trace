# ContextTrace SOTA Readiness Gate

Status: `not_ready`
Generated: `2026-06-29T14:58:37+00:00`
Claim allowed: `false`
Checks passed: `8/10`

## Claim Policy

Do not claim broad SOTA; use the benchmarked, local-first evidence-chain forensics positioning.

## Gate Results

| Gate | Result | Requirement |
| --- | --- | --- |
| `primary_bundle_integrity` | `passed` | The primary external bundle and every listed artifact pass checksum and structure validation. |
| `external_dataset_count` | `passed` | At least 2 external datasets are scored end to end with frozen artifacts and documented commands. |
| `primary_independent_review` | `failed` | The primary external run has complete independent review with zero validation errors or warnings. |
| `primary_failure_label_macro_f1` | `passed` | Primary external `failure_label_macro_f1` must be >= 0.75. |
| `primary_dangerous_false_green_rate` | `passed` | Primary external `dangerous_false_green_rate` must be <= 0.01. |
| `primary_root_cause_accuracy` | `passed` | Primary external `root_cause_accuracy` must be >= 0.70. |
| `primary_evidence_span_overlap` | `passed` | Primary external `evidence_span_overlap` must be >= 0.70. |
| `primary_confidence_intervals` | `passed` | Primary point metrics match the scored artifact and include valid 95% case-bootstrap intervals. |
| `primary_same_id_competitors` | `passed` | At least 1 full competitor row set is scored on the exact primary IDs with unsupported diagnostics as N/A. |
| `diag150_human_audit` | `failed` | ContextTrace-Diag-150 is checksum-valid, independently signed off, and freeze-ready. |

## Remaining Blockers

- `primary_independent_review`: bundle status `calibration_only`, review kind `assisted`.
- `diag150_human_audit`: human sign-off `False`, bundle status `review_pending`.
