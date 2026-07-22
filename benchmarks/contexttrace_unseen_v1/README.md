# ContextTrace-Unseen-v1

Status: acquisition not started; no manifest is frozen and no labels exist.

This benchmark is the next data milestone for `semantic_core_v2`. It has two
independent tracks:

- **Natural OOD:** 300--500 traces from software/product documentation,
  policy/regulatory documents, and support/operational knowledge bases.
- **Temporal/source condition:** approximately 100 traces made from versioned or
  authority-contrasting document pairs.

## Acquisition contract

Every trace must be produced by a real RAG run and retain the complete retrieval
and generation configuration. The natural track must cross BM25, vector, and
hybrid retrieval; multiple chunking or reranking settings; at least two generator
models; and clean as well as naturally failing outputs. Failures must not be
manually written or injected after generation.

Every candidate record must include:

- immutable trace ID and track;
- source family, source document ID, domain, canonical URL, snapshot hash, and
  publication window;
- retriever, chunker, reranker, generator provider/model/revision, prompt hash,
  random seed when supported, and generation timestamp;
- retrieved chunk IDs, selected context, answer, citations, and token/latency
  metadata;
- no gold diagnostic labels.

No source document, source family, or publication window may overlap the declared
calibration registry. Near-duplicate snapshots must be detected by normalized
content hash before freezing.

## Freeze sequence

1. Acquire candidate sources and produce natural RAG runs without invoking either
   `semantic_v1_calibrated` or `semantic_core_v2`.
2. Run leakage checks against every calibration source registry.
3. Freeze the unlabeled manifest with `freeze_untouched_split.py`.
4. Publish the sorted trace IDs, source metadata, generator/retriever configuration
   hashes, and manifest SHA-256. Do not publish gold annotations.
5. Independently annotate and seal labels according to `ANNOTATION_MANUAL.md`.
6. Freeze `semantic_core_v2`, its NLI model/revision, thresholds, metrics,
   statistical tests, and output schema.
7. Score once. Any inspected error becomes development data for later versions.

The absence of `manifest.json` in this directory is intentional until real source
acquisition is complete.
