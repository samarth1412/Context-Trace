# Error analysis

Status: frozen pre-review analysis on the 200-case RAGTruth subset.

Observed clusters:

| Cluster | Count | Example | Review status |
| --- | ---: | --- | --- |
| Supported cases overflagged | 4 | `ragtruth_9604` | independent review pending |
| Contradictions missed | 2 | `ragtruth_121` | independent review pending |
| Primary root cause confused | 9 | `ragtruth_121` | independent review pending |
| Matched-baseline dangerous false greens | 60 | aggregate | labels pending review |
| Citation ambiguity | 0 | N/A | measured |

Evidence-span breadth, multi-span attribution, numeric/date reasoning, stale
source behavior, and judge parse failures were not measured by this run. Judge
failures were not run because no frozen judge configuration exists. These
categories must remain `not_measured` or `not_run`; zero would be a fabricated
result.

The current ContextTrace row has nine failure-label misses and zero dangerous
false greens. Independent review may change both the denominator and the error
taxonomy. Review corrections must be versioned, not edited directly into this
summary.

## Simulated-review sensitivity

Three simulated agents disagree on 142/200 RAGTruth cases and 29/150 Diag
cases. Their majority suggestions disagree with 214 frozen labels. Replacing
those labels in a sensitivity-only calculation lowers combined accuracy from
`0.974` to `0.380` and macro-F1 from `0.978` to `0.139`. No simulated suggestion
is applied; the result demonstrates the need for human adjudication.
