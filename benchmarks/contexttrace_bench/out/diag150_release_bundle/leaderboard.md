# ContextTrace-Bench Leaderboard

| System | Mode | Cases | Failure Macro-F1 | Root Cause Accuracy | Citation Error F1 | Span Overlap | Latency p95 ms | Cost / 100 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| ContextTrace | `semantic` | 150 | 1.0 | 1.0 | 1.0 | 0.95 | 11.463 | 0.0 |
| OpenAI diagnostic judge | `gpt-4.1-mini` | 150 | 0.931 | 0.953 | 1.0 | 0.921 | 7328.58 | 0.0 |

`N/A` means the candidate did not report that diagnostic field; it is not counted as an attempted failure.

## Diagnostic Coverage

| System | Root Cause Reported | Citation Status Reported | Evidence Spans Reported |
| --- | ---: | ---: | ---: |
| ContextTrace | 150 / 150 | 150 / 150 | 149 / 150 |
| OpenAI diagnostic judge | 150 / 150 | 103 / 150 | 149 / 150 |

Competitor rows are valid only when produced from a candidate prediction JSON scored by this harness. Shared faithfulness-style metrics are directly comparable; diagnostic attribution metrics require the candidate to report that field.
