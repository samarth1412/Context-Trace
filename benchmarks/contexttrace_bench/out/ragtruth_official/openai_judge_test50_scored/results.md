# ContextTrace-Bench Results

- Benchmark: `ContextTrace-Bench`
- Mode: `semantic`
- Case set: `external_case_pack`
- Case source: RAGTruth case pack adapted for ContextTrace external validation. These cases are scaffolding until answer-side hallucination spans are human-mapped to source-side evidence spans. from benchmarks/contexttrace_bench/out/ragtruth_official/ragtruth_reviewed_case_pack_test50_assisted.json

## Summary

| Metric | Value |
| --- | ---: |
| `cases` | 50 |
| `failure_label_exact_match_rate` | 0.32 |
| `failure_label_macro_f1` | 0.172 |
| `claim_verdict_macro_f1` | 0.134 |
| `claim_verdict_match_rate` | 0.0 |
| `root_cause_accuracy` | 0.34 |
| `citation_error_precision` | 1.0 |
| `citation_error_recall` | 1.0 |
| `citation_error_f1` | 1.0 |
| `evidence_span_overlap` | 0.882 |
| `root_cause_reported_cases` | 50 |
| `citation_status_reported_cases` | 50 |
| `evidence_span_reported_cases` | 15 |
| `latency_p50_ms` | 89.203 |
| `latency_p95_ms` | 329.314 |
| `cost_per_100_traces_usd` | 0.0 |
| `dangerous_false_green_rate` | 0.0 |

## Limitations

- RAGTruth evidence spans are human review artifacts derived from answer-side annotations and source passages.
- RAGTruth labels answer-side hallucination spans; source-side evidence spans require human mapping before span-localization claims.
- External case-pack results validate this dataset and adapter path only; they are not general RAG-evaluation SOTA proof.
- RAGTruth publishes response.jsonl and source_info.jsonl separately, joined by source_id.
- labels are answer-side hallucination spans; expected_evidence_spans require human curation before span-overlap claims.
- good-quality rows without hallucination spans map to no_failure_detected; span-labeled rows map to partial_support or contradicted_answer.

## Confidence Intervals

| Metric | Estimate | 95% CI | Resamples |
| --- | ---: | ---: | ---: |
| `failure_label_macro_f1` | 0.172 | 0.103 to 0.237 | 100 |
| `claim_verdict_macro_f1` | 0.134 | 0.077 to 0.166 | 100 |
| `root_cause_accuracy` | 0.34 | 0.2 to 0.48 | 100 |
| `citation_error_f1` | 1.0 | 1.0 to 1.0 | 100 |
| `evidence_span_overlap` | 0.882 | 0.814 to 0.951 | 100 |
| `dangerous_false_green_rate` | 0.0 | 0.0 to 0.0 | 100 |

## Failure Label Breakdown

| Label | Precision | Recall | F1 | TP | FP | FN |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `contradicted_answer` | 0.25 | 0.444 | 0.32 | 4 | 12 | 5 |
| `insufficient_context` | 0.0 | 1.0 | 0.0 | 0 | 6 | 0 |
| `no_failure_detected` | 1.0 | 0.314 | 0.478 | 11 | 0 | 24 |
| `partial_support` | 0.143 | 0.667 | 0.236 | 4 | 24 | 2 |
| `should_have_abstained` | 0.0 | 1.0 | 0.0 | 0 | 7 | 0 |
| `unsupported_answer` | 0.0 | 1.0 | 0.0 | 0 | 7 | 0 |

## SOTA Readiness Gates

| Metric | Gate | Value | Status |
| --- | ---: | ---: | --- |
| `failure_label_macro_f1` | `>= 0.95` | 0.172 | fail |
| `claim_verdict_macro_f1` | `>= 0.95` | 0.134 | fail |
| `root_cause_accuracy` | `>= 0.9` | 0.34 | fail |
| `citation_error_f1` | `>= 0.9` | 1.0 | pass |
| `evidence_span_overlap` | `>= 0.75` | 0.882 | pass |
| `dangerous_false_green_rate` | `<= 0.01` | 0.0 | pass |

## Misses

