# ContextTrace-Bench Error Analysis

- Benchmark: `ContextTrace-Bench`
- Mode: `semantic`
- Case set: `external_case_pack`
- Cases: `200`
- Benchmark misses: `1`
- Label misses: `1`

## Confusion Matrix

| Expected | Predicted | Count |
| --- | --- | ---: |
| `should_have_abstained, unsupported_answer` | `should_have_abstained, unsupported_answer` | 100 |
| `no_failure_detected` | `no_failure_detected` | 99 |
| `no_failure_detected` | `should_have_abstained, unsupported_answer` | 1 |

## Root-Cause Confusion

| Expected Root | Predicted Root | Count |
| --- | --- | ---: |
| `should_have_abstained` | `should_have_abstained` | 100 |
| `no_failure_detected` | `no_failure_detected` | 99 |
| `no_failure_detected` | `should_have_abstained` | 1 |

## False-Positive Labels

| Label | Count |
| --- | ---: |
| `should_have_abstained` | 1 |
| `unsupported_answer` | 1 |

## Cases To Review

- `ares_nq_example_6751220433242447969_2`: expected `['no_failure_detected']`, predicted `['should_have_abstained', 'unsupported_answer']`, root `no_failure_detected -> should_have_abstained`
  Claim: one.
  Missing: one
