# ContextTrace CAIN 2027 preregistration

Protocol version: 1.0  
Status: internally frozen before data collection  
Freeze date: 2026-07-24  
Target venue: CAIN 2027 Research Track  
Study family: untouched diagnostic generalization, source-condition transfer,
selective diagnosis, and operational feasibility

## Registration statement

This protocol was written before collection of ContextTrace-Unseen-v1, before
human annotation, before implementation of `semantic_core_v2`, and before any
evaluation on the untouched corpus. No ContextTrace-Unseen-v1 trace, prediction,
or label existed at freeze time.

All existing ContextTrace results—including RAGTruth, ContextTrace-Diag-150,
Naturalistic Eval v2, Groundedness-Truth-Gap, ARES, CRAG, the adversarial suite,
repository benchmarks, and derived subsets—are **calibration evidence**. They
cannot support an independent-test claim in this study and may not be moved into
the untouched test set.

The GroundLM manuscript is an archival submission with decision pending. It
already claims the evidence-chain formalism, the deterministic ContextTrace
system, and the earlier calibration evaluations. The prospective CAIN
contribution is therefore limited to new untouched empirical evidence,
selective diagnosis, source-condition transfer, operational evaluation, and an
optional separately approved developer study.

## Scope and study tracks

The confirmatory evaluation has two untouched tracks:

1. **Natural OOD:** target 400 real RAG traces, with an acceptable range of
   300–500, drawn from previously unused software/product documentation,
   policy/regulatory/legal-style material, and support/operational knowledge
   bases.
2. **Temporal/source condition:** target 100 real RAG traces built from
   versioned or authority-contrasting document pairs, when source access and
   licensing permit.

The primary analysis pools both tracks only for metrics whose estimand is
defined across both. Track-specific estimates are mandatory. A shortfall in the
temporal track does not permit replacing cases with authored failures.

The developer actionability study is optional, separately approved, and outside
the confirmatory family unless its protocol, human-subject determination,
materials, and analysis plan are frozen before recruitment.

## Research questions and hypotheses

### RQ1 — Diagnostic generalization

How accurately does ContextTrace identify claim-level grounding and citation
failures on source-family, domain, and time-disjoint RAG traces?

- **H1a:** `semantic_core_v2` improves failure-label macro-F1 by at least 0.15
  absolute over `semantic_v1_calibrated` on identical eligible claims.
- **H1b:** Citation-error F1 is greater than the predecessor on identical
  citation-eligible claims.

H1a is the confirmatory RQ1 hypothesis. H1b is secondary.

### RQ2 — Root-cause attribution

How accurately does ContextTrace attribute observable failures to retrieval
miss, reranking failure, chunking issue, corpus gap, stale or unsuitable source,
citation mismatch, answer overreach, insufficient context, conflict, or failure
to abstain?

- **H2a:** Overall root-cause accuracy is at least 0.75.
- **H2b:** Root-cause macro-F1 is greater than
  `semantic_v1_calibrated` on the subset for which both systems expose a
  compatible root-cause prediction.

H2a is confirmatory. H2b and per-cause results are secondary.

### RQ3 — Evidence localization

How accurately does ContextTrace identify minimal evidence spans supporting or
contradicting individual claims?

- **H3:** Mean claim-level evidence-span token F1 exceeds the
  `semantic_v1_calibrated` mean on identical span-eligible claims.

H3 is secondary because span availability and predecessor capability may vary.

### RQ4 — Selective diagnosis

Can ContextTrace abstain when evidence is insufficient, thereby reducing
dangerous false greens and high-confidence incorrect diagnoses?

- **H4a:** Unverifiable-class F1 is at least 0.60.
- **H4b:** The dangerous false-green rate is at most 0.02.
- **H4c:** Selective risk is no worse than forced classification at every
  preregistered coverage point from 0.50 through 0.90, and AURC is lower.
- **H4d:** The NLI route is invoked on fewer than 40% of eligible claims.

H4a and H4b are confirmatory. H4c and H4d are secondary engineering/selectivity
outcomes.

### RQ5 — Developer actionability

Does ContextTrace help developers identify and repair RAG failures more
accurately or quickly than aggregate evaluation scores and raw traces?

