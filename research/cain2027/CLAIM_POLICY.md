# Claim and diagnostic policy

Policy version: 1.0  
Status: Phase 1 taxonomy and scoring contract  
Freeze date: 2026-07-24

This policy defines the output concepts used by the preregistration. It is not
an annotation manual and does not create labels. Phase 3 may add annotator
examples and interface guidance, but may not silently change these concepts
after the untouched corpus is collected.

## Separation of fields

Each atomic claim is represented by separate fields:

1. claim verdict;
2. failure label;
3. primary observable root cause;
4. citation state;
5. source condition;
6. abstention requirement;
7. minimal evidence span;
8. diagnostic confidence and route.

No field implies another. In particular:

- textual support is not truth;
- a supported claim may cite a stale or low-authority source;
- a correct source may be cited incorrectly;
- low confidence is not the same as `unverifiable`;
- a diagnosis may be `not_observable` even when the failure label is clear.

## Atomic claim unitization

An atomic claim is the shortest answer span that expresses one independently
verifiable proposition while retaining material polarity, modality, quantity,
date, entity, relation, jurisdiction, exception, and condition.

- Split coordinated propositions when either could be false independently.
- Do not split a qualifier from the proposition it constrains.
- Preserve negation, uncertainty, comparative language, and temporal scope.
- Procedural steps are separate claims when each step has an independent
  evidence requirement.
- Purely conversational, formatting, or non-propositional text is marked
  `non_verifiable_text` and excluded from diagnostic metrics.
- Record exact UTF-8 answer character offsets. The text at those offsets must
  equal the stored claim text.

Systems are evaluated against adjudicated gold claim boundaries. Candidate
claim extraction is separately evaluated using boundary exact match and overlap;
diagnostic scoring uses deterministic maximum-overlap alignment with one-to-one
matching. Unmatched gold claims count as missing predictions. Unmatched
candidate claims count as spurious predictions for claim-extraction metrics and
cannot improve diagnostic scores.

## Claim verdict

Allowed values:

- `supported`: the recorded evidence entails the complete claim.
- `partially_supported`: evidence entails a material subset but omits or fails
  to establish a material component.
- `contradicted`: evidence establishes an incompatible proposition.
- `unsupported`: relevant evidence is present but does not entail the claim.
- `unverifiable`: the available trace is insufficient, ambiguous, conflicting,
  or unsuitable for a reliable verdict.

`unverifiable` is not a catch-all for parser or runtime failure. Invalid system
outputs are recorded as missing predictions.

## Failure label

Choose one primary observable failure relation:

- `none`
- `retrieval_miss`
- `context_selection_error`
- `citation_mismatch`
- `answer_overreach`
- `contradiction`
- `insufficient_evidence`
- `should_have_abstained`
- `source_condition_failure`

The label describes the dominant observed answer/evidence failure. Secondary
relations may be retained for error analysis but do not enter primary
failure-label macro-F1.

Tie-breaking order:

1. `source_condition_failure` when the claim is textually grounded but the
   decisive defect is stale, superseded, noncanonical, low-authority, or
   conflicting source status;
2. `citation_mismatch` when answer support exists in the selected context but
   the associated citation does not point to it;
3. `should_have_abstained` when an answer is asserted despite a gold
   `must_abstain` requirement;
4. the earliest directly observable pipeline-stage failure;
5. `insufficient_evidence` when no finer observable relation is justified.

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

Evidence requirements:

- `retrieval_miss`: eligible evidence exists in the indexed corpus, but the
  retriever did not return it within the recorded retrieval depth.
- `reranking_failure`: eligible evidence appears in the retrieved candidate set
  but is excluded or ranked below the context-selection boundary.
- `chunking_issue`: the source snapshot contains sufficient contiguous
  evidence, but the recorded chunking destroys the material relation or
  qualifier and no allowed selected combination preserves it.
- `corpus_gap`: no sufficient evidence exists in the recorded corpus snapshot.
- `stale_or_superseded_source`: the answer is grounded in a source demonstrably
  older than and displaced by the applicable authoritative source.
- `noncanonical_or_low_authority_source`: a more authoritative applicable
  source is identifiable and conflicts materially with the relied-upon source.
- `citation_mismatch`: selected support exists, but the citation points to a
  different, non-supporting, malformed, or absent target.
