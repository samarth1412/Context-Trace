You are acting as the principal research engineer, empirical-methods lead, and release-quality reviewer for ContextTrace.

Repository:
[https://github.com/samarth1412/Context-Trace](https://github.com/samarth1412/Context-Trace)

Primary target:
CAIN 2027 Research Track

Submission deadline:
October 30, 2026, AoE

Paper type:
Target a full research paper of up to 10 pages plus 2 pages of references. Maintain a fallback path to a 5-page short research paper or the ICSE 2027 Tool Demonstration track if the full empirical study cannot be completed responsibly.

Project context:
ContextTrace is a local-first Python SDK and CLI for diagnosing failures in RAG and agentic systems. It traces answers through retrieved contexts, claims, citations, evidence spans, verdicts, root causes, repair guidance, and regression tests.

ContextTrace v1.1.0 already includes:

* A frozen verifier named `semantic_v1_calibrated`
* A source-hash regression test protecting the frozen implementation
* Versioned JSON Schemas and artifact provenance
* Generic, temporal, policy, and frozen legacy rule-pack boundaries
* Strict privacy controls and custom redaction
* Streaming-safe FastAPI tracing
* Concurrent LangChain, LangGraph, and LlamaIndex run isolation
* Bounded and batch verification
* Python 3.10–3.13 CI
* Cross-platform wheel validation
* OIDC PyPI publishing and attestations
* Approximately 85.9% package coverage
* A published PyPI package
* A GroundLM workshop submission based on the earlier ContextTrace research
* A separate REALM submission concerning typed, staleness-aware context assembly

The existing RAGTruth, ContextTrace-Diag-150, Naturalistic Eval v2, repository benchmark, CRAG, and related repeatedly inspected results are calibration evidence. They are not independent external test evidence.

The central objective is to produce a genuinely new and defensible research contribution:

“Aggregate evaluation scores indicate that a RAG or agent system failed, while evidence-chain diagnosis can identify where the failure occurred, why it occurred, what evidence was involved, and how developers can prevent its recurrence.”

Do not turn the paper into a feature catalogue. Center it on an empirical scientific question about diagnostic accuracy, generalization, actionability, and operational feasibility.

## Non-negotiable methodological rules

These rules override convenience, deadlines, benchmark performance, or pressure to produce a positive result.

1. Never fabricate datasets, traces, annotations, users, study participants, metrics, statistical significance, baseline results, downloads, citations, reviews, or experimental outcomes.

2. Never describe generated or synthetic cases as naturally occurring failures.

3. Never call an evaluated dataset “untouched” if its labels, errors, examples, source documents, or results influenced implementation decisions.

4. Treat all previously inspected ContextTrace benchmarks as calibration evidence.

5. Do not modify `semantic_v1_calibrated`. Its source hash must remain unchanged.

6. Any successor must use a new identifier such as `semantic_core_v2` and must be implemented behind an explicit version boundary.

7. Do not implement or tune `semantic_core_v2` using ContextTrace-Unseen-v1 labels.

8. Freeze and publish the unlabeled manifest, configuration, source metadata, case IDs, and SHA-256 hash before running ContextTrace on the new cases or exposing their gold labels.

9. The implementation, thresholds, taxonomy, profiles, baselines, statistical tests, ablations, and decision rules must be locked before sealed evaluation.

10. Score the untouched test set once. After its results are inspected, it becomes evaluation evidence that cannot be reused for additional tuning.

11. If a new corpus, independent annotations, or required approvals are unavailable, stop at the appropriate gate. Clearly report the missing dependency. Never create placeholder evidence that looks real.

12. Do not claim SOTA, external validation, production safety, developer productivity improvements, or statistical superiority unless the collected evidence directly supports the claim.

13. Preserve privacy, source licenses, access restrictions, and personally identifiable information. Do not commit raw private traces.

14. Do not recruit participants, contact researchers, publish artifacts, create releases, submit papers, or push external changes without explicit user authorization.

15. Do not submit substantially overlapping archival work to multiple venues. Audit the GroundLM submission’s archival status and document how the proposed CAIN contribution is materially distinct.

## Required workflow

Work through the following phases in order. Maintain a written execution plan and update it as work progresses. Do not skip a gate merely because later work can be implemented immediately.

# Phase 0: Repository and evidence audit

Before changing anything:

1. Inspect the complete repository structure.
2. Read all contribution, release, privacy, verifier-governance, benchmark, schema, reproducibility, and research-plan documentation.
3. Inspect the current paper source and compiled PDF.
4. Inspect the GroundLM submission and determine:

   * Whether it is archival or non-archival
   * Its exact claims and contributions
   * Which parts could create publication overlap
5. Inspect `semantic_v1_calibrated`, its hash boundary, rule packs, schemas, and tests.
6. Run the current validation suite:

   * Tests
   * Coverage
   * Ruff
   * Type checks
   * Dependency audit
   * Wheel and sdist build
   * Clean wheel installation
   * Paper compilation
7. Record exact, reproducible results.
8. Inventory every existing dataset and classify it as:

   * Training
   * Development
   * Calibration
   * Previously inspected holdout
   * Independent external evidence
   * Unusable for independent evaluation
9. Audit every headline claim in the current paper against its supporting artifact.
10. Identify all missing evidence required for a CAIN full paper.

Create:

* `docs/cain-2027-gap-analysis.md`
* `research/cain2027/evidence_inventory.json`
* `research/cain2027/claim_evidence_matrix.csv`
* `research/cain2027/groundlm_overlap_audit.md`
* `research/cain2027/reproduction_status.md`

The gap analysis must separate:

* Completed engineering work
* Calibration evidence
* Missing independent evaluation
* Missing human or actionability evidence
* Missing baseline comparisons
* Missing statistical analysis
* Publication-overlap risks
* Work requiring user action or external coordination

Do not begin successor-verifier implementation during this phase.

# Phase 1: Define the research questions and preregistration

Prepare a preregistered study design centered on the following questions.

RQ1 — Diagnostic generalization:
How accurately does ContextTrace identify claim-level grounding and citation failures on source-family, domain, and time-disjoint RAG traces?

RQ2 — Root-cause attribution:
How accurately does ContextTrace attribute failures to retrieval miss, reranking failure, chunking issue, corpus gap, stale source, citation mismatch, answer overreach, insufficient context, and failure to abstain?

RQ3 — Evidence localization:
How accurately does ContextTrace identify minimal evidence spans supporting or contradicting individual claims?

RQ4 — Selective diagnosis:
Can ContextTrace abstain from making a diagnosis when evidence is insufficient, thereby reducing dangerous false-green and high-confidence incorrect diagnoses?

RQ5 — Developer actionability:
Does ContextTrace help developers identify and repair RAG failures more accurately or quickly than aggregate evaluation scores and raw traces?

RQ6 — Operational feasibility:
What latency, memory, storage, throughput, queue, and capture overhead does ContextTrace introduce across representative pipeline sizes and integrations?

Define before evaluation:

* Primary and secondary endpoints
* Label taxonomy
* Unit of analysis
* Sample-size rationale
* Inclusion and exclusion criteria
* Source/domain/time-disjointness rules
* Missing-data handling
* Confidence intervals
* Statistical tests
* Multiple-comparison policy
* Subgroup analyses
* Failure analysis procedure
* Baseline mapping rules
* Ablations
* Stop conditions
* Criteria for supporting or rejecting every hypothesis
* Rules for negative and inconclusive findings

Recommended primary metrics:

* Failure-type macro-F1
* Root-cause accuracy and macro-F1
* Evidence-span token F1 or character overlap
* Citation-error precision, recall, and F1
* Dangerous false-green rate
* Abstention precision and recall
* Selective risk-coverage curve
* Coverage at fixed error thresholds
* Calibration error or Brier score when confidence values are meaningful
* Bootstrap 95% confidence intervals
* Per-domain and per-failure-family results

Recommended operational metrics:

* Verification latency p50, p95, and p99
* Capture overhead
* Peak memory
* Stored bytes per trace
* Throughput by batch size
* Queue saturation behavior
* Truncation frequency
* Failure rate under concurrent execution

Create:

* `research/cain2027/PREREGISTRATION.md`
* `research/cain2027/EXPERIMENT_PROTOCOL.md`
* `research/cain2027/STATISTICAL_ANALYSIS_PLAN.md`
* `research/cain2027/METRIC_DEFINITIONS.md`
* `research/cain2027/CLAIM_POLICY.md`

The preregistration must clearly state that existing results are calibration evidence.

# Phase 2: Design ContextTrace-Unseen-v1

Create the infrastructure and protocol for a genuinely new dataset.

Target composition:

* Approximately 300–500 natural RAG traces
* Approximately 100 additional temporal, authority-conflict, or source-condition cases when feasible
* At least three substantially different domains:

  * Software or product documentation
  * Policy, regulatory, or legal-style documents
  * Support, operational, or knowledge-base documents
* At least three retrieval configurations:

  * BM25 or lexical
  * Dense-vector
  * Hybrid
* Multiple chunking settings
* At least two pinned generator models or model families
* Clean answers and naturally occurring failures
* Multiple answer lengths and context sizes
* Multiple citation formats
* Current, stale, conflicting, canonical, and low-authority sources

Every case must record:

* Stable case ID
* Track
* Source family
* Source document ID
* Domain
* Publication window
* Source URL or canonical identifier
* Source snapshot hash
* Retrieval configuration
* Chunking configuration
* Reranking configuration
* Generator identity and version
* Prompt hash
* Generation parameters
* Collection timestamp
* Trace schema version
* Licensing or access metadata
* Privacy classification
* Whether the case is naturally occurring or generated
* Whether it is eligible for untouched evaluation

The split must be source-document, source-family, domain, and time aware. Do not perform random row-level splits among cases derived from the same document or source family.

Implement fail-closed validation that rejects:

* Missing required metadata
* Duplicate IDs
* Duplicate source documents across forbidden boundaries
* Source-family overlap
* Domain overlap where disallowed
* Publication-window overlap
* Calibration-source overlap
* Missing hashes
* Modified manifests
* Cases generated after labels became accessible
* Any case previously passed through the successor verifier before freezing

Create:

* `benchmarks/contexttrace_unseen_v1/README.md`
* `benchmarks/contexttrace_unseen_v1/DATASET_CARD.md`
* `benchmarks/contexttrace_unseen_v1/COLLECTION_PROTOCOL.md`
* `benchmarks/contexttrace_unseen_v1/LEAKAGE_AUDIT.md`
* `benchmarks/contexttrace_unseen_v1/PRIVACY_AND_LICENSE.md`
* `benchmarks/contexttrace_unseen_v1/source_manifest.schema.json`
* `benchmarks/contexttrace_unseen_v1/case_manifest.schema.json`
* `benchmarks/contexttrace_unseen_v1/freeze_manifest.py`
* Comprehensive tests for every fail-closed condition

Important gate:

If actual new traces do not exist, build only the collection and validation infrastructure. Do not populate the final manifest with fabricated or repurposed cases.

# Phase 3: Annotation and sealed-label protocol

Create an annotation protocol covering:

* Atomic claim boundaries
* Supported, partially supported, unsupported, contradicted, and unverifiable labels
* Citation correctness
* Minimal supporting and contradicting spans
* Source freshness and authority
* Primary and secondary root causes
* Appropriate abstention
* Ambiguous cases
* Multi-source claims
* Conflicting sources
* Temporal claims
* Policy-dependent claims
* Annotation confidence
* Adjudication rules

Recommended process:

1. Conduct a pilot on 20–30 cases that are not part of the final untouched test set.
2. Revise the guide using only pilot feedback.
3. Freeze the annotation guide.
4. Independently double-annotate a meaningful subset, preferably at least 20–25%.
5. Measure inter-annotator agreement using an appropriate statistic:

   * Cohen’s kappa
   * Krippendorff’s alpha
   * Span agreement
6. Adjudicate disagreements without exposing labels to the implementation team.
7. Store gold labels separately from unlabeled candidate inputs.
8. Hash the sealed gold artifact.
9. Record every correction and adjudication.
10. Ensure candidate files contain no gold labels, reviewer notes, or label-derived metadata.

Create:

* `benchmarks/contexttrace_unseen_v1/ANNOTATION_MANUAL.md`
* `benchmarks/contexttrace_unseen_v1/ANNOTATION_SCHEMA.json`
* `benchmarks/contexttrace_unseen_v1/ANNOTATOR_TRAINING.md`
* `benchmarks/contexttrace_unseen_v1/ADJUDICATION_PROTOCOL.md`
* `benchmarks/contexttrace_unseen_v1/AGREEMENT_ANALYSIS.py`
* `benchmarks/contexttrace_unseen_v1/SEALED_EVALUATION_POLICY.md`

Do not generate human annotations using an LLM and call them independent human labels. LLM-assisted suggestions may only be used if explicitly documented and independently verified by qualified annotators.

If no independent annotator is available, stop and report this as a blocking dependency.

# Phase 4: Establish fair baselines

Evaluate only baselines that can be run or reproduced fairly.

Investigate and, where technically and legally feasible, implement adapters for:

* RAGAS
* DeepEval
* RAGChecker
* TRAIL
* RAGXplain
* Other directly relevant diagnostic or attribution frameworks identified through a current related-work review
* Simple lexical, embedding, and LLM-as-judge baselines
* Aggregate-score-only baselines for the developer study

Requirements:

* Use exactly the same case IDs and candidate inputs.
* Pin every dependency, model, prompt, and configuration.
* Record API model versions and dates.
* Cache permissible outputs.
* Do not compare incompatible metrics as if they were equivalent.
* Do not infer root-cause accuracy from a baseline that does not output root causes.
* Report unsupported mappings as “not available,” not zero.
* Separate local deterministic methods from remote judge-based methods.
* Report cost and latency.
* Preserve raw baseline outputs.
* Document baseline failures and unavailable systems.
* Never manually improve baseline outputs.

Create:

* `benchmarks/contexttrace_unseen_v1/baselines/`
* One adapter per baseline
* `BASELINE_PROTOCOL.md`
* `BASELINE_CAPABILITY_MATRIX.md`
* `BASELINE_VERSION_LOCK.json`
* Baseline integrity and identity tests

# Phase 5: Implement and freeze `semantic_core_v2`

This phase may begin only after the unlabeled manifest has been frozen and before gold labels or untouched results are accessible.

Requirements:

* Preserve `semantic_v1_calibrated` unchanged.
* Create a clearly isolated `semantic_core_v2`.
* Use only:

  * General linguistic principles
  * Public documentation
  * Existing calibration data
  * Pilot data explicitly excluded from untouched evaluation
* Do not inspect ContextTrace-Unseen-v1 outputs during implementation.
* Version all thresholds, profiles, schemas, taxonomies, prompts, and rule packs.
* Generate an implementation source hash.
* Add regression tests proving the frozen boundary.
* Add explicit capability and limitation metadata.
* Support selective diagnosis and abstention when evidence is insufficient.
* Avoid high-confidence diagnoses from weak lexical overlap alone.
* Keep support status, truth status, source status, citation status, and diagnostic confidence separate.
* Record truncation and insufficient-input conditions.
* Do not hide ambiguous outcomes inside a positive verdict.
* Ensure deterministic modes remain deterministic.
* Preserve backward compatibility for v1 artifacts.

Potential engineering work, only when justified by preregistered needs:

* Top-k evidence selection
* Pre-tokenization caching
* Batched evidence scoring
* Calibrated confidence cascade
* Explicit out-of-scope detection
* Additional temporal/source-authority reasoning
* Better contradiction handling
* Bounded parallel evaluation
* Stable diagnostic explanations

Create:

* `contexttrace/verify/semantic_core_v2/`
* Versioned v2 rule packs
* V2 profile definitions
* V2 schema/provenance updates
* Frozen source-hash test
* Migration and compatibility documentation
* Unit, adversarial, concurrency, privacy, and performance tests

Before sealed evaluation, create:

* `research/cain2027/IMPLEMENTATION_LOCK.json`
* `research/cain2027/DEPENDENCY_LOCK.json`
* `research/cain2027/EVALUATION_CONFIG.json`
* `research/cain2027/ABLATION_CONFIG.json`
* SHA-256 hashes for code, manifests, prompts, profiles, dependencies, and configurations

# Phase 6: One-time sealed evaluation

Only proceed after all required locks exist.

Before running:

1. Verify the manifest hash.
2. Verify the implementation hash.
3. Verify dependency and configuration hashes.
4. Verify that no test labels were available during development.
5. Verify all preregistered baselines and ablations.
6. Record the exact evaluation timestamp and environment.
7. Make the evaluation command fail closed if any hash differs.

Run the sealed evaluation once.

Preserve:

* Raw predictions
* Raw baseline outputs
* Metric outputs
* Confidence intervals
* Per-case errors
* Environment information
* Runtime logs
* Hashes
* Exit status

Do not tune after viewing results.

If a software defect invalidates scoring:

* Document the defect
* Preserve the invalid run
* Determine whether the test set has been compromised
* Follow the preregistered correction policy
* Do not silently rerun

Generate:

* Overall results
* Per-domain results
* Per-failure results
* Calibration plots
* Risk-coverage plots
* Confusion matrices
* Confidence intervals
* Baseline comparisons
* Cost and latency tables
* Negative and inconclusive findings
* Complete error analysis

Create reproducible scripts that generate every paper table and figure directly from locked result artifacts.

# Phase 7: Developer actionability study

Treat this as optional until human-subject requirements are resolved.

Do not recruit participants or run a study without user authorization and any required institutional approval.

First create:

* Study protocol
* Recruitment criteria
* Consent language
* Data-management plan
* Randomization plan
* Power or sample-size justification
* Task materials
* Scoring rubric
* Analysis plan
* IRB or exemption checklist

Suggested design:

* Approximately 12–20 developers, subject to power analysis and approval
* Participants debug matched RAG failures under two conditions:

  * Raw traces plus aggregate evaluator scores
  * ContextTrace diagnostic output
* Randomized task order
* Balanced failure types
* No task used to tune ContextTrace

Suggested outcomes:

* Time to correct root-cause identification
* Root-cause accuracy
* Repair-plan correctness
* Successful regression-test creation
* Number of unnecessary changes
* Confidence calibration
* Perceived workload
* Diagnostic usefulness

If approval or participants are unavailable, omit the human-study claim and position it as future work. Do not replace missing participants with simulated developers or LLM agents and call it a human study.

# Phase 8: Operational evaluation

Benchmark the released and successor implementations across:

* Small, medium, and large trace payloads
* Varying context counts
* Varying context lengths
* Single and batch verification
* Concurrent execution
* Queue saturation
* Streaming responses
* SSE exclusion
* File responses
* Background persistence
* SQLite storage
* Privacy profiles
* Hash-only mode
* Encryption hooks
* LangChain
* LangGraph
* LlamaIndex
* FastAPI
* OpenTelemetry

Measure:

* p50, p95, and p99 latency
* Peak memory
* CPU usage where available
* Storage growth
* Throughput
* Dropped or rejected traces
* Truncation
* Persistence failures
* Integration isolation failures
* Privacy leakage tests

Never claim “zero overhead.” Report measured tradeoffs.

# Phase 9: Write the CAIN paper

The paper must be written as a research paper, not library documentation.

Provisional title:

“ContextTrace: Evidence-Chain Diagnosis and Regression Testing for RAG and Agentic Systems”

Recommended structure:

1. Introduction
2. Motivation and problem formulation
3. Evidence-chain and diagnostic model
4. Verifier governance and contamination controls
5. ContextTrace-Unseen-v1
6. Experimental design
7. Diagnostic-generalization results
8. Root-cause and evidence-localization results
9. Selective diagnosis and calibration
10. Operational evaluation
11. Developer actionability study, if completed
12. Error analysis
13. Related work
14. Threats to validity
15. Ethical considerations
16. Limitations
17. Reproducibility
18. Conclusion

Required contributions:

1. A formal evidence-chain representation for connecting RAG or agent outputs to retrieved evidence, citations, failure stages, and regression tests.
2. A versioned diagnostic framework that separates support, truth, source condition, citation correctness, and diagnostic confidence.
3. A leakage-resistant evaluation protocol with a frozen verifier and source/domain/time-disjoint corpus.
4. An untouched evaluation of diagnostic generalization.
5. An operationally usable open-source artifact.
6. Developer-actionability evidence only if the study is actually completed.

Paper rules:

* Every quantitative statement must link to a generated artifact.
* Every table and figure must be generated automatically.
* Include confidence intervals, not only point estimates.
* Report negative and inconclusive results.
* Separate calibration and untouched results visually and verbally.
* Avoid “SOTA” unless the comparison is complete, same-case, statistically supported, and directly comparable.
* Do not claim that evidence support proves independent truth.
* Discuss dataset leakage, annotation uncertainty, external validity, baseline limitations, model dependence, and source licensing.
* Audit all citations against original sources.
* Do not use fake or unverifiable citations.
* Respect CAIN’s double-anonymous requirements.
* Refer to prior public work in the third person where required.
* Use an anonymous artifact repository for review.
* Do not expose author identity through URLs, package metadata, Git history, PDFs, screenshots, or cached artifacts.

Create:

* `paper/cain2027/main.tex`
* `paper/cain2027/references.bib`
* `paper/cain2027/figures/`
* `paper/cain2027/tables/`
* `paper/cain2027/CLAIM_AUDIT.md`
* `paper/cain2027/ANONYMIZATION_CHECKLIST.md`
* `paper/cain2027/SUBMISSION_CHECKLIST.md`

# Phase 10: Reproducibility artifact

Create an anonymous reviewer artifact containing:

* Exact source snapshot
* Environment lock
* Installation instructions
* One-command reproduction
* Dataset card
* Unlabeled manifest
* Permissible annotations or a documented access process
* Baseline adapters
* Evaluation scripts
* Table and figure generation
* Expected runtime and hardware
* Checksums
* Licenses
* Known limitations
* Troubleshooting guide

Preferred commands:

* `make setup`
* `make test`
* `make verify-locks`
* `make reproduce`
* `make paper`
* `make artifact-audit`

The artifact must fail clearly when required data, credentials, models, or approvals are unavailable.

Do not include:

* API keys
* Private traces
* Personal information
* Reviewer identities
* Hidden annotations in candidate files
* Local absolute paths
* Git metadata exposing identity
* Unlicensed source content
* Generated claims presented as measured evidence

# Phase 11: Final quality gates

Before declaring the work submission-ready, verify:

Engineering:

* All tests pass
* Coverage remains at or above the enforced threshold
* Ruff passes
* Type checks pass
* Dependency audit passes or documented exceptions are justified
* Wheel and sdist build
* Clean wheel installation works
* Schemas and rule packs are packaged
* Python 3.10–3.13 compatibility
* Linux, macOS, and Windows wheel smoke checks
* Privacy and concurrency adversarial tests
* No material resource warnings

Research:

* Manifest frozen before successor evaluation
* Leakage audit passes
* Implementation hash locked
* Gold labels remained sealed
* Annotation process documented
* Agreement reported
* Baselines run on identical cases
* Metrics match preregistration
* Confidence intervals reported
* Negative results preserved
* No post-test tuning
* Every claim has an artifact

Paper:

* Compiles without errors
* Fits page limits
* Anonymous PDF and artifacts
* References verified
* Tables match machine-readable results
* No GroundLM or other archival overlap violation
* Limitations and threats to validity are explicit
* Submission checklist complete

# Timeline and decision gates

July 24–August 7:

* Complete audit
* Lock research questions
* Finish preregistration
* Design corpus
* Secure an independent annotation plan
* Begin IRB or ethics consultation if pursuing a developer study

August 8–September 5:

* Collect new traces
* Complete leakage audit
* Freeze unlabeled manifest
* Lock successor design boundary

September 6–September 25:

* Complete independent annotation
* Lock implementation, dependencies, prompts, profiles, baselines, and ablations
* Verify sealed-label custody

September 26–October 5:

* Run the one-time sealed evaluation
* Run operational evaluation
* Generate tables, figures, and error analysis

October 6–October 20:

* Complete the CAIN manuscript
* Complete artifact packaging
* Perform claim and citation audits
* Obtain external paper feedback

October 21–October 29:

* Final anonymization
* Reproduce from a clean environment
* Resolve only legitimate presentation or software defects
* Do not tune against untouched results

October 30:

* Submit only after all mandatory gates pass

Fallback gate on September 15:

If new corpus collection, independent annotation, or sealed evaluation is unlikely to finish responsibly:

* Stop targeting a CAIN full paper
* Prepare a CAIN short research paper, or
* Prepare the ICSE Tool Demonstration paper and video
* Do not weaken independence requirements to preserve the full-paper plan

# Required progress reporting

At the end of every phase, report:

* What was completed
* Files created or changed
* Tests and validations run
* Exact results
* Assumptions
* Methodological risks
* External dependencies
* Blocking decisions
* Whether the project remains on track for:

  * CAIN full paper
  * CAIN short paper
  * ICSE Tool Demonstration

At no point should “implemented” be treated as equivalent to “scientifically validated.”

# Initial response required from you

Begin by:

1. Inspecting the repository and paper.
2. Producing the Phase 0 gap analysis.
3. Listing which required inputs already exist.
4. Listing which inputs require new data, humans, approvals, or user decisions.
5. Identifying publication-overlap risks with the GroundLM submission.
6. Proposing a concrete execution plan with dates and dependencies.
7. Stopping before creating new empirical evidence until the corpus and annotation requirements are genuinely satisfied.

Proceed autonomously on repository inspection, documentation, validation, schemas, scripts, tests, experiment infrastructure, and paper scaffolding.

Pause and ask the user when work requires:

* New external data access
* Independent human annotations
* IRB or ethics decisions
* Participant recruitment
* Paid model/API usage
* Publication or external uploads
* Changes that could compromise the frozen evaluation
* A choice between archival venues
