# RAGTruth Error Analysis

This report turns the RAGTruth calibration result into concrete engineering targets. It is not a publishable SOTA claim by itself.

## Summary

| Metric | Value |
| --- | ---: |
| Cases | 200 |
| Misses | 148 |
| Miss rate | 0.740 |
| Failure macro-F1 | 0.343 |
| Root-cause accuracy | 0.450 |
| Evidence span overlap | 0.551 |
| Dangerous false greens | 1 |
| Span localization misses | 48 |

## Top Calibration Targets

### Dangerous False Greens

| Case | Task | Source | Expected | Predicted | Root Cause | Span Overlap |
| --- | --- | --- | --- | --- | --- | ---: |
| `ragtruth_16056` | `QA` | `MARCO` | `partial_support` | `no_failure_detected` | `answer_overreach -> no_failure_detected` | 1.000 |

### Partial-Support Misses

| Case | Task | Source | Expected | Predicted | Root Cause | Span Overlap |
| --- | --- | --- | --- | --- | --- | ---: |
| `ragtruth_16056` | `QA` | `MARCO` | `partial_support` | `no_failure_detected` | `answer_overreach -> no_failure_detected` | 1.000 |
| `ragtruth_9775` | `Data2txt` | `Yelp` | `partial_support` | `contradicted_answer` | `answer_overreach -> conflicting_contexts` | 0.144 |
| `ragtruth_6250` | `Data2txt` | `Yelp` | `partial_support` | `contradicted_answer` | `answer_overreach -> conflicting_contexts` | 0.155 |
| `ragtruth_8561` | `Data2txt` | `Yelp` | `partial_support` | `contradicted_answer` | `answer_overreach -> conflicting_contexts` | 0.615 |
| `ragtruth_730` | `Summary` | `CNN/DM` | `partial_support` | `contradicted_answer` | `answer_overreach -> conflicting_contexts` | 0.843 |
| `ragtruth_906` | `Summary` | `CNN/DM` | `partial_support` | `contradicted_answer` | `answer_overreach -> conflicting_contexts` | 0.905 |
| `ragtruth_3638` | `Summary` | `CNN/DM` | `partial_support` | `contradicted_answer` | `answer_overreach -> conflicting_contexts` | 0.932 |
| `ragtruth_10111` | `Data2txt` | `Yelp` | `partial_support` | `contradicted_answer` | `answer_overreach -> conflicting_contexts` | 0.054 |
| `ragtruth_7236` | `Data2txt` | `Yelp` | `partial_support` | `contradicted_answer` | `answer_overreach -> conflicting_contexts` | 0.061 |
| `ragtruth_14007` | `QA` | `MARCO` | `partial_support` | `contradicted_answer` | `answer_overreach -> conflicting_contexts` | 0.735 |

### Contradicted-Answer Misses

| Case | Task | Source | Expected | Predicted | Root Cause | Span Overlap |
| --- | --- | --- | --- | --- | --- | ---: |
| `ragtruth_4263` | `Summary` | `Recent News` | `contradicted_answer` | `partial_support` | `conflicting_contexts -> answer_overreach` | 0.500 |
| `ragtruth_7052` | `Data2txt` | `Yelp` | `contradicted_answer` | `partial_support` | `conflicting_contexts -> answer_overreach` | 0.327 |
| `ragtruth_1990` | `Summary` | `CNN/DM` | `contradicted_answer` | `partial_support` | `conflicting_contexts -> answer_overreach` | 0.636 |
| `ragtruth_3639` | `Summary` | `CNN/DM` | `contradicted_answer` | `partial_support` | `conflicting_contexts -> answer_overreach` | 0.785 |
| `ragtruth_4211` | `Summary` | `Recent News` | `contradicted_answer` | `partial_support` | `conflicting_contexts -> answer_overreach` | 0.822 |
| `ragtruth_12435` | `QA` | `MARCO` | `contradicted_answer` | `partial_support` | `conflicting_contexts -> answer_overreach` | 0.938 |
| `ragtruth_12917` | `QA` | `MARCO` | `contradicted_answer` | `partial_support` | `conflicting_contexts -> answer_overreach` | 1.000 |
| `ragtruth_543` | `Summary` | `CNN/DM` | `contradicted_answer` | `partial_support` | `conflicting_contexts -> answer_overreach` | 0.500 |
| `ragtruth_1698` | `Summary` | `CNN/DM` | `contradicted_answer` | `partial_support` | `conflicting_contexts -> answer_overreach` | 0.667 |
| `ragtruth_5482` | `Summary` | `Recent News` | `contradicted_answer` | `partial_support` | `conflicting_contexts -> answer_overreach` | 0.763 |

