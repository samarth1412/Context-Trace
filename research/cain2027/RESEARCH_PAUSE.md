# ContextTrace CAIN 2027 research pause record

Status date: 2026-08-01  
Status: paused by project-owner decision  
Scope: CAIN 2027 confirmatory evaluation and paper execution

## Decision

The CAIN 2027 research program is paused while ContextTrace returns to product
development. This pause does not authorize publication claims, post-hoc repair
of the invalid evaluation, or deletion of any research artifact.

The existing 493-case ContextTrace-Unseen-v1 corpus is reclassified as
**development and exploratory evidence only**. It consists of 393 Natural OOD
cases and 100 temporal/source-condition cases. Its frozen manifest payload hash
remains:

`8bf65cd7e2c95ccfcc12e78b580fc47e4157b0f808ba3fcace0a24bfcdc2e5f6`

The corpus, source snapshots, candidate outputs, baseline outputs, execution
receipts, surrogate-label metrics, annotation attempts, hashes, and locks must
remain preserved. They may now be inspected and used for development, error
analysis, regression construction, and engineering decisions. They must not be
described as future untouched or confirmatory evidence.

## Reason

The one-time candidate execution completed, but the returned scoring receipt
disclosed that the comparison labels were created through an LLM-first process
inside the private zone rather than through the frozen independent-annotation
protocol. The resulting metrics are exploratory and cannot support the planned
confirmatory claims.

The later 60-case recovery audit did not produce valid independent labels. The
first returned workbook contained automated extraction, missing required
fields, non-exact evidence excerpts, and no completed practice cases. No sealed
independent gold artifact exists.

## Claims that remain prohibited

Until research resumes through the gate below, do not claim:

- untouched diagnostic generalization;
- confirmatory failure-label or root-cause accuracy;
- independently validated unverifiable performance;
- independently validated dangerous false-green rate;
- independently validated evidence-span localization;
- source-condition transfer on a sealed test corpus;
- CAIN submission readiness.

Engineering tests, calibration results, development-set metrics, latency, and
negative exploratory findings may be reported only with their actual status.

## Product-development boundary

Product work proceeds on a clean branch based on the released ContextTrace
1.1.0 source. The frozen `semantic_core_v2` artifact remains unchanged as a
historical research record. Product changes use a new development identity and
must not silently alter the frozen implementation or its lock.

Development may use:

- the reclassified 493-case corpus;
- existing public and calibration benchmarks;
- controlled synthetic and adversarial fixtures;
- implementation-team review and case-level error analysis;
- repeated local evaluation and threshold iteration.

Development results are not independent test evidence.

## Resume gate

CAIN research may resume only after all of the following are recorded:

1. a new verifier version is frozen before final test execution;
2. a new source-, domain-, and time-disjoint corpus is acquired after the
   development boundary is closed;
3. the new unlabeled manifest and hash are frozen before candidate execution;
4. the annotation protocol, label schema, metrics, and statistical tests are
   fixed before labels or predictions are inspected;
5. independent annotation and agreement are completed on the declared subset;
6. gold labels remain inaccessible to the implementation team until scoring;
7. the final evaluation is executed once under a new authorization.

The old 493 cases cannot satisfy this resume gate.
