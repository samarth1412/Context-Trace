# CAIN 2027 Phase 0 gap analysis

Status date: 2026-07-24  
Scope: repository and evidence audit only  
Target: CAIN 2027 Research Track, full paper (10+2 pages)  
Deadline: 2026-10-30 AoE

## Executive assessment

ContextTrace has a strong release-quality engineering base, a frozen compatibility
verifier, extensive calibration evidence, reproducible benchmark machinery, and
an existing workshop manuscript. It does **not** yet have the independent,
source/domain/time-disjoint evidence required for the proposed CAIN full-paper
claim.

No existing evaluated split qualifies as independent external test evidence for
future verifier development. RAGTruth, ContextTrace-Diag-150, Naturalistic Eval
v2, ARES, CRAG, Groundedness-Truth-Gap, the repository benchmark, the adversarial
suite, and all derived or locked subsets have been inspected or used to make
implementation, threshold, taxonomy, or paper decisions. They are calibration
evidence.

The full-paper path is feasible only if corpus acquisition starts after
preregistration, independent annotators are secured immediately, and the
remaining REALM and final-submission publication boundaries are resolved. The
GroundLM submission is now confirmed archival with decision pending, so it is a
binding prior-work constraint rather than a blocker to research. The September
15 fallback gate should remain binding.

## Repository state and audit boundary

- Public `origin/main`, verified with `git ls-remote`: commit
  `1f298adf202e0fb3b70032a73e4629bda14bb0ca`.
- Local branch: `agent/unseen-v1-foundation`, commit
  `b3ec0b45ae3386780bd6209a4a8e7f335ece02e2`, eight commits ahead of
  `origin/main`.
- Local worktree: 231 non-clean entries: 135 modified or staged, one deleted,
  and 95 untracked.
- The GroundLM manuscript, focused benchmark sources, naturalistic splits,
  annotation-audit material, and approximately 1.9 GB of generated benchmark
  output are not tracked on public `main`.
- Phase 0 validation therefore used both:
  - a clean detached worktree at public `origin/main`; and
  - non-destructive checks of the current dirty local worktree.

Uncommitted or ignored artifacts may be inspected as leads, but they are not a
stable, independently reproducible publication record until intentionally
reviewed, licensed, versioned, and committed or packaged with checksums.

## Completed engineering work

- Released ContextTrace 1.1.0 package and CLI.
- Frozen compatibility verifier identifier:
  `semantic_v1_calibrated`.
- Frozen implementation file:
  `packages/contexttrace/contexttrace/verify/facts.py`.
- Frozen implementation SHA-256:
  `4fa507db2126423c8d0787811e78d0d6ffecf5d7603828b6a6d9b23ca8207bc4`.
- Source-hash regression test and frozen legacy rule-pack declaration.
- Generic, temporal, policy, and legacy rule-pack boundaries.
- Versioned public schemas for trace, claim verification, diagnosis, repair plan,
  and regression case artifacts.
- Golden TraceV1 compatibility fixture and schema tests.
- Strict recursive privacy controls, configurable redaction, local retention,
  and storage permissions.
- Streaming-safe capture, concurrent integration isolation, bounded verification,
  batch verification, queue controls, and oversized-payload tests.
- Python 3.10–3.13 CI matrix, 80% coverage gate, cross-platform wheel smoke
  checks, dependency audit, and release workflow.
- Deterministic benchmark, ablation, candidate-adapter, review-packet,
  manifest, and claim-gate infrastructure.
- Compilable ARR and GroundLM-style paper sources.

Engineering completeness is not scientific validation.

## Calibration evidence

The following results are useful for regression, taxonomy development, protocol
design, and baseline plumbing, but not for a new independent CAIN test claim:

- ContextTrace-Bench (500 engineering cases with generated variants).
- ContextTrace-Diag-150 (author-curated public-document cases; review pending).
- RAGTruth stratified 200 and all derived/locked subsets.
- ARES NQ 200.
- CRAG Task 1 v5 200 and the RAGChecker agreement analysis.
- Groundedness-Truth-Gap 180.
- Naturalistic Audit v1 (50), Dev (40), and Eval v2 (84).
- The 90-case adversarial stress suite.
- The 50-case annotation-audit packet and all LLM-simulated annotations.
- The 14-case injected source-condition set.
- Demo datasets, bundled verifier cases, and public-app smoke runs.

The exact classification is machine-readable in
`research/cain2027/evidence_inventory.json`.

## Missing independent evaluation

The CAIN full paper still requires:

1. A newly acquired corpus of real RAG executions, not manually authored failure
   outputs.
2. Natural OOD traces spanning previously unused software/product documentation,
   policy/regulatory sources, and support/operational knowledge bases.
3. BM25, vector, and hybrid retrieval; multiple chunking/reranking
   configurations; at least two generator models; and both clean and naturally
   failing answers.
4. A separate temporal/source-condition track using versioned or
   authority-contrasting source pairs.
5. Source-document, normalized-content, source-family, domain, and publication
   window disjointness from every calibration source.