### Source-Spans With Bad Localization

| Case | Task | Source | Expected | Predicted | Root Cause | Span Overlap |
| --- | --- | --- | --- | --- | --- | ---: |
| `ragtruth_6550` | `Data2txt` | `Yelp` | `contradicted_answer` | `contradicted_answer` | `conflicting_contexts -> conflicting_contexts` | 0.654 |
| `ragtruth_8153` | `Data2txt` | `Yelp` | `contradicted_answer` | `contradicted_answer` | `conflicting_contexts -> conflicting_contexts` | 0.174 |
| `ragtruth_8474` | `Data2txt` | `Yelp` | `contradicted_answer` | `contradicted_answer` | `conflicting_contexts -> conflicting_contexts` | 0.099 |
| `ragtruth_9552` | `Data2txt` | `Yelp` | `contradicted_answer` | `contradicted_answer` | `conflicting_contexts -> conflicting_contexts` | 0.113 |
| `ragtruth_8727` | `Data2txt` | `Yelp` | `contradicted_answer` | `contradicted_answer` | `conflicting_contexts -> conflicting_contexts` | 0.115 |
| `ragtruth_10006` | `Data2txt` | `Yelp` | `contradicted_answer` | `contradicted_answer` | `conflicting_contexts -> conflicting_contexts` | 0.401 |
| `ragtruth_4263` | `Summary` | `Recent News` | `contradicted_answer` | `partial_support` | `conflicting_contexts -> answer_overreach` | 0.500 |
| `ragtruth_7138` | `Data2txt` | `Yelp` | `contradicted_answer` | `contradicted_answer` | `conflicting_contexts -> conflicting_contexts` | 0.086 |
| `ragtruth_5691` | `Data2txt` | `Yelp` | `contradicted_answer` | `contradicted_answer` | `conflicting_contexts -> conflicting_contexts` | 0.137 |
| `ragtruth_9775` | `Data2txt` | `Yelp` | `partial_support` | `contradicted_answer` | `answer_overreach -> conflicting_contexts` | 0.144 |

### Root-Cause Misses

| Case | Task | Source | Expected | Predicted | Root Cause | Span Overlap |
| --- | --- | --- | --- | --- | --- | ---: |
| `ragtruth_16056` | `QA` | `MARCO` | `partial_support` | `no_failure_detected` | `answer_overreach -> no_failure_detected` | 1.000 |
| `ragtruth_4263` | `Summary` | `Recent News` | `contradicted_answer` | `partial_support` | `conflicting_contexts -> answer_overreach` | 0.500 |
| `ragtruth_9775` | `Data2txt` | `Yelp` | `partial_support` | `contradicted_answer` | `answer_overreach -> conflicting_contexts` | 0.144 |
| `ragtruth_6250` | `Data2txt` | `Yelp` | `partial_support` | `contradicted_answer` | `answer_overreach -> conflicting_contexts` | 0.155 |
| `ragtruth_7052` | `Data2txt` | `Yelp` | `contradicted_answer` | `partial_support` | `conflicting_contexts -> answer_overreach` | 0.327 |
| `ragtruth_8561` | `Data2txt` | `Yelp` | `partial_support` | `contradicted_answer` | `answer_overreach -> conflicting_contexts` | 0.615 |
| `ragtruth_1990` | `Summary` | `CNN/DM` | `contradicted_answer` | `partial_support` | `conflicting_contexts -> answer_overreach` | 0.636 |
| `ragtruth_3639` | `Summary` | `CNN/DM` | `contradicted_answer` | `partial_support` | `conflicting_contexts -> answer_overreach` | 0.785 |
| `ragtruth_4211` | `Summary` | `Recent News` | `contradicted_answer` | `partial_support` | `conflicting_contexts -> answer_overreach` | 0.822 |
| `ragtruth_730` | `Summary` | `CNN/DM` | `partial_support` | `contradicted_answer` | `answer_overreach -> conflicting_contexts` | 0.843 |

