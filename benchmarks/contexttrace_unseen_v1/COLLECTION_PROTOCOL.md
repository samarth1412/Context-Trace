# ContextTrace-Unseen-v1 collection protocol

Protocol version: 1.0  
Status: Natural OOD schedule locked; collection not started
Date: 2026-07-24

## Governing rule

The dataset must contain real, unedited outputs from recorded RAG
configurations. It may not contain manually written failures, injected answer
defects, reused benchmark cases, or examples selected using ContextTrace
predictions.

This protocol implements Phase 2 only. Annotation, successor-verifier
implementation, and evaluation begin only at their later gates.

## Roles and access

- **Collection operator:** acquires approved sources and runs RAG generation.
- **License/privacy reviewer:** approves source access, redistribution, and PII
  handling before a source becomes eligible.
- **Manifest custodian:** runs leakage checks and freezes the unlabeled
  manifest.
- **Label custodian:** appointed before annotation but receives no materials
  during collection.
- **Verifier implementers:** receive no gold labels and may not execute either
  evaluated verifier on candidate cases before freeze.

One person may hold the first three roles if every action is logged. The label
custodian must be independent of successor-verifier implementation.

## Step 1 — Approve source families

Before downloading source content, record:

- top-level domain group and fine-grained `domain_id`;
- source family, document, and lineage identifiers;
- canonical URL or stable identifier;
- source owner/publisher;
- license or terms URL;
- access restrictions and authentication needs;
- redistribution class;
- privacy classification;
- expected publication window;
- whether a temporal/authority counterpart exists.

Only public sources with `collection_permitted: true` and approved license
review are eligible for the production freeze. Do not bypass robots,
authentication, rate limits, paywalls, or contractual access controls.

User approval is required for the selected source families and their terms
before actual acquisition.

## Step 2 — Snapshot and normalize

Store a read-only raw snapshot and a UTF-8 normalized-text artifact. Record:

- raw snapshot SHA-256;
- normalized text path;
- normalized content SHA-256;
- collection and publication timestamps;
- content type and language;
- canonical identifier and source conditions;
- near-duplicate cluster identifier.

The freezer calculates normalized content by:

1. decoding the normalized-text artifact as UTF-8;
2. Unicode NFKC normalization;
3. collapsing every whitespace run to one ASCII space;
4. Unicode case folding;
5. SHA-256 over UTF-8 bytes.

Extraction from HTML, PDF, or other raw formats must be deterministic and
versioned separately. Extraction-version changes require new snapshot records.

`source_document_id` identifies one immutable document snapshot.
`document_lineage_id` groups versions or replacements. Versioned documents
therefore use different document IDs even when they share a lineage.

## Step 3 — Establish temporal and authority pairs

For each temporal/source-condition case, record two distinct source IDs and one
pair type. The authority basis must rely on publisher identity, official
replacement notices, effective dates, version history, or another source-level
criterion established before generation.

Do not infer authority from whether a candidate answer later agrees with a
source. Exclude a pair when ordering, applicability, or authority cannot be
established independently.

## Step 4 — Freeze the generation schedule

Before the first eligible run, approve and hash:

- source-to-configuration allocation;
- BM25, vector, and hybrid implementations/revisions;
- index construction;
- chunk strategies, sizes, overlaps, and units;
- rerankers, revisions, and top-N settings;
- at least two generator model families and immutable revisions;
- prompt templates;
- generation parameters;
- retry and timeout policy;
- citation format;
- random seeds where supported;
- provider budget and output-redistribution rules.

The Natural OOD allocation must cover all three retrieval families in every
domain group, multiple chunk sizes, reranking on/off, and at least two generator
families. No source family may exceed 10% of the track.

Exact generator/provider choices and paid API use require user authorization.

The 396-case Natural OOD schedule is locked in `generation_schedule.json` at
the hash recorded in `GENERATION_LOCK.md`. The temporal schedule is not yet
eligible because no approved versioned or authority-contrasting source pairs
have been acquired. The Natural lock does not authorize model calls.

## Step 5 — Execute actual RAG runs