6. A published unlabeled manifest, configuration record, sorted IDs, and
   SHA-256 before ContextTrace execution or label exposure.
7. Sealed, one-time evaluation after implementation, thresholds, taxonomy,
   profile, baselines, statistical tests, and schema are locked.
8. A durable chain of custody showing who could access labels and when.

`benchmarks/contexttrace_unseen_v1/` now contains the Phase 2 collection
protocol, dataset card, privacy/license policy, source and case schemas,
fail-closed freezer/verifier, and 50 focused tests. Acquisition has not started,
no candidate or frozen manifest exists, and no labels exist.

## Missing human and actionability evidence

- Phase 3 annotation infrastructure is complete: the frozen manual and schema,
  annotator training, adjudication protocol, field-specific agreement analysis,
  sealed-evaluation policy, and 22 focused tests are present.
- No completed independent review exists for RAGTruth or Diag-150.
- No independent annotations exist for ContextTrace-Unseen-v1.
- No two-annotator field-level agreement or adjudication record exists for a new
  independent corpus.
- No human developer-actionability study has started.
- Existing LLM-simulated annotation and actionability pilots are protocol stress
  tests only.
- Institutional human-subjects/IRB requirements have not been resolved for a
  developer study.
- Annotator qualifications, compensation, training, assignment, adjudication,
  and conflict rules are not yet approved.

RQ5 must be removed or explicitly deferred if approvals and recruitment cannot
be completed without compromising the sealed evaluation.

## Missing baseline comparisons

Existing RAGAS, DeepEval, RAGChecker, lexical, MiniLM, and generic-judge runs are
calibration or plumbing evidence. The untouched CAIN comparison still needs:

- `semantic_v1_calibrated` on identical sealed traces as the primary predecessor.
- Aggregate or score-only baselines mapped only to outputs they actually expose.
- At least one pinned LLM-judge baseline with immutable model revision, prompt,
  temperature, parser, retry policy, token use, latency, and cost.
- A pinned local NLI model and revision for the successor cascade.
- Same-ID coverage checks and explicit `N/A` values for unsupported diagnostics.
- Predeclared handling of baseline failures, missing outputs, and rate limits.

Paid API use or model access requires user authorization.

## Phase 1 statistical design

Phase 1 closed this design gap on 2026-07-24. The preregistration, experiment
protocol, statistical analysis plan, metric definitions, and claim policy now
define:

- confirmatory and secondary endpoints;
- a 500-trace target with source-family diversity and precision rationale;
- claim units, endpoint populations, and clustering rules;
- 10,000 deterministic hierarchical source-family bootstrap replicates;
- paired cluster-randomization tests and Holm correction;
- confidence intervals for classification, selectivity, calibration,
  localization, and operational outcomes;
- missing-output, baseline-failure, subgroup-support, negative-result, and stop
  rules;
- frozen claim unitization, alignment, taxonomy, and aggregation semantics.

The remaining work is implementation and validation of the scorer on synthetic
fixtures before the sealed evaluation. No untouched data or results were used
to create this design.

## Operational-evidence gap

The released software has engineering tests for limits and concurrency, but CAIN
RQ6 requires measured operational evidence on representative workloads:

- p50/p95 latency and throughput by trace size and verifier route;
- memory, storage, and capture overhead;
- queue saturation and backpressure behavior under measured load;
- integration-specific overhead;
- NLI invocation rate and local model resource use;
- failure behavior for oversized inputs and unavailable models.

This work must use a separately frozen performance protocol. It is not a paper
contribution merely because the code already has limits.

## Publication-overlap risks

### GroundLM

The current workshop manuscript, *Groundedness Is Not Truth: Evidence-Chain
Forensics for Retrieval-Augmented Generation*, already claims:

- the evidence-chain formalism;
- the ContextTrace deterministic local SDK/CLI;
- separation of support, source condition, citation, abstention, root cause,
  repair, and regression prevention;
- Groundedness-Truth-Gap;
- Naturalistic Eval v2, RAGTruth controls, stress tests, and same-ID baselines;
- an operational, inspectable diagnostic contract.

Those elements cannot be presented as new CAIN contributions. On 2026-07-24,
the user confirmed that the submission is archival and its decision is pending,
and supplied the exact anonymous nine-page submitted PDF. Its SHA-256 is
`ab8f211dc0102a12fbc6691135aecb11a8fe38dc638a4973cac1f3fbab6957ca`,
identical to the current `paper/main.pdf`. The repository still lacks the
OpenReview receipt and final decision record.

The safe CAIN distinction is a new empirical software-engineering study:
generalization on genuinely untouched real RAG traces, selective diagnosis with
explicit abstention, field-level independent annotation, source-condition
transfer, and measured operational/developer outcomes. The GroundLM system and
formalism must be treated as prior work.

### REALM

The governing specification mentions a separate REALM submission on typed,
staleness-aware context assembly. No manuscript, submission receipt, claims,
author list, or archival status is present in this repository. Any CAIN claim
about typed source state, context assembly, precedence, or staleness therefore
has unresolved overlap risk.

See `research/cain2027/groundlm_overlap_audit.md`.

