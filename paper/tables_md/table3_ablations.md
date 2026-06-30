# Table3 Ablations

| Variant | Availability | Review status | Failure F1 | Root cause | Citation F1 | Span overlap | False green | p95 ms | Cost / 100 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Full ContextTrace | available | engineering regression benchmark | 1.000 | 1.000 | 1.000 | 0.862 | 0.000 | 38.978 | 0.000 |
| Lexical-only verifier | available | engineering regression benchmark | 0.419 | N/A | N/A | N/A | 0.232 | 3.366 | 0.000 |
| Semantic-only verifier | available | engineering regression benchmark | 0.419 | N/A | N/A | N/A | 0.232 | 20.541 | 0.000 |
| No citation module | available | engineering regression benchmark | 0.831 | 0.878 | N/A | 0.862 | 0.122 | 36.000 | 0.000 |
| No contradiction checks | available | engineering regression benchmark | 0.812 | 0.980 | 1.000 | 0.862 | 0.008 | 41.366 | 0.000 |
| No abstention logic | available | engineering regression benchmark | 0.875 | 0.372 | 1.000 | 0.862 | 0.000 | 38.715 | 0.000 |
| No root-cause classifier | available | engineering regression benchmark | 1.000 | N/A | 1.000 | 0.862 | 0.000 | 45.393 | 0.000 |
| No source trust/freshness | available | engineering regression benchmark | 0.708 | 0.888 | 1.000 | 0.862 | 0.112 | 17.151 | 0.000 |
| No evidence-span localization | available | engineering regression benchmark | 0.982 | 0.998 | 1.000 | N/A | 0.000 | 57.817 | 0.000 |
| NLI-only mode | not_available | engineering regression benchmark | N/A | N/A | N/A | N/A | N/A | N/A | N/A |
| Judge-only mode | not_available | engineering regression benchmark | N/A | N/A | N/A | N/A | N/A | N/A | N/A |

All rows expose review status; `N/A`, `not_run`, and `not_measured` are never imputed.
