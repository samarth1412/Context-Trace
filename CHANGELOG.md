# Changelog

All notable changes to ContextTrace will be documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this project uses semantic versioning after public release.

## [Unreleased]

### Added

- Nothing yet.

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
