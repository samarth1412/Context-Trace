# ContextTrace-Unseen-v1

Status date: 2026-07-26

Phase: complete two-track collection privately frozen at Gate C

Dataset version: not assigned

Frozen manifest: complete 493-case private two-track manifest present and
independently retained; not published

Gold labels: absent

ContextTrace-Unseen-v1 is the planned untouched evaluation corpus for selective
evidence-chain diagnosis. It is designed to test generalization across new
source families, fine-grained domains, publication windows, and source
conditions without reusing any previously inspected ContextTrace benchmark.

No candidate trace or label is published in this directory. The repository
contains acquired-source metadata, locked schedule and pre-acquisition
artifacts, collection records, and validation, privacy, and freezing
infrastructure. The Natural OOD traces and frozen unlabeled manifest remain in
the private collection root.

## Planned tracks

- **Natural OOD:** target 400 real RAG traces, acceptable range 300–500, from
  software/product documentation, policy/regulatory material, and
  support/operational knowledge bases.
- **Temporal/source condition:** target approximately 100 real RAG traces using
  archived/current, old/replacement, noncanonical/canonical, or
  low-authority/authoritative source pairs.

Every case must be the unedited output of an actual recorded RAG run. Manually
written failures, injected errors, repurposed calibration cases, and generated
placeholders are ineligible.

## Phase 2 files

- `DATASET_CARD.md`: intended use, composition, limitations, and current status.
- `COLLECTION_PROTOCOL.md`: source approval, RAG generation, chain of custody,
  and freeze sequence.
- `GENERATION_LOCK.md`: the human-readable 396-case Natural OOD allocation,
  privacy/cost controls, schedule hash, and temporal authorization boundary.
- `generation_schedule.json`: deterministic source-to-configuration allocation;
  its exact hash was separately authorized for the completed Natural OOD run.
- `temporal_pre_acquisition_catalog.json`: exact 20-pair, 100-case temporal
  review object; its presence does not authorize acquisition or model calls.
- `TEMPORAL_PRE_ACQUISITION_REVIEW.md`: source-pair roster, authority,
  license/access, disjointness, allocation, budget, and decision boundary.
- `build_temporal_pre_acquisition_catalog.py`: deterministic builder and
  fail-closed validator for the temporal review object.
- `TEMPORAL_ACQUISITION_AUTHORIZATION.md`: verbatim exact-hash decision `11A`
  and exclusions.
- `TEMPORAL_ACQUISITION_RECORD.md`: completed 37-source/20-pair acquisition,
  validation outcome, integrity hashes, and next decision boundary.
- `temporal_source_manifest.json`, `temporal_acquisition_ledger.json`, and
  `temporal_acquisition_validation.json`: metadata-only integrity records.
- `acquire_temporal_sources.py`: exact-identity collector and independent
  offline reconstruction validator; it contains no generation or verifier
  integration.
- `TEMPORAL_GENERATION_LOCK.md`: exact 100-case allocation, deconfounding
  amendment, questions, source-pool rules, privacy/cost guard, hash, and
  authorization boundary.
- `temporal_generation_schedule.json`: deterministic execution lock; its
  presence does not authorize model calls.
- `build_temporal_generation_schedule.py`: offline builder and fail-closed
  schedule validator.
- `TEMPORAL_RUN_AUTHORIZATION.md` and `temporal_run_authorization.json`:
  exact-hash authorization for the completed 100-slot temporal run.
- `collect_temporal.py`: answer-only temporal collector with frozen-query,
  source-pool, retry, privacy, and budget guards.
- `TEMPORAL_COLLECTION_RECORD.md` and `temporal_collection_record.json`:
  aggregate outcome and private temporal artifact hashes.
- `compose_two_track_freeze.py`: deterministic offline Gate C compositor,
  uniform cross-track leakage audit, and independent seal verifier.
- `TWO_TRACK_FREEZE_RECORD.md` and `two_track_freeze_record.json`: aggregate
  composition, leakage, retention, and final private seal hashes.
- `LEAKAGE_AUDIT.md`: disjointness dimensions and fail-closed audit status.
- `PRIVACY_AND_LICENSE.md`: source, redistribution, privacy, and secret-handling
  requirements.
- `source_manifest.schema.json`: source snapshot and calibration-registry
  contract.
- `case_manifest.schema.json`: candidate RAG trace and configuration contract.
- `freeze_manifest.py`: schema validation, leakage rejection, byte-level hash
  validation, composition checks, sealing, and post-freeze verification.

`ANNOTATION_MANUAL.md` and the legacy checklist are existing Phase 3
scaffolding. They are not activated by Phase 2.

## Freeze contract

The production freeze requires:

1. an approved source manifest;
2. a populated calibration registry;
3. a candidate case manifest with no labels or predictions;
4. locally retained source and trace artifacts matching every declared hash;
5. at least 300 eligible Natural OOD traces and the preregistered source-family
   diversity;
6. no invocation of `semantic_v1_calibrated` or `semantic_core_v2`;
7. no label creation or access before freeze.

Run from the repository root:

```bash
.venv/bin/python -m benchmarks.contexttrace_unseen_v1.freeze_manifest freeze \
  --source-manifest PATH_TO_SOURCE_MANIFEST \
  --case-manifest PATH_TO_CASE_MANIFEST \
  --calibration-registry PATH_TO_CALIBRATION_REGISTRY \
  --artifact-root PATH_TO_ARTIFACT_ROOT \
  --output PATH_TO_FROZEN_MANIFEST
```

The command writes the frozen unlabeled manifest and a `.sha256` sidecar.
External publication of either requires explicit user authorization.

Verify against the independently retained or published hash:

```bash
.venv/bin/python -m benchmarks.contexttrace_unseen_v1.freeze_manifest verify \
  --manifest PATH_TO_FROZEN_MANIFEST \
  --expected-sha256 PUBLISHED_SHA256 \
  --artifact-root PATH_TO_ARTIFACT_ROOT
```

The production manifest is now privately frozen and independently retained.
It remains absent from Git by design; only aggregate counts and integrity
hashes are recorded here. Publication still requires explicit authorization.
