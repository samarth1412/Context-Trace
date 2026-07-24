# ContextTrace-Unseen-v1 leakage audit

Audit version: 1.0  
Status: **not run—no candidate sources or cases exist**  
Date: 2026-07-24

This file defines the audit that must pass before a frozen unlabeled manifest
can exist. It does not claim that the future corpus is disjoint.

## Calibration boundary

All previously inspected ContextTrace evidence is calibration data, including
RAGTruth and derived subsets, ContextTrace-Diag-150, Naturalistic Audit/Dev/Eval
v2, Groundedness-Truth-Gap, ARES, CRAG, repository benchmark cases, adversarial
stress cases, source-condition injections, demonstrations, review packets, and
public-app smoke outputs.

The production calibration registry must enumerate their source material at the
same granularity as candidate sources. An empty registry fails closed.

## Mandatory disjointness dimensions

| Dimension | Purpose | Failure behavior |
| --- | --- | --- |
| `source_id` | Reject a reused immutable snapshot record | Stop |
| `source_document_id` | Reject the same document snapshot | Stop |
| `source_family` | Prevent sibling documents from leaking source conventions | Stop |
| `domain_id` | Enforce fine-grained domain novelty | Stop |
| `publication_window` | Enforce declared time separation | Stop |
| `snapshot_sha256` | Detect byte-identical snapshots | Stop |
| `normalized_content_sha256` | Detect format/whitespace/case variants | Stop |
| `near_duplicate_cluster_id` | Detect paraphrased, mirrored, or version-near material | Stop |

The broad domain groups are sampling strata and are intentionally shared across
the study design. `domain_id` is the finer disjointness key.

## Candidate-internal leakage

The audit also rejects:

- duplicate source IDs or document IDs;
- duplicate case IDs;
- duplicate trace artifact paths;
- identical content copied across incompatible family/domain clusters;
- one source document used in both evaluation tracks;
- temporal pairs that do not name two distinct case sources;
- case metadata inconsistent with its primary source;
- selected context IDs absent from retrieval results;
- any label, annotation, adjudication, verdict, root cause, evidence span,
  prediction, or reviewer note in candidate inputs;
- any prior evaluated-verifier invocation;
- case generation after label creation/access;
- generation before source acquisition or after candidate-manifest creation.

Multiple RAG runs over one document are permitted within one track, but they
remain one correlated source-document/family cluster during analysis.

## Hash and mutation audit

At freeze time:

- raw snapshot bytes must match `snapshot_sha256`;
- normalized text must match the defined normalized-content hash;
- trace bytes must match `trace_sha256`;
- configuration and prompt hashes must be present and syntactically valid;
- input manifests receive canonical JSON hashes;
- the frozen payload receives a SHA-256 seal.

After freeze, verification recomputes the payload seal. Supplying the
independently published hash detects replacement and resealing. Optional
artifact verification rechecks every retained byte artifact.

## Required audit record

When real candidates exist, replace the status with a dated audit record that
contains:

- candidate source and case counts;
- calibration-registry count and hash;
- source/case schema versions;
- freezer source revision and hash;
- overlap counts for every dimension;
- internal duplicate and near-duplicate counts;
- excluded records with predeclared reasons;
- artifact verification count;
- candidate label/verifier scan result;
- final manifest payload hash;
- operator and independent reviewer;
- deviations or unresolved risks.

Zero overlap must be demonstrated, not assumed.

## Current result

No audit result is available because:

- source acquisition has not started;
- the full calibration source registry has not been built;
- candidate manifests do not exist;
- no real RAG trace is eligible for freezing.

Accordingly, `manifest.json`, a manifest sidecar, and any “untouched” evidence
claim must remain absent.
