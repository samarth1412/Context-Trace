# ContextTrace-Bench Leaderboard

| System | Mode | Cases | Failure Macro-F1 | Root Cause Accuracy | Citation Error F1 | Span Overlap | Latency p95 ms | Cost / 100 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| ContextTrace | `semantic` | 20 | 0.144 | 0.25 | 1.0 | N/A | 518.777 | 0.0 |

`N/A` means the candidate did not report that diagnostic field; it is not counted as an attempted failure.

## Diagnostic Coverage

| System | Root Cause Reported | Citation Status Reported | Evidence Spans Reported |
| --- | ---: | ---: | ---: |
| ContextTrace | 20 / 20 | 20 / 20 | 0 / 20 |

Competitor rows are valid only when produced from a candidate prediction JSON scored by this harness. Shared faithfulness-style metrics are directly comparable; diagnostic attribution metrics require the candidate to report that field.
