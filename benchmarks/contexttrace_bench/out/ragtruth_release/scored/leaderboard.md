# ContextTrace-Bench Leaderboard

| System | Mode | Cases | Failure Macro-F1 | Root Cause Accuracy | Citation Error F1 | Span Overlap | Latency p95 ms | Cost / 100 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| ContextTrace | `semantic` | 200 | 0.955 | 0.955 | 1.0 | 0.786 | 2442.996 | 0.0 |
| RAGAS | `gpt-4.1-mini max_output_tokens=32768` | 200 | 0.152 | N/A | N/A | N/A | 48699.394 | 0.0 |

`N/A` means the candidate did not report that diagnostic field; it is not counted as an attempted failure.

## Diagnostic Coverage

| System | Root Cause Reported | Citation Status Reported | Evidence Spans Reported |
| --- | ---: | ---: | ---: |
| ContextTrace | 200 / 200 | 200 / 200 | 75 / 200 |
| RAGAS | 0 / 200 | 0 / 200 | 0 / 200 |

Competitor rows are valid only when produced from a candidate prediction JSON scored by this harness. Shared faithfulness-style metrics are directly comparable; diagnostic attribution metrics require the candidate to report that field.
