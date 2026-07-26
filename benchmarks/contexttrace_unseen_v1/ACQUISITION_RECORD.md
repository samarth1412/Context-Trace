# ContextTrace-Unseen-v1 source acquisition record

Record version: 1.0

Recorded: 2026-07-25

Status: source acquisition and deterministic local normalization complete;
trace generation not started

## Authorization and scope

The project owner authorized decision 9A on 2026-07-24:

- acquire and locally normalize only the exact 36 reviewed source snapshots;
- do not generate traces;
- do not invoke a local or hosted generator;
- do not invoke a ContextTrace verifier;
- do not annotate, evaluate, publish, or make external project changes.

During content-yield review, the project owner authorized amendment 10A on
2026-07-25:

- correct the Airflow root from `docs` to `airflow-core/docs` at the same
  commit;
- correct the Hadoop root from `hadoop-project` to
  `hadoop-common-project/hadoop-common/src/site/markdown` at the same commit;
- replace the inadequate HBase repository path with allowlisted operational
  documentation from the official HBase 2.6.5 binary release archive;
- recognize `.rdoc` as eligible source documentation within the already
  approved Ruby snapshot;
- do not substitute any source family or broaden authorization to model calls.

The HBase archive did not contain the monolithic reference guide expected
during amendment review. It did contain version-matched operational pages.
Only seven predeclared pages were retained: ACID semantics, bulk loading,
Cygwin operation, metrics, pseudo-distributed operation, replication, and
resources. Javadocs, generated reports, binaries, and all other archive members
were excluded. The upstream archive's published SHA-512 matched:

`67c1f59b7530a6f02cce6d3df8c0ba620130862a31828331584eee892922c37fbdb32b9e5320e897e1557d352e2f54aa0ddc097780abcd841a8d494134320a1a`.

## Result

The retained corpus-source layer contains:

| Measure | Result |
| --- | ---: |
| Source families | 36 |
| Software/product families | 12 |
| Policy/regulatory families | 12 |
| Support/operational families | 12 |
| Repository/release documentation files | 9,148 |
| Retained legal/NOTICE files | 40 |
| Raw retained snapshot bytes | 38,541,058 |
| UTF-8 normalized-text bytes | 124,613,611 |
| Calibration normalized-hash collisions | 0 |
| Model calls | 0 |
| Verifier calls | 0 |
| RAG traces | 0 |

The acquired sources are inputs, not empirical results. No answer, failure,
label, prediction, metric, or evaluation result exists in this record.

## Integrity and storage

The private working root is
`.tmp-contexttrace-unseen-v1-acquisition/`. It is covered by the repository's
existing `.tmp-*/` ignore rule and has mode `0700`. It contains:

- immutable sparse checkouts at the approved commits;
- the SHA-512-verified upstream HBase archive;
- deterministic filtered raw snapshots;
- deterministic UTF-8 normalized-text artifacts.

Raw third-party bytes and the upstream release archive are not staged for Git.
The candidate source manifest and acquisition ledger contain allowable
metadata and hashes only. Nothing has been published externally.

Integrity anchors:

| Artifact | SHA-256 |
| --- | --- |
| Reviewed/authorized catalog | `a85d00004bd19672d5ede7413775e311c479a948429c2e11bd1e6168d780d1b0` |
| Candidate source manifest | `6508533e869ef99930a4b29bea699779438a79dd951a8dbf2d04c78804bd90cc` |
| Acquisition ledger | `e773689a8841b0d5a25d7c78e48e0f209e80c208ec95612a1276c2c59a03763e` |
| Acquisition implementation | `4350e3633cc061de9531e64d472648239d65651b0e92c13383f183481e525be5` |
| Offline validator | `c6792df3a35f81f37fdf825788829b889a60673f547dd08f1f5eadae2a24b7e5` |

The candidate source manifest is not the frozen unlabeled dataset manifest.
It has not been published, and the source-to-generation schedule has not been
created or frozen.

## Validation

The offline validator:

- validates the source-manifest schema;
- requires the exact 36 catalog families and three balanced groups;
- re-hashes every raw and normalized artifact;
- reconstructs every normalized artifact from retained raw bytes;
- checks safe deterministic archive members and metadata;
- verifies repository commits, the HBase upstream SHA-512 and member
  allowlist, and eCFR part identities;
- requires a minimum reviewed documentation yield for repository/release
  snapshots;
- rejects exact normalized-content overlap with the calibration registry;
- requires zero model, verifier, and trace counts.

Run:

```bash
.venv/bin/python -m \
  benchmarks.contexttrace_unseen_v1.validate_acquisition
```

The 2026-07-25 result is recorded in `acquisition_validation.json`.

## Next gate

The 396-case Natural OOD schedule has been frozen and hashed at the value
recorded in `GENERATION_LOCK.md`. A separate recorded authorization of that
exact hash is required before generation starts.

The temporal/source-condition acquisition was later completed under its own
exact-hash decision and is recorded separately in
`TEMPORAL_ACQUISITION_RECORD.md`. Its source-to-generation schedule is not yet
created or authorized.
