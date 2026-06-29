# ContextTrace-Bench Leaderboard

| System | Mode | Cases | Failure Macro-F1 | Root Cause Accuracy | Citation Error F1 | Span Overlap | Latency p95 ms | Cost / 100 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| ContextTrace | `semantic` | 200 | 0.995 | 0.995 | 1.0 | 1.0 | 18.619 | 0.0 |
| RAGAS | `gpt-4.1-mini` | 200 | 0.471 | N/A | N/A | N/A | 14821.814 | 0.0 |
| DeepEval | `gpt-4.1-mini` | 200 | 0.388 | N/A | N/A | N/A | 7934.588 | 0.0 |

`N/A` means the candidate did not report that diagnostic field; it is not counted as an attempted failure.

## Diagnostic Coverage

| System | Root Cause Reported | Citation Status Reported | Evidence Spans Reported |
| --- | ---: | ---: | ---: |
| ContextTrace | 200 / 200 | 200 / 200 | 89 / 200 |
| RAGAS | 0 / 200 | 0 / 200 | 0 / 200 |
| DeepEval | 0 / 200 | 0 / 200 | 0 / 200 |

Competitor rows are valid only when produced from a candidate prediction JSON scored by this harness. Shared faithfulness-style metrics are directly comparable; diagnostic attribution metrics require the candidate to report that field.
