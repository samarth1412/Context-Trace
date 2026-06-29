# ContextTrace-Bench Results

- Benchmark: `ContextTrace-Bench`
- Mode: `semantic`
- Case set: `external_case_pack`
- Case source: RAGTruth case pack adapted for ContextTrace external validation. These cases are scaffolding until answer-side hallucination spans are human-mapped to source-side evidence spans. from benchmarks\contexttrace_bench\out\ragtruth_release\ragtruth_reviewed_case_pack.json

## Summary

| Metric | Value |
| --- | ---: |
| `cases` | 200 |
| `failure_label_exact_match_rate` | 0.955 |
| `failure_label_macro_f1` | 0.955 |
| `claim_verdict_macro_f1` | 0.337 |
| `claim_verdict_match_rate` | 0.0 |
| `root_cause_accuracy` | 0.955 |
| `citation_error_precision` | 1.0 |
| `citation_error_recall` | 1.0 |
| `citation_error_f1` | 1.0 |
| `evidence_span_overlap` | 0.786 |
| `root_cause_reported_cases` | 200 |
| `citation_status_reported_cases` | 200 |
| `evidence_span_reported_cases` | 75 |
| `latency_p50_ms` | 790.849 |
| `latency_p95_ms` | 2442.996 |
| `cost_per_100_traces_usd` | 0.0 |
| `dangerous_false_green_rate` | 0.0 |

## Limitations

- RAGTruth evidence spans are human review artifacts derived from answer-side annotations and source passages.
- RAGTruth labels answer-side hallucination spans; source-side evidence spans require human mapping before span-localization claims.
- External case-pack results validate this dataset and adapter path only; they are not general RAG-evaluation SOTA proof.
- RAGTruth publishes response.jsonl and source_info.jsonl separately, joined by source_id.
- labels are answer-side hallucination spans; expected_evidence_spans require human curation before span-overlap claims.
- good-quality rows without hallucination spans map to no_failure_detected; span-labeled rows map to partial_support or contradicted_answer.
- stratified samples are deterministic and should record sample_size, sample_seed, and stratify_by fields before review.

## Confidence Intervals

| Metric | Estimate | 95% CI | Resamples |
| --- | ---: | ---: | ---: |
| `failure_label_macro_f1` | 0.955 | 0.922 to 0.977 | 100 |
| `claim_verdict_macro_f1` | 0.337 | 0.2 to 0.733 | 100 |
| `root_cause_accuracy` | 0.955 | 0.925 to 0.98 | 100 |
| `citation_error_f1` | 1.0 | 1.0 to 1.0 | 100 |
| `evidence_span_overlap` | 0.786 | 0.728 to 0.837 | 100 |
| `dangerous_false_green_rate` | 0.0 | 0.0 to 0.0 | 100 |

## Failure Label Breakdown

| Label | Precision | Recall | F1 | TP | FP | FN |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `contradicted_answer` | 0.911 | 0.953 | 0.932 | 41 | 4 | 2 |
| `no_failure_detected` | 1.0 | 0.965 | 0.982 | 110 | 0 | 4 |
| `partial_support` | 0.886 | 0.929 | 0.907 | 39 | 5 | 3 |
| `unsupported` | 1.0 | 1.0 | 1.0 | 1 | 0 | 0 |

## SOTA Readiness Gates

| Metric | Gate | Value | Status |
| --- | ---: | ---: | --- |
| `failure_label_macro_f1` | `>= 0.95` | 0.955 | pass |
| `claim_verdict_macro_f1` | `>= 0.95` | 0.337 | fail |
| `root_cause_accuracy` | `>= 0.9` | 0.955 | pass |
| `citation_error_f1` | `>= 0.9` | 1.0 | pass |
| `evidence_span_overlap` | `>= 0.75` | 0.786 | pass |
| `dangerous_false_green_rate` | `<= 0.01` | 0.0 | pass |

## Misses

| Case | Expected | Predicted | Root Cause |
| --- | --- | --- | --- |
| `ragtruth_121` | `contradicted_answer` | `partial_support` | `conflicting_contexts -> answer_overreach` |
| `ragtruth_123` | `partial_support` | `partial_support` | `answer_overreach -> answer_overreach` |
| `ragtruth_730` | `partial_support` | `contradicted_answer` | `answer_overreach -> conflicting_contexts` |
| `ragtruth_1513` | `partial_support` | `partial_support` | `answer_overreach -> answer_overreach` |
| `ragtruth_4211` | `contradicted_answer` | `partial_support` | `conflicting_contexts -> answer_overreach` |
| `ragtruth_5417` | `unsupported` | `unsupported` | `answer_overreach -> answer_overreach` |
| `ragtruth_7236` | `partial_support` | `contradicted_answer` | `answer_overreach -> conflicting_contexts` |
| `ragtruth_9604` | `no_failure_detected` | `partial_support` | `no_failure_detected -> answer_overreach` |
| `ragtruth_9775` | `partial_support` | `partial_support` | `answer_overreach -> answer_overreach` |
| `ragtruth_10072` | `no_failure_detected` | `partial_support` | `no_failure_detected -> answer_overreach` |
| `ragtruth_14007` | `partial_support` | `contradicted_answer` | `answer_overreach -> conflicting_contexts` |
| `ragtruth_15904` | `no_failure_detected` | `partial_support` | `no_failure_detected -> answer_overreach` |
| `ragtruth_15933` | `no_failure_detected` | `contradicted_answer` | `no_failure_detected -> conflicting_contexts` |