## Miss Groups

### By Task Type

| Value | Cases | Misses | Miss Rate | False Greens | Root Misses | Span Misses |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `Data2txt` | 64 | 57 | 0.891 | 0 | 29 | 34 |
| `Summary` | 76 | 50 | 0.658 | 0 | 42 | 11 |
| `QA` | 60 | 41 | 0.683 | 1 | 39 | 3 |

### By Source Dataset

| Value | Cases | Misses | Miss Rate | False Greens | Root Misses | Span Misses |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `Yelp` | 64 | 57 | 0.891 | 0 | 29 | 34 |
| `MARCO` | 60 | 41 | 0.683 | 1 | 39 | 3 |
| `CNN/DM` | 49 | 33 | 0.673 | 0 | 29 | 6 |
| `Recent News` | 27 | 17 | 0.630 | 0 | 13 | 5 |

### By Model

| Value | Cases | Misses | Miss Rate | False Greens | Root Misses | Span Misses |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `llama-2-7b-chat` | 33 | 28 | 0.848 | 0 | 18 | 12 |
| `llama-2-13b-chat` | 35 | 28 | 0.800 | 0 | 20 | 10 |
| `llama-2-70b-chat` | 35 | 26 | 0.743 | 0 | 18 | 9 |
| `gpt-4-0613` | 31 | 24 | 0.774 | 1 | 22 | 4 |
| `gpt-3.5-turbo-0613` | 32 | 24 | 0.750 | 0 | 22 | 4 |
| `mistral-7B-instruct` | 34 | 18 | 0.529 | 0 | 10 | 9 |

### By RAGTruth Label Type

| Value | Cases | Misses | Miss Rate | False Greens | Root Misses | Span Misses |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `no_hallucination_span` | 112 | 86 | 0.768 | 0 | 86 | 0 |
| `Evident Conflict` | 41 | 35 | 0.854 | 0 | 10 | 29 |
| `Evident Baseless Info` | 44 | 30 | 0.682 | 1 | 12 | 23 |
| `Subtle Baseless Info` | 11 | 4 | 0.364 | 0 | 2 | 3 |
| `Subtle Conflict` | 2 | 1 | 0.500 | 0 | 1 | 1 |

### By Expected Label

| Value | Cases | Misses | Miss Rate | False Greens | Root Misses | Span Misses |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `no_failure_detected` | 112 | 86 | 0.768 | 0 | 86 | 0 |
| `contradicted_answer` | 43 | 36 | 0.837 | 0 | 11 | 30 |
| `partial_support` | 44 | 25 | 0.568 | 1 | 13 | 17 |
| `unsupported` | 1 | 1 | 1.000 | 0 | 0 | 1 |

## Root Cause Confusion

| Expected | Predicted | Count |
| --- | --- | ---: |
| `no_failure_detected` | `answer_overreach` | 64 |
| `answer_overreach` | `answer_overreach` | 32 |
| `conflicting_contexts` | `conflicting_contexts` | 32 |
| `no_failure_detected` | `no_failure_detected` | 26 |
| `no_failure_detected` | `conflicting_contexts` | 22 |
| `answer_overreach` | `conflicting_contexts` | 12 |
| `conflicting_contexts` | `answer_overreach` | 11 |
| `answer_overreach` | `no_failure_detected` | 1 |
