# ContextTrace CAIN 2027 experiment protocol

Protocol version: 1.0  
Status: internally frozen before data collection  
Freeze date: 2026-07-24

## Purpose

This document turns the preregistered research questions into an executable
sequence. It does not authorize source acquisition, paid APIs, annotation,
participant recruitment, successor-verifier implementation, or evaluation.
Those activities remain subject to their phase gates and explicit approvals.

## Experimental separation

Three non-overlapping evidence roles are enforced:

| Role | Permitted use | Prohibited use |
| --- | --- | --- |
| Calibration/development | Taxonomy examples, implementation, thresholds, test plumbing, pilot analysis | Independent-test claims |
| Pilot | Annotation training and protocol debugging; excluded by source family from untouched test | Final metrics or verifier tuning after exposure |
| Untouched test | One-time locked evaluation | Implementation, threshold, taxonomy, prompt, or analysis changes |

Every existing ContextTrace benchmark is calibration or development evidence as
recorded in `evidence_inventory.json`. ContextTrace-Unseen-v1 must contain only
newly acquired eligible cases.

## Stage gates

### Gate A — Phase 1 protocol lock

Required:

- the five Phase 1 documents exist and validate as a coherent contract;
- GroundLM is recorded as an archival submission with decision pending;
- confirmatory hypotheses, outcomes, inference, negative-result rules, and
  publication boundary are fixed;
- no dataset collection, annotation, v2 implementation, or evaluation has
  started.

### Gate B — Collection authorization

Before Phase 2 source acquisition:

- approve source families and license/access terms;
- approve generator models/providers, redistribution rules, and maximum budget;
- create a calibration-source registry and domain ontology;
- define the source-family and publication-window identifiers without using
  future labels;
- ensure collection code never calls either evaluated verifier.

### Gate C — Unlabeled manifest freeze

Before annotation or `semantic_core_v2` implementation:

- all required source and generation metadata validate;
- exact, normalized-content, near-duplicate, family, domain, and time leakage
  checks pass;
- candidate files contain no gold or prediction-derived fields;
- sorted case IDs, configuration hashes, source metadata, and manifest SHA-256
  are frozen;
- any external publication is explicitly authorized.

### Gate D — Annotation seal

Before implementers can access labels:

- annotator training and pilot are complete on excluded sources;
- guide and schema are frozen;
- independent annotations and adjudication are stored outside the
  implementation workspace;
- label custodian and access log are active;
- the gold artifact is hashed and sealed.

### Gate E — Implementation and analysis lock

Before sealed evaluation:

- `semantic_v1_calibrated` source hash still matches the Phase 0 record;
- `semantic_core_v2`, its output schema, profiles, thresholds, and prompts are
  frozen;
- local NLI model, tokenizer, immutable revision, numerical precision, and
  artifact hashes are frozen;
- baseline and ablation configurations are executable on candidate-only inputs;
- metric and statistical tests pass on synthetic fixtures;
- implementation, dependency, manifest, and evaluation hashes all match.

### Gate F — One-time evaluation

The command must fail closed if any lock differs. It records environment,
timestamps, raw outputs, exit status, and hashes. Labels are joined only in the
custodian-controlled scoring environment. No tuning follows result inspection.

## Natural OOD design

Target 400 eligible traces, acceptable range 300–500:

- approximately one third each from software/product documentation,
  policy/regulatory/legal-style sources, and support/operational knowledge
  bases;
- at least 12 source families per domain and 36 overall;
- no source family above 10% of the track;
- BM25/lexical, dense-vector, and hybrid retrieval represented in every domain;
- at least two chunk sizes and two chunk-overlap settings overall;
- reranking both enabled and disabled where the retriever supports it;
- at least two pinned generator models or model families;
- clean and naturally failing generations retained under the same eligibility
  rules;
- multiple answer lengths, context counts, and citation formats.

Configuration allocation is determined before generation using a balanced
factor schedule. Cases are not retained or rejected because a verifier score,
failure label, or desired performance result is observed. Manual review before
freeze is limited to metadata validity, privacy, license, source availability,
and obvious pipeline corruption.

## Temporal/source-condition design

Target 100 eligible traces, with four prespecified pair types:

- archived policy to current policy;
- old API documentation to replacement API;
- noncanonical copy to canonical source;
- low-authority summary to authoritative source.

