# ContextTrace-Unseen-v1 Natural OOD collection record

Record version: 1.0

Collection status: complete

Collection window: 2026-07-26T15:22:25.640662Z through
2026-07-26T17:25:28.466080Z

## Locked inputs

- Authorized generation schedule SHA-256:
  `e850d3eb6d374547cdbc70b2c0da02e0db8d9ff043633a577d9319f3d69e1695`
- Candidate source manifest SHA-256:
  `6508533e869ef99930a4b29bea699779438a79dd951a8dbf2d04c78804bd90cc`
- Acquired sources: 36, with 12 in each preregistered domain group
- Calibration normalized-content collisions: 0
- Pinned local generator/query model: Gemma 3 4B
- Pinned hosted generator: `gpt-5-mini-2025-08-07`
- Hosted hard ceiling: USD 10.00

## Collection outcome

- Scheduled Natural OOD slots processed: 396
- Untouched traces retained: 393
- Structural collection failures retained in the failure ledger: 3
- Source families represented: 36
- Retrieval-family counts: 131 BM25, 131 vector, 131 hybrid
- Domain counts: 132 software/product documentation, 129 policy/regulatory,
  132 support/operational
- Generator counts: 196 Gemma 3, 197 GPT-5 mini
- Successful local query-authoring calls: 396
- Successful local answer-generation calls: 196
- Successful hosted answer-generation calls: 197
- Retryable transport failures: 0
- Nonretryable provider failures: 0
- Total successful model calls: 789
- Hosted charge recorded from provider usage: USD 0.1524005
- Verifier calls: 0
- Labels created or accessed: false

The three failures were:

- `ctu1_natural_reg_fda_05`
- `ctu1_natural_reg_fda_06`
- `ctu1_natural_reg_fda_10`

For each, the immutable FDA source under the locked
`word_window_512_64_v1` configuration produced seven chunks while the schedule
required eight selected contexts. The collector did not duplicate contexts,
substitute a source, alter the configuration, or replace a failed case.

## Private freeze

- Frozen unlabeled case count: 393
- Frozen manifest SHA-256:
  `4ac9270ad3ac056e605bd7ec4623493293d83e7c2bf8d2b1e71fb28292e92fa2`
- Frozen artifact count: 465
- Natural OOD composition gate: met
- Temporal/source-condition target: not met and not attempted

The frozen manifest, traces, raw provider responses, embedding cache, and
budget ledger remain in the private mode-0700 collection workspace. They are
not committed or published by this record.

## Validation

- Candidate case-manifest schema errors: 0
- Pending hosted reservations: 0
- Acquisition, schedule, collection, and freeze tests: 78 passed
- Frozen manifest and every referenced artifact hash: verified
- Full source-family, domain-group, retrieval-family, two-model, two-chunk-size,
  and reranking-state composition checks: passed

