# ContextTrace-Unseen-v1 pre-acquisition review

Review version: 0.1

Date: 2026-07-24

Status: machine review passed; external human-exposure attestation pending

## Outcome

The approved 36-family roster has been reduced to an exact, immutable
pre-acquisition catalog:

- 12 software/product documentation families;
- 12 policy/regulatory families;
- 12 support/operational families;
- 11 planned Natural OOD traces per family;
- 396 planned Natural OOD traces overall.

No source snapshot has been retained for the candidate corpus and no generator
has been called. The catalog is not yet authorized for acquisition.

Machine-readable catalog:
`benchmarks/contexttrace_unseen_v1/pre_acquisition_catalog.json`.

## Calibration exposure audit

`build_calibration_registry.py` scanned every JSON/JSONL artifact under the
prespecified benchmark, dataset, example, validation, and packaged-verifier
roots, including ignored/untracked benchmark output present in the workspace.

Observed result:

| Check | Result |
| --- | ---: |
| Structured files scanned | 2,433 |
| Read errors | 0 |
| Prior source URLs | 139 |
| Explicit prior family aliases | 38 |
| Prior dataset-level exposures | 23 |
| Conservative calibration registry records | 173 |
| Exact candidate family overlaps | 0 |
| Exact candidate domain-ID overlaps | 0 |
| Exact candidate canonical-URL overlaps | 0 |

The generated registry conforms to `source_manifest.schema.json`. All 173
provenance artifact hashes and normalized hashes were independently recomputed.
The registry deliberately retains legacy dataset sentinels and family-only
records where prior artifacts lack complete source snapshots.

This scan cannot discover:

- sources inspected outside the repository;
- private notes, deleted files, browser history, or unrecorded experiments;
- another contributor's undocumented exposure;
- family aliases not inferable from recorded identifiers.

That gap is resolved only by a human attestation or by replacing affected
families.

## Repository documentation review

Each of the 24 repository-backed documentation snapshots is pinned to a
40-character commit SHA-1. Twenty-three use released tags; Apache Pulsar's
official documentation repository has no suitable release tag, so the catalog
uses its immutable 2026-07-21 documentation commit and records the exception.

Every commit-pinned documentation path returned HTTP 200 during review:

- GitLab, Rust, Go, Node.js, Ruby, Spark, Flink, Beam, Airflow, NumPy, pandas,
  and JupyterLab;
- Kafka, Cassandra, Hadoop, HBase, ZooKeeper, Pulsar, Solr, Druid, Tomcat,
  HTTP Server, ActiveMQ Artemis, and Camel.

License profiles were reviewed from official repository/project terms:

- GitLab documentation: CC BY-SA 4.0;
- Rust: MIT or Apache-2.0;
- Go, NumPy, pandas, and JupyterLab: BSD-family terms;
- Node.js: MIT plus applicable third-party notices;
- Ruby: Ruby/BSD terms;
- Apache projects: Apache-2.0 plus applicable NOTICE files.

The acquisition filter excludes vendored, embedded, generated, or third-party
material unless its own terms are reviewed. Attribution and NOTICE artifacts
are retained alongside every source snapshot. Hosted-model transmission is
allowed only after the path-level filter has run.

## Regulatory-source review

Rendered eCFR pages currently redirect automated clients to an access-request
page. The approved collection method therefore prohibits rendered-site
scraping and uses only the official eCFR Versioner API.

The official titles endpoint reported an `up_to_date_as_of` date of
2026-07-22. The exact catalog pins that date and one practical CFR part per
issuing program:

| Family | Frozen part |
| --- | --- |
| SEC | 17 CFR part 240 — Securities Exchange Act rules |
| FTC | 16 CFR part 314 — Safeguards Rule |
| FDA | 21 CFR part 11 — electronic records/signatures |
| CFPB | 12 CFR part 1005 — Regulation E |
| OSHA | 29 CFR part 1904 — injury/illness recordkeeping |
| EPA | 40 CFR part 98 — greenhouse-gas reporting |
| FCC | 47 CFR part 64 — common-carrier rules |
| CMS | 42 CFR part 482 — hospital conditions |
| FAA | 14 CFR part 107 — small unmanned aircraft |
| NRC | 10 CFR part 20 — radiation protection |
| USDA | 7 CFR part 205 — National Organic Program |
| FMCSA | 49 CFR part 395 — hours of service |

The structure API confirmed all twelve parts exist, are not reserved, and have
content at the pinned date.

GovInfo states that U.S. Government works are generally public domain while
warning that government publications can contain third-party copyrighted
material. The extraction policy therefore excludes incorporated standards,
editorial third-party matter, images, forms, and other separately protected
content. Only the official regulatory text and government-authored metadata are
eligible.

## Hosted-model review

Approved candidate text is public and redistributable under its recorded terms.
The hosted route remains:

- model snapshot: `gpt-5-mini-2025-08-07`;
- API `store=false`;
- no personal-data or metadata-only source text;
- default abuse-monitoring retention recorded as up to 30 days unless the
  project has stricter controls;
- USD 10 total hard ceiling;
- no paid call before the source/configuration schedule is frozen.

The local route remains `gemma3:4b` at the manifest and weight hashes recorded
in `research/cain2027/GATE_B_DECISION_RECORD.md`.

## Remaining blocker: external exposure

Before this catalog can be frozen for acquisition, every person who influenced
ContextTrace/GroundLM verifier logic, prompts, thresholds, taxonomy, examples,
or benchmark selection must disclose whether any proposed family or its
documents were previously used for that work.

General familiarity with a product does not automatically count. Reading or
using its documentation to design, debug, calibrate, demonstrate, or assess the
verifier does count.

Decision choices:

- **8A — No additional project-relevant exposure.** The repository inventory
  is complete to the best of the team's knowledge.
- **8B — Additional exposure exists.** Provide the affected family IDs; they
  will be moved to calibration and replaced.
- **8C — Exposure is uncertain.** Identify the uncertain people or families;
  those families will be conservatively replaced or independently screened.

Until this attestation is recorded,
`validate_pre_acquisition --require-attestation` fails closed.

## Commands run

```bash
.venv/bin/python -m benchmarks.contexttrace_unseen_v1.build_calibration_registry
.venv/bin/python -m benchmarks.contexttrace_unseen_v1.validate_pre_acquisition
.venv/bin/python -m pytest -q \
  benchmarks/tests/test_unseen_calibration_registry.py \
  benchmarks/tests/test_pre_acquisition_catalog.py
```

Current focused result: 8 tests passed.
