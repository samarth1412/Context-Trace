# Selective Evidence-Chain Diagnosis for Actionable RAG Debugging

This is the successor-paper plan. The existing RAGTruth, Diag-150, Naturalistic
Eval v2, and repository results are calibration evidence for
`semantic_v1_calibrated`, not an external test set.

## RQ1: Does fine-grained diagnosis generalize?

Build a confidence-gated cascade:

```text
deterministic checks -> uncertain cases only: local NLI -> still uncertain: abstain or optional judge
```

Do not force a root-cause label when evidence is insufficient. Pre-register and
report selective-risk curves, coverage, expected calibration error, dangerous
false-green rate, latency, and cost alongside macro-F1. Targets for the
successor verifier are root-cause accuracy at least 0.75, unverifiable F1 at
least 0.60, failure-label macro-F1 improvement of at least 0.15 absolute, and
dangerous false-green rate below 0.02. These are targets, not current results.

The final test set must be separated from calibration data by source document,
domain, and source time window. Publish its ID/hash manifest before successor
implementation and score it once after the verifier, taxonomy, profile, and
thresholds are locked.

## RQ2: Are diagnoses actionable for developers?

Run a real counterbalanced developer study with three conditions: scalar RAG
metrics, an LLM-judge explanation, and the ContextTrace evidence chain plus
repair plan. Recruit approximately 20--30 participants and assign 6--8 broken
pipeline tasks per participant.

Measure correct root cause, correct repair, time to repair, hidden regression
pass rate, unnecessary modifications, recurrence, and confidence calibration.
Analyze repeated observations with mixed-effects models or paired tests. Check
institutional human-subject requirements before recruitment. LLM-simulated
ratings may pilot the protocol but are not evidence of human actionability.

## RQ3: Does diagnosis transfer to agent traces?

Either narrow all claims to RAG or evaluate the agent layer on TRAIL. The transfer
representation should connect tool output to downstream claim, propagated error,
and observable root cause. Keep this extension after RQ1 so agent scope does not
mask unresolved RAG attribution errors.

## Release rule

Every result artifact must state its schema, taxonomy, verifier, and profile
versions. Any inspection of untouched-test errors retires that split to
calibration status for future verifier development.
