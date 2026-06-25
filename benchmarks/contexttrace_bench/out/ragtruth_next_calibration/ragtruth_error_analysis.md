# RAGTruth Error Analysis

This report turns the RAGTruth calibration result into concrete engineering targets. It is not a publishable SOTA claim by itself.

## Summary

| Metric | Value |
| --- | ---: |
| Cases | 200 |
| Misses | 38 |
| Miss rate | 0.190 |
| Failure macro-F1 | 0.950 |
| Root-cause accuracy | 0.950 |
| Evidence span overlap | 0.786 |
| Dangerous false greens | 0 |
| Span localization misses | 25 |

## Top Calibration Targets

### Dangerous False Greens

No cases in this bucket.

### Partial-Support Misses

| Case | Task | Source | Expected | Predicted | Root Cause | Span Overlap |
| --- | --- | --- | --- | --- | --- | ---: |
| `ragtruth_730` | `Summary` | `CNN/DM` | `partial_support` | `contradicted_answer` | `answer_overreach -> conflicting_contexts` | 0.843 |
| `ragtruth_14007` | `QA` | `MARCO` | `partial_support` | `contradicted_answer` | `answer_overreach -> conflicting_contexts` | 0.861 |
| `ragtruth_7236` | `Data2txt` | `Yelp` | `partial_support` | `contradicted_answer` | `answer_overreach -> conflicting_contexts` | 1.000 |

### Contradicted-Answer Misses

| Case | Task | Source | Expected | Predicted | Root Cause | Span Overlap |
| --- | --- | --- | --- | --- | --- | ---: |
| `ragtruth_7052` | `Data2txt` | `Yelp` | `contradicted_answer` | `partial_support` | `conflicting_contexts -> answer_overreach` | 0.797 |
| `ragtruth_4211` | `Summary` | `Recent News` | `contradicted_answer` | `partial_support` | `conflicting_contexts -> answer_overreach` | 0.822 |
| `ragtruth_121` | `Summary` | `CNN/DM` | `contradicted_answer` | `partial_support` | `conflicting_contexts -> answer_overreach` | 0.864 |

### Source-Spans With Bad Localization

| Case | Task | Source | Expected | Predicted | Root Cause | Span Overlap |
| --- | --- | --- | --- | --- | --- | ---: |
| `ragtruth_8153` | `Data2txt` | `Yelp` | `contradicted_answer` | `contradicted_answer` | `conflicting_contexts -> conflicting_contexts` | 0.586 |
| `ragtruth_10006` | `Data2txt` | `Yelp` | `contradicted_answer` | `contradicted_answer` | `conflicting_contexts -> conflicting_contexts` | 0.401 |
| `ragtruth_8727` | `Data2txt` | `Yelp` | `contradicted_answer` | `contradicted_answer` | `conflicting_contexts -> conflicting_contexts` | 0.487 |
| `ragtruth_7301` | `Data2txt` | `Yelp` | `contradicted_answer` | `contradicted_answer` | `conflicting_contexts -> conflicting_contexts` | 0.152 |
| `ragtruth_6250` | `Data2txt` | `Yelp` | `partial_support` | `partial_support` | `answer_overreach -> answer_overreach` | 0.393 |
| `ragtruth_6052` | `Data2txt` | `Yelp` | `contradicted_answer` | `contradicted_answer` | `conflicting_contexts -> conflicting_contexts` | 0.525 |
| `ragtruth_7011` | `Data2txt` | `Yelp` | `partial_support` | `partial_support` | `answer_overreach -> answer_overreach` | 0.577 |
| `ragtruth_1967` | `Summary` | `CNN/DM` | `contradicted_answer` | `contradicted_answer` | `conflicting_contexts -> conflicting_contexts` | 0.600 |
| `ragtruth_5417` | `Summary` | `Recent News` | `unsupported` | `unsupported` | `answer_overreach -> answer_overreach` | 0.629 |
| `ragtruth_5691` | `Data2txt` | `Yelp` | `contradicted_answer` | `contradicted_answer` | `conflicting_contexts -> conflicting_contexts` | 0.643 |

### Root-Cause Misses

