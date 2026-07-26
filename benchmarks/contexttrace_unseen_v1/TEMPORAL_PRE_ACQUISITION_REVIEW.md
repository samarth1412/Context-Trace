# ContextTrace-Unseen-v1 temporal pre-acquisition review

Review version: 1.0

Date: 2026-07-26

Status: exact catalog locked and machine-validated; owner exposure attestation
and source-acquisition authorization pending

## Outcome

The temporal/source-condition track now has an exact pre-acquisition object:

- 20 distinct source pairs and 100 planned real-RAG cases;
- five pairs and 25 cases for each of the four preregistered pair types;
- 37 immutable source identities because seven authoritative U.S. Code
  snapshots are safely shared across the two authority-comparison strata;
- zero exact source-family, domain-ID, or canonical-identifier overlap with
  the recorded calibration registry or Natural OOD source manifest;
- zero paid endpoints and a USD 0 acquisition hard limit;
- no source acquisition, corpus retention, model call, verifier call,
  annotation, label access, evaluation, or publication authorization.

Machine-readable catalog:
`benchmarks/contexttrace_unseen_v1/temporal_pre_acquisition_catalog.json`.

Catalog SHA-256:
`a3781a725ad5100a610e8a6e2bec1b7458903333622ce0461d095c88c8bd6678`.

The catalog contains reviewed remote identities and expected metadata only. It
is not the final unlabeled corpus manifest. The final temporal generation
schedule cannot be frozen until authorized acquisition has produced locally
retained normalized-source hashes and pair-yield validation.

## Exact pair roster

| Pair type | Exact pair | Left → right snapshot | Cases |
| --- | --- | --- | ---: |
| Archived → current policy | COPPA, 16 CFR part 312 | eCFR 2020-01-01 → 2026-07-22 | 5 |
| Archived → current policy | Information blocking, 45 CFR part 171 | eCFR 2021-01-01 → 2026-07-22 | 5 |
| Archived → current policy | Workplace safety, 29 CFR part 1910 | eCFR 2020-01-01 → 2026-07-22 | 5 |
| Archived → current policy | Hazardous waste, 40 CFR part 261 | eCFR 2020-01-01 → 2026-07-22 | 5 |
| Archived → current policy | Aircraft airworthiness, 14 CFR part 25 | eCFR 2020-01-01 → 2026-07-22 | 5 |
| Old API → replacement API | scikit-learn feature names | 1.0.2 `get_feature_names` → 1.2.0 `get_feature_names_out` | 5 |
| Old API → replacement API | Matplotlib histogram normalization | 2.2.0 `normed` → 3.1.0 `density` | 5 |
| Old API → replacement API | SciPy image reading | SciPy 1.2.0 `misc.imread` → ImageIO 2.37.4 `imread` | 5 |
| Old API → replacement API | pytest fixture decorator | pytest 3.0.0 `yield_fixture` → 6.2.5 `fixture` | 5 |
| Old API → replacement API | Pillow resampling | Pillow 9.1.0 `ANTIALIAS` → 10.0.0 `Resampling.LANCZOS` | 5 |
| Noncanonical → canonical | Freedom of Information Act | Wikisource revision 13890117 → OLRC 5 U.S.C. § 552 | 5 |
| Noncanonical → canonical | Copyright fair use | Wikisource revision 14231081 → OLRC 17 U.S.C. § 107 | 5 |
| Noncanonical → canonical | Federal minimum wage | Wikisource revision 14227477 → OLRC 29 U.S.C. § 206 | 5 |
| Noncanonical → canonical | Patent eligibility | Wikisource revision 14305370 → OLRC 35 U.S.C. § 101 | 5 |
| Noncanonical → canonical | Civil-rights action | Wikisource revision 14227426 → OLRC 42 U.S.C. § 1983 | 5 |
| Low-authority → authoritative | HIPAA | Wikipedia revision 1357830950 → OLRC title 42 sections | 5 |
| Low-authority → authoritative | COPPA | Wikipedia revision 1359675456 → OLRC 15 U.S.C. §§ 6501–6506 | 5 |
| Low-authority → authoritative | Occupational Safety and Health Act | Wikipedia revision 1365514586 → OLRC 29 U.S.C. §§ 651–678 | 5 |
| Low-authority → authoritative | DMCA | Wikipedia revision 1358968889 → OLRC 17 U.S.C. §§ 512, 1201 | 5 |
| Low-authority → authoritative | Computer Fraud and Abuse Act | Wikipedia revision 1362897733 → OLRC 18 U.S.C. § 1030 | 5 |

Every git-backed snapshot is pinned to a 40-character commit, every Wikimedia
snapshot to a numeric revision ID, every eCFR snapshot to an effective date
plus preflight byte count and SHA-256, and every OLRC title to release point
119-102 plus preflight byte count and SHA-256. Acquisition must fail closed if
any downloaded identity or hash differs.

## Authority and material-relationship review

- Archived/current pairs use two official point-in-time eCFR Versioner API
  responses for the same title and part. Preflight hashes differ for every
  pair; acquisition must also record a structural XML diff and reject a pair
  without enough material changed text.
