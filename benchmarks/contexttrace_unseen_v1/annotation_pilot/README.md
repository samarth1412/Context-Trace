# ContextTrace excluded-source annotation pilot

Status: blind inputs frozen; human pilot not started

This package contains 22 previously exposed calibration cases:

- 12 development cases whose source URLs were already registered in the
  frozen calibration registry;
- 10 previously inspected real-world RAG traces at exact recorded Git blobs.

It contains no untouched case, production label, gold field, expected field,
category, rationale, ContextTrace prediction, verifier output, or NLI output.
The blind packet SHA-256 is
`82394d36dc4565ba0d16685c2be34f344e95dda4a29be5e534cfc866b71a5431`.

## Human execution

After the isolated label zone is active, the custodian:

1. gives all 22 blind cases independently to Annotator A and Annotator B;
2. requires output conforming to `../ANNOTATION_SCHEMA.json`;
3. receives, validates, hashes, and makes each raw submission read-only;
4. computes field-level pre-adjudication agreement without changing raw data;
5. creates blinded disagreement packets;
6. adjudicates using `../ADJUDICATION_PROTOCOL.md`;
7. records guide defects and clarifications using pilot cases only;
8. freezes the revised annotation manual before qualification;
9. keeps every pilot output outside the implementation workspace.

The implementation team may receive only operational pass/fail status and
non-revealing hashes. Do not return pilot labels, class counts, agreement
values, disagreements, examples, or rationales.

## Important boundary

This package is for training and protocol refinement. It must never be merged
with the 493-case untouched corpus or used for independent-test claims.
