# ContextTrace-Unseen-v1 sealed evaluation policy

Policy version: 1.0

Status: Gate C corpus frozen; provisional custodian appointed; no gold artifact exists

## Objective

Keep candidate inputs and gold labels separated until the candidate
implementation, dependencies, models, thresholds, output schema, metrics,
statistics, baselines, and ablations are frozen.

## Storage zones

### Candidate zone

May contain:

- frozen unlabeled manifest;
- source and trace artifacts allowed by their terms;
- candidate output schema;
- implementation and baseline inputs.

Must not contain annotations, label counts, reviewer notes, adjudication,
agreement reports, gold hashes with revealing filenames, or label-derived
metadata.

### Label zone

Access-controlled and unavailable to verifier implementers. Contains:

- raw annotation submissions;
- assignment and access records;
- schema-validation receipts;
- pre-adjudication agreement outputs;
- disagreement packets;
- adjudication ledger;
- sealed gold;
- correction and incident logs.

### Scoring zone

Created only for the one-time evaluation. It receives locked predictions and
sealed gold under the custodian. It has no authority to modify candidate code,
predictions, or labels.

## Required roles

- **Label custodian:** controls the label zone and releases only allowed status
  signals.
- **Implementation custodian:** freezes code, dependencies, models, prompts,
  thresholds, and output schema without label access.
- **Evaluation operator:** verifies locks and performs the one-time join.
- **Integrity reviewer:** determines whether incidents compromise the untouched
  claim.

The label custodian cannot be a `semantic_core_v2` implementer.

## Access policy

Before the evaluation lock, the implementation team may learn only:

- annotation has not started/in progress/complete;
- whether schema validation passes;
- whether the preregistered support-count sufficiency gate is met, expressed
  only as pass/fail without field or class identities;
- whether an operational blocker exists.

It may not learn label prevalence, agreement values, disagreements, examples,
annotator notes, source-condition counts, or which sufficiency check failed.

Every label-zone read records person/role, artifact hash, reason, and timestamp.

## Artifact chain

Seal separately:

1. each raw annotator submission;
2. assignment file;
3. agreement output;
4. adjudication ledger;
5. adjudicated gold;
6. correction ledger;
7. final scoring inputs and outputs.

Use canonical JSON/JSONL ordering rules documented with the sealing utility.
Store SHA-256 receipts outside the writable label directory. A hash alone does
not authorize access.

## Gold-release gate

The scoring zone cannot receive gold until all are present and verified:

- frozen unlabeled manifest and published/independently retained hash;
- calibration-overlap audit;
- `semantic_v1_calibrated` source-hash check;
- `semantic_core_v2` implementation lock;
- dependency and environment locks;
- NLI model/tokenizer revisions and artifact hashes;
- taxonomy, claim policy, annotation guide, and output schema hashes;
- prompts, profiles, thresholds, and routing rules;
- baseline and ablation locks;
- metric/scorer source hash and tests;
- preregistered statistical configuration;
- candidate predictions created without gold access;
- signed access-log attestation.

Any mismatch fails closed.

## One-time scoring

1. Copy or mount locked predictions read-only.
2. Verify prediction case IDs and hashes against the frozen manifest.
3. Verify sealed gold and adjudication hashes.
4. Join by case and adjudicated claim alignment in the scoring zone.
5. Run the frozen scorer once.
6. Preserve raw outputs, logs, environment, hashes, exit status, and timestamp.
7. Mark the dataset as inspected evaluation evidence.
8. Do not return case-level labels or errors to implementers until all
   confirmatory artifacts are immutable.

After results are inspected, the dataset can never again be called untouched
for verifier development.

## Defects and incidents

If a software defect, corrupted artifact, accidental label disclosure, or
unauthorized access occurs:

- stop immediately;
- preserve the invalid run and all hashes;
- record what was visible, by whom, and when;
- do not silently fix or rerun;
- have the integrity reviewer determine whether labels or errors influenced any
  mutable component;
- retire the split to calibration if independence cannot be defended.

A corrected rerun is confirmatory only when the preregistered correction policy
and independent review establish that test information could not influence the
correction.

## Prohibited shortcuts

- storing gold beside candidate JSON;
- emailing labels to implementers;
- including labels in filenames or manifest metadata;
- reporting class prevalence during model development;
- using agreement disagreements as development examples;
- tuning after a dry run against gold;
- substituting LLM labels for independent human labels;
- regenerating predictions after result inspection;
- deleting an invalid scoring attempt.

## Current gate

The complete 493-case corpus is privately frozen under payload SHA-256
`8bf65cd7e2c95ccfcc12e78b580fc47e4157b0f808ba3fcace0a24bfcdc2e5f6`.
Candidate `sar` is provisionally appointed as label custodian/adjudicator but
has not completed human activation. No independent annotator assignment, raw
annotation, agreement result, or sealed gold exists. The gold-release gate
remains closed.
