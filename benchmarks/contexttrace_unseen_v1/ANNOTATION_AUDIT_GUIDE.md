# ContextTrace 60-case annotation task

You will label 60 cases independently in one Excel workbook. The six practice
cases are not scored.

Expected time: about 8–12 hours for your independent work. Stop and contact SAR
if the task appears likely to take substantially longer.

## What you do

1. Open the `ANNOTATE-*.xlsx` workbook.
2. Complete the six cases in the `PRACTICE` sheets.
3. After the practice discussion, complete all 60 cases in the `PRODUCTION`
   sheets.
4. Complete the `ATTESTATION` sheet.
5. Return only the completed workbook to SAR. You do not edit any JSON.

## Rules

1. Use your own judgment. Do not use an LLM, ContextTrace, another verifier,
   web search, system predictions, or Phase 6 metrics.
2. Do not view or discuss the other submission until SAR confirms that both
   original submissions have been received and hashed.
3. Use only the supplied trace and source files.
4. Do not change a submitted production file after SAR hashes it.
5. During consensus, use `unresolved` if no agreement is possible. Do not force
   an answer.

## How to label each case

1. Read the query, answer, retrieved chunks, selected contexts, and citations.
2. Split the answer into the shortest independently verifiable claims. Copy
   each claim exactly from the answer.
3. For every propositional claim, record:

   - claim verdict;
   - one primary failure label;
   - one primary observable root cause;
   - citation state;
   - source condition;
   - abstention requirement;
   - minimal evidence span(s);
   - a short rationale.

4. Copy the shortest decisive evidence text exactly and record its source and
   chunk IDs. Leave offset columns blank; SAR calculates them from the exact
   text after submission.
5. Use `not_observable` when the trace cannot distinguish the root cause.
6. Mark the claim complete only after every required label is filled.

Use the allowed values and evidence-span format in `ANNOTATION_SCHEMA.json`.
Secondary-label arrays and notes may be empty. Confidence is your 1–5
confidence in the annotation, not a system score.

## Practice

Complete the six cases in the `PRACTICE` sheets independently. You may then
discuss only those six cases with the other annotator to clarify the rules.
Practice cases are never scored.

## After your independent submission

SAR preserves and hashes both original submissions, then computes field-level
agreement. You will receive only the disagreement items. Resolve those items
with the other annotator and add a one-sentence rationale. Your original
submission remains unchanged.

## Scope

This task checks whether independent labels change the conclusions produced by
the earlier invalid LLM-first labels. It does not make the dataset untouched.
