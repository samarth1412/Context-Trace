# CRAG Gold-Answer Grounding Calibration

- Status: `review_pending`
- Publishable: `false`
- Label scope: `unreviewed_gold_answer_proxy`
- Cases: `200`
- Proxy accepted: `95` (`47.5%`)
- Flagged for grounding review: `105` (`52.5%`)
- Truncated contexts: `511 / 1000` (`51.1%`)

These are gold-answer grounding-review statistics, not failure-detection accuracy.

## Predicted Labels

| Label | Cases |
| --- | ---: |
| `contradicted_answer` | 17 |
| `insufficient_context` | 24 |
| `no_failure_detected` | 95 |
| `partial_support` | 14 |
| `should_have_abstained` | 91 |
| `unsupported_answer` | 51 |

## By Domain

| Value | Cases | Accepted | Acceptance Rate |
| --- | ---: | ---: | ---: |
| `finance` | 60 | 17 | 28.3% |
| `movie` | 37 | 15 | 40.5% |
| `music` | 41 | 25 | 61.0% |
| `open` | 42 | 26 | 61.9% |
| `sports` | 20 | 12 | 60.0% |

## By Question Type

| Value | Cases | Accepted | Acceptance Rate |
| --- | ---: | ---: | ---: |
| `aggregation` | 29 | 14 | 48.3% |
| `comparison` | 29 | 18 | 62.1% |
| `false_premise` | 25 | 0 | 0.0% |
| `multi-hop` | 24 | 12 | 50.0% |
| `post-processing` | 25 | 6 | 24.0% |
| `set` | 25 | 17 | 68.0% |
| `simple` | 23 | 14 | 60.9% |
| `simple_w_condition` | 20 | 14 | 70.0% |

## By Static Or Dynamic

| Value | Cases | Accepted | Acceptance Rate |
| --- | ---: | ---: | ---: |
| `fast-changing` | 48 | 26 | 54.2% |
| `real-time` | 15 | 4 | 26.7% |
| `slow-changing` | 67 | 34 | 50.7% |
| `static` | 70 | 31 | 44.3% |

## By Split

| Value | Cases | Accepted | Acceptance Rate |
| --- | ---: | ---: | ---: |
| `0` | 99 | 41 | 41.4% |
| `1` | 101 | 54 | 53.5% |

## Limitations

- CRAG gold answers are correctness references, not independent labels that every answer claim is grounded by the supplied web pages.
- Proxy acceptance means ContextTrace emitted only no_failure_detected for a gold answer; it is not failure-detection accuracy.
- Flagged rows require independent source-grounding review before labels, spans, or public claims are valid.
- Truncated page contexts can create legitimate grounding-review flags.