Aim for at least 20 traces per pair type; remaining allocation may follow source
availability without inspecting system predictions. Every pair records
canonical identifiers, snapshots, timestamps/effective dates, the authority
rule, and the material relationship. A pair is excluded if freshness or
authority cannot be established independently of the answer.

The same RAG generation contract applies. The answer may be grounded in the
provided source and still be unsafe because that source is stale or unsuitable.

## Candidate generation controls

Each trace records at minimum the metadata listed in Phase 2 of the governing
specification. In addition:

- prompts are versioned and hashed before generation;
- random seeds are recorded where supported; nondeterministic provider behavior
  is declared;
- raw provider responses and retry history are retained subject to license and
  privacy rules;
- generation failures are logged, not regenerated selectively based on answer
  quality;
- retries follow one frozen mechanical policy;
- source snapshots precede or equal the recorded collection timestamp;
- no manually edited answer is eligible.

Provider and model identities are deliberately not invented in Phase 1. Exact
choices require user authorization and must be locked before the first eligible
generation. Changing a model after collection begins creates a new
configuration stratum and requires a protocol amendment.

## Systems and baseline mappings

All systems receive the same claim text, query, selected contexts, retrieval
metadata, source metadata allowed by the candidate schema, and citation
references. Gold labels and adjudication notes are never inputs.

| System | Failure/verdict | Root cause | Evidence span | Citation | Confidence/selectivity |
| --- | --- | --- | --- | --- | --- |
| `semantic_core_v2` | Yes | Yes | Yes | Yes | Yes |
| `semantic_v1_calibrated` | Yes where schema permits | Compatible subset only | Where exposed | Where exposed | No probabilistic claim unless documented |
| Deterministic lexical baseline | Binary support proxy only | N/A | Best-overlap span | N/A | Score only |
| Frozen embedding baseline | Binary support proxy only | N/A | Best-scoring chunk | N/A | Similarity score |
| Frozen local NLI baseline | Verdict mapping only | N/A | Input span/chunk only | N/A | Model score |
| Aggregate evaluator(s) | Declared supported outputs only | N/A | N/A unless native | Native output only | Native score |
| Diagnostic baseline(s) | Native fields only | Native compatible fields | Native field only | Native field only | Native field only |
| Frozen LLM judge, if authorized | Prompt-schema fields only | Prompt-schema fields only | Prompt-schema fields only | Prompt-schema fields only | Parsed confidence only |

Candidate baseline families for feasibility review are RAGAS, DeepEval,
RAGChecker, TRAIL, RAGXplain, simple lexical and embedding methods, and a pinned
LLM judge. Inclusion requires legal/technical feasibility, immutable
configuration, same-ID execution, and successful identity tests. Unavailable or
incompatible outputs are reported as `N/A`; systems are never manually repaired.

The primary statistical comparison remains `semantic_core_v2` against
`semantic_v1_calibrated`. Other baseline comparisons are secondary and cannot
replace it.

### Frozen v1 compatibility mapping

The predecessor is mapped claim by claim; trace summaries are not copied onto
every claim. Its root labels map as follows:

| v1 root label | Phase 1 root cause |
| --- | --- |
| `no_failure_detected` | `none` |
| `retrieval_miss` | `retrieval_miss` |
| `answer_overreach` | `answer_overreach` |
| `partial_context_support` | `insufficient_selected_context` |
| `wrong_source_cited`, `missing_cited_source` | `citation_mismatch` |
| `conflicting_contexts` | `conflicting_contexts` |
| `stale_context` | `stale_or_superseded_source` |
| `low_authority_source` | `noncanonical_or_low_authority_source` |
| `insufficient_context` | `insufficient_selected_context` |
| `corpus_gap` | `corpus_gap` |
| `should_have_abstained` | `failure_to_abstain` |
| unknown or unmapped value | `not_observable` |

The v1 failure label is derived from its claim verdict, citation state, source
status, abstention record, and mapped root cause using the tie order in
`CLAIM_POLICY.md`. It cannot receive credit for reranking or chunking diagnoses
that it does not expose. The mapping is implemented as a pure tested adapter and
its source hash is locked before evaluation.

## Ablations

The following v2 ablations are prespecified if the corresponding component is
present in the frozen implementation:

1. `deterministic_only`: disable NLI; unresolved cases abstain.
2. `forced_classification`: disable final abstention while preserving scores.
3. `no_source_condition`: mask freshness, authority, and canonicality features.
4. `no_citation_features`: mask citation-target features.
5. `no_route_disagreement`: use the deterministic result when deterministic and
   NLI routes disagree.