No confirmatory RQ5 hypothesis is registered in this protocol. RQ5 is deferred
unless a separate protocol receives the required institutional determination
and user authorization before recruitment. If omitted, no developer
productivity or actionability claim will be made.

### RQ6 — Operational feasibility

What latency, memory, storage, throughput, queue, and capture overhead does
ContextTrace introduce across representative pipeline sizes and integrations?

- **H6:** No directional superiority hypothesis is asserted. The study will
  report prespecified descriptive estimates and tradeoffs, including p50, p95,
  and p99 latency. “Zero overhead” is not an eligible conclusion.

## Confirmatory endpoints

The four confirmatory endpoints are:

1. paired absolute change in failure-label macro-F1 for
   `semantic_core_v2` versus `semantic_v1_calibrated`;
2. `semantic_core_v2` root-cause accuracy;
3. `semantic_core_v2` unverifiable-class F1;
4. `semantic_core_v2` dangerous false-green rate.

The study supports its full confirmatory success claim only if the point
estimates meet all prespecified gates:

- failure-label macro-F1 improvement at least 0.15;
- root-cause accuracy at least 0.75;
- unverifiable F1 at least 0.60;
- dangerous false-green rate at most 0.02.

Confidence intervals and adjusted hypothesis-test results are reported beside
the gates. Passing a point-estimate gate does not justify a superiority claim
when its uncertainty includes no improvement. Mixed outcomes must be reported
endpoint by endpoint; they may not be collapsed into an omnibus “validated”
claim.

## Secondary endpoints

- failure-label micro-F1 and per-class precision, recall, and F1;
- root-cause macro-F1, per-cause results, and `not_observable` performance;
- claim-verdict macro-F1;
- evidence-span token F1 and character intersection-over-union;
- citation-error precision, recall, and F1;
- abstention precision, recall, and coverage;
- selective risk-coverage curve, AURC, and coverage at fixed error rates;
- Brier score and expected calibration error when confidence has a locked
  probabilistic interpretation;
- NLI invocation and unresolved-disagreement rates;
- trace-level “any dangerous false green” rate;
- p50, p95, and p99 latency, model-call rate, peak memory, stored bytes,
  throughput, queue behavior, truncation, and concurrent failure rates.

## Units of analysis

- The prediction unit is an atomic answer claim.
- Evidence spans and citations are evaluated at the claim-source pair.
- Root causes are evaluated per claim; a trace-level root cause is not inferred
  by majority vote.
- Dangerous false-green rate is claim-level, with a mandatory trace-level
  sensitivity analysis.
- Operational latency and resource outcomes are measured per verification or
  capture operation.
- The independent sampling cluster for inference is the source family. Claims,
  traces, and documents within a source family are correlated and remain
  bundled during resampling.

Claim boundaries and aggregation are governed by `CLAIM_POLICY.md`.

## Sampling and size rationale

The target is 500 untouched traces: 400 Natural OOD and 100 temporal/source
condition. The Natural OOD target is approximately balanced across the three
domains and must contain at least 12 independent source families per domain and
at least 36 source families overall. No source family may dominate more than
10% of the Natural OOD track.

This is a precision- and cluster-diversity-based design, not a promise of power
derived from unknown future class prevalence. With approximately 40 or more
independent source-family clusters, the hierarchical bootstrap can characterize
between-family variation; hundreds of traces provide claim coverage without
pretending claims from the same documents are independent.

Before gold labels are unsealed, a label custodian may report only aggregate
support-count sufficiency flags, not class identities or system results. A
confirmatory class requires at least 20 adjudicated positive claims and
representation in at least five source families. If a class fails this rule,
its per-class result is reported as descriptive/inconclusive; classes are not
merged or replaced after unsealing. The predefined macro-F1 is still reported
over supported classes, with omitted zero-support classes identified.

## Eligibility and disjointness

Eligible cases must be outputs of an actual, configuration-recorded RAG
pipeline. Both successful and naturally failing answers are eligible. Manually
written failures, post-generation error injection, output editing, missing
source snapshots, inaccessible licenses, private data, and traces passed through
either evaluated verifier before the manifest freeze are excluded.

The untouched corpus must be disjoint from the calibration registry by:

- exact and normalized source-document content;
- source document identifier and snapshot;
- source family;
- domain, using the preregistered domain ontology;
- publication window where the design declares a time holdout;
- prompt/example content derived from calibration cases.

