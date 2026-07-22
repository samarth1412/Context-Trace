# Verifier governance

The current semantic verifier is frozen as `semantic_v1_calibrated`. Its RAGTruth,
ContextTrace-Diag-150, Naturalistic Eval v2, and repository benchmark results are
calibration evidence, not external test evidence.

The freeze boundary is recorded in
`contexttrace/verify/rulepacks/legacy_ragtruth_calibrated.yaml`, including the
implementation hash and the benchmark families that must not drive further rule
changes. Existing callers retain the calibrated compatibility behavior. New work
must use a new verifier version and must not inspect the untouched test labels or
errors before the implementation is locked.

## Untouched-test protocol

1. Collect cases from source documents, domains, and time windows absent from all
   calibration sets. Do not randomly split cases derived from the same document.
2. Require every case to declare `id`, `track`, `source_family`,
   `source_document_id`, `domain`, and `publication_window` before freezing.
3. Run `freeze_untouched_split.py` and publish the resulting sorted IDs and SHA-256
   manifest before implementing the successor verifier.
4. Keep gold annotations and test outputs inaccessible to implementers until the
   successor verifier, thresholds, taxonomy, and profile are locked.
5. Score once. Subsequent inspection turns the split into calibration data and
   requires a newly collected test split.

Human relabeling can improve annotation quality, but it does not restore test-set
independence after implementation decisions were based on those examples.

## Rule-pack boundary

`generic_v1.yaml`, `temporal.yaml`, and `policy.yaml` define the intended boundary
for successor work. Domain packs are opt-in. The legacy calibrated pack is not a
source of rules for an independent evaluation model.
