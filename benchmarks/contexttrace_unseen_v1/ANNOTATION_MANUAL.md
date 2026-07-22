# ContextTrace-Unseen-v1 annotation manual

Annotators receive the query, answer, retrieved chunks, selected context,
citations, and source snapshots. They do not receive ContextTrace predictions.
Annotations are claim-level unless a field is explicitly trace-level.

## Unitization

Split the answer into minimal independently verifiable claims. Preserve qualifiers,
negation, quantities, entities, relationships, dates, and policy conditions. A
sentence containing two independently falsifiable propositions produces two
claims. Record exact answer character offsets for every claim.

## Fields

### Claim verdict

- `supported`: selected evidence entails the complete claim.
- `partially_supported`: evidence entails only a proper subset or omits a material
  qualifier.
- `contradicted`: evidence entails an incompatible proposition.
- `unsupported`: evidence is relevant but does not entail the claim.
- `unverifiable`: available material is insufficient, ambiguous, or unsuitable for
  a reliable verdict.

Grounding is not truth. A claim can be textually supported while the source is
stale, superseded, non-canonical, or low authority; encode that in source condition.

### Failure label

Choose the observable failure that best describes the answer/evidence relation:
`none`, `retrieval_miss`, `context_selection_error`, `citation_mismatch`,
`answer_overreach`, `contradiction`, `insufficient_evidence`,
`should_have_abstained`, or `source_condition_failure`. Do not infer a hidden
pipeline defect when the trace does not expose it.

### Primary observable root cause

Choose exactly one: `none`, `retriever_omitted_available_evidence`,
`reranker_or_selector_dropped_evidence`, `corpus_missing_evidence`,
`generator_ignored_or_exceeded_evidence`, `citation_points_to_wrong_chunk`,
`contexts_conflict`, `source_stale_or_superseded`, `source_noncanonical`,
`source_low_authority`, or `not_observable`. Use `not_observable` rather than
guessing between indistinguishable mechanisms.

### Citation state

Choose `not_applicable`, `correct`, `partial`, `wrong_source`, `missing`, or
`malformed`. Citation correctness concerns whether the cited span supports the
associated claim, not whether another uncited chunk supports it.

### Source condition

Choose one primary state: `current_canonical`, `current_noncanonical`, `stale`,
`superseded`, `low_authority`, `conflicting_authorities`, or `unknown`. Record the
specific snapshot IDs and comparison evidence used. Prefer `unknown` when
publication order, authority, or canonical status cannot be established.

### Abstention requirement

Choose `must_answer`, `may_answer_with_qualification`, or `must_abstain`. Use
`must_abstain` when no available evidence can safely support an answer or when
unresolved authoritative conflicts make a direct answer unsafe.

### Minimal evidence span

Select the shortest contiguous source span that preserves the entities,
relationship, polarity, quantity, date, and material conditions needed for the
verdict. Record source ID plus UTF-8 character start/end offsets. Multiple spans
are allowed only when no single span is sufficient. Contradiction spans must
include the conflicting proposition, not merely topical text.

## Independent annotation and adjudication

Two annotators independently label all headline cases; if capacity is constrained,
they must cover a preregistered stratified subset of at least 50% from every
domain, track, retriever family, generator, and source-condition category. The
remaining cases receive one annotation and are excluded from agreement claims.

Preserve both raw annotations. An adjudicator records the selected value, whether
the disagreement was definitional or evidentiary, and a short rationale without
overwriting either original. Report agreement separately for claim boundaries,
claim verdict, failure label, primary root cause, citation state, source condition,
abstention requirement, and evidence spans. Use field-appropriate statistics
rather than a combined kappa; report exact agreement and class prevalence beside
chance-corrected measures. Report span token-F1 and character IoU for evidence.

## Sealing

Store raw annotations, disagreements, and adjudications in access-controlled
files unavailable to implementers. Do not export gold labels to the development
workspace until the signed release-lock record confirms the verifier version, NLI
artifact hash, thresholds, metrics, tests, and candidate output schema.
