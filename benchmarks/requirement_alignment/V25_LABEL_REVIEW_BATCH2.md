# V25 development label review: second 50 cases

The next 50 cases, `review-0050` through `review-0099`, now have provisional
model-assisted proposals. The cumulative first pass covers **100/500 cases
(20%)**, with 400 unreviewed. This percentage describes annotation coverage,
not release readiness. No replacement labels have been approved.

## Findings

The new batch disagrees with 27 of 50 inherited labels and has 29 explicit
scope or ambiguity flags. Cumulatively, there are 50 disagreements and 56 flags
among 100 reviewed cases. Flags and disagreements overlap but are different
counts; every proposal requires adjudication, even without an explicit flag.
These are disagreement rates, not established label-error rates or verifier
accuracy measurements.

| Inherited verdict | New cases | Proposal agrees | Proposal differs |
|---|---:|---:|---:|
| supported | 11 | 4 | 7 |
| partially_supported | 7 | 6 | 1 |
| unsupported | 8 | 3 | 5 |
| contradicted | 10 | 6 | 4 |
| unverifiable | 14 | 4 | 10 |

Of the seven new inherited-supported disagreements, three proposals are
partially supported, three unverifiable, and one unsupported. The gaps concern
unestablished scope, personal versus administrative attribution, mismatched
years, or conflicting statistics. They identify cases to adjudicate; they are
not measured false supports from the baseline or Jev.

The new cases reinforce several rubric questions: whether a statement reports
speech or asserts its embedded proposition; whether the named individual or
their administration performed an action; and whether an unspecified time
window permits a numerical comparison. A missing crash count does not mean
zero crashes. Evidence about an ingredient does not establish the efficacy
of a proposed treatment. These judgments use the supplied text only and
are not external factual findings.

## Blinding limitation discovered in the supplied evidence

The mapping key and candidate outputs were hidden while drafting the new
proposals. However, original source prose can itself contain fact-check
assessments. `review-0070` includes an assessment of a related, differently
worded claim, and `review-0095` includes an explicit truth assessment alongside
conflicting numerical evidence. These examples were recorded before unblinding
and are not an exhaustive contamination audit of all 500 inputs.

Consequently, describe this as **mapping-label-blinded review**, not fully
label-free evidence or an independent blind evaluation. The original evidence
was preserved to keep the comparisons on identical inputs; silently editing it
would invalidate that binding. Before any subsequent train/evaluation run,
audit assessment-bearing source prose and freeze an explicit input policy.
Any exclusion or sanitization must produce a separately versioned dataset with
source provenance. Do not treat this snapshot as satisfying that future gate.

## Provenance and limits

The development assistant authored the proposals from the selected evidence.
It is a language model involved in the project, not an independent human
annotator. The first batch's comparison and earlier aggregate findings were
already known. No new-batch mapping labels or model predictions were loaded
before drafting. Commit `ea49ea6` froze the cumulative snapshot hash before
the new-batch comparison. All first-batch rows and all 400 unreviewed rows
remain unchanged from the previous snapshot.

No Jev or other external inference API was called. Rationales are reviewer
notes, not provider explanations. The original labels, original review pack,
and first-batch snapshot are preserved. Text and rationales remain outside Git
in `/private/tmp/contexttrace_external_data/v25_model_assisted_review_batch2.json`.
The tracked report contains IDs, hashes, labels, issue codes, and counts only.

`results/v25_review_batch2.json` is **cumulative**, including the unchanged
first 50 rows; do not add its totals to batch 1. The table above describes only
the 50 new rows. The summarizer verifies the frozen snapshot, all 500 input
bindings, reviewed-ID coverage, and evidence references. Six focused V25
tests pass. These checks verify integrity, not semantic correctness.

## Next step and release decision

Continue the remaining 400 first-pass reviews, retain the evidence-contamination
flags, and adjudicate proposals and recurring rubric questions before adopting
replacement development targets. The same owner can adjudicate; do not describe
that as independent annotation. Keep these consumed examples as development
data permanently. No candidate was retrained or rescored against these
proposals, and no new release gate was passed. Stable runtime behavior and
local-only restrictions are unchanged.

## Reproduce the cumulative comparison

From a checkout with its development environment installed:

```bash
PYTHONPATH=packages/contexttrace:. .venv/bin/python \
  -m benchmarks.requirement_alignment.v25_review summarize \
  --review /private/tmp/contexttrace_external_data/v25_model_assisted_review_batch2.json \
  --key /private/tmp/contexttrace_external_data/v25_review_key.json \
  --freeze benchmarks/requirement_alignment/results/v25_review_batch2_freeze.json \
  --output benchmarks/requirement_alignment/results/v25_review_batch2.json
```

This reproduces comparison and integrity checks when the external files are
available. It does not reproduce semantic judgments or fill unreviewed rows.
