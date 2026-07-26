# CAIN 2027 Gate B decision record

Decision-record version: 1.0

Recorded: 2026-07-26

Gate status: Natural OOD collection frozen; temporal catalog locked pending
acquisition authorization

## Approval log

- 2026-07-24 — Project owner selected `7A`, approving the 36-family roster in
  `benchmarks/contexttrace_unseen_v1/SOURCE_FAMILY_APPROVAL_ROSTER.md` for
  document-level license, access, and calibration-overlap review. This does not
  authorize corpus-content download or generation until that review is
  completed and the exact document catalog is frozen.
- 2026-07-24 — Project owner selected `8A`, attesting that no additional
  project-relevant exposure to the proposed source families or documents is
  known beyond the repository calibration inventory. The exact catalog passed
  document, license/access, and recorded-overlap review and is ready for a
  separate final acquisition decision. This attestation does not itself
  authorize content download, normalization, or model calls.
- 2026-07-24 — Project owner selected `9A`, authorizing acquisition and local
  normalization of only the exact 36 reviewed source snapshots. The decision
  does not authorize source substitution, trace generation, local or hosted
  model calls, annotation, evaluation, publication, or external changes.
- 2026-07-25 — Project owner authorized amendment `10A` after content-yield
  review. The Airflow and Hadoop documentation roots were corrected without
  changing their repositories or commits; HBase 2.6.5 moved to an official
  SHA-512-verified Apache release archive with a strict operational-page
  allowlist; and Ruby RDoc became an eligible source format. No source family
  was substituted and model-call authorization was not broadened.
- 2026-07-25 — Acquisition and deterministic local normalization completed
  for all 36 families. Offline reconstruction validated 9,148 documentation
  files, 40 legal/NOTICE files, balanced 12/12/12 groups, zero calibration
  normalized-hash collisions, and zero model, verifier, or trace calls.
- 2026-07-24 — Project owner confirmed that the OpenAI API project uses the
  default data-retention mode and approved it for this public-source study.
  Hosted requests remain limited to eligible public source text, use the
  Responses API with `store=false`, exclude personal data and secrets, and are
  subject to the recorded abuse-monitoring retention of up to 30 days.
- 2026-07-24 — The deterministic 396-case Natural OOD generation schedule was
  created and validated at SHA-256
  `e850d3eb6d374547cdbc70b2c0da02e0db8d9ff043633a577d9319f3d69e1695`.
  The lock balances every factor within each domain and records prompts,
  retrievers, chunking, reranking, model revisions, retries, timeouts, privacy,
  and the fail-closed hosted cost guard. This records a review object; it does
  not authorize model calls.
- 2026-07-26 — The project owner explicitly authorized execution of the exact
  Natural OOD schedule SHA-256
  `e850d3eb6d374547cdbc70b2c0da02e0db8d9ff043633a577d9319f3d69e1695`
  under the recorded USD 10 hard ceiling. The authorization scope and
  exclusions are preserved in
  `benchmarks/contexttrace_unseen_v1/NATURAL_OOD_RUN_AUTHORIZATION.md`.
- 2026-07-26 — The project owner selected Option A, retaining the planned
  temporal/source-condition track. An exact 20-pair, 100-case pre-acquisition
  catalog was locked at SHA-256
  `a3781a725ad5100a610e8a6e2bec1b7458903333622ce0461d095c88c8bd6678`.
  This selection authorizes preparation and review only; it does not supply
  the external-exposure attestation or authorize source acquisition, model
  calls, annotation, evaluation, publication, or release.
- 2026-07-26 — The project owner supplied the exact temporal-source exposure
  attestation and authorized decision `11A`: zero-cost acquisition and local
  normalization of only catalog SHA-256
  `a3781a725ad5100a610e8a6e2bec1b7458903333622ce0461d095c88c8bd6678`.
  Source substitution, paid endpoints, query/trace generation, model or
  verifier calls, annotation, evaluation, publication, and release remain
  unauthorized. The verbatim authorization and machine-readable scope are in
  `benchmarks/contexttrace_unseen_v1/TEMPORAL_ACQUISITION_AUTHORIZATION.md`
  and `temporal_acquisition_authorization.json`.
- 2026-07-26 — Acquisition and deterministic local normalization completed for
  all 37 exact temporal source identities and 20 pairs. Offline reconstruction
  validated 52,206,111 raw bytes, 17,461,866 normalized bytes, 34 retained
  repository license files, 52 selected statutory sections, zero normalized
  hash collisions with prior corpora, zero Wikimedia user-metadata records,
  and zero paid, model, verifier, or trace calls. No source was substituted.
  The temporal source manifest SHA-256 is
  `6b3bbd4dff5ed7a2a80e26f87a7cf17a670be92083071526d33c2a3f60abf96e`.

## User-authorized decisions

The following choices were made directly by the project owner:

1. Use only public, official sources with explicit reuse permission.
2. Use one pinned local generator and one pinned hosted generator.
3. Use the two already-available annotators, with separate label custody and
   adjudication.
4. Use the already-installed `gemma3:4b` local model.
5. Use the pinned OpenAI `gpt-5-mini-2025-08-07` snapshot with a lower budget
   than the originally proposed USD 25 ceiling.
6. Because no independent third person is currently available, prepare a
   recruitment and custody package before annotation.

The 36 proposed source families and their exact snapshots have passed review
and are authorized for local acquisition and normalization under decision 9A.

## Frozen generator identities

### Local stratum