| Case | Task | Source | Expected | Predicted | Root Cause | Span Overlap |
| --- | --- | --- | --- | --- | --- | ---: |
| `ragtruth_7052` | `Data2txt` | `Yelp` | `contradicted_answer` | `partial_support` | `conflicting_contexts -> answer_overreach` | 0.797 |
| `ragtruth_4211` | `Summary` | `Recent News` | `contradicted_answer` | `partial_support` | `conflicting_contexts -> answer_overreach` | 0.822 |
| `ragtruth_730` | `Summary` | `CNN/DM` | `partial_support` | `contradicted_answer` | `answer_overreach -> conflicting_contexts` | 0.843 |
| `ragtruth_14007` | `QA` | `MARCO` | `partial_support` | `contradicted_answer` | `answer_overreach -> conflicting_contexts` | 0.861 |
| `ragtruth_121` | `Summary` | `CNN/DM` | `contradicted_answer` | `partial_support` | `conflicting_contexts -> answer_overreach` | 0.864 |
| `ragtruth_7236` | `Data2txt` | `Yelp` | `partial_support` | `contradicted_answer` | `answer_overreach -> conflicting_contexts` | 1.000 |
| `ragtruth_9604` | `Data2txt` | `Yelp` | `no_failure_detected` | `partial_support` | `no_failure_detected -> answer_overreach` | N/A |
| `ragtruth_10072` | `Data2txt` | `Yelp` | `no_failure_detected` | `partial_support` | `no_failure_detected -> answer_overreach` | N/A |
| `ragtruth_15904` | `QA` | `MARCO` | `no_failure_detected` | `partial_support` | `no_failure_detected -> answer_overreach` | N/A |
| `ragtruth_15933` | `QA` | `MARCO` | `no_failure_detected` | `contradicted_answer` | `no_failure_detected -> conflicting_contexts` | N/A |

## Miss Groups

### By Task Type

| Value | Cases | Misses | Miss Rate | False Greens | Root Misses | Span Misses |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `Data2txt` | 64 | 22 | 0.344 | 0 | 4 | 17 |
| `Summary` | 76 | 12 | 0.158 | 0 | 3 | 7 |
| `QA` | 60 | 4 | 0.067 | 0 | 3 | 1 |

### By Source Dataset

| Value | Cases | Misses | Miss Rate | False Greens | Root Misses | Span Misses |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `Yelp` | 64 | 22 | 0.344 | 0 | 4 | 17 |
| `CNN/DM` | 49 | 8 | 0.163 | 0 | 2 | 4 |
| `Recent News` | 27 | 4 | 0.148 | 0 | 1 | 3 |
| `MARCO` | 60 | 4 | 0.067 | 0 | 3 | 1 |

### By Model

| Value | Cases | Misses | Miss Rate | False Greens | Root Misses | Span Misses |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `llama-2-7b-chat` | 33 | 11 | 0.333 | 0 | 2 | 8 |
| `llama-2-13b-chat` | 35 | 9 | 0.257 | 0 | 4 | 5 |
| `llama-2-70b-chat` | 35 | 7 | 0.200 | 0 | 1 | 6 |
| `mistral-7B-instruct` | 34 | 5 | 0.147 | 0 | 1 | 4 |
| `gpt-3.5-turbo-0613` | 32 | 4 | 0.125 | 0 | 1 | 1 |
| `gpt-4-0613` | 31 | 2 | 0.065 | 0 | 1 | 1 |

### By RAGTruth Label Type

| Value | Cases | Misses | Miss Rate | False Greens | Root Misses | Span Misses |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `Evident Baseless Info` | 44 | 18 | 0.409 | 0 | 4 | 12 |
| `Evident Conflict` | 41 | 16 | 0.390 | 0 | 2 | 14 |
| `no_hallucination_span` | 112 | 4 | 0.036 | 0 | 4 | 0 |
| `Subtle Conflict` | 2 | 2 | 1.000 | 0 | 1 | 1 |
| `Subtle Baseless Info` | 11 | 2 | 0.182 | 0 | 0 | 1 |

### By Expected Label

| Value | Cases | Misses | Miss Rate | False Greens | Root Misses | Span Misses |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `contradicted_answer` | 43 | 18 | 0.419 | 0 | 3 | 15 |
| `partial_support` | 42 | 15 | 0.357 | 0 | 3 | 9 |
| `no_failure_detected` | 114 | 4 | 0.035 | 0 | 4 | 0 |
| `unsupported` | 1 | 1 | 1.000 | 0 | 0 | 1 |

## Root Cause Confusion

| Expected | Predicted | Count |
| --- | --- | ---: |
| `no_failure_detected` | `no_failure_detected` | 110 |
| `answer_overreach` | `answer_overreach` | 40 |
| `conflicting_contexts` | `conflicting_contexts` | 40 |
| `answer_overreach` | `conflicting_contexts` | 3 |
| `conflicting_contexts` | `answer_overreach` | 3 |
| `no_failure_detected` | `answer_overreach` | 3 |
| `no_failure_detected` | `conflicting_contexts` | 1 |
