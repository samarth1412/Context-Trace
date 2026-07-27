# Label custodian and adjudicator recruitment package

Package version: 1.0

Date: 2026-07-24

Status: candidate `sar` provisionally appointed; human activation pending

## Role to fill

Recruit one independent person to serve as both:

- **label custodian**, controlling the isolated label workspace, assignments,
  access log, artifact validation, hashes, and sealed gold; and
- **adjudicator**, resolving disagreements only after two immutable independent
  annotations and pre-adjudication agreement analysis exist.

Expected effort is approximately 20–35 hours, depending on disagreement rate.
This is a research-operations role, not a request to evaluate ContextTrace.

## Required qualifications

The candidate must:

- be able to read technical, policy, and support documents carefully;
- follow a frozen annotation manual and make evidence-linked decisions;
- be comfortable with structured JSON/JSONL or willing to use a validated
  annotation interface;
- maintain confidential research artifacts and basic access logs;
- understand that `unknown`, `unverifiable`, and `not_observable` are valid
  outcomes;
- disclose professional, financial, authorship, supervisory, and close
  personal conflicts with the project and annotators;
- agree not to disclose label prevalence, disagreements, examples, or
  case-level information to verifier implementers before the evaluation lock;
- have no role implementing, tuning, or selecting `semantic_core_v2`,
  `semantic_v1_calibrated`, NLI models, thresholds, prompts, or baselines.

Prior annotation or empirical-software-research experience is preferred but
not required if the candidate passes training and pilot qualification.

## Automatic exclusions

Do not appoint:

- the successor-verifier implementation lead;
- either of the two independent annotators;
- anyone who has already inspected verifier predictions on candidate test
  cases;
- anyone whose compensation depends on a favorable result;
- anyone who cannot keep the label zone outside the implementation workspace;
- anyone unwilling to preserve unresolved disagreements and original raw
  submissions.

If the project owner is implementing the verifier, the project owner cannot
hold this role.

## Candidate invitation text

> ContextTrace is recruiting an independent label custodian and adjudicator for
> a sealed evaluation of RAG failure diagnosis. The role manages two blinded
> annotator submissions, computes or supervises field-level agreement, resolves
> documented disagreements using a frozen manual, and seals the resulting gold
> labels. You will not run or assess the system under study, and you must not
> share labels or aggregate label information with its implementers before the
> locked evaluation. Expected effort is approximately 20–35 hours. Please
> disclose relevant project, authorship, employment, supervisory, financial, or
> close personal conflicts. Compensation, if any, is fixed by effort and never
> by study outcome.

Sending this invitation, offering compensation, or recruiting a person is an
external action and requires the project owner to do it or explicitly authorize
another person to do it.

## Screening questions

Ask each candidate:

1. Have you contributed code, data, annotations, review, or authorship to
   ContextTrace, GroundLM, or the proposed CAIN 2027 study?
2. Have you seen predictions or case-level errors from any ContextTrace
   verifier on the candidate dataset?
3. Do you supervise, report to, live with, or have a close personal or
   financial relationship with an implementer or either annotator?
4. Can you keep the label artifacts in a location inaccessible to
   implementers and maintain an append-only access log?
5. Can you commit to applying the frozen manual even when a more favorable
   system label appears plausible?
6. Can you preserve raw disagreements and record `unresolved` when the manual
   does not determine an answer?
7. Are you available for training, a qualification pilot, production
   adjudication, sealing, and a final chain-of-custody attestation?

Record answers privately. The repository should contain only a pseudonymous
candidate ID, eligibility outcome, conflict category, reviewer, and date—not
contact details or unnecessary personal information.

## Selection decision

Use the following fail-closed rule:

- any verifier implementation or candidate-prediction exposure: reject;
- direct conflict that cannot be managed through recusal: reject;
- inability to isolate labels or preserve records: reject;
- otherwise: provisionally eligible, subject to training and pilot.

If a conflict is uncertain, pause and obtain an independent research-integrity
decision. Do not resolve uncertainty by omitting it from the record.

## Compensation rule

Compensation is not yet approved. Before making an offer, the project owner
must select a fixed hourly rate or fixed role honorarium and confirm any
institutional, tax, employment, and IRB requirements. Payment must not depend
on agreement level, class balance, system performance, paper acceptance, or
completion speed.

Unpaid participation is acceptable only when genuinely voluntary and permitted
by the candidate's institution. Authorship must follow contribution standards;
it is not automatic compensation for custody or annotation.

## Onboarding sequence

1. Assign a pseudonymous ID.
2. Obtain conflict and prediction-exposure attestations.
3. Give access to the governing specification, annotation manual, annotation
   schema, training guide, adjudication protocol, and sealed-evaluation policy.
4. Keep all untouched cases and labels unavailable during initial training.
5. Run the excluded-source qualification pilot.
6. Require the frozen qualification threshold in `ANNOTATOR_TRAINING.md`.
7. Create the label zone and access-log template.
8. Test schema validation, canonical hashing, backup, and recovery using
   synthetic records only.
9. Record acceptance of duties and prohibited disclosures.
10. Activate access only after the unlabeled manifest seal is verified.

## Minimal label-zone layout

The custodian creates this outside the ContextTrace repository:

```text
contexttrace-label-zone/
  access-log.jsonl
  assignments/
  raw/annotator-a/
  raw/annotator-b/
  validation-receipts/
  agreement/
  disagreement-packets/
  adjudication-ledger/
  gold/
  correction-ledger/
  receipts-read-only/
```

Required controls:

- implementation accounts have no read access;
- raw submissions become read-only after receipt and hashing;
- hash receipts are copied to a separately controlled location;
- backups inherit the same access restrictions;
- every read and write records pseudonymous person, role, purpose, artifact
  hash, timestamp with timezone, and action;
- no label or class name appears in filenames visible to implementers;
- contact and compensation records are stored separately from research labels.

## Activation checklist

The role is active only when all boxes can be supported by records:

- [ ] Candidate passed conflict and exposure screening.
- [ ] Compensation/volunteer arrangement was approved.
- [ ] Candidate completed manual and adjudication training.
- [ ] Candidate passed the excluded-source pilot.
- [ ] Label zone exists outside the repository.
- [ ] Access control was tested with an implementation account.
- [ ] Append-only access logging was tested.
- [ ] Synthetic hash/seal/recovery rehearsal passed.
- [ ] Candidate signed the prohibited-disclosure attestation.
- [ ] Frozen unlabeled manifest hash was received and verified.

Until then, the dataset may be collected and frozen under Gate B/C, but no
untouched annotation may begin.

## Human actions required now

The project owner must:

1. identify at least one candidate;
2. choose whether the role is paid or voluntary;
3. check institutional and IRB requirements before recruitment;
4. send the invitation;
5. return only the candidate's pseudonymous ID and screening outcome to the
   implementation workspace.

On 2026-07-27, the project owner reported candidate `sar` as eligible,
voluntary, and not requiring institutional/IRB review. The provisional
appointment is recorded in `LABEL_CUSTODIAN_APPOINTMENT.md` and
`label_custodian_appointment.json`. Production access remains inactive until
the candidate-generated activation receipts satisfy every unchecked item.