## Work requiring user action or external coordination

### Required user decisions

1. Provide the GroundLM OpenReview submission receipt and final decision when
   available.
2. Provide the REALM manuscript/receipt and its archival status.
3. Approve data-source families and their licenses/terms.
4. Approve generator models, API providers, maximum budget, and whether all
   outputs may be redistributed.
5. Name a label custodian who is not a successor-verifier implementer.
6. Secure at least two independent annotators plus an adjudicator, with
   qualifications and compensation.
7. Resolve IRB/human-subject requirements before recruiting developers.
8. Decide by 2026-09-15 whether to continue the full paper or move to the short
   paper/tool-demo fallback.

### External blockers

- New source access and license review.
- Independent annotator availability.
- Secure sealed-label storage and access control.
- Potential paid model and baseline access.
- IRB or institutional determination for RQ5.
- GroundLM final decision/concurrent-review state and REALM publication
  constraints at submission time.
- CAIN submission link is still listed as TDB on the official CFP as of the
  audit date.

## Required inputs: existing versus new

### Already exists

- Frozen v1 verifier, hash boundary, schemas, profiles, and tests.
- Release-quality SDK/CLI and package.
- Calibration corpora and results.
- Benchmark and baseline adapters.
- Review packet and annotation-manual scaffolding.
- Untouched-manifest freeze utility.
- Paper and artifact build infrastructure.
- A concrete successor-study concept and preliminary success gates.

### Requires new data

- 300–500 natural OOD RAG traces.
- Approximately 100 temporal/source-condition traces.
- Source snapshots, licenses, provenance, publication windows, and content hashes.
- Development data separate from the sealed test.

### Requires humans

- Two independent annotators for all headline cases, or the preregistered
  stratified minimum.
- An adjudicator.
- A label custodian.
- Developer-study participants if RQ5 remains.
- Independent paper/method feedback.

### Requires approval or a user choice

- GroundLM final decision record and REALM publication strategy.
- Data licenses and external access.
- Paid APIs and budget.
- IRB/ethics path.
- Recruitment and compensation.
- External publication of the unlabeled manifest.
- Full-paper versus fallback decision.

## Proposed dated execution plan

No work below Phase 0 was started during this audit.

| Dates | Gate and dependency | Planned outcome |
| --- | --- | --- |
| Jul 24–Jul 28 | Phase 0 closeout; GroundLM archival status confirmed; REALM record remains | Preserve the GroundLM prior-work boundary and complete repository snapshot strategy |
| Jul 24–Jul 28 | Phase 1; no data collection until approved | Freeze RQs, endpoints, taxonomy, statistics, baselines, exclusions, stop rules, and ethics plan |
| Aug 8–Aug 28 | Phase 2 acquisition, contingent on source/license/model approval | Produce real RAG candidate traces and provenance without running either verifier |
| Aug 29–Sep 5 | Leakage checks and public unlabeled freeze, contingent on publication approval | Publish sorted IDs/configuration/source metadata and manifest hash |
| Sep 6–Sep 15 | Independent annotation begins; successor development uses only separate dev data | Verify annotation throughput and make the binding full/fallback decision |
| Sep 16–Sep 25 | Complete annotation, agreement, adjudication, and model/schema lock | Seal gold labels and sign the release-lock record |
| Sep 26–Oct 3 | One-time sealed evaluation | Generate immutable results without tuning |
| Oct 4–Oct 10 | Operational study and prespecified statistical analysis | Complete RQ1–RQ4/RQ6 evidence; RQ5 only if approved and completed |
| Oct 11–Oct 20 | Manuscript and artifact | Write claims from frozen outputs and disclose prior GroundLM/REALM work |
| Oct 21–Oct 29 | Clean-room reproduction, anonymity, claim/citation audit | Submission-ready package with no result-driven tuning |
| Oct 30 | Submit only if all mandatory gates pass | CAIN submission |

### September 15 fallback rule

Move to a 5+2 page CAIN short paper or ICSE tool demonstration if any of the
following remains unlikely to finish responsibly:

- frozen new corpus;
- independent annotation;
- sealed one-time evaluation;
- resolved archival overlap;
- reproducible artifact.

Do not weaken independence or relabel calibration data to preserve the full-paper
schedule.

## Track assessment

- **CAIN full paper:** at risk but recoverable; the research may proceed, while
  later gates still require a new corpus, humans, sealing, and a resolved REALM
  and final concurrent-review boundary.
- **CAIN short paper:** viable fallback if the study design and partial
  infrastructure are sound but evaluation cannot complete.
- **ICSE Tool Demonstration:** strongest fallback based on current engineering,
  provided its deadline and overlap rules are independently checked.

## Phase status

Phase 0 is complete. Phase 1 protocol artifacts were internally frozen on
2026-07-24. Phase 2 collection and freeze infrastructure is complete, but no
real source or trace acquisition has started. Phase 3 annotation and
sealed-label infrastructure is complete, but human annotation is blocked
because no independent annotators, adjudicator, label custodian, or frozen
corpus exist. No successor-verifier implementation, participant recruitment, or
new evaluation has been started.