- API pairs use immutable first-party project documentation or docstrings.
  Each project's own deprecation documentation identifies the replacement.
  Acquisition is restricted to the exact allowlisted paths in the catalog.
- Noncanonical/canonical pairs contrast a pinned Wikisource community
  transcription with the matching section in the OLRC-prepared U.S. Code.
- Low-authority/authoritative pairs contrast a pinned Wikipedia informational
  summary with the applicable OLRC U.S. Code sections. The summary is retained
  unedited; it is not reconciled to the statute during acquisition.

“Authoritative” is an operational source-condition label relative to a
community transcription or summary. It does not assert that every U.S. Code
title has been enacted as positive law or that codified text always determines
ultimate legal effect. Acquisition must preserve title-level positive-law
status and any Statutes at Large caveat; generation must not turn the contrast
into legal advice.

Pair acceptance is based on source identity, authority, and material
relationship—not on anticipated answer correctness, verifier behavior, or
expected failure label.

## License, access, and privacy review

The eCFR and OLRC snapshots are U.S. Government works. The catalog records the
GovInfo government-work policy and excludes incorporated standards,
third-party editorial material, images, forms, and separately licensed media.
Issuing-body attribution is retained.

The five software pairs retain their repository licenses: BSD-3-Clause for
scikit-learn and SciPy, the Matplotlib project license, BSD-2-Clause for
ImageIO, MIT for pytest, and HPND for Pillow. Only first-party allowlisted
documentation and docstrings are eligible; vendored, generated, binary, test,
and third-party content is excluded.

Wikimedia text is reviewed under CC BY-SA 4.0. Acquisition must retain page
URL, page/revision ID, and an author-history attribution link. Talk pages,
usernames, edit summaries, user pages, non-text media, and fair-use content
are excluded.

All sources are public and require no authentication. Credentials, account
identifiers, request headers, and user metadata are outside the corpus.

This is a documented machine review, not legal advice. The project owner must
approve the catalog and remains responsible for the final reuse decision.

## Disjointness and exposure

The validator compares candidate source families, fine-grained domain IDs, and
canonical identifiers against both:

- `calibration/registry.json`; and
- `candidate_source_manifest.json`, the Natural OOD source manifest.

All three exact-overlap sets are empty. This automated result cannot detect
unrecorded reading, experiments, private notes, browser history, or exposure
by another contributor. Before acquisition, the project owner must attest that
none of these exact source pairs or documents influenced ContextTrace/GroundLM
verifier logic, prompts, thresholds, taxonomy, examples, or benchmark
selection. Ordinary subject-matter familiarity alone is not exposure.

Any later-discovered project-relevant exposure moves the affected source to
calibration and requires a replacement before the final unlabeled manifest is
frozen.

## Prespecified case allocation

The 100 slots are deterministic:

- 25 cases per pair type and five per exact pair;
- 34 BM25, 33 dense-vector, and 33 hybrid retrieval cases;
- 50 pinned-local and 50 pinned-hosted generator routes;
- 50 cases at 256/32 and 50 at 512/64 chunk size/overlap;
- 50 with deterministic reranking and 50 without;
- per pair: two left-only contexts, one mixed left-first, one right-only, and
  one mixed right-first context;
- per pair: direct-fact, scope, comparison, constraints, and
  qualified-summary question styles.

The allocation is a pre-acquisition plan. Source chunk IDs, queries, selected
contexts, and final configuration hashes are deliberately absent until
authorized acquisition and yield validation are complete.

## Budget and staged authorization

Source acquisition uses only public zero-cost endpoints:

- normal operating limit: USD 0;
- hard limit: USD 0;
- model calls during acquisition: none.

For later planning only, the catalog proposes 50 hosted initial generations,
at most two total attempts per request, a 50,000-byte input preflight cap, and
an 800-output-token cap. At the pinned recorded prices, the conservative
all-attempts upper bound is USD 1.41; the proposed normal limit is USD 2 and
hard ceiling is USD 3. These values do not authorize generation. A separate
exact-hash decision is required after acquisition and schedule freeze.

## Current decision boundary

An owner decision may authorize only acquisition and deterministic local
normalization of the exact catalog hash above. It must not authorize source
substitution, query or trace generation, local or hosted model calls, verifier
calls, labels, annotation, evaluation, manifest publication, or release.

After acquisition, the next mechanical gate is:

1. verify every immutable identity, expected hash, license artifact, and
   exclusion;
2. normalize the allowlisted text and record artifact hashes;
3. validate pair alignment and minimum changed/contrasting evidence yield;
4. reject rather than silently replace an ineligible pair;
5. build and hash the final 100-case temporal generation schedule;
6. request a separate generation authorization for that exact hash.

## Verification

```bash
.venv/bin/python -m \
  benchmarks.contexttrace_unseen_v1.build_temporal_pre_acquisition_catalog

.venv/bin/pytest -q \
  benchmarks/tests/test_unseen_v1_temporal_pre_acquisition.py
```

Current result: 8 tests passed. The tests cover deterministic reconstruction,
the committed hash, exact balance, prior-corpus identity disjointness,
authorization and budget boundaries, immutable-hash requirements, pair-role
integrity, case allocation, and overwrite protection.
