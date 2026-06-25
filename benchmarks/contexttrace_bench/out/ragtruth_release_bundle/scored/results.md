# ContextTrace-Bench Results

- Benchmark: `ContextTrace-Bench`
- Mode: `semantic`
- Case set: `external_case_pack`
- Case source: RAGTruth case pack adapted for ContextTrace external validation. These cases are scaffolding until answer-side hallucination spans are human-mapped to source-side evidence spans. from benchmarks\contexttrace_bench\out\ragtruth_release\ragtruth_reviewed_case_pack.json

## Summary

| Metric | Value |
| --- | ---: |
| `cases` | 200 |
| `failure_label_exact_match_rate` | 0.445 |
| `failure_label_macro_f1` | 0.343 |
| `claim_verdict_macro_f1` | 0.143 |
| `claim_verdict_match_rate` | 0.0 |
| `root_cause_accuracy` | 0.45 |
| `citation_error_precision` | 1.0 |
| `citation_error_recall` | 1.0 |
| `citation_error_f1` | 1.0 |
| `evidence_span_overlap` | 0.551 |
| `root_cause_reported_cases` | 200 |
| `citation_status_reported_cases` | 200 |
| `evidence_span_reported_cases` | 76 |
| `latency_p50_ms` | 129.285 |
| `latency_p95_ms` | 467.435 |
| `cost_per_100_traces_usd` | 0.0 |
| `dangerous_false_green_rate` | 0.005 |

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
| `failure_label_macro_f1` | 0.343 | 0.281 to 0.501 | 100 |
| `claim_verdict_macro_f1` | 0.143 | 0.109 to 0.733 | 100 |
| `root_cause_accuracy` | 0.45 | 0.37 to 0.515 | 100 |
| `citation_error_f1` | 1.0 | 1.0 to 1.0 | 100 |
| `evidence_span_overlap` | 0.551 | 0.48 to 0.63 | 100 |
| `dangerous_false_green_rate` | 0.005 | 0.0 to 0.015 | 100 |

## Failure Label Breakdown

| Label | Precision | Recall | F1 | TP | FP | FN |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `contradicted_answer` | 0.485 | 0.744 | 0.587 | 32 | 34 | 11 |
| `no_failure_detected` | 0.963 | 0.232 | 0.374 | 26 | 1 | 86 |
| `partial_support` | 0.29 | 0.705 | 0.411 | 31 | 76 | 13 |
| `unsupported` | 1.0 | 0.0 | 0.0 | 0 | 0 | 1 |

## SOTA Readiness Gates

| Metric | Gate | Value | Status |
| --- | ---: | ---: | --- |
| `failure_label_macro_f1` | `>= 0.95` | 0.343 | fail |
| `claim_verdict_macro_f1` | `>= 0.95` | 0.143 | fail |
| `root_cause_accuracy` | `>= 0.9` | 0.45 | fail |
| `citation_error_f1` | `>= 0.9` | 1.0 | pass |
| `evidence_span_overlap` | `>= 0.75` | 0.551 | fail |
| `dangerous_false_green_rate` | `<= 0.01` | 0.005 | pass |

## Misses

