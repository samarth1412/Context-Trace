# Direct requirement-alignment development set

## Purpose

This artifact measures direct evidence-to-requirement decisions using upstream
human labels. It exists for model diagnosis and v3 selection. It is not an
untouched confirmation set and must not be reported as one.

## Source and construction

The source is the official ContractNLI development member from the locally
pinned archive:

- archive SHA-256:
  `e03fc77bbf8b53e2976a250e81d8a294bc3d5e5fb014521e477dee9340d6287b`;
- member: `contract-nli/dev.json`;
- member SHA-256:
  `310af7d661d2ab50ee3700169cef524c75f39fb296bbf5a515c229eb0f42e68e`;
- license: CC BY 4.0.

ContractNLI directly labels each contractual hypothesis as `Entailment`,
`Contradiction`, or `NotMentioned`. ContextTrace maps entailment to `covered`
and the other two relations to the existing `missing` requirement label. The
original three-way relation remains in provenance for separate safety analysis.
No model or API generated any target.

The frozen set contains 240 cases: 80 from each relation. Deterministic
round-robin sampling spreads cases across the available hypotheses. All 61
development documents and all 17 hypotheses are represented.

Entailment and contradiction inputs contain only upstream annotated evidence
spans. Not-mentioned annotations have no evidence spans, so their inputs use at
most three deterministic lexical retrieval spans from the same document. Every
input stays within a 180-word evidence budget. Thirty-seven labeled candidates
whose complete annotated evidence exceeded that budget were excluded before
sampling.

## Isolation and limitations

The ContractNLI training split is not used by this artifact. The test split was
not accessed and remains available for a later, frozen confirmation experiment.
Targets are absent from model inputs.

This set is legal-domain data with 17 hypotheses repeated across documents.
Claim and requirement text are identical because each hypothesis is itself one
direct requirement. Results therefore measure transfer to direct contractual
requirements, not the full diversity of open-domain RAG claims. Not-mentioned
performance includes the deterministic evidence selector and should be
reported with that qualifier.
