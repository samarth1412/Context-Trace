# ContextTrace-Unseen-v1 Natural OOD run authorization

Authorization version: 1.0

Authorized: 2026-07-26

Project-owner statement:

> I approve Natural OOD generation schedule
> e850d3eb6d374547cdbc70b2c0da02e0db8d9ff043633a577d9319f3d69e1695
> under the recorded $10 hard ceiling.

## Authorized scope

This authorization permits:

- offline verification of the acquired-source manifest and exact schedule hash;
- installation and verification of the dependencies pinned by that schedule;
- implementation and offline dry-run validation of a collection runner that
  executes only the locked configurations;
- deterministic local query-authoring calls for the 396 scheduled cases;
- 198 scheduled local Gemma answer-generation calls;
- 198 scheduled OpenAI GPT-5 mini answer-generation calls;
- only the mechanically allowed retries in the locked schedule;
- retention of unedited outputs, transport failures, usage, latency,
  configuration hashes, and chain-of-custody records;
- hosted spend only within the USD 8 operating allocation, USD 2 retry
  contingency, and USD 10 hard ceiling.

## Not authorized

This authorization does not permit:

- temporal/source-condition acquisition or generation;
- source substitution or schedule-hash changes;
- manual query or answer editing, failure injection, or semantic selection;
- ContextTrace verifier execution;
- label creation, access, annotation, or adjudication;
- successor-verifier implementation or evaluation;
- manifest, dataset, paper, tag, package, or other external publication;
- spending above USD 10.

The runner must stop before the first model call if the source manifest,
generation schedule, pinned model identities, privacy controls, or cost guard
do not match the authorized lock.
