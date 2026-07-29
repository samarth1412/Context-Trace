# Prospective shared-device label-custody amendment

Amendment ID: `cain2027-custody-2026-07-29-a1`

Recorded: 2026-07-29

Status: project-owner direction recorded; custodian acceptance and encrypted
storage verification pending

## Timing and rationale

The project owner elected to use one physical macOS laptop for implementation
and label-custody operations. The original ordinary-folder rehearsal correctly
failed the implementation-access-denial gate.

This amendment is prospective with respect to all human labels. No pilot or
untouched annotation, gold label, disagreement, agreement statistic, system
prediction, verifier result, or NLI result exists or was inspected when it was
recorded. Natural and temporal answer collection was already complete, but
this storage-only change cannot alter the frozen questions, sources, answers,
case IDs, configurations, or manifest seal.

The amendment changes no hypothesis, metric, threshold, taxonomy, model,
baseline, statistical test, or evaluation rule. It changes only the custody
mechanism and the strength of permitted isolation claims.

## Required controls

The shared laptop may be used only if all controls below are satisfied before
pilot material is released:

1. Custodian `sar` creates an AES-256-encrypted APFS disk image or encrypted
   removable volume outside the ContextTrace repository.
2. Only `sar` knows the encryption password. It is not saved in the project
   owner's Keychain, browser, password manager, shell history, notes, or
   repository.
3. The ordinary Desktop rehearsal directory is never used for pilot or
   production annotations.
4. The project owner logs out and is absent whenever the encrypted volume is
   mounted. No implementation process, screen recording, remote-login
   session, backup agent, or synchronization client may access the mounted
   volume.
5. `sar` mounts the volume only for authorized custody work, records the
   session in the append-only access log, and unmounts it immediately after
   the session.
6. Annotator assignments and submissions move only through `sar`; neither
   annotator sends labels to the implementation team.
7. Raw submissions, agreement outputs, disagreement packets, adjudication,
   gold labels, and correction records remain inside the encrypted volume.
8. Any backup is separately encrypted and controlled by `sar`.
9. Only allowlisted, non-revealing receipts may leave the encrypted volume.
10. Any unexpected implementation access, password disclosure, mounted-volume
    exposure, or label leakage stops the study and triggers an integrity
    review.

## Activation evidence

Before pilot release, `sar` must return a non-revealing attestation confirming:

- the encrypted volume exists and uses AES-256;
- the password is known only to `sar` and is not stored on the owner account;
- mount, unmount, encrypted-at-rest, and recovery checks passed;
- the ordinary Desktop rehearsal directory will not store annotations;
- the project owner will be logged out and absent during mounted sessions;
- the access-log and prohibited-disclosure rules are accepted.

The implementation side may verify encryption metadata and receipt hashes but
must not receive the password, mounted path, volume contents, or label-derived
information.

## Claim boundary

If activated under this amendment, the study may claim independent human
custody with AES-256 encryption at rest and procedural non-concurrent access on
shared hardware.

It may not claim:

- separate physical hardware;
- absolute administrator-level inaccessibility while the volume is mounted;
- a fully independent institutional data enclave; or
- that the original rehearsal's implementation-access-denial gate passed.

This limitation must be disclosed in the paper and artifact documentation.
