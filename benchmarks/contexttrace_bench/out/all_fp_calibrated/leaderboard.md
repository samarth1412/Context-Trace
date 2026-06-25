# ContextTrace-Bench Leaderboard

| System | Mode | Cases | Failure Macro-F1 | Root Cause Accuracy | Citation Error F1 | Span Overlap | Latency p95 ms | Cost / 100 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| ContextTrace | `semantic` | 500 | 1.0 | 1.0 | 1.0 | 0.862 | 13.435 | 0.0 |

`N/A` means the candidate did not report that diagnostic field; it is not counted as an attempted failure.

## Diagnostic Coverage

| System | Root Cause Reported | Citation Status Reported | Evidence Spans Reported |
| --- | ---: | ---: | ---: |
| ContextTrace | 500 / 500 | 500 / 500 | 188 / 500 |

Competitor rows are valid only when produced from a candidate prediction JSON scored by this harness. Shared faithfulness-style metrics are directly comparable; diagnostic attribution metrics require the candidate to report that field.
