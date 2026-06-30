# RQ4 actionability status

The paired 40-case protocol and blinded packet are complete. Human data
collection has not started, so no human actionability, preference, time, or
agreement result is available.

The preregistration compares two settings:

- `semantic_core`: score and claim-verdict output with diagnostic modules disabled.
- `evidence_chain`: full ContextTrace diagnosis with spans, citation state,
  source assessment, root cause, reasons, and suggested fixes.

This two-condition design must not be changed after seeing responses. A future
three-condition raw-trace/score-only/full-diagnosis experiment may be registered
as a separate study, but it cannot be presented as the preregistered RQ4.

A separate controlled LLM-simulated pilot was run with three role prompts and
the pinned `gpt-4.1-nano-2025-04-14` model. All 360 RQ4 agent-setting rows parsed
successfully. Raw/score/evidence-chain root-cause accuracy was
`0.067/0.117/0.908`, while mean actionability was `3.767/3.608/3.333` and false
green rate was `0.625/0.550/0.400`. Because actionability declined, the
registered positive proxy claim is not supported. This pilot is not human
validation and cannot satisfy RQ4 paper or SOTA gates.

See `ARR_ACTIONABILITY_PROTOCOL.md` for human sampling, blinding, outcome
definitions, and scoring commands. Send only `actionability_packet.json` to
human reviewers.
