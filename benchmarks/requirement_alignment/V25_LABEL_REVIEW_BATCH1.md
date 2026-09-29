# V25 development label review: first 50 cases

The first 50 cases in the existing hash-ordered blinded pack now have provisional
model-assisted reviews. This completes 50/500 first-pass proposals (10% of the
annotation pass), not 10% of release readiness. There are 450 cases left in the
pass, and no replacement labels have been approved.

## Findings

The proposals disagree with 23 of 50 inherited labels. This is a disagreement
rate, not an established benchmark error rate. Twenty-seven cases carry explicit
ambiguity or scope-adjudication flags, including some whose proposed label
agrees with the inherited one. Every proposal remains provisional, including
the other 23 cases without a specific ambiguity flag.

| Inherited verdict | Cases reviewed | Proposal agrees | Proposal differs |
|---|---:|---:|---:|
| supported | 12 | 6 | 6 |
| partially_supported | 8 | 6 | 2 |
| unsupported | 7 | 4 | 3 |
| contradicted | 10 | 6 | 4 |
| unverifiable | 13 | 5 | 8 |

Five inherited supported cases are proposed as partially supported because
the selected evidence omits a material date, denominator, duration, attribution,
or qualification. One is proposed as unsupported because a supplied lower
bound does not entail the claim's numerical threshold. A partially-supported
case is proposed as contradicted because the selected evidence gives a different
number for a material fact. All remain subject to adjudication.

The most important rubric questions are:

- Reported speech: does the claim assert that someone said something, the truth
  of what they said, or both? A rebuttal of the embedded statement does not by
  itself refute the attribution.
- Measurement scope: a one-time count is not an annual flow; route length is
  not total track length; an estimate bound is not an exact total.
- Missing detail versus contradiction: omitted evidence is not a refutation,
  and an offer to perform an action does not establish the completed action.
- Ambiguous referents, units, and dates: record ambiguity instead of silently
  filling a currency, person, or time interval from outside knowledge.
- Institutional attribution: an office or department's action/ownership does
  not necessarily establish the named individual's personal action/ownership.

These distinctions explain why upstream fact-check labels cannot simply be
treated as selected-evidence labels. They do not excuse model errors or certify
the proposed replacements.

## Provenance and limits

The development assistant reviewed the displayed claim and selected evidence,
without loading the mapping key or candidate predictions during drafting.
The reviewer is a language model involved in the project, not an independent
human annotator. Earlier aggregate experiment findings were already known.
The first 50 proposals were hash-locked in commit `1b4063d` before loading
the key and computing agreement. The original labels, model outputs, and
unfilled original review template were not changed.

Each reviewed row stores a short reviewer-authored rationale, references to
actual supplied evidence IDs, an issue category, and an adjudication flag.
These rationales are not attributed to Jev and are not provider explanations.
No Jev or other external inference API was called for this batch. Text-bearing
review data remain outside Git at
`/private/tmp/contexttrace_external_data/v25_model_assisted_review.json`.

The committed report contains only IDs, numeric summaries, label proposals,
issue codes, and input/rationale hashes. Its validator rejects post-freeze
changes, altered evidence (including unreviewed rows), missing bindings, and
references to evidence IDs not supplied in the pack. It cannot prove a
semantic judgment correct.

## Decision and next step

Continue the remaining 450 cases under the same rubric and blinded input view,
then adjudicate the proposals and the scope flags before creating revised
development targets. Do not retrain or rescore the candidate against these
proposals to claim an improvement. The 500 consumed cases remain development
data permanently. No release gate has been newly passed by this review.

## Reproduce the comparison

```bash
PYTHONPATH=packages/contexttrace:. .venv/bin/python \
  -m benchmarks.requirement_alignment.v25_review summarize \
  --review /private/tmp/contexttrace_external_data/v25_model_assisted_review.json \
  --key /private/tmp/contexttrace_external_data/v25_review_key.json \
  --freeze benchmarks/requirement_alignment/results/v25_review_batch1_freeze.json \
  --output benchmarks/requirement_alignment/results/v25_review_batch1.json
```

The raw text/rationales are external; the script reproduces comparison and
integrity checks against their committed hashes. It does not reproduce the
reviewer's semantic decisions or invent labels for the unreviewed rows.
