# ARR ablations

The full run registers eleven variants. Nine execute through production profile
boundaries; two remain unavailable because no model, provider, prompt, cache,
and cost contract was frozen before the run.

| Variant | Availability | Failure F1 | Root cause | Span overlap | False green |
| --- | --- | ---: | ---: | ---: | ---: |
| Full ContextTrace | available | 1.000 | 1.000 | 0.862 | 0.000 |
| Lexical-only verifier | available | 0.419 | N/A | N/A | 0.232 |
| Semantic-only verifier | available | 0.419 | N/A | N/A | 0.232 |
| No citation module | available | 0.831 | 0.878 | 0.862 | 0.122 |
| No contradiction checks | available | 0.812 | 0.980 | 0.862 | 0.008 |
| No abstention logic | available | 0.875 | 0.372 | 0.862 | 0.000 |
| No root-cause classifier | available | 1.000 | N/A | 0.862 | 0.000 |
| No source trust/freshness | available | 0.708 | 0.888 | 0.862 | 0.112 |
| No evidence-span localization | available | 0.982 | 0.998 | N/A | 0.000 |
| NLI-only mode | not available | N/A | N/A | N/A | N/A |
| Judge-only mode | not available | N/A | N/A | N/A | N/A |

Metrics use 500 frozen cases per executable profile and deterministic 400-draw
case bootstraps. These are pre-review engineering results. They establish
module sensitivity, not broad SOTA.

Exact profiles and unavailable reasons are in `ARR_EXPERIMENTS.json`. Machine
outputs are `out/arr_full/ablations.json` and `out/arr_full/ablations.md`.