Each ablation uses the same code revision and case IDs, changes only the named
configuration, and is hashed before evaluation. If a component does not exist,
the ablation is `N/A`, not replaced post hoc. Ablations are secondary; no
multiple-comparison-adjusted superiority claim is planned for them.

## Evaluation execution

1. Create a clean, isolated environment from the dependency lock.
2. Verify all hashes and access-control attestations.
3. Run candidate-only schema validation without labels.
4. Execute each locked system and ablation once under the retry policy.
5. Preserve raw outputs before scoring.
6. Join gold labels in the controlled scoring environment.
7. Calculate metrics and 10,000 hierarchical bootstrap replicates.
8. Generate predefined tables, plots, subgroup summaries, and failure logs.
9. Write a signed evaluation receipt containing commands, timestamps, hashes,
   environment, exit codes, and deviations.
10. Move the evaluated corpus to “inspected evaluation evidence”; it is never
    untouched again.

## Failure and missing-output policy

- Schema-invalid output is a missing prediction and a system failure.
- Timeouts, rate limits, out-of-memory events, and parser failures are retained
  in the denominator of availability, cost, and latency metrics.
- Primary diagnostic metrics use the conservative scoring rules in the
  statistical plan; complete-case results are sensitivity analyses only.
- A baseline may receive its frozen retry count, but retries may not depend on
  gold labels or answer correctness.
- A global provider outage pauses execution before labels are inspected. Any
  resumed run is documented and uses the same lock.
- A system-wide software defect preserves the invalid run and triggers the
  preregistered integrity review; it never causes silent replacement.

## Failure analysis

After all confirmatory metrics are finalized, errors are sampled using a
prespecified matrix:

- up to 10 highest-confidence errors per failure family;
- up to 10 abstentions per domain;
- up to 10 v2/v1 disagreements per track;
- all dangerous false greens when there are at most 100, otherwise a
  deterministic source-family-stratified sample of 100;
- all invalid or missing predictions.

The analysis may describe patterns but cannot change labels, thresholds,
taxonomies, exclusions, or confirmatory results. Any newly discovered annotation
error is preserved with the original label and handled under the correction
policy.

## Operational experiment for RQ6

Operational results are separate from diagnostic accuracy. Synthetic load
fixtures are permitted and must be labeled synthetic.

Prespecified payload tiers:

| Tier | Contexts | Approx. tokens/context | Approx. answer tokens |
| --- | ---: | ---: | ---: |
| Small | 2 | 256 | 128 |
| Medium | 10 | 512 | 512 |
| Large | 50 | 1,024 | 2,048 |

For each supported mode:

- 30 warm-up operations followed by at least 100 measured operations;
- single and batch sizes 8 and 32;
- concurrency 1, 4, 16, and the configured queue limit;
- verifier routes: deterministic, NLI-routed, and mixed, where available;
- SQLite persistence, hash-only privacy, strict redaction, and no-persistence
  modes;
- streaming, SSE exclusion, file response, and background-persistence paths;
- LangChain, LangGraph, LlamaIndex, FastAPI, and OpenTelemetry integrations
  where supported by the release.

Measure wall-clock latency p50/p95/p99, throughput, peak resident memory, CPU
time where available, bytes stored, rejected/dropped operations, truncation,
persistence failures, queue saturation, and integration-isolation failures.
Record hardware, OS, Python version, model runtime, thread settings, warm/cold
state, and background load. NLI download/setup time is reported separately.

No operational benchmark starts until its fixture generator and measurement
script are frozen. Performance optimization after viewing results belongs to a
future engineering version and does not alter the sealed diagnostic evaluation.

## Optional RQ5 boundary

RQ5 is not activated by this document. If later authorized, its separate
protocol must specify participants, counterbalancing, tasks, outcomes, power,
consent, compensation, privacy, exclusions, and analysis before recruitment.
Existing LLM simulations may be used only as calibration for task wording and
must not be described as developer evidence.

## Reproducibility outputs

The final artifact must retain, subject to access restrictions:

- source and case manifests plus hashes;
- generation and retry configurations;
- candidate-only inputs;
- frozen predictions and baseline outputs;
- gold hash and custodian receipt, with public labels only when authorized;
- metric and statistical source code;
- tables and figures generated from immutable results;
- environment and dependency locks;
- deviation, failure, and access logs.

Raw private data, secrets, provider credentials, annotator identities, and
restricted source content are never committed.