The three top-level study strata are broad source classes, not the disjointness
key. Phase 2 must register a finer domain identifier—for example a specific
product ecosystem, regulatory jurisdiction/topic, or operational service
family—and prove that identifier unused by calibration evidence.

No row-level random split may separate traces derived from the same document,
snapshot pair, or source family. Exact validation rules belong to Phase 2 and
must fail closed.

## Systems and comparison policy

The primary paired comparison is:

- candidate: frozen `semantic_core_v2`;
- predecessor: frozen `semantic_v1_calibrated`.

Secondary baselines are prespecified in `EXPERIMENT_PROTOCOL.md`. A baseline is
scored only on outputs it actually exposes. Unsupported fields are `N/A`, not
zero, and are excluded from pairwise tests requiring that field. Every
dependency, local model, remote model, prompt, threshold, parser, retry policy,
and mapping must be locked before the sealed run.

## Analysis and multiplicity

All eligible systems receive identical candidate inputs and case IDs. The
analysis uses 10,000 deterministic hierarchical bootstrap replicates, seeded
with `20271030`, resampling source families and retaining all nested documents,
traces, and claims. Paired system differences are computed within each
replicate.

Two-sided paired cluster-randomization tests are used where the endpoint admits
a system-label swap. The four confirmatory endpoint tests form one family and
use Holm correction at family-wise alpha 0.05. Threshold-gate assessments are
estimation claims and are not converted into significance claims.

Full methods, missing-data rules, subgroup constraints, and interval definitions
are in `STATISTICAL_ANALYSIS_PLAN.md`.

## Stop, invalidation, and negative-result rules

Collection stops at the first of:

- 500 eligible Natural OOD traces, or the approved resource ceiling;
- 120 eligible temporal/source-condition traces, or exhaustion of approved,
  license-compatible versioned pairs;
- a privacy, license, contamination, or chain-of-custody violation;
- the dated fallback gate in the governing execution specification.

The study may proceed with 300–500 Natural OOD traces and fewer than 100 temporal
cases, but every shortfall is disclosed. Below 300 Natural OOD traces, below 30
source families, loss of sealed-label independence, or verifier exposure before
the unlabeled freeze invalidates the untouched full-paper claim.

The sealed test is scored once. A software defect does not authorize a silent
rerun. The invalid run and defect are preserved; an independent integrity review
decides whether the test was exposed and whether any corrected run can remain
confirmatory. Otherwise the split is retired to calibration.

Null, negative, or mixed findings are publishable outcomes. The team will not:

- tune thresholds or taxonomy after unsealing;
- remove difficult domains, classes, or sources based on results;
- relabel an endpoint as primary;
- call missing baseline capability a score of zero;
- replace unavailable human evidence with simulated participants;
- describe a calibration split as untouched.

## Change control and sealing

Changes before any data collection require a dated amendment with rationale,
author, affected hypotheses, and new file hashes. Changes after collection
starts must additionally state whether collection behavior could have been
influenced. Changes after labels or system results are available are
post-registration deviations and cannot redefine confirmatory claims.

Before the one-time evaluation, the following must be frozen and hashed:

- unlabeled manifest and source/configuration metadata;
- calibration-overlap report;
- candidate implementation and dependency locks;
- NLI model and immutable revision;
- taxonomy, candidate output schema, profiles, prompts, and thresholds;
- baseline versions and mappings;
- metric implementation, bootstrap seed, tests, and ablations.

Gold labels, annotator notes, disagreements, and adjudication records remain
outside the implementation workspace under a named custodian. External
publication of a preregistration or manifest requires explicit user
authorization.

## Ethics and approvals

Only public or explicitly authorized sources with recorded license/access terms
are eligible. Raw private traces and personal data may not enter the repository.
Generator API use, paid baselines, redistribution, annotator recruitment, and
participant recruitment require explicit authorization. RQ5 requires an IRB or
equivalent institutional determination before recruitment.

## Interpretation boundary

This study can evaluate diagnosis of evidence available in recorded traces. It
does not establish real-world truth, production safety, universal domain
generalization, or causal internals not observable in a trace. A grounded claim
may still rely on a stale, noncanonical, low-authority, or conflicting source.
The system must keep support, source condition, citation state, truth status,
and diagnostic confidence separate.
