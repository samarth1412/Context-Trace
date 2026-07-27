# ContextTrace-Unseen-v1 annotator training

Training version: 1.0

Status: protocol only; no annotators assigned

## Eligibility

Annotators should be able to:

- read technical and policy-style English precisely;
- distinguish textual entailment, missing support, and contradiction;
- inspect retrieval and citation records;
- reason about dates, versions, source authority, and scope;
- record exact character offsets;
- follow confidentiality and independence requirements.

Annotators must disclose conflicts with ContextTrace development, candidate
source ownership, or system implementation. A successor-verifier implementer
cannot serve as an independent test annotator.

## Training sequence

1. Read the annotation manual and Phase 1 claim policy.
2. Complete a terminology check without access to test cases.
3. Review hypothetical examples illustrating every label.
4. Practice claim segmentation and source offsets.
5. Independently annotate 10 calibration exercises.
6. Review feedback on rules, not desired agreement.
7. Complete a 20–30 case pilot drawn from source families excluded from the
   untouched test.
8. Participate in guide clarification using pilot disagreements only.
9. Complete a qualification set after the guide is frozen.
10. Sign independence, assistance, and confidentiality attestations.

Training and pilot cases are calibration data. Their source documents,
families, domain IDs, publication windows, and near-duplicate clusters are added
to the calibration registry.

## Terminology check

The check must establish that an annotator can explain:

- why support is not truth;
- the difference between `unsupported` and `unverifiable`;
- the difference between `retrieval_miss`, `reranking_failure`,
  `chunking_issue`, and `corpus_gap`;
- when `not_observable` is required;
- why support elsewhere does not repair a wrong citation;
- how source freshness differs from authority;
- the distinction between `may_answer_with_qualification` and `must_abstain`;
- what makes an evidence span minimal.

Incorrect answers trigger retraining, not disclosure of test examples.

## Calibration exercises

Exercises must include:

- compound claims and material qualifiers;
- unsupported versus contradicted claims;
- empty retrieval and incomplete selected context;
- a retrieved-but-dropped relevant chunk;
- chunk-boundary loss;
- missing and wrong-source citations;
- current versus superseded documentation;
- noncanonical and low-authority sources;
- equally authoritative conflict;
- policy jurisdiction and effective-date scope;
- multi-source support;
- required abstention.

All examples are hypothetical or excluded calibration cases and are labeled as
such.

## Pilot

The pilot contains 20–30 real or approved calibration cases, independently
annotated under the same interface planned for the test. It is used only to:

- find unclear guide language;
- test offset tooling and schema validation;
- estimate annotation time;
- identify missing source metadata;
- refine training examples;
- test adjudication logistics.

Do not use pilot outcomes to tune the successor verifier if the pilot shares any
source dimension with the untouched set. The safest policy is to register every
pilot case as calibration.

## Qualification

Qualification occurs after the guide is frozen. Minimum requirements:

- 100% schema-valid submissions;
- no overlapping claim boundaries;
- at least 0.85 exact agreement with adjudicated training answers for claim
  verdict, citation state, and abstention requirement;
- at least 0.75 exact agreement for primary root cause;
- mean evidence-span token F1 at least 0.75;
- no systematic confusion of support and source condition;
- no independence or assistance violation.

These are training thresholds, not study agreement results. Failure leads to
targeted retraining and one requalification attempt. Continued failure excludes
the annotator from headline cases.

## Assignment

Before labels exist, generate a stratified assignment covering:

- at least 25% double annotation, with 50% preferred;
- every source-family stratum selected without labels;
- every domain and track;
- retriever and generator families;
- source-condition pair types;
- balanced workload and no annotator-specific source cluster.

The assignment file contains blind case IDs only and is hashed. Annotators work
independently and submit immutable files to the custodian.

## Assistance and communication

- Do not use ContextTrace, baselines, search engines, or unapproved external
  sources while labeling.
- Do not discuss assigned cases before both raw submissions are sealed.
- Do not use an LLM unless the protocol explicitly authorizes and records it.
- Report interface, source, or ambiguity problems privately to the custodian.
- Never include credentials, personal information, or system predictions in
  notes.

## Monitoring without contamination

The custodian may monitor:

- completion rate;
- schema failures;
- annotation duration;
- missing source artifacts;
- offset validation;
- assistance and access attestations.

The implementation team receives no label counts, class prevalence,
disagreements, examples, or annotator notes. Before the implementation lock, it
may receive only an aggregate “annotation operations on track/not on track”
status.

## Current human dependency

Candidate `sar` is provisionally appointed as label custodian/adjudicator but
is not activated. No independent annotator assignment is recorded. Candidate
training, excluded-source pilot qualification, production annotator training,
and test annotation have not begun.
