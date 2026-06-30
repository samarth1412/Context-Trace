# RQ4 actionability status

The paired 40-case protocol and blinded packet are complete. Human data
collection has not started, so no actionability, preference, time, or agreement
result is available.

The preregistration compares two settings:

- `semantic_core`: score and claim-verdict output with diagnostic modules disabled.
- `evidence_chain`: full ContextTrace diagnosis with spans, citation state,
  source assessment, root cause, reasons, and suggested fixes.

This two-condition design must not be changed after seeing responses. A future
three-condition raw-trace/score-only/full-diagnosis experiment may be registered
as a separate study, but it cannot be presented as the preregistered RQ4.

No controlled simulated pilot was run because the repository has no frozen
provider, model version, prompt cache, or cost record. Using an unpinned model
would not produce reproducible paper evidence. Table 4 therefore remains N/A.

See `ARR_ACTIONABILITY_PROTOCOL.md` for sampling, blinding, outcome definitions,
and scoring commands. Send only `actionability_packet.json` to reviewers.
