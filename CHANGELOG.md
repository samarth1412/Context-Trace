# Changelog

All notable changes to ContextTrace will be documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this project uses semantic versioning after public release.

## [Unreleased]

### Added

- Claim output now separates `support_status`, `truth_status`, and `source_status` so grounded evidence is not presented as independent truth.
- Judge mode now sends selected evidence spans with char-offset metadata instead of broad retrieved contexts.
- Optional `contexttrace[nli]` and `contexttrace[nli-onnx]` extras plus `--mode nli` for local claim-versus-span entailment and contradiction checks.
- Local NLI model loading is explicit and offline-only through `CONTEXTTRACE_NLI_MODEL_PATH`; ContextTrace never downloads NLI models automatically.

### Changed

- Verification and QA reports now say "grounded" for span-backed support and explicitly note that grounding is not a truth or freshness guarantee.

## [0.8.0] - 2026-06-04

### Added

- First-class local judge providers for Ollama, LM Studio, vLLM, and local OpenAI-compatible servers.
- `contexttrace judge-calibrate` for scoring a configured local judge against bundled golden RAG failure cases, including exact-match rate, contradiction recall, citation match, abstention match, and dangerous-miss rate.
- Local JSON judge cache at `.contexttrace/judge_cache.json` with deterministic claim/context/model/prompt cache keys.
- Local-only/offline enforcement that blocks remote judge URLs while `local_only: true` is active.
- Optional `contexttrace[local-ml]` extra and `--mode local_ml` verifier mode with offline hash embeddings by default and local SentenceTransformers model-path support.
- Role-aware semantic contradiction checks for location, attribution, causal direction, version, number, URL, and negation conflicts.
- Adversarial verification benchmark cases for local-first privacy, endpoint, numeric, version, and relation mistakes.
- OpenTelemetry export spans aligned with modern GenAI/OpenInference-style span kinds for retrieval, LLM answers, verification, and agent/tool events.

### Changed

- Judge docs and CLI help now present Ollama/local providers as the default higher-accuracy path, with remote judges explicitly opt-in.
- `contexttrace init` writes local judge cache settings by default.

## [0.7.0] - 2026-06-04

### Added

- `contexttrace suite create` for turning saved portable RAG traces into local regression-suite cases.
- `contexttrace suite run` for replaying saved queries against a RAG endpoint, running evidence QA, comparing against the baseline trace, and exiting non-zero when cases fail.
- `contexttrace suite add`, `suite list`, `suite remove`, and `suite prune` for managing suite cases as failures are discovered, fixed, or retired.
- `contexttrace suite report` for local HTML regression-suite reports with failed cases, resolved failures, and claim-level QA summaries.
- Regression-suite examples, a GitHub Actions starter workflow, and validation-story docs for the saved-failure-to-CI workflow.

## [0.6.0] - 2026-06-04

### Added

- `contexttrace audit-benchmark --case-set real` for validating retrieval-audit labels against bundled public OSS documentation and GitHub issue cases.
- Public-source audit benchmark cases covering retrieval misses, chunking issues, reranking failures, corpus gaps, answer overreach, stale sources, insufficient context, and clean retrieval.
- `capture_rag_trace` and `write_rag_trace` helpers for exporting in-memory RAG artifacts to portable `contexttrace verify` JSON.
- `contexttrace capture endpoint` for turning one live RAG endpoint response into portable `contexttrace verify` JSON, with optional immediate verification and local HTML report generation.
- `contexttrace capture response` for turning a saved RAG endpoint response JSON file into the same portable verification trace format.
- `contexttrace inspect trace.json` for checking portable trace shape, extracted claims, context IDs, citation references, warnings, and suggested next commands before verification.
- `contexttrace qa trace.json --corpus docs/` for running inspect, verify, optional corpus audit, risk scoring, and prioritized next actions in one local workflow.
- Retrieval audit diagnostics now include failure stages, evidence status, diagnostic signals, failure paths, developer summaries, and prioritized recommended actions.
- Validation pack docs for recording public-source RAG app runs and saved-response debugging workflows.
- Public RAG app validation harnesses, including an end-to-end LangChain/Ollama/FAISS run against a public RAG repository.

## [0.5.0] - 2026-06-04

### Added

- `contexttrace audit trace.json --corpus docs/` for local corpus-level retrieval failure diagnosis.
- Retrieval audit labels for retrieval misses, reranking failures, chunking issues, corpus gaps, answer overreach, stale sources, and insufficient context.
- Local HTML audit reports that explain whether unsupported claims failed because retrieval missed evidence, the source corpus lacks coverage, or generation overclaimed.

## [0.4.0] - 2026-06-04

### Added

- `contexttrace compare baseline.json current.json` for local regression diffing across two claim-level verification runs.
- `contexttrace compare --json --report --fail-on ...` for CI-friendly detection of new unsupported claims, citation regressions, support-rate drops, should-abstain flips, and new root causes.
- Local HTML regression reports that show metric deltas, new failures, resolved failures, root-cause changes, and raw JSON summaries.

## [0.3.0] - 2026-06-03

### Added

- Document-backed verification benchmark cases sourced from ContextTrace docs and release artifacts.
- External verification benchmark case set sourced from Qdrant, Chroma, Haystack, LangChain docs, and public Chroma GitHub issues.
- `contexttrace verify-benchmark --case-set external|all` for running third-party benchmark cases.
- `contexttrace verify-benchmark --report` for local HTML benchmark reports with misses to inspect.
- Claim and evidence sentence splitting safeguards for version numbers and file paths.
- Evidence span metadata with character offsets and stable span hashes in verification output.
- Required, matched, and missing fact diagnostics for claim-level verdicts and reports.
- Claim-level root-cause diagnosis for retrieval misses, answer overreach, wrong citations, conflicting contexts, insufficient context, and should-have-abstained failures.

## [0.2.0] - 2026-06-03

### Added

- Local claim-level evidence verification through `contexttrace verify`.
- Bundled `contexttrace verify-demo` golden traces for PyPI users.
- Portable RAG trace schema for query, answer, retrieved contexts, optional citations, and metadata.
- Atomic claim decomposition, `partially_supported` verdicts, evidence highlighting, and `--fail-on` CI gates for verification.
- Local semantic verification mode and bundled `contexttrace verify-benchmark` precision/recall benchmark.
- Rule-based claim extraction, deterministic evidence matching, support verdicts, citation mismatch detection, abstention judgment, local HTML verification reports, demo traces, and pytest coverage.
- PyPI release metadata, `contexttrace --version`, build workflow, and release documentation.
- SDK-first trace logging for RAG pipelines.
- FastAPI backend with API-key authentication.
- SQLAlchemy models and Alembic migrations for traces, chunks, answers, citations, failure reports, eval sets, external RAG endpoints, and agent events.
- Citation verification with provider-based LLM judge abstraction.
- Failure classification and suggested fixes.
- Local HTML report generation.
- Batch evaluation and GitHub Action CLI support.
- Next.js dashboard, reports, trace detail pages, and hosted playground.
- LangChain, LlamaIndex, FastAPI middleware, LangGraph beta, and OpenTelemetry integrations.
- Hosted playground document parsing, chunking, retrieval strategy comparison, and sample datasets.
- Context policy runtime diagnostics.
- Public benchmark pipeline and website benchmark data export.
- Practical RAG reliability score.

## [0.1.0] - 2026-05-31

### Added

- Initial open-source launch baseline.