The collection harness must log:

- stable case ID;
- complete retrieval candidate set;
- selected context IDs;
- query, answer, and citations;
- source IDs;
- timestamps, retries, token use, and latency;
- every configuration and configuration hash;
- raw provider response when terms permit;
- verifier history, which must remain empty.

The candidate trace artifact is a JSON object with:

- `case_id`;
- non-empty `query` and unedited non-empty `answer`;
- `retrieved_chunks`, each with an ID and text;
- `selected_context_ids`, all contained in the retrieved IDs;
- a `citations` list, which may be empty.

`semantic_v1_calibrated`, `semantic_core_v2`, and label-derived heuristics must
not run in the collection path. Collection operators may inspect transport
errors and metadata validity, but may not retain or discard a case because it
looks correct, incorrect, or diagnostically interesting.

Retries follow the frozen mechanical policy. A generation that still fails
after the allowed retries is logged as a collection failure and is not silently
replaced by a hand-written answer.

## Step 6 — Build candidate manifests

Create:

1. a candidate source manifest conforming to
   `source_manifest.schema.json`;
2. a populated calibration registry using the same source record schema and
   `manifest_kind: contexttrace_calibration_registry`;
3. a case manifest conforming to `case_manifest.schema.json`.

The calibration registry must cover every previously inspected source and must
declare disjointness for:

- source ID;
- source document ID;
- source family;
- fine-grained domain ID;
- publication window;
- raw snapshot hash;
- normalized content hash;
- near-duplicate cluster ID.

Candidate metadata, nested metadata, and trace artifacts must contain no labels,
adjudication, evidence spans, root causes, verdicts, predictions, or reviewer
notes.

## Step 7 — Run pre-freeze review

Before freezing:

- reconcile all IDs against artifact bytes;
- verify source and trace hashes;
- confirm timestamps include time zones and precede manifest creation;
- confirm sources were collected before generation;
- confirm selected contexts are a subset of retrieved chunks;
- confirm license and privacy classifications;
- run exact and near-duplicate clustering;
- confirm no source document crosses Natural OOD and temporal tracks;
- confirm labels do not exist and have never been accessible;
- confirm verifier history is empty;
- record exclusions and their predeclared reasons.

The review cannot use a verifier prediction.

## Step 8 — Freeze and seal

Run the production command in `README.md`. Unlike structural unit tests, the CLI
always enforces the full composition floor:

- 300–500 Natural OOD cases;
- at least 36 source families and 12 per domain group;
- all retrieval families in every group;
- at least two model families and chunk sizes;
- reranking enabled and disabled.

The temporal target is recorded as met at 80–120 cases. A smaller temporal track
may be sealed when source feasibility requires it, but the shortfall remains in
the composition record and limits paper claims.

The freezer validates schemas, policies, artifacts, calibration disjointness,
case-source consistency, composition, and forbidden fields. It emits:

- sorted unlabeled source and case metadata;
- hashes of input manifests and retained artifacts;
- composition summary;
- SHA-256 seal;
- external `.sha256` sidecar.

Any rejection stops the freeze. Do not edit the output or weaken a check to
force acceptance.

## Step 9 — Publish the unlabeled commitment

With explicit user authorization, publish:

- frozen unlabeled manifest;
- sidecar/payload SHA-256;
- schemas and freezer revision;
- calibration-overlap result;
- collection/configuration hashes;
- source metadata allowed by applicable terms.

Do not publish raw restricted content, secrets, gold labels, annotator notes, or
private provider records. Retain the independently published hash outside the
dataset workspace.

Only after this commitment may the project advance to annotation and successor
implementation under their separate access rules.

## Amendments and failures

Before collection, a change requires a dated protocol amendment. After
collection begins, record whether the change could influence outputs. After
manifest freeze, the original manifest and seal are immutable.

If a source disappears, a license changes, or corruption is discovered:

1. preserve the original record;
2. stop downstream work;
3. record the incident;
4. determine whether the untouched set is compromised;
5. create a new version only under an explicit amendment.

Never silently replace a frozen case.
