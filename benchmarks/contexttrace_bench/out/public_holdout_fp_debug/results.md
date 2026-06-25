# ContextTrace-Bench Results

- Benchmark: `ContextTrace-Bench`
- Mode: `semantic`
- Case set: `public_holdout`
- Case source: curated public holdout docs from RAG, vector database, observability, and evaluator projects

## Summary

| Metric | Value |
| --- | ---: |
| `cases` | 150 |
| `failure_label_exact_match_rate` | 1.0 |
| `failure_label_macro_f1` | 1.0 |
| `claim_verdict_macro_f1` | 1.0 |
| `claim_verdict_match_rate` | 1.0 |
| `root_cause_accuracy` | 1.0 |
| `citation_error_precision` | 1.0 |
| `citation_error_recall` | 1.0 |
| `citation_error_f1` | 1.0 |
| `evidence_span_overlap` | 0.95 |
| `root_cause_reported_cases` | 150 |
| `citation_status_reported_cases` | 150 |
| `evidence_span_reported_cases` | 149 |
| `latency_p50_ms` | 5.904 |
| `latency_p95_ms` | 21.097 |
| `cost_per_100_traces_usd` | 0.0 |
| `dangerous_false_green_rate` | 0.0 |

## Confidence Intervals

| Metric | Estimate | 95% CI | Resamples |
| --- | ---: | ---: | ---: |
| `failure_label_macro_f1` | 1.0 | 1.0 to 1.0 | 100 |
| `claim_verdict_macro_f1` | 1.0 | 1.0 to 1.0 | 100 |
| `root_cause_accuracy` | 1.0 | 1.0 to 1.0 | 100 |
| `citation_error_f1` | 1.0 | 1.0 to 1.0 | 100 |
| `evidence_span_overlap` | 0.95 | 0.937 to 0.964 | 100 |
| `dangerous_false_green_rate` | 0.0 | 0.0 to 0.0 | 100 |

## Failure Label Breakdown

| Label | Precision | Recall | F1 | TP | FP | FN |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `citation_mismatch` | 1.0 | 1.0 | 1.0 | 21 | 0 | 0 |
| `contradicted_answer` | 1.0 | 1.0 | 1.0 | 29 | 0 | 0 |
| `no_failure_detected` | 1.0 | 1.0 | 1.0 | 73 | 0 | 0 |
| `partial_support` | 1.0 | 1.0 | 1.0 | 26 | 0 | 0 |
| `should_have_abstained` | 1.0 | 1.0 | 1.0 | 30 | 0 | 0 |
| `unsupported_answer` | 1.0 | 1.0 | 1.0 | 1 | 0 | 0 |

## SOTA Readiness Gates

| Metric | Gate | Value | Status |
| --- | ---: | ---: | --- |
| `failure_label_macro_f1` | `>= 0.95` | 1.0 | pass |
| `claim_verdict_macro_f1` | `>= 0.95` | 1.0 | pass |
| `root_cause_accuracy` | `>= 0.9` | 1.0 | pass |
| `citation_error_f1` | `>= 0.9` | 1.0 | pass |
| `evidence_span_overlap` | `>= 0.75` | 0.95 | pass |
| `dangerous_false_green_rate` | `<= 0.01` | 0.0 | pass |

## Misses

No benchmark misses under the current labeled checks.
