# Requirement-alignment dataset card

## Purpose

This training-only artifact supports the next experimental ContextTrace local
verifier. It teaches two related decisions: whether evidence covers one exact
claim requirement and whether an evidence group completely covers a claim.
It is not a model result and does not change product defaults.

## Source and isolation

The builder uses the pinned official WiCE train file with SHA-256
`3ef74c7203e1d9b369cb2c145e764d8ab4743f008f9765fa47f9bdd6ffa2d2e1`.
It retained 1,093 source cases: 460 `supported` and 633
`partially_supported`. The 167 `not_supported` cases were excluded because
this dataset targets complete versus incomplete coverage when some supporting
annotation exists.

Normalized claims were checked against 15 existing development and held-out
case packs. No overlap was found. Splitting occurs at the source-case level:
929 cases are training data and 164 are internal validation. There is no case
or normalized-claim overlap between those partitions.

## Examples

The frozen dataset contains 3,118 examples:

| Task and target | Examples |
| --- | ---: |
| Claim-group completeness: complete | 460 |
| Claim-group completeness: incomplete | 1,448 |
| Requirement alignment: covered | 605 |
| Requirement alignment: missing | 605 |

The construction sources are:

| Construction | Examples | Supervision |
| --- | ---: | --- |
| Complete annotated group | 1,065 | human claim label; inherited by exact requirements |
| Partial annotated group | 633 | human claim label |
| Same-document hard negative | 1,065 | weak annotation-exclusion label |
| Remove one annotated sentence | 355 | weak deterministic counterfactual |

Every requirement is an exact substring of the whitespace-normalized claim and
records character offsets. Model inputs contain only the claim, optional
requirement, and evidence. Targets and source labels are stored separately.

## Limitations

WiCE supplies claim-level evidence groups rather than requirement-level human
annotations. Requirement positives therefore inherit complete-claim support.
Removing one sentence can leave redundant support, and unannotated
same-document sentences can contain support omitted by the upstream annotation.
All examples retain construction provenance so training can exclude or ablate
these weak labels.

The prior 60-case extension has already informed research decisions. A trained
model needs a newly frozen, disjoint validation pack before any promotion or
held-out claim.
