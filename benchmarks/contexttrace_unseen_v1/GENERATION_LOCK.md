# ContextTrace-Unseen-v1 generation lock

Lock version: 1.0

Recorded: 2026-07-24

Status: Natural OOD schedule locked; exact-hash generation authorized

## Locked artifacts

| Artifact | SHA-256 |
| --- | --- |
| Candidate source manifest | `6508533e869ef99930a4b29bea699779438a79dd951a8dbf2d04c78804bd90cc` |
| Generation schedule | `e850d3eb6d374547cdbc70b2c0da02e0db8d9ff043633a577d9319f3d69e1695` |

The schedule is
`benchmarks/contexttrace_unseen_v1/generation_schedule.json`; its external
sidecar is `generation_schedule.json.sha256`. The builder and verifier are in
`build_generation_schedule.py`. Rebuilding is deterministic and refuses to
overwrite a different lock.

## Natural OOD allocation

The lock contains 396 actual-RAG case slots:

- 36 source families and 11 cases per family;
- 132 cases in each of software/product documentation, policy/regulatory, and
  support/operational knowledge;
- 132 cases each for BM25, dense-vector, and hybrid retrieval;
- 198 cases per chunking configuration: 256/32 and 512/64 word-token
  size/overlap;
- 198 cases with deterministic reranking and 198 without;
- 198 cases for pinned local `gemma3:4b` and 198 for pinned hosted
  `gpt-5-mini-2025-08-07`;
- 132 cases each with no citations, inline numeric citations, and exact context
  ID citations;
- 132 cases each selecting 3, 5, and 8 contexts;
- 198 concise and 198 detailed answer prompts.

Within every domain group, every factor is exactly marginally balanced.
Assignments are made by a deterministic salted hash over case IDs, without
source-content, label, answer, or verifier information.

## Query creation

Each family receives the same 11 prespecified query styles. A pinned local
Gemma call creates exactly one question from a deterministically chosen public
source excerpt. The query must be one non-empty line of at most 240 characters
ending in a question mark.

Humans may inspect only transport and structural validity. They may not select,
rewrite, retain, or reject a query based on apparent difficulty, answerability,
anticipated label, or expected verifier behavior.

## Retrieval and generation

- BM25 is Okapi BM25 with `k1=1.2`, `b=0.75`, candidate `k=20`, and stable
  chunk-ID tie breaking.
- Dense retrieval is exact cosine over normalized
  `sentence-transformers/all-MiniLM-L6-v2` embeddings at immutable revision
  `1110a243fdf4706b3f48f1d95db1a4f5529b4d41`.
- Hybrid retrieval uses equal-weight reciprocal-rank fusion with `rrf_k=60`.
- Enabled reranking uses the frozen deterministic query-likelihood
  configuration recorded in the JSON lock.
- Both answer generators receive the same evidence-only prompt contract.
  Answers are retained unedited, including natural errors and abstentions.
- No ContextTrace verifier, label, manual error injection, or semantic
  eligibility decision is permitted during collection.

## Hosted privacy and cost guard

The hosted route uses the Responses API with `store=false`, no tools, standard
service tier, default project retention, and a recorded abuse-monitoring
retention maximum of 30 days. Personal data, secrets, credentials,
`metadata_only` source text, account identifiers, and authorization headers are
forbidden.

The guard is fail-closed:

- USD 8 normal operating allocation;
- USD 2 retry contingency;
- USD 10 hard ceiling;
- 198 scheduled hosted requests;
- at most two total attempts per request;
- 50,000 UTF-8 input-byte preflight maximum;
- 800 output/reasoning-token maximum per attempt;
- conservative all-attempts upper bound: USD 5.5836;
- missing usage is charged at the conservative preflight maximum;
- collection stops before any request that could exceed a limit.

No configuration may be silently changed to avoid a cost, timeout, or provider
failure.

## Retry and failure policy

One retry is allowed only for the frozen transient transport conditions.
There is no retry for answer quality, apparent correctness, failure type,
refusal, or abstention. After exhaustion, the failure is recorded and the case
is not manually replaced.

Hosted and local generation each run at concurrency one. Every raw response,
retry, usage record, latency, and configuration hash is retained subject to
the privacy and redistribution policy.

## Temporal/source-condition pre-acquisition lock

The exact temporal pre-acquisition catalog is now locked at SHA-256
`a3781a725ad5100a610e8a6e2bec1b7458903333622ce0461d095c88c8bd6678`.
It contains 20 versioned or authority-contrasting pairs, 37 immutable source
identities, and a deterministic 100-case plan:

- 25 archived-policy to current-policy cases;
- 25 old-API to replacement-API cases;
- 25 noncanonical-copy to canonical-source cases;
- 25 low-authority-summary to authoritative-source cases.

The catalog passes exact source-family, domain-ID, and canonical-identifier
disjointness checks against both calibration and Natural OOD records. License,
access, privacy, immutability, authority-basis, and material-relationship
reviews are recorded in `TEMPORAL_PRE_ACQUISITION_REVIEW.md`.

This is not a generation-schedule amendment. Temporal source acquisition
remains unauthorized until the project owner supplies the required exposure
attestation and explicitly approves the exact catalog hash. Generation remains
unauthorized until acquired normalized-source hashes and pair-yield validation
support a final schedule, that schedule is frozen, and its exact hash receives
a separate authorization.

No placeholder, manually authored conflict, source substitution, or reuse of a
Natural OOD source is permitted.

## Verification

```bash
.venv/bin/python -m \
  benchmarks.contexttrace_unseen_v1.build_generation_schedule verify \
  --source-manifest \
  benchmarks/contexttrace_unseen_v1/candidate_source_manifest.json \
  --schedule benchmarks/contexttrace_unseen_v1/generation_schedule.json \
  --expected-sha256 \
  e850d3eb6d374547cdbc70b2c0da02e0db8d9ff043633a577d9319f3d69e1695
```

Passing verification proves structural integrity and allocation balance. The
separate project-owner authorization for this exact hash is preserved in
`NATURAL_OOD_RUN_AUTHORIZATION.md`.
