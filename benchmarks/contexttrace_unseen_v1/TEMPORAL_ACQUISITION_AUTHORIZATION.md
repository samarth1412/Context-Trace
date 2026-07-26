# ContextTrace-Unseen-v1 temporal acquisition authorization

Recorded: 2026-07-26

Decision: 11A

Status: exact-hash, zero-cost source acquisition and local normalization
authorized

## Project-owner authorization

> I attest that none of the 20 exact temporal source pairs in catalog SHA-256
> a3781a725ad5100a610e8a6e2bec1b7458903333622ce0461d095c88c8bd6678
> influenced ContextTrace/GroundLM development, and I authorize zero-cost
> acquisition and local normalization of only that exact catalog. This does
> not authorize substitutions, model or verifier calls, annotation,
> evaluation, publication, or release.

## Enforced scope

The authorized catalog is
`benchmarks/contexttrace_unseen_v1/temporal_pre_acquisition_catalog.json` at
SHA-256
`a3781a725ad5100a610e8a6e2bec1b7458903333622ce0461d095c88c8bd6678`.

Permitted:

- download only the 37 immutable public source identities in that catalog;
- retain and deterministically normalize only the allowlisted first-party
  text, required license/attribution material, and exact government text;
- verify immutable IDs, expected hashes and sizes, source-pair relationships,
  exclusions, disjointness, and minimum usable text yield;
- write private local artifacts and repository metadata-only integrity records.

Not permitted:

- source, revision, section, path, or pair substitution;
- paid endpoints or API charges;
- query authoring or trace generation;
- local or hosted model calls;
- ContextTrace/GroundLM verifier calls;
- labels, annotation, adjudication, evaluation, or result inspection;
- manifest publication, external upload, GitHub release, dataset release, or
  other publication.

Any identity, hash, access, license, exclusion, or evidence-yield failure must
stop or mark the exact source/pair ineligible. It must not be repaired by
silently changing the frozen catalog.
