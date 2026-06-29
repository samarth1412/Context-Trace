# ContextTrace-Bench Results

- Benchmark: `ContextTrace-Bench`
- Mode: `semantic`
- Case set: `external_case_pack`
- Case source: ARES-NQ-example case pack adapted for ContextTrace external validation from generic JSON/JSONL rows. from benchmarks\contexttrace_bench\out\ares_nq_example\smoke200_compared\external_case_pack.json

## Summary

| Metric | Value |
| --- | ---: |
| `cases` | 200 |
| `failure_label_exact_match_rate` | 0.995 |
| `failure_label_macro_f1` | 0.995 |
| `claim_verdict_macro_f1` | N/A |
| `claim_verdict_match_rate` | N/A |
| `root_cause_accuracy` | 0.995 |
| `citation_error_precision` | 1.0 |
| `citation_error_recall` | 1.0 |
| `citation_error_f1` | 1.0 |
| `evidence_span_overlap` | 1.0 |
| `root_cause_reported_cases` | 200 |
| `citation_status_reported_cases` | 200 |
| `evidence_span_reported_cases` | 89 |
| `latency_p50_ms` | 9.27 |
| `latency_p95_ms` | 18.619 |
| `cost_per_100_traces_usd` | 0.0 |
| `dangerous_false_green_rate` | 0.0 |

## Limitations

- Generic external case packs preserve upstream labels as supplied; publishable claims require documenting the upstream dataset and labeling protocol.
- Evidence-span metrics are only meaningful when expected_evidence_spans are supplied by the external dataset or an independent reviewer.
- External case-pack results validate this dataset and adapter path only; they are not general RAG-evaluation SOTA proof.
- Use this adapter for CRAG/ARES-style exports after normalizing rows to query, answer, contexts, and expected_label fields.
- Rows without answer text or contexts are skipped because ContextTrace cannot verify them fairly.

## Confidence Intervals

| Metric | Estimate | 95% CI | Resamples |
| --- | ---: | ---: | ---: |
| `failure_label_macro_f1` | 0.995 | 0.981 to 1.0 | 100 |
| `root_cause_accuracy` | 0.995 | 0.98 to 1.0 | 100 |
| `citation_error_f1` | 1.0 | 1.0 to 1.0 | 100 |
| `evidence_span_overlap` | 1.0 | 1.0 to 1.0 | 100 |
| `dangerous_false_green_rate` | 0.0 | 0.0 to 0.0 | 100 |

## Failure Label Breakdown

| Label | Precision | Recall | F1 | TP | FP | FN |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `no_failure_detected` | 1.0 | 0.99 | 0.995 | 99 | 0 | 1 |
| `should_have_abstained` | 0.99 | 1.0 | 0.995 | 100 | 1 | 0 |
| `unsupported_answer` | 0.99 | 1.0 | 0.995 | 100 | 1 | 0 |

## SOTA Readiness Gates

| Metric | Gate | Value | Status |
| --- | ---: | ---: | --- |
| `failure_label_macro_f1` | `>= 0.95` | 0.995 | pass |
| `claim_verdict_macro_f1` | `>= 0.95` | 0.0 | fail |
| `root_cause_accuracy` | `>= 0.9` | 0.995 | pass |
| `citation_error_f1` | `>= 0.9` | 1.0 | pass |
| `evidence_span_overlap` | `>= 0.75` | 1.0 | pass |
| `dangerous_false_green_rate` | `<= 0.01` | 0.0 | pass |

## Misses

| Case | Expected | Predicted | Root Cause |
| --- | --- | --- | --- |
| `ares_nq_example_6751220433242447969_2` | `no_failure_detected` | `should_have_abstained, unsupported_answer` | `no_failure_detected -> should_have_abstained` |