| Case | Expected | Predicted | Root Cause |
| --- | --- | --- | --- |
| `ragtruth_24` | `no_failure_detected` | `no_failure_detected` | `no_failure_detected -> no_failure_detected` |
| `ragtruth_25` | `no_failure_detected` | `partial_support` | `no_failure_detected -> answer_overreach` |
| `ragtruth_26` | `no_failure_detected` | `no_failure_detected` | `no_failure_detected -> no_failure_detected` |
| `ragtruth_27` | `no_failure_detected` | `partial_support` | `no_failure_detected -> answer_overreach` |
| `ragtruth_28` | `contradicted_answer` | `partial_support` | `conflicting_contexts -> answer_overreach` |
| `ragtruth_29` | `contradicted_answer` | `partial_support` | `conflicting_contexts -> answer_overreach` |
| `ragtruth_42` | `no_failure_detected` | `no_failure_detected` | `no_failure_detected -> no_failure_detected` |
| `ragtruth_43` | `no_failure_detected` | `partial_support` | `no_failure_detected -> answer_overreach` |
| `ragtruth_44` | `contradicted_answer` | `contradicted_answer` | `conflicting_contexts -> conflicting_contexts` |
| `ragtruth_45` | `no_failure_detected` | `partial_support` | `no_failure_detected -> answer_overreach` |
| `ragtruth_46` | `contradicted_answer` | `contradicted_answer` | `conflicting_contexts -> conflicting_contexts` |
| `ragtruth_47` | `no_failure_detected` | `partial_support` | `no_failure_detected -> answer_overreach` |
| `ragtruth_54` | `no_failure_detected` | `no_failure_detected` | `no_failure_detected -> no_failure_detected` |
| `ragtruth_55` | `no_failure_detected` | `contradicted_answer` | `no_failure_detected -> conflicting_contexts` |
| `ragtruth_56` | `no_failure_detected` | `contradicted_answer, insufficient_context, should_have_abstained, unsupported_answer` | `no_failure_detected -> insufficient_context` |
| `ragtruth_57` | `no_failure_detected` | `partial_support` | `no_failure_detected -> answer_overreach` |
| `ragtruth_58` | `partial_support` | `contradicted_answer, insufficient_context, partial_support, should_have_abstained, unsupported_answer` | `answer_overreach -> should_have_abstained` |
| `ragtruth_59` | `no_failure_detected` | `contradicted_answer, insufficient_context, should_have_abstained, unsupported_answer` | `no_failure_detected -> should_have_abstained` |
| `ragtruth_66` | `no_failure_detected` | `partial_support` | `no_failure_detected -> answer_overreach` |
| `ragtruth_67` | `no_failure_detected` | `partial_support` | `no_failure_detected -> answer_overreach` |
| `ragtruth_68` | `partial_support` | `contradicted_answer, should_have_abstained, unsupported_answer` | `answer_overreach -> should_have_abstained` |
| `ragtruth_69` | `no_failure_detected` | `contradicted_answer, insufficient_context, partial_support, should_have_abstained, unsupported_answer` | `no_failure_detected -> should_have_abstained` |
| `ragtruth_70` | `no_failure_detected` | `no_failure_detected` | `no_failure_detected -> no_failure_detected` |
| `ragtruth_71` | `no_failure_detected` | `contradicted_answer, partial_support, should_have_abstained, unsupported_answer` | `no_failure_detected -> should_have_abstained` |
| `ragtruth_120` | `no_failure_detected` | `no_failure_detected` | `no_failure_detected -> no_failure_detected` |
| `ragtruth_121` | `contradicted_answer` | `partial_support` | `conflicting_contexts -> answer_overreach` |
| `ragtruth_122` | `partial_support` | `partial_support` | `answer_overreach -> answer_overreach` |
| `ragtruth_123` | `partial_support` | `partial_support` | `answer_overreach -> answer_overreach` |
| `ragtruth_124` | `contradicted_answer` | `partial_support` | `conflicting_contexts -> answer_overreach` |
| `ragtruth_125` | `no_failure_detected` | `partial_support` | `no_failure_detected -> answer_overreach` |
| `ragtruth_138` | `no_failure_detected` | `partial_support` | `no_failure_detected -> answer_overreach` |
| `ragtruth_139` | `no_failure_detected` | `partial_support` | `no_failure_detected -> answer_overreach` |
| `ragtruth_140` | `no_failure_detected` | `no_failure_detected` | `no_failure_detected -> no_failure_detected` |
| `ragtruth_141` | `contradicted_answer` | `contradicted_answer, insufficient_context` | `conflicting_contexts -> conflicting_contexts` |
| `ragtruth_142` | `no_failure_detected` | `contradicted_answer, insufficient_context, partial_support, should_have_abstained, unsupported_answer` | `no_failure_detected -> should_have_abstained` |
| `ragtruth_143` | `no_failure_detected` | `partial_support` | `no_failure_detected -> answer_overreach` |
| `ragtruth_144` | `no_failure_detected` | `no_failure_detected` | `no_failure_detected -> no_failure_detected` |
| `ragtruth_145` | `no_failure_detected` | `partial_support` | `no_failure_detected -> answer_overreach` |
| `ragtruth_146` | `contradicted_answer` | `partial_support` | `conflicting_contexts -> answer_overreach` |
| `ragtruth_147` | `no_failure_detected` | `no_failure_detected` | `no_failure_detected -> no_failure_detected` |
| `ragtruth_148` | `no_failure_detected` | `partial_support` | `no_failure_detected -> answer_overreach` |
| `ragtruth_149` | `no_failure_detected` | `partial_support` | `no_failure_detected -> answer_overreach` |
| `ragtruth_180` | `contradicted_answer` | `contradicted_answer` | `conflicting_contexts -> conflicting_contexts` |
| `ragtruth_181` | `no_failure_detected` | `contradicted_answer` | `no_failure_detected -> conflicting_contexts` |
| `ragtruth_182` | `no_failure_detected` | `contradicted_answer` | `no_failure_detected -> conflicting_contexts` |
| `ragtruth_183` | `no_failure_detected` | `no_failure_detected` | `no_failure_detected -> no_failure_detected` |
| `ragtruth_184` | `partial_support` | `contradicted_answer` | `answer_overreach -> conflicting_contexts` |
| `ragtruth_185` | `partial_support` | `contradicted_answer, partial_support` | `answer_overreach -> conflicting_contexts` |
| `ragtruth_204` | `no_failure_detected` | `no_failure_detected` | `no_failure_detected -> no_failure_detected` |
| `ragtruth_205` | `no_failure_detected` | `partial_support` | `no_failure_detected -> answer_overreach` |
