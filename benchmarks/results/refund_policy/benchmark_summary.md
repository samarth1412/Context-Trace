# ContextTrace Benchmark Summary

Dataset: `refund_policy`

| Strategy | Citation Support | Unsupported Claims | Failure Rate | Retrieval Miss | Tokens | Latency | Cost |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| contexttrace_adaptive | 0.914 | 0.058 | 0.000 | 0.000 | 251.2 | 636.0 ms | $0.000251 |
| hybrid_rerank | 0.888 | 0.092 | 0.000 | 0.000 | 231.0 | 539.5 ms | $0.000225 |
| corrective_rag | 0.864 | 0.136 | 0.000 | 0.000 | 273.2 | 735.3 ms | $0.000249 |
| hybrid | 0.837 | 0.163 | 0.000 | 0.000 | 234.5 | 441.0 ms | $0.000188 |
| bm25_top_k | 0.802 | 0.214 | 0.250 | 0.000 | 193.2 | 315.7 ms | $0.000154 |
| dense_top_k | 0.766 | 0.234 | 1.000 | 0.000 | 200.5 | 368.7 ms | $0.000160 |

## Honest Tradeoffs

- contexttrace_adaptive produced the highest citation support, but it is not always the cheapest path.
- bm25_top_k had the lowest average cost, with lower reliability on evidence-sensitive questions.
- bm25_top_k had the lowest latency, which can matter for interactive support workflows.
- Retrieval miss rate is reported separately because citation support alone can hide missed-evidence failures.

## Chart Artifacts

- `citation_support`: `benchmarks/results/refund_policy/charts/citation_support.svg`
- `failure_rate`: `benchmarks/results/refund_policy/charts/failure_rate.svg`
- `average_cost_usd`: `benchmarks/results/refund_policy/charts/average_cost_usd.svg`
