# ContextTrace-Unseen-v1 annotation manual

Guide version: 1.0

Status: frozen protocol; no annotation has started

Date: 2026-07-24

## Purpose and boundary

Annotators identify what can be observed in a recorded RAG trace. They do not
judge whether ContextTrace is correct, infer hidden pipeline internals, or
establish real-world truth beyond the supplied source snapshots.

Keep these concepts separate:

- claim support;
- failure relation;
- observable root cause;
- citation correctness;
- source freshness and authority;
- whether the answer should abstain;
- confidence in the annotation.

A claim can be textually supported and still rely on a stale, superseded,
noncanonical, low-authority, or conflicting source.

## Blinded materials

Annotators receive:

- blinded case ID;
- query and unedited answer;
- complete retrieved chunks and selected-context identifiers;
- citations;
- approved source snapshots and source-condition metadata;
- recorded retrieval, chunking, and reranking stages needed for observable
  attribution;
- this guide and the annotation interface.

Annotators must not receive:

- ContextTrace or baseline predictions;
- scores, confidence, repair suggestions, or error analyses;
- case names that reveal intended labels;
- another annotator's work;
- future adjudication decisions;
- implementation-team notes.

Report any accidental exposure immediately and stop that assignment.

## Annotation workflow

For each case:

1. Read the query and answer without labeling.
2. Segment the answer into atomic propositional claims.
3. Mark non-propositional answer spans separately.
4. For each claim, inspect selected context, then the complete retrieved set,
   citations, and approved source snapshots.
5. Select minimal supporting and/or contradicting spans.
6. Assign claim verdict, citation state, source condition, and abstention need.
7. Assign the primary failure label.
8. Assign one primary observable root cause and optional secondary causes.
9. Record ambiguity flags, field-level confidence, and a concise rationale.
10. Validate offsets and complete every required field before submission.

Do not begin with a guessed root cause. Evidence relation and source condition
come first.

## Atomic claim boundaries

An atomic claim is the shortest answer span expressing one independently
verifiable proposition while preserving every material:

- entity and relationship;
- quantity or threshold;
- polarity or negation;
- modality or certainty;
- date, version, or temporal scope;
- jurisdiction or policy scope;
- condition, exception, or prerequisite.

### Split a sentence when

- two propositions could independently be true or false;
- a list contains independently checkable factual items;
- two procedural steps require different evidence;
- one clause asserts a result and another gives a distinct reason.

### Keep text together when

- a qualifier changes the proposition it modifies;
- separating a date, negation, exception, or jurisdiction would change meaning;
- a pronoun or antecedent is needed to identify the proposition;
- the text is one inseparable comparative or causal claim.

### Non-propositional text

Mark greetings, headings, formatting, pure requests, and content-free
transitions as `non_verifiable_text`. Record their offsets, but do not assign
diagnostic labels.

Use zero-based UTF-8 character offsets with an exclusive end. The stored
`claim_text` must exactly equal `answer[start:end]`. Do not normalize answer text
before recording boundaries.

## Claim verdict

Choose exactly one:

- `supported`: selected evidence entails the complete claim.
- `partially_supported`: evidence entails a material subset but omits or fails
  to establish another material component.
- `unsupported`: topically relevant material exists, but it does not entail the
  claim and does not establish the opposite.
- `contradicted`: applicable evidence establishes an incompatible proposition.
- `unverifiable`: available material is insufficient, ambiguous, conflicting,
  or unsuitable for a reliable verdict.

### Verdict decision rules

- Missing a material quantity, exception, date, or scope is
  `partially_supported`, not `supported`.
- Topical word overlap without the asserted relationship is `unsupported`.
- Use `contradicted` only when the evidence supports an incompatible
  proposition, not merely when support is absent.
- Use `unverifiable` when the trace does not permit a reliable support decision.
  Do not use it to hide uncertainty between labels that the evidence can
  resolve.
- Source staleness does not automatically change a textually entailed claim
  from `supported`; record the source defect separately.

## Failure label

Choose one primary observed answer/evidence failure:

- `none`
- `retrieval_miss`
- `context_selection_error`
- `citation_mismatch`
- `answer_overreach`
- `contradiction`
- `insufficient_evidence`
- `should_have_abstained`
- `source_condition_failure`

