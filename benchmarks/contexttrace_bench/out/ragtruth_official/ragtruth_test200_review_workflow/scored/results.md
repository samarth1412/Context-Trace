# ContextTrace-Bench Results

- Benchmark: `ContextTrace-Bench`
- Mode: `semantic`
- Case set: `external_case_pack`
- Case source: RAGTruth case pack adapted for ContextTrace external validation. These cases are scaffolding until answer-side hallucination spans are human-mapped to source-side evidence spans. from benchmarks\contexttrace_bench\out\ragtruth_official\ragtruth_test200_review_workflow\ragtruth_reviewed_case_pack.json

## Summary

| Metric | Value |
| --- | ---: |
| `cases` | 200 |
| `failure_label_exact_match_rate` | 0.225 |
| `failure_label_macro_f1` | 0.15 |
| `claim_verdict_macro_f1` | 0.18 |
| `claim_verdict_match_rate` | 0.005 |
| `root_cause_accuracy` | 0.255 |
| `citation_error_precision` | 1.0 |
| `citation_error_recall` | 1.0 |
| `citation_error_f1` | 1.0 |
| `evidence_span_overlap` | 0.555 |
| `root_cause_reported_cases` | 200 |
| `citation_status_reported_cases` | 200 |
| `evidence_span_reported_cases` | 76 |
| `latency_p50_ms` | 119.768 |
| `latency_p95_ms` | 404.626 |
| `cost_per_100_traces_usd` | 0.0 |
| `dangerous_false_green_rate` | 0.025 |

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
| `failure_label_macro_f1` | 0.15 | 0.114 to 0.189 | 100 |
| `claim_verdict_macro_f1` | 0.18 | 0.147 to 0.207 | 100 |
| `root_cause_accuracy` | 0.255 | 0.185 to 0.305 | 100 |
| `citation_error_f1` | 1.0 | 1.0 to 1.0 | 100 |
| `evidence_span_overlap` | 0.555 | 0.48 to 0.634 | 100 |
| `dangerous_false_green_rate` | 0.025 | 0.005 to 0.045 | 100 |

## Failure Label Breakdown

| Label | Precision | Recall | F1 | TP | FP | FN |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `contradicted_answer` | 0.345 | 0.442 | 0.388 | 19 | 36 | 24 |
| `insufficient_context` | 0.0 | 1.0 | 0.0 | 0 | 49 | 0 |
| `no_failure_detected` | 0.8 | 0.179 | 0.293 | 20 | 5 | 92 |
| `partial_support` | 0.243 | 0.795 | 0.372 | 35 | 109 | 9 |
| `should_have_abstained` | 0.0 | 1.0 | 0.0 | 0 | 52 | 0 |
| `unsupported` | 1.0 | 0.0 | 0.0 | 0 | 0 | 1 |
| `unsupported_answer` | 0.0 | 1.0 | 0.0 | 0 | 51 | 0 |

## SOTA Readiness Gates

| Metric | Gate | Value | Status |
| --- | ---: | ---: | --- |
| `failure_label_macro_f1` | `>= 0.95` | 0.15 | fail |
| `claim_verdict_macro_f1` | `>= 0.95` | 0.18 | fail |
| `root_cause_accuracy` | `>= 0.9` | 0.255 | fail |
| `citation_error_f1` | `>= 0.9` | 1.0 | pass |
| `evidence_span_overlap` | `>= 0.75` | 0.555 | fail |
| `dangerous_false_green_rate` | `<= 0.01` | 0.025 | fail |

## Misses

