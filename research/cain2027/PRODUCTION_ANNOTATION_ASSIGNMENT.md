# ContextTrace-Unseen-v1 production annotation assignment

Recorded: 2026-07-29

Status: label-free annotator packets built; human annotation pending

Packet version: `contexttrace-production-annotation-packet-v1`

Frozen manifest SHA-256:
`8bf65cd7e2c95ccfcc12e78b580fc47e4157b0f808ba3fcace0a24bfcdc2e5f6`

Private assignment-plan payload SHA-256:
`77b23a05249e223ac886717bf9e8fe236f679ef6cfd0e9197449dc7f2a2ae52e`

## Allocation

- total cases: 493;
- `pul`: 309 cases;
- `sid`: 308 cases;
- double-annotated cases: 124/493 (25.15%);
- temporal/source-condition cases double-annotated: 100/100;
- stratified Natural OOD cases double-annotated: 24;
- remaining Natural OOD cases assigned once: 369.

The 24 Natural OOD overlap cases are selected deterministically across domain,
retrieval family, generator family, reranking state, chunk size, and source
family. The remaining Natural OOD cases are divided deterministically while
balancing annotator workload.

Each private packet contains its assigned trace inputs, relevant normalized
source material, source-condition metadata, the frozen annotation documents,
and an empty writable per-case annotation template. It contains no gold label,
prediction, verifier output, NLI output, disagreement, or agreement result.

The case-level overlap plan remains under the custodian. Only aggregate
allocation and its payload hash are recorded here.
