# Shared-device label-custody deviation

Recorded: 2026-07-29

Status: prospective amendment prepared; custodian acceptance and encrypted
storage verification pending; production label access remains inactive

## Event

At the project owner's direction, candidate custodian `sar` ran the synthetic
label-zone rehearsal in the project owner's administrator-controlled macOS
account. The run used no frozen manifest, untouched case, pilot case,
annotation, label, prediction, verifier output, or NLI output.

The returned receipt is internally valid and its file SHA-256 matches the
sidecar. It establishes:

- directory-layout creation;
- private POSIX modes;
- append-only hash-chain rehearsal;
- synthetic seal, backup, and recovery;
- duties and disclosure attestation.

It does not establish implementation-account access denial. The receipt
correctly records `implementation_account_denial_attested: false` and
`overall_zone_rehearsal_passed: false`.

## Methodological consequence

The candidate is not activated for production label custody. A directory on an
implementation-controlled administrator account cannot satisfy the current
sealed-evaluation policy's requirement that the label zone be unavailable to
verifier implementers.

No test or pilot annotation may begin from this receipt. It must not be
described as a passed activation rehearsal.

## Resolution required

Before annotation, either:

1. move custody to storage technically unavailable to the implementation
   account and obtain a new valid receipt with access denial attested; or
2. adopt a prospective protocol amendment, approved before labels exist, that
   defines a defensible encrypted shared-device custody procedure and narrows
   all independence and sealing claims accordingly.

Using an ordinary folder in the project owner's account is not an acceptable
resolution.

The project owner selected the second path on 2026-07-29. The prospective
controls and narrowed claim boundary are recorded in
`research/cain2027/SHARED_DEVICE_CUSTODY_AMENDMENT.md`. The amendment is not
operational until `sar` accepts it and returns the required encrypted-storage
attestation.
