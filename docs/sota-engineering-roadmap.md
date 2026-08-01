# ContextTrace SOTA engineering roadmap

The engineering objective is a narrow, testable claim: ContextTrace should be
the strongest reproducible selective verifier for fine-grained RAG diagnosis,
with particular strength on stale, superseded, conflicting, and low-authority
source conditions. No current development result is presented as SOTA evidence.

## Product boundary

Development targets the Python SDK, CLI, and versioned JSON artifacts. New HTML
reports, dashboards, and report-rendering work are out of scope. Existing legacy
report commands remain compatibility surfaces only and receive no SOTA-roadmap
investment.

## Engineering sequence

1. **Atomic claims and exact offsets.** Split independently verifiable facts
   without splitting entity names or object lists. Preserve exact answer spans
   and reconstruct an explicit verification subject only from observable text.
2. **Dedicated local checker.** Develop on public and explicitly designated
   development corpora using hard negatives for numbers, dates, entities,
   negation, roles, source versions, authority, and citation decoys. Keep the
   generic pinned NLI model as a reproducible baseline.
3. **Calibrated selective routing.** Calibrate confidence and abstention on a
   development split. Report ECE, risk-coverage/AURC, dangerous false greens,
   model-call rate, latency, and memory.
4. **Source-condition reasoning.** Model current/canonical, stale, superseded,
   low-authority, noncanonical, and conflicting-source cases only from observable
   metadata and document relations.
5. **Hierarchical evidence.** Verify document to evidence span to atomic claim to
   answer, including multi-span evidence and exact supporting/refuting spans.
6. **Reproducible baseline comparison.** Evaluate against available versions of
   RefChecker, MiniCheck, RAGChecker, RAGAS, and newer reproducible checkers on at
   least two external benchmarks.
7. **One locked untouched evaluation.** Freeze the verifier, unitizer, model,
   thresholds, taxonomy, schema, metrics, and statistical tests before test-label
   access. Score source/domain/time-disjoint natural RAG and temporal/source-pair
   tracks once.

## SOTA candidate gates

- dangerous false-green rate at most 0.01 on the primary untouched track;
- at least 3 absolute macro-F1 points over the strongest reproducible baseline
  on two external benchmarks;
- source-condition macro-F1 at least 0.80;
- observable root-cause accuracy at least 0.80;
- evidence-span F1 at least 5 points over the strongest baseline;
- expected calibration error at most 0.05;
- model invocation rate below 0.40;
- bootstrap confidence intervals and ablations for atomic claims, source
  features, selective routing, and the dedicated checker.

These are candidate gates, not current claims. A failed gate produces another
development cycle and a newly untouched test split if test errors were exposed.

## Human-only gates

No human participation is needed for stages 1--6 when only public and declared
development data are used. Human input becomes mandatory before stage 7 for:

- confirming that proposed source families were untouched by development;
- independently labeling the locked test cases and adjudicating disagreements;
- approving the final claim language after the one-shot score is available.

If a developer-actionability study is later resumed, institutional or ethics
requirements must be checked before recruiting participants. That study is not
required to establish the core verifier result.

## Development status

- Stage 1 is implemented as exact-offset atomic unitization in the unreleased
  v2.1 profile.
- Stage 2 now includes a provenance-recorded observable-conflict checker, a
  reproducible 24-pair synthetic regression pack, and a hash-locked learned
  support-risk gate trained on 96 source-family-disjoint development examples.
  Broader public and external development data remain necessary before this
  stage can be considered mature.
- Stage 3 has an initial calibrated support/reject mechanism with ECE, AURC,
  selective coverage, and selective risk recorded on separate synthetic
  validation and held-out-development families. Calibration on broader public
  and external development data remains pending.
- Stage 4 has an initial relational source-condition reasoner and a 54-case
  source-family-disjoint synthetic development pack. Replacement links,
  within-lineage version/time comparisons, authority labels, inconsistent
  metadata precedence, and authoritative conflicts are covered. External
  temporal/source-condition transfer remains pending.
- Stage 5 has an initial hierarchical attribution engine and a 42-case
  source-family-disjoint synthetic pack. It links answer offsets to atomic
  claims and exact supporting or refuting source spans, including complementary
  spans across documents. External span-labeled evaluation remains pending.
- Stage 6 now has a fail-closed artifact lock and 600-case same-ID development
  comparison across RAGTruth/RAGAS, ARES/RAGAS, and CRAG/RAGChecker. ContextTrace
  beats RAGAS on ARES with 0.995 macro-F1 and zero dangerous false greens after
  adding query-conditioned fragment verification, but loses on RAGTruth and its
  RAGTruth NLI invocation rate misses the candidate gate. CRAG is reported only
  as proxy agreement. RefChecker and MiniCheck remain unavailable rather than
  receiving unverified scores, so Stage 6 is not complete and no SOTA claim is
  supported.
- Stage 7 remains pending. No untouched labels were accessed by Stage 6.
