# Changelog

All notable changes to ContextTrace will be documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this project uses semantic versioning after public release.

## [Unreleased]

### Added

- `contexttrace audit-benchmark --case-set real` for validating retrieval-audit labels against bundled public OSS documentation and GitHub issue cases.
- Real audit benchmark cases covering retrieval misses, chunking issues, reranking failures, corpus gaps, answer overreach, stale sources, insufficient context, and clean retrieval.

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

- Real-document verification benchmark cases sourced from ContextTrace docs and release artifacts.
- External verification benchmark case set sourced from Qdrant, Chroma, Haystack, LangChain docs, and public Chroma GitHub issues.
- `contexttrace verify-benchmark --case-set external|all` for running third-party real-world benchmark cases.
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
