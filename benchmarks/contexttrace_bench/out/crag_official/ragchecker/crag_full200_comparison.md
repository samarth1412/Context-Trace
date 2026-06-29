# CRAG ContextTrace-RAGChecker Grounding Comparison

- Status: `review_pending`
- Publishable: `false`
- Label scope: `unreviewed_gold_answer_proxy`
- Matched IDs: `200 / 200`
- RAGChecker errors: `0`

| System | Proxy Accepted | Acceptance Rate | Flagged |
| --- | ---: | ---: | ---: |
| ContextTrace | 95 | 47.5% | 105 |
| RAGChecker | 93 | 46.5% | 107 |

## Agreement

| Metric | Value |
| --- | ---: |
| Agreement | 150 / 200 (75.0%) |
| Cohen's kappa | 0.4982 |
| Exact McNemar p-value | 0.887725 |
| Both accept | 69 |
| Both flag | 81 |
| ContextTrace accepts, RAGChecker flags | 26 |
| ContextTrace flags, RAGChecker accepts | 24 |

## RAGChecker Mean Diagnostics

| Metric | Mean |
| --- | ---: |
| `claim_recall` | 0.4903 |
| `context_precision` | 0.336 |
| `context_utilization` | 0.4311 |
| `f1` | 0.6428 |
| `faithfulness` | 0.5073 |
| `hallucination` | 0.1079 |
| `noise_sensitivity_in_irrelevant` | 0.006 |
| `noise_sensitivity_in_relevant` | 0.1104 |
| `precision` | 0.6857 |
| `recall` | 0.6732 |
| `self_knowledge` | 0.2948 |

## Limitations

- The compared response is the official CRAG gold answer. This isolates grounding behavior but is not a generated-RAG answer-quality comparison.
- CRAG correctness references do not independently prove that every gold-answer claim is supported by the supplied pages.
- Acceptance rates, agreement, kappa, and McNemar statistics measure evaluator behavior on an unreviewed proxy; they are not verifier accuracy or a public SOTA result.
- Rows with truncated contexts may create legitimate evaluator disagreement.
