# ContextTrace-Bench Error Analysis

- Benchmark: `ContextTrace-Bench`
- Mode: `semantic`
- Case set: `public_holdout`
- Cases: `150`
- Benchmark misses: `0`
- Label misses: `0`

## Confusion Matrix

| Expected | Predicted | Count |
| --- | --- | ---: |
| `no_failure_detected` | `no_failure_detected` | 73 |
| `contradicted_answer, should_have_abstained` | `contradicted_answer, should_have_abstained` | 29 |
| `partial_support` | `partial_support` | 26 |
| `citation_mismatch` | `citation_mismatch` | 21 |
| `should_have_abstained, unsupported_answer` | `should_have_abstained, unsupported_answer` | 1 |

## Root-Cause Confusion

| Expected Root | Predicted Root | Count |
| --- | --- | ---: |
| `no_failure_detected` | `no_failure_detected` | 73 |
| `conflicting_contexts` | `conflicting_contexts` | 29 |
| `answer_overreach` | `answer_overreach` | 26 |
| `wrong_source_cited` | `wrong_source_cited` | 21 |
| `should_have_abstained` | `should_have_abstained` | 1 |

## False-Positive Labels

| Label | Count |
| --- | ---: |
| `none` | 0 |

## Cases To Review

No benchmark misses under the current labeled checks.
