---
name: Acquire ContextTrace-Unseen-v1
about: Collect and freeze source/domain/time-disjoint natural RAG traces
title: "Acquire and freeze ContextTrace-Unseen-v1 with source/domain/time-disjoint natural RAG traces"
labels: research, data
assignees: ""
---

## Objective

Acquire and publish the unlabeled ContextTrace-Unseen-v1 manifest before any
`semantic_core_v2` implementation or evaluation.

## Deliverables

- [ ] 300--500 Natural OOD traces spanning software/product documentation,
  policy/regulatory documents, and support/operational knowledge bases.
- [ ] Approximately 100 temporal/source-condition traces from versioned or
  authority-contrasting document pairs.
- [ ] BM25, vector, and hybrid retrieval; multiple chunking/reranking settings;
  at least two pinned generator models; clean and naturally failing answers.
- [ ] Immutable source snapshots, hashes, canonical URLs, source families,
  domains, and publication windows.
- [ ] Leakage audit proving separation from all calibration sources.
- [ ] Published unlabeled IDs/configuration manifest and SHA-256 before scoring.
- [ ] Independent annotation and sealed adjudication records following
  `benchmarks/contexttrace_unseen_v1/ANNOTATION_MANUAL.md`.

## Exclusions

Do not run ContextTrace on candidates before the manifest is frozen. Do not
manually author failures, inspect sealed labels during model development, begin
TRAIL transfer, recruit human-study participants, or include 1.2 performance and
dashboard work in this issue.

## Exit condition

The issue closes when the public unlabeled manifest/hash and leakage report are
available and the sealed-label custodian confirms that annotations are ready for
one-time scoring after the preregistration lock.