- `answer_overreach`: the generator adds a material proposition, scope,
  certainty, condition, or conclusion not licensed by selected evidence.
- `insufficient_selected_context`: the recorded context is too incomplete for a
  reliable claim, without enough trace evidence to attribute the loss to
  retrieval, reranking, chunking, or corpus construction.
- `conflicting_contexts`: applicable sources in the trace conflict and the
  answer does not resolve or qualify the conflict.
- `failure_to_abstain`: the trace provides adequate signals that a direct answer
  is unsafe, but the generator asserts one.
- `not_observable`: the trace cannot distinguish among two or more plausible
  causes. Annotators and systems must not infer hidden internals.

When multiple failures occur, choose the earliest observable cause that is
necessary for the downstream failure, except that a source-condition defect
remains primary when the core research question is whether apparently grounded
evidence is stale or unsuitable. Preserve secondary causes for error analysis.

## Citation state

Allowed values:

- `not_applicable`: the task and answer require no citation;
- `correct`: the cited target supports the complete associated claim;
- `partial`: it supports only a material subset;
- `wrong_source`: the target is present but does not support the claim;
- `missing`: a citation is required but absent;
- `malformed`: the citation cannot be resolved under the frozen parser.

The binary citation-error endpoint treats `partial`, `wrong_source`, `missing`,
and `malformed` as errors. It excludes `not_applicable`.

## Source condition

Allowed primary values:

- `current_canonical`
- `current_noncanonical`
- `stale`
- `superseded`
- `low_authority`
- `conflicting_authorities`
- `unknown`

Source status requires recorded comparison evidence: snapshot identifiers,
publication/effective dates where available, canonical ownership or authority
rule, and the material conflict. If authority or ordering cannot be established,
use `unknown`.

## Abstention requirement

Allowed values:

- `must_answer`
- `may_answer_with_qualification`
- `must_abstain`

`must_abstain` applies when no available evidence can safely support the
requested answer or unresolved authoritative conflict makes an unqualified
answer unsafe. A qualified response may satisfy
`may_answer_with_qualification`; silence or refusal is not automatically
correct when evidence clearly supports `must_answer`.

## Evidence span

The minimal evidence span is the shortest source text that preserves every
material entity, relation, polarity, quantity, date, exception, and condition
needed for the verdict. Store:

- source snapshot and chunk identifiers;
- UTF-8 character start and exclusive end offsets;
- exact span text;
- role: `supporting` or `contradicting`.

Multiple spans are permitted only when no single span is sufficient. Boilerplate
and neighboring sentences are excluded unless they carry a necessary qualifier
or antecedent. Empty gold spans are valid only for claims whose available trace
contains no supporting or contradicting text; they are excluded from span
localization metrics and retained for retrieval/corpus-gap diagnosis.

## Selective output and confidence

The candidate output must record:

- final prediction or abstention;
- confidence in the diagnosis, not source truth;
- route: `deterministic`, `nli`, `deterministic_nli_agreement`,
  `deterministic_nli_disagreement`, or `unresolved`;
- truncation and insufficient-input flags;
- evidence identifiers used.

The intended cascade is deterministic checks, then a pinned local NLI model only
for low-confidence claims, then abstention for unresolved disagreement or
insufficient evidence. Threshold values, NLI artifact, and confidence semantics
must be frozen in the implementation lock. An abstention is not scored as a
green verdict.

## Dangerous false green

A gold-positive dangerous case is any claim with:

- claim verdict `partially_supported`, `unsupported`, `contradicted`, or
  `unverifiable`; or
- failure label other than `none`; or
- citation error when citation is applicable; or
- source condition other than `current_canonical` where that condition
  materially affects answer safety; or
- abstention requirement `must_abstain`.

A dangerous false green occurs when the system emits an unqualified positive
claim verdict and no failure/citation/source warning, does not abstain, and meets
the frozen “green” confidence threshold. Invalid or missing predictions are not
greens; they are counted separately and handled under the missing-output policy.

## Versioning

Any semantic change to a label, tie-break rule, alignment rule, or endpoint
mapping increments this policy version and requires a preregistration amendment.
Examples may be clarified in Phase 3 only when they do not change label
membership or scoring.
