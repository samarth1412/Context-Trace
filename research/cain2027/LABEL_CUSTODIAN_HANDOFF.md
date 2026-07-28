# Label custodian handoff for `sar`

Handoff version: 1.0

Status: ready for candidate action; no production labels may be created

## Materials to provide

Give `sar` read-only copies of:

1. `docs/cain-2027-execution-spec.md`;
2. `benchmarks/contexttrace_unseen_v1/ANNOTATION_MANUAL.md`;
3. `benchmarks/contexttrace_unseen_v1/ANNOTATION_SCHEMA.json`;
4. `benchmarks/contexttrace_unseen_v1/ANNOTATOR_TRAINING.md`;
5. `benchmarks/contexttrace_unseen_v1/ADJUDICATION_PROTOCOL.md`;
6. `benchmarks/contexttrace_unseen_v1/SEALED_EVALUATION_POLICY.md`;
7. `research/cain2027/LABEL_CUSTODIAN_ADJUDICATOR_RECRUITMENT.md`;
8. after training and the excluded-source pilot pass, the private frozen
   unlabeled manifest and its SHA-256 sidecar.

The expected frozen payload SHA-256 is
`8bf65cd7e2c95ccfcc12e78b580fc47e4157b0f808ba3fcace0a24bfcdc2e5f6`.

## Candidate actions

`sar` must personally:

1. read the materials;
2. sign or otherwise attest to independence, confidentiality, prohibited
   disclosure, and the role exclusions;
3. complete the terminology check and calibration exercises;
4. complete and pass the excluded-source pilot and qualification;
5. create a label zone outside the ContextTrace repository and outside every
   implementation account's readable storage;
6. run the synthetic rehearsal tool from a custodian-controlled environment;
7. test that an implementation account cannot read the label zone;
8. verify the frozen manifest seal;
9. return only the non-revealing activation receipt.

Do not return raw exercises, pilot labels, class counts, disagreements,
examples, or label-zone paths to the implementation workspace.

## Staged synthetic rehearsal command

Before receiving the private frozen manifest, the candidate runs:

```bash
.venv/bin/python -m \
  benchmarks.contexttrace_unseen_v1.label_zone_rehearsal rehearse-zone \
  --zone /CUSTODIAN-CONTROLLED/contexttrace-label-zone \
  --candidate-id sar \
  --receipt /CUSTODIAN-CONTROLLED/zone-rehearsal-receipt.json \
  --implementation-denial-attested \
  --duties-attested
```

The tool refuses to operate inside the ContextTrace repository, creates only
synthetic records, tests hashing and recovery, and emits a receipt containing
no labels or test-case metadata.

After training and the excluded-source pilot pass, the candidate receives the
private frozen manifest and runs:

```bash
.venv/bin/python -m \
  benchmarks.contexttrace_unseen_v1.label_zone_rehearsal verify-manifest \
  --candidate-id sar \
  --manifest /READ-ONLY/contexttrace_unseen_v1_frozen_unlabeled.json \
  --expected-sha256 \
  8bf65cd7e2c95ccfcc12e78b580fc47e4157b0f808ba3fcace0a24bfcdc2e5f6 \
  --receipt /CUSTODIAN-CONTROLLED/manifest-verification-receipt.json
```

Production activation requires the valid zone-rehearsal and manifest
verification receipts plus separate training and pilot qualification records.

## Receipt fields allowed back

Only these fields may return to this repository:

- candidate ID;
- tool version;
- rehearsal timestamp;
- frozen manifest verification pass/fail;
- directory-layout pass/fail;
- mode/ownership check pass/fail;
- append-only log rehearsal pass/fail;
- synthetic seal/recovery pass/fail;
- implementation-account denial pass/fail, separately attested by the
  candidate;
- duties/disclosure attestation pass/fail;
- overall zone-rehearsal pass/fail;
- frozen-manifest verification pass/fail, only after training and pilot;
- receipt SHA-256.

No untouched annotation begins until every activation item is recorded as
passed.