Tie order:

1. `source_condition_failure` when the decisive problem is stale, superseded,
   noncanonical, low-authority, or conflicting source status;
2. `citation_mismatch` when answer support exists but the cited target does not
   provide it;
3. `should_have_abstained` when an answer is asserted despite
   `must_abstain`;
4. the earliest directly observable pipeline-stage failure;
5. `insufficient_evidence` when no finer relation is observable.

Optional secondary failure labels preserve additional downstream effects. Do
not duplicate the primary label in the secondary list.

## Primary observable root cause

Choose exactly one:

- `none`
- `retrieval_miss`
- `reranking_failure`
- `chunking_issue`
- `corpus_gap`
- `stale_or_superseded_source`
- `noncanonical_or_low_authority_source`
- `citation_mismatch`
- `answer_overreach`
- `insufficient_selected_context`
- `conflicting_contexts`
- `failure_to_abstain`
- `not_observable`

### Evidence requirements

- `retrieval_miss`: sufficient evidence exists in the recorded indexed corpus,
  but is absent from the recorded retrieval results.
- `reranking_failure`: sufficient evidence is retrieved but removed or placed
  below the recorded selection boundary.
- `chunking_issue`: the snapshot contains sufficient contiguous evidence, but
  the recorded chunking separates or removes a necessary relation, qualifier,
  or antecedent.
- `corpus_gap`: sufficient evidence is absent from the recorded corpus
  snapshot.
- `stale_or_superseded_source`: the relied-upon source is demonstrably displaced
  by a newer applicable authoritative source.
- `noncanonical_or_low_authority_source`: a materially more authoritative
  applicable source exists and the answer relies on the weaker source.
- `citation_mismatch`: support exists, but the citation is missing, malformed,
  or points to a non-supporting target.
- `answer_overreach`: the answer adds scope, certainty, conditions, or content
  not licensed by selected evidence.
- `insufficient_selected_context`: selected context is inadequate, but the
  recorded trace cannot attribute the loss more specifically.
- `conflicting_contexts`: applicable trace sources materially conflict and the
  answer fails to resolve or qualify the conflict.
- `failure_to_abstain`: trace evidence establishes that a direct answer is
  unsafe, but one is asserted.
- `not_observable`: two or more causes remain indistinguishable from the trace.

Use the earliest observable necessary cause, except that a material
source-condition defect remains primary for apparently grounded but unsafe
claims. Record optional secondary causes without repeating the primary cause.
Never infer a reranking, chunking, or corpus defect unless the corresponding
trace stage is available.

## Citation state

Choose exactly one:

- `not_applicable`: no citation is required for this claim/task.
- `correct`: the cited target supports the complete claim.
- `partial`: the target supports only a material subset.
- `wrong_source`: the target resolves but does not support the claim.
- `missing`: a citation is required but absent.
- `malformed`: the citation cannot be resolved by the frozen citation rules.

Judge the citation actually associated with the claim. Support elsewhere in the
context does not make a wrong citation correct.

## Source condition

Choose exactly one:

- `current_canonical`
- `current_noncanonical`
- `stale`
- `superseded`
- `low_authority`
- `conflicting_authorities`
- `unknown`

Record source-condition evidence separately:

- snapshot identifiers;
- publication or effective dates where available;
- applicable authority or canonicality rule;
- material conflict;
- short rationale.

Use `unknown` when ordering, authority, jurisdiction, or applicability cannot be
established from approved source metadata. Do not infer authority from writing
style or agreement with the answer.

## Abstention requirement

Choose exactly one:

- `must_answer`: the available evidence supports a direct answer.
- `may_answer_with_qualification`: a bounded answer is acceptable only if it
  states the material uncertainty, scope, or conflict.
- `must_abstain`: no safe direct answer is supportable, or unresolved
  authoritative conflict makes assertion unsafe.

Evaluate the answer actually provided. An unnecessary refusal is not correct
for `must_answer`. An unqualified assertion does not satisfy
`may_answer_with_qualification`.

## Minimal evidence spans

Select the shortest contiguous source span preserving every material entity,
relationship, polarity, quantity, date, exception, and condition needed for the
verdict.

Each span records:

- source and chunk IDs;
- zero-based UTF-8 character start and exclusive end within the source
  snapshot;
