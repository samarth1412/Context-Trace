# ContextTrace-Unseen-v1 temporal generation lock

Lock version: 1.0

Recorded: 2026-07-26

Status: exact schedule frozen and executed under separate exact-hash authorization

## Frozen artifact

The temporal schedule is
`benchmarks/contexttrace_unseen_v1/temporal_generation_schedule.json`.

Schedule SHA-256:
`b6250401aadaaf913d7a8e9a5f095d2816cb798f9d512340d0702b8bb233340d`.

Its sidecar is `temporal_generation_schedule.json.sha256`. The offline builder
and fail-closed validator are in `build_temporal_generation_schedule.py`.
Rebuilding is deterministic and refuses to overwrite a different lock.

The schedule binds these completed inputs:

| Input | SHA-256 |
| --- | --- |
| Temporal pre-acquisition catalog | `a3781a725ad5100a610e8a6e2bec1b7458903333622ce0461d095c88c8bd6678` |
| Temporal source manifest | `6b3bbd4dff5ed7a2a80e26f87a7cf17a670be92083071526d33c2a3f60abf96e` |
| Temporal acquisition ledger | `2bb77e35b7f9fad3a080bcb2b2986cc7090e622de0444ea6f7240740a5584ca1` |
| Temporal acquisition validation | `6f01d38b1f8d985da9d701ba250af219c2ba2a18a6c19c08f2bbe5d77b2e8a10` |

## Allocation

The lock contains 100 actual-RAG answer-generation slots:

- 20 exact source pairs and five cases per pair;
- 25 cases each for archived/current policy, old/replacement API,
  noncanonical/canonical, and low-authority/authoritative contrasts;
- 34 BM25, 33 exact dense-vector, and 33 hybrid retrieval cases;
- 50 cases each at 256/32 and 512/64 token size/overlap;
- 50 with deterministic reranking and 50 without;
- 50 pinned local Gemma 3 and 50 pinned hosted GPT-5 mini answer calls;
- 34 exact-source-ID, 33 inline-numeric, and 33 no-citation prompts;
- 50 concise and 50 detailed answer prompts;
- 20 each for direct-fact, scope, comparison, constraints, and
  qualified-summary questions;
- 40 left-only, 20 right-only, 20 mixed-left-first, and 20
  mixed-right-first source pools.

Answer length is balanced 25/25 within each generator route. Generator
allocation differs by at most one case within every pair type.

## Pre-generation design amendment

The preliminary catalog assigned the same context mode to the same question
style in every pair. That would perfectly confound question style with source
availability.

Before any query, answer, prediction, label, or verifier result existed, the
schedule applied a deterministic five-pair Latin rotation within each pair
type. It preserves:

- all 20 approved pairs and 37 acquired sources;
- all 100 case IDs and five question styles per pair;
- the per-pair source-mode multiset: two left-only, one right-only, one
  mixed-left-first, and one mixed-right-first;
- the global 40/20/20/20 mode totals;
- every retrieval, chunking, reranking, generator, and citation assignment.

After rotation, each question style has eight left-only and four of every
other source mode. No source or case was substituted. The exact rule and hash
of the preliminary plan are embedded in the schedule.

## Frozen questions

All 100 user questions are stored verbatim in the schedule. They are produced
by one fixed template for each of the five question styles and one
pair-specific public topic established during source review.

- There is no query-authoring model call.
- Every question is unique, one line, at most 204 characters, and ends in a
  question mark.
- Humans may not rewrite, select, reject, or replace a question after lock.
- Questions are not written to inject an answer error. Clean answers, errors,
  and abstentions must arise from the actual source pool, retrieval, and
  generator behavior.

This removes 100 auxiliary local model calls compared with the Natural OOD
query-authoring workflow and makes the temporal question set exactly
reconstructable before generation.

## Source-pool and retrieval rule

Each case indexes only its frozen candidate source pool:

- `left_only`: the archived, deprecated, noncanonical, or low-authority side;
- `right_only`: the current, replacement, canonical, or authoritative side;
- mixed modes: both sides, with the named first side affecting only stable
  chunk-ID and exact-score tie resolution.

There is no per-side retrieval quota in mixed cases. Retrieval may naturally
select one or both sides. Imposing a quota after seeing results is forbidden.

Documents are chunked independently so no chunk crosses a source boundary.
The retriever considers 20 candidates, deterministic reranking is applied when
scheduled, and up to three contexts are passed to the generator. At least one
context is required. The three-context cap accommodates complete short
statutory sections without fabricating or duplicating chunks.

The chunker, BM25, pinned MiniLM dense retriever, hybrid RRF, reranker,
generator definitions, and six answer prompts are byte-for-byte compatible
with the Natural OOD schedule.

## Generation and retention

The local route remains pinned to `gemma3:4b` and its recorded manifest and
weight digests. The hosted route remains pinned to
`gpt-5-mini-2025-08-07`, Responses API `store=false`, no tools, minimal
reasoning effort, and an 800 output/reasoning-token cap.

Every answer is retained unedited, including refusals, abstentions, unsupported
answers, and source-condition mistakes. There is no retry for answer quality,
correctness, citation quality, failure type, refusal, or abstention.

One retry is allowed only for the frozen transient transport conditions.
Exhausted cases are recorded as structural collection failures and are not
replaced. Hosted and local routes each run at concurrency one.

No ContextTrace/GroundLM verifier, NLI model, label, annotation, adjudication,
or semantic eligibility decision is permitted during collection.

## Privacy and cost guard

Only the already reviewed public normalized text is eligible. Wikimedia
usernames and edit summaries, personal data not explicitly reviewed,
credentials, secrets, metadata-only text, authorization headers, API keys,
account identifiers, and credential paths are forbidden.

The hosted guard is fail-closed:

- USD 2 normal operating limit;
- USD 1 retry contingency;
- USD 3 hard ceiling;
- 50 scheduled hosted initial requests;
- at most two total attempts per hosted request;
- 50,000 UTF-8 input-byte preflight maximum;
- 800 output/reasoning-token maximum per attempt;
- conservative all-attempts upper bound: USD 1.41;
- missing usage is charged at the conservative request maximum;
- pilots and retries count against the same ceiling;
- collection stops before a request that could exceed a limit.

No model, prompt, source pool, output length, or case allocation may be
silently changed to avoid a cost, timeout, or provider failure.

## Authorization boundary

This lock does not itself authorize generation. Its authorization fields
remain false. The project owner separately authorized only execution of this
exact schedule under the USD 3 hard ceiling on 2026-07-26. That execution
completed all 100 slots with no structural failures or retries and charged USD
0.03685225 for 50 hosted attempts.

The separate authorization and aggregate chain-of-custody record are in
`TEMPORAL_RUN_AUTHORIZATION.md`, `temporal_run_authorization.json`,
`TEMPORAL_COLLECTION_RECORD.md`, and `temporal_collection_record.json`.
Private unedited artifacts remain Git-ignored and unpublished.

No pilot, query rewriting, verifier or NLI calls, annotation, evaluation,
publication, release, or source substitution was authorized or performed.

## Verification

```bash
.venv/bin/python -m \
  benchmarks.contexttrace_unseen_v1.build_temporal_generation_schedule \
  verify \
  --expected-sha256 \
  b6250401aadaaf913d7a8e9a5f095d2816cb798f9d512340d0702b8bb233340d
```

Passing verification proves input-hash integrity, source-role binding,
question reconstruction, component compatibility, factor balance,
deconfounding, case hashes, privacy/cost boundaries, and the absence of
downstream authorization. It does not run a model or establish scientific
results.
