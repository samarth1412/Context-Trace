# Table5 Error Analysis

| Cluster | Review status | Count | Example | What happened / likely cause | Planned fix | Affects broad claim |
| --- | --- | --- | --- | --- | --- | --- |
| Supported claim overflagged | assisted_review_pending_independent | 4 | ragtruth_9604 | Support threshold or label boundary | Independent adjudication and calibrated claim decomposition | True |
| Contradiction missed | assisted_review_pending_independent | 2 | ragtruth_121 | Taxonomy boundary or implicit contradiction | Adjudicate labels; add contradiction regression cases | True |
| Evidence span too broad | assisted_review_pending_independent | not_measured | N/A | No dedicated breadth annotation | Add span-boundary error tags during review | unknown |
| Multi-span evidence failure | assisted_review_pending_independent | not_measured | N/A | Distributed evidence is not separately tagged | Add multi-span annotations and recall metric | unknown |
| Root cause confused | assisted_review_pending_independent | 9 | ragtruth_121 | Failure label and upstream cause are difficult to separate | Adjudicate root causes and report agreement | True |
| Numeric/date normalization error | assisted_review_pending_independent | not_measured | N/A | No dedicated numeric/date error tag | Add typed normalization error labels | unknown |
| Citation mismatch ambiguity | assisted_review_pending_independent | 0 | N/A | No citation mismatch was observed in the primary errors | Retain citation-specific regression coverage | False |
| Stale/source-trust limitation | assisted_review_pending_independent | not_measured | N/A | RAGTruth does not independently label source freshness | Evaluate on a temporally labeled dataset | unknown |
| Score-only baseline false-green | same-ID cached baseline | 60 | aggregate | Score-only output lacks diagnostic coverage | Report same-ID false-green rate and N/A fields | True |
| Judge parse failure | not_run | not_run | N/A | Judge-only mode is unavailable without a frozen provider | Pin provider/model/cache/cost before running | unknown |

All rows expose review status; `N/A`, `not_run`, and `not_measured` are never imputed.
