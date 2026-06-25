# ContextTrace-Bench Results

- Benchmark: `ContextTrace-Bench`
- Mode: `semantic`
- Case set: `all`
- Case source: real ContextTrace repository docs plus external OSS docs and public GitHub issues plus deterministic generated variants from the same traces

## Summary

| Metric | Value |
| --- | ---: |
| `cases` | 500 |
| `failure_label_exact_match_rate` | 1.0 |
| `failure_label_macro_f1` | 1.0 |
| `claim_verdict_macro_f1` | 1.0 |
| `claim_verdict_match_rate` | 1.0 |
| `root_cause_accuracy` | 1.0 |
| `citation_error_precision` | 1.0 |
| `citation_error_recall` | 1.0 |
| `citation_error_f1` | 1.0 |
| `evidence_span_overlap` | 0.862 |
| `root_cause_reported_cases` | 500 |
| `citation_status_reported_cases` | 500 |
| `evidence_span_reported_cases` | 188 |
| `latency_p50_ms` | 5.283 |
| `latency_p95_ms` | 13.435 |
| `cost_per_100_traces_usd` | 0.0 |
| `dangerous_false_green_rate` | 0.0 |

## Confidence Intervals

| Metric | Estimate | 95% CI | Resamples |
| --- | ---: | ---: | ---: |
| `failure_label_macro_f1` | 1.0 | 1.0 to 1.0 | 100 |
| `claim_verdict_macro_f1` | 1.0 | 1.0 to 1.0 | 100 |
| `root_cause_accuracy` | 1.0 | 1.0 to 1.0 | 100 |
| `citation_error_f1` | 1.0 | 1.0 to 1.0 | 100 |
| `evidence_span_overlap` | 0.862 | 0.842 to 0.879 | 100 |
| `dangerous_false_green_rate` | 0.0 | 0.0 to 0.0 | 100 |

## Failure Label Breakdown

| Label | Precision | Recall | F1 | TP | FP | FN |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `citation_mismatch` | 1.0 | 1.0 | 1.0 | 61 | 0 | 0 |
| `contradicted_answer` | 1.0 | 1.0 | 1.0 | 10 | 0 | 0 |
| `low_authority_source` | 1.0 | 1.0 | 1.0 | 28 | 0 | 0 |
| `no_failure_detected` | 1.0 | 1.0 | 1.0 | 56 | 0 | 0 |
| `partial_support` | 1.0 | 1.0 | 1.0 | 3 | 0 | 0 |
| `should_have_abstained` | 1.0 | 1.0 | 1.0 | 324 | 0 | 0 |
| `stale_source` | 1.0 | 1.0 | 1.0 | 28 | 0 | 0 |
| `unsupported_answer` | 1.0 | 1.0 | 1.0 | 314 | 0 | 0 |

## SOTA Readiness Gates

| Metric | Gate | Value | Status |
| --- | ---: | ---: | --- |
| `failure_label_macro_f1` | `>= 0.95` | 1.0 | pass |
| `claim_verdict_macro_f1` | `>= 0.95` | 1.0 | pass |
| `root_cause_accuracy` | `>= 0.9` | 1.0 | pass |
| `citation_error_f1` | `>= 0.9` | 1.0 | pass |
| `evidence_span_overlap` | `>= 0.75` | 0.862 | pass |
| `dangerous_false_green_rate` | `<= 0.01` | 0.0 | pass |

## Misses

No benchmark misses under the current labeled checks.