| Case | Expected | Predicted | Root Cause |
| --- | --- | --- | --- |
| `ragtruth_58` | `partial_support` | `contradicted_answer` | `answer_overreach -> conflicting_contexts` |
| `ragtruth_59` | `no_failure_detected` | `contradicted_answer` | `no_failure_detected -> conflicting_contexts` |
| `ragtruth_123` | `partial_support` | `partial_support` | `answer_overreach -> answer_overreach` |
| `ragtruth_334` | `no_failure_detected` | `partial_support` | `no_failure_detected -> answer_overreach` |
| `ragtruth_351` | `no_failure_detected` | `partial_support` | `no_failure_detected -> answer_overreach` |
| `ragtruth_355` | `no_failure_detected` | `partial_support` | `no_failure_detected -> answer_overreach` |
| `ragtruth_543` | `contradicted_answer` | `partial_support` | `conflicting_contexts -> answer_overreach` |
| `ragtruth_586` | `no_failure_detected` | `partial_support` | `no_failure_detected -> answer_overreach` |
| `ragtruth_730` | `partial_support` | `contradicted_answer` | `answer_overreach -> conflicting_contexts` |
| `ragtruth_878` | `no_failure_detected` | `partial_support` | `no_failure_detected -> answer_overreach` |
| `ragtruth_906` | `partial_support` | `contradicted_answer` | `answer_overreach -> conflicting_contexts` |
| `ragtruth_924` | `no_failure_detected` | `partial_support` | `no_failure_detected -> answer_overreach` |
| `ragtruth_1153` | `no_failure_detected` | `contradicted_answer` | `no_failure_detected -> conflicting_contexts` |
| `ragtruth_1355` | `no_failure_detected` | `partial_support` | `no_failure_detected -> answer_overreach` |
| `ragtruth_1513` | `partial_support` | `contradicted_answer` | `answer_overreach -> conflicting_contexts` |
| `ragtruth_1566` | `no_failure_detected` | `partial_support` | `no_failure_detected -> answer_overreach` |
| `ragtruth_1648` | `no_failure_detected` | `contradicted_answer` | `no_failure_detected -> conflicting_contexts` |
| `ragtruth_1678` | `no_failure_detected` | `partial_support` | `no_failure_detected -> answer_overreach` |
| `ragtruth_1683` | `no_failure_detected` | `contradicted_answer` | `no_failure_detected -> conflicting_contexts` |
| `ragtruth_1698` | `contradicted_answer` | `partial_support` | `conflicting_contexts -> answer_overreach` |
| `ragtruth_1990` | `contradicted_answer` | `partial_support` | `conflicting_contexts -> answer_overreach` |
| `ragtruth_2136` | `no_failure_detected` | `partial_support` | `no_failure_detected -> answer_overreach` |
| `ragtruth_2359` | `no_failure_detected` | `partial_support` | `no_failure_detected -> answer_overreach` |
| `ragtruth_2469` | `no_failure_detected` | `partial_support` | `no_failure_detected -> answer_overreach` |
| `ragtruth_2653` | `no_failure_detected` | `partial_support` | `no_failure_detected -> answer_overreach` |
| `ragtruth_2675` | `no_failure_detected` | `partial_support` | `no_failure_detected -> answer_overreach` |
| `ragtruth_2892` | `no_failure_detected` | `partial_support` | `no_failure_detected -> answer_overreach` |
| `ragtruth_3611` | `no_failure_detected` | `partial_support` | `no_failure_detected -> answer_overreach` |
| `ragtruth_3638` | `partial_support` | `contradicted_answer` | `answer_overreach -> conflicting_contexts` |
| `ragtruth_3639` | `contradicted_answer` | `partial_support` | `conflicting_contexts -> answer_overreach` |
| `ragtruth_3770` | `no_failure_detected` | `partial_support` | `no_failure_detected -> answer_overreach` |
| `ragtruth_3771` | `no_failure_detected` | `contradicted_answer` | `no_failure_detected -> conflicting_contexts` |
| `ragtruth_4211` | `contradicted_answer` | `partial_support` | `conflicting_contexts -> answer_overreach` |
| `ragtruth_4263` | `contradicted_answer` | `partial_support` | `conflicting_contexts -> answer_overreach` |
| `ragtruth_4348` | `no_failure_detected` | `partial_support` | `no_failure_detected -> answer_overreach` |
| `ragtruth_4524` | `no_failure_detected` | `partial_support` | `no_failure_detected -> answer_overreach` |
| `ragtruth_4527` | `no_failure_detected` | `partial_support` | `no_failure_detected -> answer_overreach` |
| `ragtruth_4777` | `no_failure_detected` | `partial_support` | `no_failure_detected -> answer_overreach` |
| `ragtruth_4955` | `no_failure_detected` | `contradicted_answer` | `no_failure_detected -> conflicting_contexts` |
| `ragtruth_5201` | `no_failure_detected` | `contradicted_answer` | `no_failure_detected -> conflicting_contexts` |
| `ragtruth_5274` | `no_failure_detected` | `partial_support` | `no_failure_detected -> answer_overreach` |
| `ragtruth_5416` | `no_failure_detected` | `partial_support` | `no_failure_detected -> answer_overreach` |
| `ragtruth_5417` | `unsupported` | `partial_support` | `answer_overreach -> answer_overreach` |
| `ragtruth_5482` | `contradicted_answer` | `partial_support` | `conflicting_contexts -> answer_overreach` |
| `ragtruth_5829` | `no_failure_detected` | `partial_support` | `no_failure_detected -> answer_overreach` |
| `ragtruth_5850` | `no_failure_detected` | `contradicted_answer` | `no_failure_detected -> conflicting_contexts` |
| `ragtruth_6250` | `partial_support` | `contradicted_answer` | `answer_overreach -> conflicting_contexts` |
| `ragtruth_6913` | `no_failure_detected` | `partial_support` | `no_failure_detected -> answer_overreach` |
| `ragtruth_6996` | `no_failure_detected` | `partial_support` | `no_failure_detected -> answer_overreach` |
| `ragtruth_7008` | `no_failure_detected` | `partial_support` | `no_failure_detected -> answer_overreach` |
| `ragtruth_7019` | `no_failure_detected` | `partial_support` | `no_failure_detected -> answer_overreach` |
| `ragtruth_7052` | `contradicted_answer` | `partial_support` | `conflicting_contexts -> answer_overreach` |
| `ragtruth_7236` | `partial_support` | `contradicted_answer` | `answer_overreach -> conflicting_contexts` |
| `ragtruth_7279` | `no_failure_detected` | `partial_support` | `no_failure_detected -> answer_overreach` |
| `ragtruth_7281` | `no_failure_detected` | `partial_support` | `no_failure_detected -> answer_overreach` |
| `ragtruth_8557` | `no_failure_detected` | `contradicted_answer` | `no_failure_detected -> conflicting_contexts` |
| `ragtruth_8561` | `partial_support` | `contradicted_answer` | `answer_overreach -> conflicting_contexts` |
| `ragtruth_8664` | `no_failure_detected` | `partial_support` | `no_failure_detected -> answer_overreach` |
| `ragtruth_8778` | `no_failure_detected` | `contradicted_answer` | `no_failure_detected -> conflicting_contexts` |
| `ragtruth_9212` | `no_failure_detected` | `partial_support` | `no_failure_detected -> answer_overreach` |
| `ragtruth_9604` | `no_failure_detected` | `partial_support` | `no_failure_detected -> answer_overreach` |
| `ragtruth_9679` | `no_failure_detected` | `partial_support` | `no_failure_detected -> answer_overreach` |
| `ragtruth_9775` | `partial_support` | `contradicted_answer` | `answer_overreach -> conflicting_contexts` |
| `ragtruth_9937` | `no_failure_detected` | `partial_support` | `no_failure_detected -> answer_overreach` |
| `ragtruth_10072` | `no_failure_detected` | `partial_support` | `no_failure_detected -> answer_overreach` |
| `ragtruth_10111` | `partial_support` | `contradicted_answer` | `answer_overreach -> conflicting_contexts` |
| `ragtruth_10352` | `no_failure_detected` | `contradicted_answer` | `no_failure_detected -> conflicting_contexts` |
| `ragtruth_10463` | `no_failure_detected` | `partial_support` | `no_failure_detected -> answer_overreach` |
| `ragtruth_10543` | `no_failure_detected` | `contradicted_answer` | `no_failure_detected -> conflicting_contexts` |
| `ragtruth_10547` | `no_failure_detected` | `partial_support` | `no_failure_detected -> answer_overreach` |
| `ragtruth_10819` | `no_failure_detected` | `contradicted_answer` | `no_failure_detected -> conflicting_contexts` |
| `ragtruth_11286` | `no_failure_detected` | `contradicted_answer` | `no_failure_detected -> conflicting_contexts` |
| `ragtruth_11520` | `no_failure_detected` | `contradicted_answer` | `no_failure_detected -> conflicting_contexts` |
| `ragtruth_11908` | `partial_support` | `contradicted_answer` | `answer_overreach -> conflicting_contexts` |
| `ragtruth_12240` | `no_failure_detected` | `contradicted_answer` | `no_failure_detected -> conflicting_contexts` |
| `ragtruth_12298` | `no_failure_detected` | `partial_support` | `no_failure_detected -> answer_overreach` |
| `ragtruth_12435` | `contradicted_answer` | `partial_support` | `conflicting_contexts -> answer_overreach` |
| `ragtruth_12469` | `no_failure_detected` | `partial_support` | `no_failure_detected -> answer_overreach` |
| `ragtruth_12690` | `no_failure_detected` | `partial_support` | `no_failure_detected -> answer_overreach` |
| `ragtruth_12691` | `no_failure_detected` | `partial_support` | `no_failure_detected -> answer_overreach` |
| `ragtruth_12917` | `contradicted_answer` | `partial_support` | `conflicting_contexts -> answer_overreach` |
| `ragtruth_13073` | `no_failure_detected` | `partial_support` | `no_failure_detected -> answer_overreach` |
| `ragtruth_13159` | `no_failure_detected` | `partial_support` | `no_failure_detected -> answer_overreach` |
| `ragtruth_13233` | `no_failure_detected` | `partial_support` | `no_failure_detected -> answer_overreach` |
| `ragtruth_13309` | `no_failure_detected` | `partial_support` | `no_failure_detected -> answer_overreach` |
| `ragtruth_13430` | `no_failure_detected` | `partial_support` | `no_failure_detected -> answer_overreach` |
| `ragtruth_13445` | `no_failure_detected` | `contradicted_answer` | `no_failure_detected -> conflicting_contexts` |
| `ragtruth_13563` | `no_failure_detected` | `partial_support` | `no_failure_detected -> answer_overreach` |
| `ragtruth_13720` | `no_failure_detected` | `partial_support` | `no_failure_detected -> answer_overreach` |
| `ragtruth_13916` | `no_failure_detected` | `partial_support` | `no_failure_detected -> answer_overreach` |
| `ragtruth_14005` | `no_failure_detected` | `partial_support` | `no_failure_detected -> answer_overreach` |
| `ragtruth_14007` | `partial_support` | `contradicted_answer` | `answer_overreach -> conflicting_contexts` |
| `ragtruth_14323` | `contradicted_answer` | `partial_support` | `conflicting_contexts -> answer_overreach` |
| `ragtruth_14327` | `no_failure_detected` | `partial_support` | `no_failure_detected -> answer_overreach` |
| `ragtruth_14380` | `no_failure_detected` | `partial_support` | `no_failure_detected -> answer_overreach` |
| `ragtruth_14508` | `no_failure_detected` | `partial_support` | `no_failure_detected -> answer_overreach` |
| `ragtruth_14805` | `no_failure_detected` | `contradicted_answer` | `no_failure_detected -> conflicting_contexts` |
| `ragtruth_15179` | `no_failure_detected` | `contradicted_answer` | `no_failure_detected -> conflicting_contexts` |
| `ragtruth_15272` | `no_failure_detected` | `partial_support` | `no_failure_detected -> answer_overreach` |
| `ragtruth_15467` | `no_failure_detected` | `partial_support` | `no_failure_detected -> answer_overreach` |
| `ragtruth_15628` | `no_failure_detected` | `contradicted_answer` | `no_failure_detected -> conflicting_contexts` |
| `ragtruth_15718` | `no_failure_detected` | `partial_support` | `no_failure_detected -> answer_overreach` |
| `ragtruth_15780` | `no_failure_detected` | `partial_support` | `no_failure_detected -> answer_overreach` |
| `ragtruth_15786` | `no_failure_detected` | `contradicted_answer` | `no_failure_detected -> conflicting_contexts` |
| `ragtruth_15788` | `no_failure_detected` | `partial_support` | `no_failure_detected -> answer_overreach` |
| `ragtruth_15904` | `no_failure_detected` | `partial_support` | `no_failure_detected -> answer_overreach` |
| `ragtruth_15933` | `no_failure_detected` | `contradicted_answer` | `no_failure_detected -> conflicting_contexts` |
| `ragtruth_15969` | `no_failure_detected` | `partial_support` | `no_failure_detected -> answer_overreach` |
| `ragtruth_16056` | `partial_support` | `no_failure_detected` | `answer_overreach -> no_failure_detected` |
| `ragtruth_16057` | `no_failure_detected` | `partial_support` | `no_failure_detected -> answer_overreach` |
| `ragtruth_16119` | `no_failure_detected` | `partial_support` | `no_failure_detected -> answer_overreach` |
| `ragtruth_16565` | `no_failure_detected` | `partial_support` | `no_failure_detected -> answer_overreach` |