| Case | Expected | Predicted | Root Cause |
| --- | --- | --- | --- |
| `ragtruth_58` | `partial_support` | `contradicted_answer, insufficient_context, should_have_abstained, unsupported_answer` | `answer_overreach -> should_have_abstained` |
| `ragtruth_59` | `no_failure_detected` | `contradicted_answer, should_have_abstained, unsupported_answer` | `no_failure_detected -> should_have_abstained` |
| `ragtruth_121` | `contradicted_answer` | `contradicted_answer, insufficient_context` | `conflicting_contexts -> conflicting_contexts` |
| `ragtruth_123` | `partial_support` | `partial_support` | `answer_overreach -> answer_overreach` |
| `ragtruth_331` | `no_failure_detected` | `partial_support` | `no_failure_detected -> answer_overreach` |
| `ragtruth_332` | `no_failure_detected` | `partial_support` | `no_failure_detected -> answer_overreach` |
| `ragtruth_334` | `no_failure_detected` | `partial_support` | `no_failure_detected -> answer_overreach` |
| `ragtruth_351` | `no_failure_detected` | `contradicted_answer, insufficient_context, should_have_abstained, unsupported_answer` | `no_failure_detected -> should_have_abstained` |
| `ragtruth_355` | `no_failure_detected` | `partial_support` | `no_failure_detected -> answer_overreach` |
| `ragtruth_543` | `contradicted_answer` | `partial_support` | `conflicting_contexts -> answer_overreach` |
| `ragtruth_586` | `no_failure_detected` | `contradicted_answer, insufficient_context` | `no_failure_detected -> conflicting_contexts` |
| `ragtruth_656` | `contradicted_answer` | `contradicted_answer, insufficient_context, should_have_abstained, unsupported_answer` | `conflicting_contexts -> should_have_abstained` |
| `ragtruth_690` | `no_failure_detected` | `no_failure_detected` | `no_failure_detected -> no_failure_detected` |
| `ragtruth_695` | `partial_support` | `partial_support` | `answer_overreach -> answer_overreach` |
| `ragtruth_730` | `partial_support` | `contradicted_answer, insufficient_context, should_have_abstained` | `answer_overreach -> conflicting_contexts` |
| `ragtruth_835` | `no_failure_detected` | `partial_support` | `no_failure_detected -> answer_overreach` |
| `ragtruth_838` | `no_failure_detected` | `partial_support` | `no_failure_detected -> answer_overreach` |
| `ragtruth_878` | `no_failure_detected` | `partial_support` | `no_failure_detected -> answer_overreach` |
| `ragtruth_885` | `partial_support` | `insufficient_context, should_have_abstained, unsupported_answer` | `answer_overreach -> should_have_abstained` |
| `ragtruth_906` | `partial_support` | `contradicted_answer` | `answer_overreach -> conflicting_contexts` |
| `ragtruth_924` | `no_failure_detected` | `partial_support` | `no_failure_detected -> answer_overreach` |
| `ragtruth_1153` | `no_failure_detected` | `contradicted_answer` | `no_failure_detected -> conflicting_contexts` |
| `ragtruth_1157` | `contradicted_answer` | `contradicted_answer, insufficient_context, should_have_abstained` | `conflicting_contexts -> insufficient_context` |
| `ragtruth_1355` | `no_failure_detected` | `partial_support` | `no_failure_detected -> answer_overreach` |
| `ragtruth_1513` | `partial_support` | `contradicted_answer, partial_support, unsupported_answer` | `answer_overreach -> conflicting_contexts` |
| `ragtruth_1566` | `no_failure_detected` | `partial_support` | `no_failure_detected -> answer_overreach` |
| `ragtruth_1586` | `partial_support` | `partial_support` | `answer_overreach -> answer_overreach` |
| `ragtruth_1587` | `no_failure_detected` | `no_failure_detected` | `no_failure_detected -> no_failure_detected` |
| `ragtruth_1648` | `no_failure_detected` | `contradicted_answer, insufficient_context, should_have_abstained, unsupported_answer` | `no_failure_detected -> insufficient_context` |
| `ragtruth_1678` | `no_failure_detected` | `partial_support` | `no_failure_detected -> answer_overreach` |
| `ragtruth_1683` | `no_failure_detected` | `contradicted_answer, insufficient_context, partial_support, should_have_abstained, unsupported_answer` | `no_failure_detected -> should_have_abstained` |
| `ragtruth_1698` | `contradicted_answer` | `no_failure_detected` | `conflicting_contexts -> no_failure_detected` |
| `ragtruth_1967` | `contradicted_answer` | `contradicted_answer, insufficient_context` | `conflicting_contexts -> conflicting_contexts` |
| `ragtruth_1990` | `contradicted_answer` | `should_have_abstained, unsupported_answer` | `conflicting_contexts -> should_have_abstained` |
| `ragtruth_2136` | `no_failure_detected` | `partial_support` | `no_failure_detected -> answer_overreach` |
| `ragtruth_2359` | `no_failure_detected` | `partial_support` | `no_failure_detected -> answer_overreach` |
| `ragtruth_2454` | `no_failure_detected` | `no_failure_detected` | `no_failure_detected -> no_failure_detected` |
| `ragtruth_2469` | `no_failure_detected` | `partial_support` | `no_failure_detected -> answer_overreach` |
| `ragtruth_2653` | `no_failure_detected` | `partial_support` | `no_failure_detected -> answer_overreach` |
| `ragtruth_2668` | `contradicted_answer` | `no_failure_detected` | `conflicting_contexts -> no_failure_detected` |
| `ragtruth_2675` | `no_failure_detected` | `no_failure_detected` | `no_failure_detected -> no_failure_detected` |
| `ragtruth_2876` | `contradicted_answer` | `contradicted_answer, unsupported_answer` | `conflicting_contexts -> retrieval_miss` |
| `ragtruth_2892` | `no_failure_detected` | `partial_support` | `no_failure_detected -> answer_overreach` |
| `ragtruth_2894` | `no_failure_detected` | `no_failure_detected` | `no_failure_detected -> no_failure_detected` |
| `ragtruth_3560` | `partial_support` | `partial_support` | `answer_overreach -> answer_overreach` |
| `ragtruth_3611` | `no_failure_detected` | `partial_support` | `no_failure_detected -> answer_overreach` |
| `ragtruth_3638` | `partial_support` | `contradicted_answer, insufficient_context, partial_support, should_have_abstained, unsupported_answer` | `answer_overreach -> should_have_abstained` |
| `ragtruth_3639` | `contradicted_answer` | `partial_support` | `conflicting_contexts -> answer_overreach` |
| `ragtruth_3770` | `no_failure_detected` | `partial_support` | `no_failure_detected -> answer_overreach` |
| `ragtruth_3771` | `no_failure_detected` | `contradicted_answer, partial_support` | `no_failure_detected -> conflicting_contexts` |
| `ragtruth_3814` | `partial_support` | `partial_support` | `answer_overreach -> answer_overreach` |
| `ragtruth_3866` | `partial_support` | `partial_support` | `answer_overreach -> answer_overreach` |
| `ragtruth_3952` | `no_failure_detected` | `partial_support` | `no_failure_detected -> answer_overreach` |
| `ragtruth_4052` | `contradicted_answer` | `no_failure_detected` | `conflicting_contexts -> no_failure_detected` |
| `ragtruth_4064` | `contradicted_answer` | `contradicted_answer` | `conflicting_contexts -> conflicting_contexts` |
| `ragtruth_4065` | `partial_support` | `partial_support` | `answer_overreach -> answer_overreach` |
| `ragtruth_4196` | `partial_support` | `partial_support` | `answer_overreach -> answer_overreach` |
| `ragtruth_4211` | `contradicted_answer` | `partial_support` | `conflicting_contexts -> answer_overreach` |
| `ragtruth_4218` | `no_failure_detected` | `partial_support` | `no_failure_detected -> answer_overreach` |
| `ragtruth_4226` | `no_failure_detected` | `no_failure_detected` | `no_failure_detected -> no_failure_detected` |
| `ragtruth_4263` | `contradicted_answer` | `partial_support` | `conflicting_contexts -> answer_overreach` |
| `ragtruth_4339` | `no_failure_detected` | `no_failure_detected` | `no_failure_detected -> no_failure_detected` |
| `ragtruth_4348` | `no_failure_detected` | `partial_support` | `no_failure_detected -> answer_overreach` |
| `ragtruth_4524` | `no_failure_detected` | `partial_support` | `no_failure_detected -> answer_overreach` |
| `ragtruth_4527` | `no_failure_detected` | `partial_support` | `no_failure_detected -> answer_overreach` |
| `ragtruth_4573` | `no_failure_detected` | `no_failure_detected` | `no_failure_detected -> no_failure_detected` |
| `ragtruth_4575` | `no_failure_detected` | `no_failure_detected` | `no_failure_detected -> no_failure_detected` |
| `ragtruth_4777` | `no_failure_detected` | `partial_support` | `no_failure_detected -> answer_overreach` |
| `ragtruth_4781` | `no_failure_detected` | `no_failure_detected` | `no_failure_detected -> no_failure_detected` |
| `ragtruth_4955` | `no_failure_detected` | `contradicted_answer, insufficient_context, should_have_abstained, unsupported_answer` | `no_failure_detected -> should_have_abstained` |
| `ragtruth_5201` | `no_failure_detected` | `contradicted_answer, should_have_abstained, unsupported_answer` | `no_failure_detected -> conflicting_contexts` |
| `ragtruth_5274` | `no_failure_detected` | `partial_support` | `no_failure_detected -> answer_overreach` |
| `ragtruth_5416` | `no_failure_detected` | `partial_support` | `no_failure_detected -> answer_overreach` |
| `ragtruth_5417` | `unsupported` | `partial_support` | `answer_overreach -> answer_overreach` |
| `ragtruth_5482` | `contradicted_answer` | `partial_support` | `conflicting_contexts -> answer_overreach` |
| `ragtruth_5691` | `contradicted_answer` | `partial_support` | `conflicting_contexts -> answer_overreach` |
| `ragtruth_5829` | `no_failure_detected` | `insufficient_context, partial_support, should_have_abstained, unsupported_answer` | `no_failure_detected -> should_have_abstained` |
| `ragtruth_5850` | `no_failure_detected` | `partial_support` | `no_failure_detected -> answer_overreach` |
| `ragtruth_6051` | `contradicted_answer` | `contradicted_answer, insufficient_context, partial_support, should_have_abstained, unsupported_answer` | `conflicting_contexts -> should_have_abstained` |
| `ragtruth_6052` | `contradicted_answer` | `partial_support` | `conflicting_contexts -> answer_overreach` |
| `ragtruth_6250` | `partial_support` | `contradicted_answer, insufficient_context, partial_support, should_have_abstained, unsupported_answer` | `answer_overreach -> should_have_abstained` |
| `ragtruth_6256` | `partial_support` | `insufficient_context, partial_support, should_have_abstained, unsupported_answer` | `answer_overreach -> should_have_abstained` |
| `ragtruth_6550` | `contradicted_answer` | `contradicted_answer, insufficient_context, partial_support, should_have_abstained, unsupported_answer` | `conflicting_contexts -> should_have_abstained` |
| `ragtruth_6686` | `partial_support` | `partial_support` | `answer_overreach -> answer_overreach` |
| `ragtruth_6913` | `no_failure_detected` | `contradicted_answer, insufficient_context, partial_support, should_have_abstained, unsupported_answer` | `no_failure_detected -> insufficient_context` |
| `ragtruth_6927` | `contradicted_answer` | `insufficient_context, partial_support, should_have_abstained, unsupported_answer` | `conflicting_contexts -> insufficient_context` |
| `ragtruth_6996` | `no_failure_detected` | `partial_support` | `no_failure_detected -> answer_overreach` |
| `ragtruth_7008` | `no_failure_detected` | `partial_support` | `no_failure_detected -> answer_overreach` |
| `ragtruth_7011` | `partial_support` | `contradicted_answer, insufficient_context, should_have_abstained` | `answer_overreach -> insufficient_context` |
| `ragtruth_7019` | `no_failure_detected` | `contradicted_answer, partial_support, should_have_abstained, unsupported_answer` | `no_failure_detected -> should_have_abstained` |
| `ragtruth_7036` | `partial_support` | `insufficient_context, partial_support, should_have_abstained, unsupported_answer` | `answer_overreach -> should_have_abstained` |
| `ragtruth_7052` | `contradicted_answer` | `contradicted_answer, insufficient_context, partial_support, should_have_abstained, unsupported_answer` | `conflicting_contexts -> should_have_abstained` |
| `ragtruth_7137` | `partial_support` | `insufficient_context, partial_support, should_have_abstained, unsupported_answer` | `answer_overreach -> insufficient_context` |
| `ragtruth_7138` | `contradicted_answer` | `contradicted_answer, insufficient_context, partial_support, should_have_abstained, unsupported_answer` | `conflicting_contexts -> should_have_abstained` |
| `ragtruth_7153` | `contradicted_answer` | `contradicted_answer, insufficient_context, partial_support, unsupported_answer` | `conflicting_contexts -> answer_overreach` |
| `ragtruth_7236` | `partial_support` | `partial_support` | `answer_overreach -> answer_overreach` |
| `ragtruth_7262` | `contradicted_answer` | `partial_support` | `conflicting_contexts -> answer_overreach` |
| `ragtruth_7265` | `partial_support` | `contradicted_answer, should_have_abstained, unsupported_answer` | `answer_overreach -> should_have_abstained` |
| `ragtruth_7279` | `no_failure_detected` | `partial_support` | `no_failure_detected -> answer_overreach` |
| `ragtruth_7281` | `no_failure_detected` | `partial_support` | `no_failure_detected -> answer_overreach` |
| `ragtruth_7292` | `contradicted_answer` | `partial_support` | `conflicting_contexts -> answer_overreach` |
| `ragtruth_7301` | `contradicted_answer` | `partial_support` | `conflicting_contexts -> answer_overreach` |
| `ragtruth_8153` | `contradicted_answer` | `contradicted_answer, insufficient_context, partial_support, should_have_abstained, unsupported_answer` | `conflicting_contexts -> should_have_abstained` |
| `ragtruth_8474` | `contradicted_answer` | `contradicted_answer, insufficient_context, partial_support, should_have_abstained, unsupported_answer` | `conflicting_contexts -> should_have_abstained` |
| `ragtruth_8557` | `no_failure_detected` | `partial_support` | `no_failure_detected -> answer_overreach` |
| `ragtruth_8561` | `partial_support` | `insufficient_context, partial_support, should_have_abstained, unsupported_answer` | `answer_overreach -> should_have_abstained` |
| `ragtruth_8625` | `partial_support` | `insufficient_context, partial_support, should_have_abstained, unsupported_answer` | `answer_overreach -> should_have_abstained` |
| `ragtruth_8627` | `partial_support` | `partial_support` | `answer_overreach -> answer_overreach` |
| `ragtruth_8664` | `no_failure_detected` | `partial_support` | `no_failure_detected -> answer_overreach` |
| `ragtruth_8672` | `partial_support` | `partial_support` | `answer_overreach -> answer_overreach` |
| `ragtruth_8727` | `contradicted_answer` | `insufficient_context, partial_support, should_have_abstained, unsupported_answer` | `conflicting_contexts -> should_have_abstained` |
| `ragtruth_8778` | `no_failure_detected` | `contradicted_answer, insufficient_context, partial_support, should_have_abstained, unsupported_answer` | `no_failure_detected -> should_have_abstained` |
| `ragtruth_8939` | `contradicted_answer` | `partial_support` | `conflicting_contexts -> answer_overreach` |
| `ragtruth_9069` | `partial_support` | `partial_support, should_have_abstained, unsupported_answer` | `answer_overreach -> should_have_abstained` |
| `ragtruth_9071` | `partial_support` | `partial_support` | `answer_overreach -> answer_overreach` |
| `ragtruth_9212` | `no_failure_detected` | `partial_support` | `no_failure_detected -> answer_overreach` |
| `ragtruth_9542` | `partial_support` | `contradicted_answer, insufficient_context, should_have_abstained, unsupported_answer` | `answer_overreach -> should_have_abstained` |
| `ragtruth_9552` | `contradicted_answer` | `partial_support` | `conflicting_contexts -> answer_overreach` |
| `ragtruth_9553` | `contradicted_answer` | `contradicted_answer, insufficient_context, partial_support, should_have_abstained, unsupported_answer` | `conflicting_contexts -> should_have_abstained` |
| `ragtruth_9604` | `no_failure_detected` | `partial_support` | `no_failure_detected -> answer_overreach` |
| `ragtruth_9679` | `no_failure_detected` | `contradicted_answer, insufficient_context, partial_support, should_have_abstained, unsupported_answer` | `no_failure_detected -> conflicting_contexts` |
| `ragtruth_9775` | `partial_support` | `contradicted_answer, insufficient_context, partial_support, should_have_abstained, unsupported_answer` | `answer_overreach -> should_have_abstained` |
| `ragtruth_9840` | `partial_support` | `partial_support` | `answer_overreach -> answer_overreach` |
| `ragtruth_9937` | `no_failure_detected` | `partial_support` | `no_failure_detected -> answer_overreach` |
| `ragtruth_10006` | `contradicted_answer` | `partial_support` | `conflicting_contexts -> answer_overreach` |
| `ragtruth_10072` | `no_failure_detected` | `partial_support` | `no_failure_detected -> answer_overreach` |
| `ragtruth_10111` | `partial_support` | `contradicted_answer, insufficient_context, partial_support, unsupported_answer` | `answer_overreach -> retrieval_miss` |
| `ragtruth_10352` | `no_failure_detected` | `partial_support` | `no_failure_detected -> answer_overreach` |
| `ragtruth_10366` | `contradicted_answer` | `partial_support` | `conflicting_contexts -> answer_overreach` |
| `ragtruth_10463` | `no_failure_detected` | `partial_support` | `no_failure_detected -> answer_overreach` |
| `ragtruth_10543` | `no_failure_detected` | `contradicted_answer, insufficient_context, partial_support, should_have_abstained, unsupported_answer` | `no_failure_detected -> conflicting_contexts` |
| `ragtruth_10547` | `no_failure_detected` | `contradicted_answer, insufficient_context, partial_support, should_have_abstained, unsupported_answer` | `no_failure_detected -> should_have_abstained` |
| `ragtruth_10819` | `no_failure_detected` | `contradicted_answer, partial_support, should_have_abstained, unsupported_answer` | `no_failure_detected -> should_have_abstained` |
| `ragtruth_11286` | `no_failure_detected` | `partial_support` | `no_failure_detected -> answer_overreach` |
| `ragtruth_11447` | `contradicted_answer` | `contradicted_answer, insufficient_context, should_have_abstained, unsupported_answer` | `conflicting_contexts -> conflicting_contexts` |
| `ragtruth_11450` | `contradicted_answer` | `partial_support` | `conflicting_contexts -> answer_overreach` |
| `ragtruth_11520` | `no_failure_detected` | `contradicted_answer, insufficient_context, partial_support, should_have_abstained, unsupported_answer` | `no_failure_detected -> should_have_abstained` |
| `ragtruth_11522` | `contradicted_answer` | `contradicted_answer, insufficient_context, partial_support, should_have_abstained, unsupported_answer` | `conflicting_contexts -> should_have_abstained` |
| `ragtruth_11524` | `contradicted_answer` | `contradicted_answer, insufficient_context, partial_support, should_have_abstained, unsupported_answer` | `conflicting_contexts -> should_have_abstained` |
| `ragtruth_11908` | `partial_support` | `contradicted_answer, insufficient_context, partial_support, should_have_abstained, unsupported_answer` | `answer_overreach -> answer_overreach` |
| `ragtruth_12022` | `no_failure_detected` | `no_failure_detected` | `no_failure_detected -> no_failure_detected` |
| `ragtruth_12218` | `no_failure_detected` | `no_failure_detected` | `no_failure_detected -> no_failure_detected` |
| `ragtruth_12240` | `no_failure_detected` | `contradicted_answer, partial_support` | `no_failure_detected -> conflicting_contexts` |
| `ragtruth_12298` | `no_failure_detected` | `partial_support` | `no_failure_detected -> answer_overreach` |
| `ragtruth_12435` | `contradicted_answer` | `partial_support` | `conflicting_contexts -> answer_overreach` |
| `ragtruth_12469` | `no_failure_detected` | `partial_support` | `no_failure_detected -> answer_overreach` |
| `ragtruth_12690` | `no_failure_detected` | `partial_support` | `no_failure_detected -> answer_overreach` |
| `ragtruth_12691` | `no_failure_detected` | `partial_support` | `no_failure_detected -> answer_overreach` |
| `ragtruth_12917` | `contradicted_answer` | `partial_support` | `conflicting_contexts -> answer_overreach` |
| `ragtruth_13070` | `partial_support` | `partial_support` | `answer_overreach -> answer_overreach` |
| `ragtruth_13073` | `no_failure_detected` | `partial_support` | `no_failure_detected -> answer_overreach` |
| `ragtruth_13159` | `no_failure_detected` | `partial_support` | `no_failure_detected -> answer_overreach` |
| `ragtruth_13160` | `partial_support` | `partial_support` | `answer_overreach -> answer_overreach` |
| `ragtruth_13163` | `partial_support` | `partial_support` | `answer_overreach -> answer_overreach` |
| `ragtruth_13233` | `no_failure_detected` | `partial_support` | `no_failure_detected -> answer_overreach` |
| `ragtruth_13293` | `partial_support` | `partial_support` | `answer_overreach -> answer_overreach` |
| `ragtruth_13309` | `no_failure_detected` | `partial_support` | `no_failure_detected -> answer_overreach` |
| `ragtruth_13363` | `partial_support` | `partial_support` | `answer_overreach -> answer_overreach` |
| `ragtruth_13430` | `no_failure_detected` | `partial_support` | `no_failure_detected -> answer_overreach` |
| `ragtruth_13442` | `contradicted_answer` | `contradicted_answer, insufficient_context, should_have_abstained` | `conflicting_contexts -> conflicting_contexts` |
| `ragtruth_13445` | `no_failure_detected` | `contradicted_answer` | `no_failure_detected -> conflicting_contexts` |
| `ragtruth_13560` | `no_failure_detected` | `no_failure_detected` | `no_failure_detected -> no_failure_detected` |
| `ragtruth_13563` | `no_failure_detected` | `partial_support` | `no_failure_detected -> answer_overreach` |
| `ragtruth_13720` | `no_failure_detected` | `partial_support` | `no_failure_detected -> answer_overreach` |
| `ragtruth_13916` | `no_failure_detected` | `partial_support` | `no_failure_detected -> answer_overreach` |
| `ragtruth_14005` | `no_failure_detected` | `partial_support` | `no_failure_detected -> answer_overreach` |
| `ragtruth_14007` | `partial_support` | `no_failure_detected` | `answer_overreach -> no_failure_detected` |
| `ragtruth_14098` | `partial_support` | `partial_support` | `answer_overreach -> answer_overreach` |
| `ragtruth_14286` | `no_failure_detected` | `no_failure_detected` | `no_failure_detected -> no_failure_detected` |
| `ragtruth_14323` | `contradicted_answer` | `partial_support` | `conflicting_contexts -> answer_overreach` |
| `ragtruth_14327` | `no_failure_detected` | `insufficient_context, partial_support, should_have_abstained` | `no_failure_detected -> insufficient_context` |
| `ragtruth_14380` | `no_failure_detected` | `should_have_abstained, unsupported_answer` | `no_failure_detected -> should_have_abstained` |
| `ragtruth_14508` | `no_failure_detected` | `partial_support` | `no_failure_detected -> answer_overreach` |
| `ragtruth_14511` | `partial_support` | `partial_support` | `answer_overreach -> answer_overreach` |
| `ragtruth_14805` | `no_failure_detected` | `contradicted_answer, insufficient_context, should_have_abstained, unsupported_answer` | `no_failure_detected -> conflicting_contexts` |
| `ragtruth_14861` | `no_failure_detected` | `no_failure_detected` | `no_failure_detected -> no_failure_detected` |
| `ragtruth_14995` | `no_failure_detected` | `no_failure_detected` | `no_failure_detected -> no_failure_detected` |
| `ragtruth_15179` | `no_failure_detected` | `contradicted_answer, insufficient_context, should_have_abstained` | `no_failure_detected -> insufficient_context` |
| `ragtruth_15270` | `no_failure_detected` | `no_failure_detected` | `no_failure_detected -> no_failure_detected` |
| `ragtruth_15272` | `no_failure_detected` | `partial_support` | `no_failure_detected -> answer_overreach` |
| `ragtruth_15467` | `no_failure_detected` | `partial_support` | `no_failure_detected -> answer_overreach` |
| `ragtruth_15628` | `no_failure_detected` | `contradicted_answer, unsupported_answer` | `no_failure_detected -> conflicting_contexts` |
| `ragtruth_15712` | `contradicted_answer` | `contradicted_answer` | `conflicting_contexts -> conflicting_contexts` |
| `ragtruth_15718` | `no_failure_detected` | `partial_support` | `no_failure_detected -> answer_overreach` |
| `ragtruth_15755` | `partial_support` | `partial_support` | `answer_overreach -> answer_overreach` |
| `ragtruth_15780` | `no_failure_detected` | `partial_support` | `no_failure_detected -> answer_overreach` |
| `ragtruth_15786` | `no_failure_detected` | `contradicted_answer` | `no_failure_detected -> conflicting_contexts` |
| `ragtruth_15788` | `no_failure_detected` | `partial_support` | `no_failure_detected -> answer_overreach` |
| `ragtruth_15904` | `no_failure_detected` | `partial_support` | `no_failure_detected -> answer_overreach` |
| `ragtruth_15933` | `no_failure_detected` | `contradicted_answer, insufficient_context, should_have_abstained, unsupported_answer` | `no_failure_detected -> should_have_abstained` |
| `ragtruth_15969` | `no_failure_detected` | `partial_support` | `no_failure_detected -> answer_overreach` |
| `ragtruth_16056` | `partial_support` | `no_failure_detected` | `answer_overreach -> no_failure_detected` |
| `ragtruth_16057` | `no_failure_detected` | `partial_support` | `no_failure_detected -> answer_overreach` |
| `ragtruth_16118` | `no_failure_detected` | `no_failure_detected` | `no_failure_detected -> no_failure_detected` |
| `ragtruth_16119` | `no_failure_detected` | `partial_support` | `no_failure_detected -> answer_overreach` |
| `ragtruth_16565` | `no_failure_detected` | `partial_support` | `no_failure_detected -> answer_overreach` |
| `ragtruth_16795` | `no_failure_detected` | `no_failure_detected` | `no_failure_detected -> no_failure_detected` |
| `ragtruth_16895` | `partial_support` | `partial_support` | `answer_overreach -> answer_overreach` |
| `ragtruth_17250` | `no_failure_detected` | `partial_support` | `no_failure_detected -> answer_overreach` |
