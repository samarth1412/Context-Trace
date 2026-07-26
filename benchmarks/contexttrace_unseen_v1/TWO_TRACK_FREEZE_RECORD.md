# ContextTrace-Unseen-v1 complete two-track freeze record

Record version: 1.0

Frozen: 2026-07-26

Status: Gate C complete; private, unlabeled, unscored, and unpublished

## Frozen composition

The complete private manifest contains 493 untouched candidate traces:

- 393 Natural OOD cases from 36 source families;
- 100 temporal/source-condition cases from 20 frozen source pairs;
- 73 candidate sources in total;
- all three preregistered domain groups and retrieval families;
- two generator model families, two chunk sizes, and both reranking states.

The Natural OOD target of 300–500 cases and temporal target of 80–120 cases
both pass the production composition policy.

## Integrity and leakage result

The production Gate C validator passed schema, source policy, artifact-byte,
trace-structure, case/source binding, license, privacy, timestamp, label
absence, verifier-history, composition, and calibration-disjointness checks.
It verified 639 referenced artifacts.

The two acquisition pipelines historically used different meanings for
`normalized_content_sha256`: Natural OOD used NFKC/whitespace/casefold
semantic fingerprints, while temporal acquisition used exact file-byte
hashes. Neither frozen input was changed. The composite explicitly records
the original hash method per source and additionally applies
`semantic_nfkc_whitespace_casefold_v1` uniformly to all tracks:

- candidate sources: 73;
- unique uniform semantic fingerprints: 73;
- cross-candidate duplicate groups: 0;
- calibration sources checked: 173;
- candidate/calibration collisions: 0.

## Private seal

| Artifact | SHA-256 |
| --- | --- |
| Frozen manifest payload seal | `8bf65cd7e2c95ccfcc12e78b580fc47e4157b0f808ba3fcace0a24bfcdc2e5f6` |
| Frozen manifest file bytes | `6b1b48ed4ed8bc9b4966b9218b77406b2d925ae1b6d8991f630726415c5c01e4` |
| Combined source manifest file | `794603f6287445cefad2893d091f325b2c2da6acf24028fe702a75fe91712ccc` |
| Combined case manifest file | `25653bea25a7b845f650d9e879fd4c8d64f143967907f2eb2e144a8b4a77c13b` |
| Composition lock | `20daf06711f0f76002cff0366d4b491b2e897019b5a88e252aef5e9893eb68da` |
| Private Gate C record | `c19f8b6f87577a0ce5f860a9dd7d65046c6f73b121fdc87f7371ef02acf594b3` |

The primary private root
`.tmp-contexttrace-unseen-v1-two-track-freeze` is mode `0700`, Git-ignored,
approximately 249 MiB, and contains the manifest plus every referenced
artifact. A separate mode-`0700`, Git-ignored retention root,
`.tmp-contexttrace-unseen-v1-two-track-retained`, contains an independently
verified byte-identical copy of the frozen manifest and its sidecar.

## Downstream boundary

No label was created or accessed. No ContextTrace verifier, NLI model,
annotation, scoring, evaluation, publication, or release action occurred.

Gate C completion permits the project to begin Phase 3 only after a qualified
independent label custodian/adjudicator is appointed and its access zone is
activated. It does not authorize annotation or `semantic_core_v2`
implementation by itself.