| Field | Frozen value |
| --- | --- |
| Provider/runtime | Ollama |
| Model | `gemma3:4b` |
| Model family | Gemma 3 |
| Ollama manifest digest | `sha256:a2af6cc3eb7fa8be8504abaf9b04e88f17a119ec3f04a3addf55f92841195f5a` |
| Weight-layer digest | `sha256:aeda25e63ebd698fab8638ffb778e68bed908b960d39d0becc650fa981609d25` |
| Weight-layer size | 3,338,792,448 bytes |
| Template digest | `sha256:e0a42594d802e5d31cdc786deb4823edb8adff66094d49de8fffe976d753e348` |
| Parameter-layer digest | `sha256:3116c52250752e00dd06b16382e952bd33c34fd79fc4fe3a5d2c77cf7de1b14b` |
| Bundled-license digest | `sha256:dd084c7d92a3c1c14cc09ae77153b903fd2024b64a100a0cc8ec9316063d2dbc` |
| Output terms | Gemma Terms state that Google claims no rights in generated output |

The manifest and weight-layer digests were recomputed from the installed
artifacts on 2026-07-24. The mutable `gemma3:4b` tag is never sufficient on its
own: the harness must fail when either recorded digest changes.

The installed Modelfile defaults (`temperature=1`, `top_k=64`, `top_p=0.95`)
are not yet generation settings. Final generation parameters, prompt, seed
policy, and Ollama/runtime version belong to the configuration lock created
before the first eligible run.

Terms references:

- <https://ai.google.dev/gemma/terms>
- <https://ai.google.dev/gemma/prohibited_use_policy>
- <https://ollama.com/library/gemma3/tags>

### Hosted stratum

| Field | Frozen value |
| --- | --- |
| Provider | OpenAI API |
| Model | `gpt-5-mini-2025-08-07` |
| Model family | GPT-5 mini |
| Endpoint | Responses API with `store=false`, unless a later privacy review requires a stricter eligible endpoint/configuration |
| Published standard input price | USD 0.25 per 1M tokens |
| Published standard cached-input price | USD 0.025 per 1M tokens |
| Published standard output price | USD 2.00 per 1M tokens |
| Training use | API data not used for training unless the account explicitly opts in |
| Project data-retention mode | Default |
| Default abuse-log retention | Up to 30 days |
| Output rights | Customer owns output as between customer and OpenAI, subject to applicable terms and law |

Terms and operational references:

- <https://developers.openai.com/api/docs/models/gpt-5-mini>
- <https://platform.openai.com/docs/models/default-usage-policies-by-endpoint>
- <https://openai.com/policies/terms-of-use/>

Before the first request, the collection operator must verify the project-level
data controls and record only the control state, never account identifiers or
credentials. Content with personal data or a `metadata_only` redistribution
classification is not sent to the hosted model without a specific documented
review.

## Approved budget envelope

The total hosted-generation hard ceiling is **USD 10.00** for
ContextTrace-Unseen-v1 acquisition, including pilots, eligible cases, and
mechanical retries.

- Normal operating allocation: USD 8.00.
- Contingency reserved for frozen-policy retries: USD 2.00.
- No request may be sent when its conservative maximum estimate would make the
  cumulative upper bound exceed USD 10.00.
- The harness must calculate cost from provider-reported uncached input,
  cached input, reasoning/output, and any separately billed units.
- A missing usage record is charged using the request's conservative token
  maximum, not as zero.
- Pilot spending counts toward the same ceiling.
- Collection stops, rather than silently changing model, prompt, output length,
  or case allocation, when the ceiling is reached.
- A budget increase requires another explicit user decision and a dated
  protocol amendment.

For scale, 600 successful calls averaging 12,000 uncached input tokens and
1,000 output tokens would cost approximately USD 3.00 at the recorded standard
rates. The USD 8 operating allocation therefore permits substantial headroom,
but this is a planning estimate rather than permission to ignore the hard
guard.

No paid call had been made under this authorization when this record was
created.

## Annotation custody decision

Two annotators are available, but the required independent label
custodian/adjudicator is not. Annotation remains blocked until a qualified
person accepts the role and the access-zone checklist in
`LABEL_CUSTODIAN_ADJUDICATOR_RECRUITMENT.md`.

The preferred staffing arrangement is:

- Annotator A and Annotator B work independently.
- One third person acts as both label custodian and adjudicator.
- The implementation lead has no label-zone access.
- A separate integrity reviewer is named before one-time evaluation. This
  person may be recruited later but cannot be the implementation lead.

Combining custody and adjudication is allowed because the role is independent
of implementation and sees labels by design. It does not remove the need for
two independent raw annotation submissions or pre-adjudication agreement.

## Remaining Gate B blockers

Completed: exact source-family approval, per-family license/access review,
repository calibration-source inventory, 8A external-exposure attestation,
and acquisition, normalization, hashing, and validation of the amended source
snapshots without invoking a model or verifier.

Completed for Natural OOD: exact source-to-configuration allocation, prompts,
retrieval/chunking/reranking settings, query-authoring policy, generator
parameters, retry rules, timeouts, privacy controls, and hosted cost guard.
The exact lock and verification command are in
`benchmarks/contexttrace_unseen_v1/GENERATION_LOCK.md`.

Completed for the temporal track: exact pair review, owner exposure
attestation, exact-hash acquisition authorization, acquisition, normalization,
artifact hashing, pair-yield checks, prior-corpus disjointness validation, and
offline reconstruction without source substitution or downstream calls.

Remaining:

1. Build and review the final temporal generation schedule from the acquired
   source hashes.
2. Freeze that schedule and obtain a separate exact-hash generation
   authorization.
3. After temporal collection, freeze and independently retain the complete
   two-track unlabeled manifest before any label access.
4. Recruit and onboard the label custodian/adjudicator before annotation.

Natural OOD generation ran only under its exact recorded lock and its private
unlabeled manifest is frozen. Temporal acquisition is complete; temporal
generation remains unauthorized. Annotation may start only after the complete
two-track unlabeled manifest is frozen and the custody blocker is closed.
