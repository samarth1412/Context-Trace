# ContextTrace-Unseen-v1 temporal acquisition record

Record version: 1.0

Recorded: 2026-07-26

Status: complete and independently reconstructable; temporal generation not
authorized

## Authorized scope

The project owner authorized decision `11A` for zero-cost acquisition and
local normalization of only temporal catalog SHA-256
`a3781a725ad5100a610e8a6e2bec1b7458903333622ce0461d095c88c8bd6678`.
The verbatim decision is preserved in
`TEMPORAL_ACQUISITION_AUTHORIZATION.md`.

The authorization excluded source substitution, paid endpoints, query or
trace generation, model and verifier calls, labels, annotation, evaluation,
publication, and release. Those exclusions remained enforced throughout the
run.

## Outcome

All exact catalog identities were acquired and deterministically normalized:

| Measure | Result |
| --- | ---: |
| Source identities | 37 |
| Source pairs | 20 |
| Planned temporal case slots | 100 |
| eCFR point-in-time XML snapshots | 10 |
| Commit-pinned GitHub snapshots | 10 |
| OLRC release-point ZIP snapshots | 7 |
| MediaWiki revision snapshots | 10 |
| Retained raw bytes | 52,206,111 |
| Normalized UTF-8 bytes | 17,461,866 |
| Retained repository license files | 34 |
| Selected statutory sections | 52 |
| Prior-corpus normalized-hash collisions | 0 |
| Wikimedia user-metadata records | 0 |
| Paid endpoint calls | 0 |
| Model calls | 0 |
| Verifier calls | 0 |
| RAG traces | 0 |

Every pair passed its frozen authority/material-relationship check and
mechanical evidence-yield check. No source, revision, path, section, or pair
was substituted.

## Source-specific verification

- eCFR responses match every cataloged effective date, expected byte count,
  and SHA-256. XML normalization excludes graphics, forms, scripts, styles,
  SVG, and other non-text elements.
- Repository content is restricted to the catalog's exact first-party path
  allowlist at the pinned 40-character commit. Commit-pinned root license
  material is retained in deterministic archives.
- OLRC archives match every release-point byte count and SHA-256. ZIP traversal,
  encryption, and expansion limits are enforced. Only the exact cataloged
  sections are normalized; 52 sections were found. Title-level positive-law
  status and the ultimate-legal-effect limitation are retained as metadata.
- Wikimedia content matches every cataloged page ID, revision ID, timestamp,
  and byte size, and its API content SHA-1 is retained. The raw record excludes
  usernames, edit summaries, talk pages, and account metadata. Normalization
  removes references, external-link sections, templates, media, comments, and
  user-oriented metadata while retaining article/statutory text.

## Pair-yield validation

The validator reconstructs normalized text from retained raw bytes before
checking each pair:

- archived/current pairs require non-identical content and at least five
  changed non-empty lines on both sides;
- old/replacement API pairs require the frozen deprecation/replacement anchors
  in the correct source side;
- noncanonical/canonical and low-authority/authoritative pairs require the
  exact OLRC section selection and distinct paired text;
- every pair must retain sufficient text and two distinct normalized hashes.

The pair records contain structural counts and sequence ratios only. They do
not contain correctness judgments, predictions, failure labels, or evaluation
results.

## Recoverable collection events

The first pass stopped on an official eCFR HTTP 503 for the exact current 29
CFR part 1910 snapshot. The endpoint later recovered and returned the
preflight-matching bytes. No alternate endpoint or snapshot was used.

Pre-ledger validation also detected and corrected four extraction mechanics:

- repository normalization was changed from catalog path order to
  deterministic archive path order;
- OLRC en-dash section identifiers were normalized for matching only;
- the minimum text floor was adjusted for the complete but short 35 U.S.C.
  § 101 source;
- the current MediaWiki API's hexadecimal content SHA-1 representation was
  validated directly.

These changes neither altered the frozen source identities nor inspected
system outputs. Superseded pre-ledger normalized files were moved to a
recoverable temporary location; they are not corpus artifacts.

## Integrity and storage

The private artifact root is
`.tmp-contexttrace-unseen-v1-temporal-acquisition/`. It is covered by the
repository's `.tmp-*/` ignore rule and has mode `0700`. Raw source bytes and
normalized text are not staged for Git or published.

Integrity anchors:

| Artifact | SHA-256 |
| --- | --- |
| Temporal catalog | `a3781a725ad5100a610e8a6e2bec1b7458903333622ce0461d095c88c8bd6678` |
| Authorization JSON | `9c88da5c234bc5ae97d6ecf6bcf14b0c2bec0963a371ba78ac6797a104cc3733` |
| Temporal source manifest | `6b3bbd4dff5ed7a2a80e26f87a7cf17a670be92083071526d33c2a3f60abf96e` |
| Temporal acquisition ledger | `2bb77e35b7f9fad3a080bcb2b2986cc7090e622de0444ea6f7240740a5584ca1` |
| Acquisition validation | `6f01d38b1f8d985da9d701ba250af219c2ba2a18a6c19c08f2bbe5d77b2e8a10` |
| Acquisition and validator implementation | `7618bd746ce77a2b73a844ed1676850f9bace7389448e017ad249f6f52a682fd` |

The source manifest and ledger are metadata integrity records, not the final
unlabeled case manifest. They have not been published externally.

## Independent offline validation

```bash
.venv/bin/python -m \
  benchmarks.contexttrace_unseen_v1.acquire_temporal_sources validate
```

The command revalidates the manifest schema, reconstructs all 37 normalized
sources from retained raw bytes, recomputes artifact/member hashes, rechecks
the 20 pair-yield records, rejects prior-corpus normalized-content overlap, and
requires zero paid, model, verifier, and trace counts. The recorded result is
`temporal_acquisition_validation.json`.

## Next gate

Acquisition does not authorize generation. The next step is to build the exact
100-case temporal source-to-configuration schedule from these acquired source
hashes, review its prompts, retrieval/chunking/reranking settings, privacy and
cost guard, freeze its SHA-256, and request a separate exact-hash generation
authorization.
