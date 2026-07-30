# ContextTrace 60-case human audit

This is a human-only audit of an already consumed evaluation corpus. It is not
a new untouched test set and must not be described as one.

## People and workload

- Pul independently annotates all 60 production cases.
- Sid independently annotates the same 60 production cases.
- Both first annotate the same six excluded practice cases.
- After both production submissions are finished and hashed, Pul and Sid
  resolve only their disagreements by consensus.
- SAR handles files and computes agreement. SAR does not choose labels.

Expected time: approximately 8–12 hours per annotator and 2–4 hours for
consensus. Stop if the actual pace implies substantially more work.

## Absolute rules

1. Human judgment only. Do not use an LLM, ContextTrace, another verifier,
   web search, or system predictions.
2. Work independently until both complete production submissions are hashed.
3. Use only the supplied trace and source files.
4. Never inspect the earlier Phase 6 metrics while annotating.
5. Preserve each original submission unchanged.
6. If the humans cannot agree during consensus, record `unresolved`; do not
   force an answer.

## For each case

1. Read the query, answer, retrieved chunks, selected contexts, and citations.
2. Split the answer into the shortest independently verifiable claims.
3. Record exact answer character offsets.
4. For every propositional claim, fill:

   - claim verdict;
   - one primary failure label;
   - one primary observable root cause;
   - citation state;
   - source condition;
   - abstention requirement;
   - minimal evidence span(s);
   - a short rationale.

5. Use `not_observable` when the trace cannot distinguish the root cause.
6. Mark the case complete only after every required field is filled.

The allowed values and evidence-span format remain those in
`ANNOTATION_SCHEMA.json`. Secondary-label arrays may be empty. Notes may be
empty. Confidence is a 1–5 judgment of the human annotation, not the system.

## Minimal practice step

Pul and Sid independently complete the six files under `work/practice/`.
They may then discuss only those six cases and clarify how they interpret the
guide. Practice cases are never scored. No qualification exam or security
rehearsal is required.

## Production and consensus

After practice, each person completes all files under `work/production/`.
They sign `HUMAN-ONLY-ATTESTATION.txt` and give only their completed folder to
SAR. SAR hashes both folders before showing either submission to the other
annotator.

SAR computes field-level agreement. Pul and Sid then see only disagreement
items and agree on a final value with a one-sentence rationale. The original
submissions remain unchanged.

## Interpretation

This audit answers one narrow question: do independent human labels materially
change the conclusions from the invalid LLM-first gold? It cannot restore
untouched status. If the frozen verifier performs plausibly against these
human labels, collect a new untouched corpus for the final paper. If it still
fails badly, improve the verifier using a separate development corpus first.
