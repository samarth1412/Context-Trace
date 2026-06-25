# ContextTrace-Bench Error Analysis

- Benchmark: `ContextTrace-Bench`
- Mode: `semantic`
- Case set: `all`
- Cases: `500`
- Benchmark misses: `0`
- Label misses: `0`

## Confusion Matrix

| Expected | Predicted | Count |
| --- | --- | ---: |
| `should_have_abstained, unsupported_answer` | `should_have_abstained, unsupported_answer` | 314 |
| `citation_mismatch` | `citation_mismatch` | 61 |
| `no_failure_detected` | `no_failure_detected` | 56 |
| `low_authority_source` | `low_authority_source` | 28 |
| `stale_source` | `stale_source` | 28 |
| `contradicted_answer, should_have_abstained` | `contradicted_answer, should_have_abstained` | 10 |
| `partial_support` | `partial_support` | 3 |

## Root-Cause Confusion

| Expected Root | Predicted Root | Count |
| --- | --- | ---: |
| `should_have_abstained` | `should_have_abstained` | 314 |
| `no_failure_detected` | `no_failure_detected` | 56 |
| `wrong_source_cited` | `wrong_source_cited` | 32 |
| `missing_cited_source` | `missing_cited_source` | 29 |
| `low_authority_source` | `low_authority_source` | 28 |
| `stale_context` | `stale_context` | 28 |
| `conflicting_contexts` | `conflicting_contexts` | 10 |
| `answer_overreach` | `answer_overreach` | 3 |

## False-Positive Labels

| Label | Count |
| --- | ---: |
| `none` | 0 |

## Cases To Review

No benchmark misses under the current labeled checks.
