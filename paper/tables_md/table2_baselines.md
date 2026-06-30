# Table2 Baselines

| System | Review status | Cases | Failure F1 | Claim F1 | Root cause | Citation F1 | Span overlap | False green |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ContextTrace | assisted_review_pending_independent | 200 | 0.955 | 0.337 | 0.955 | 1.000 | 0.786 | 0.000 |
| RAGAS | same-ID cached baseline | 200 | 0.152 | 0.533 | N/A | N/A | N/A | 0.300 |

All rows expose review status; `N/A`, `not_run`, and `not_measured` are never imputed.