- exact source text;
- `supporting` or `contradicting` role.

Multiple spans are allowed only when no single span is sufficient. Exclude
neighboring text and boilerplate unless it carries a necessary qualifier or
antecedent. A contradiction span must include the incompatible proposition.

No span is appropriate when the available source contains no supporting or
contradicting text. Leave the span list empty and explain the relevant
retrieval/corpus insufficiency.

## Special cases

### Ambiguous claim boundaries

Choose the narrowest defensible boundary and add `claim_boundary_ambiguous`.
Do not create overlapping claims merely to preserve alternatives.

### Multi-source claims

Use multiple spans only when the proposition genuinely requires combining
sources. Each source must contribute a necessary part. Record
`multi_source_claim`.

### Conflicting sources

First determine applicability and authority. If equally applicable authorities
conflict, use `conflicting_authorities`, consider `must_abstain` or qualified
answering, and use root cause `conflicting_contexts`. If one source clearly
governs, label the weaker source condition instead.

### Temporal claims

Preserve dates, versions, and “current/as of” language in the claim boundary.
Use the source state applicable at the query's time. Do not treat a later source
as governing an earlier historical question unless the source says so.

### Policy-dependent claims

Preserve jurisdiction, population, effective date, exceptions, and
preconditions. A policy from another scope is not evidence for the target scope.
Use `policy_scope_uncertain` when applicability cannot be established.

### Retrieval-stage ambiguity

If the corpus or pre-rerank candidate set is unavailable, do not guess
`retrieval_miss`, `reranking_failure`, or `corpus_gap`. Use
`insufficient_selected_context` or `not_observable` as appropriate.

## Annotation confidence

Rate each categorical field and the overall annotation from 1 to 5:

- `1`: guess; decisive information is absent;
- `2`: weak; multiple plausible readings remain;
- `3`: moderate; best label is supported but a material ambiguity exists;
- `4`: high; evidence and rule are clear;
- `5`: very high; direct, unambiguous evidence and rule.

Confidence does not change the selected label. A low-confidence case still
requires a best label plus ambiguity flags and rationale.

## LLM assistance

LLM-generated labels are not independent human annotations. For headline
independent annotation, the default is `model_assistance.used: false`.

If assistance is exceptionally authorized, disclose provider, model, revision,
prompt hash, affected fields, and whether suggestions were shown before the
human decision. The annotator must independently verify every field. Assisted
annotations are reported as a separate subgroup and cannot silently replace the
required unassisted independent subset.

## Independent annotation

Two annotators independently label every headline case. If capacity requires a
subset, freeze a source-family-stratified double-annotation assignment before
labels exist. It must cover at least 25% overall and every domain, track,
retriever family, generator family, and source-condition stratum. The Phase 1
preference remains 50% coverage.

Annotators may not communicate about assigned cases before submitting immutable
raw files. Raw submissions are hashed before any comparison.

## Quality-control checks

Before submission:

- claim text equals answer offsets;
- claims do not overlap;
- propositional claims contain every required field;
- secondary labels exclude the primary label;
- evidence text equals source offsets;
- evidence source IDs exist in the packet;
- citation state is consistent with citation presence;
- `none` root cause accompanies only a no-failure annotation;
- source-condition evidence exists for non-current conditions;
- confidence and ambiguity flags are complete;
- no predictions or other annotator labels are present.

Schema validation is necessary but not sufficient.

## Adjudication

Adjudication begins only after agreement is computed from untouched raw
submissions. Preserve every annotator value. Record one event per disagreed
field or claim boundary, disagreement type, selected value, evidence, rationale,
adjudicator, and timestamp.

Adjudicators do not see system predictions. They may request a blind source
clarification but cannot ask implementers which label benefits the system.

See `ADJUDICATION_PROTOCOL.md`.

## Corrections and guide changes

Pilot feedback may revise the guide only on 20–30 cases excluded from the
untouched test by source family. After guide freeze:

- wording clarification with no semantic effect is logged;
- a label or decision-rule change increments the guide and claim-policy version;
- affected cases require blind reannotation;
- no post-result change can redefine confirmatory labels.

Never overwrite a raw annotation. Corrections are new versioned records linked
to the original hash.
