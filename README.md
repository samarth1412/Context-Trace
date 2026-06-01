# ContextTrace

[![Build](https://github.com/samarth1412/Context-Trace/actions/workflows/ci.yml/badge.svg)](https://github.com/samarth1412/Context-Trace/actions)
[![PyPI](https://img.shields.io/badge/pypi-coming_soon-blue)](https://pypi.org/project/contexttrace/)
[![Python](https://img.shields.io/badge/python-3.8%2B-blue)](packages/contexttrace/pyproject.toml)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

ContextTrace is a local-first SDK and CLI for debugging RAG and agent reliability. It stores traces locally in SQLite, verifies whether citations support answer claims, classifies failure modes, and generates HTML reports without requiring a hosted dashboard.

## Why

RAG failures often look plausible:

- retrieved chunks miss critical evidence
- selected context drops the right source
- citations point to documents that do not support the claim
- long context increases cost and noise
- agents use stale memory or the wrong tool

ContextTrace records the evidence path so you can inspect what happened locally before users find the issue.

## Quickstart

```bash
pip install contexttrace
contexttrace init
contexttrace demo --dataset refund_policy
contexttrace report --last --open
```

Ten-line SDK example:

```python
from contexttrace import ContextTrace

ct = ContextTrace(project="support-rag")

with ct.trace(query="What is the refund policy?") as trace:
    trace.log_retrieval([{"chunk_id": "c1", "content": "Refunds are available within 30 days."}])
    trace.log_context(chunk_ids=["c1"])
    trace.log_answer("Refunds are available within 30 days.")
    trace.log_citations([{"claim": "Refunds are available within 30 days.", "source_chunk_id": "c1"}])
    trace.evaluate()
```

By default, traces are stored at `.contexttrace/contexttrace.db`.

## CLI

```bash
contexttrace init
contexttrace status
contexttrace demo --dataset refund_policy
contexttrace traces list
contexttrace traces show <trace_id>
contexttrace report --last --open
contexttrace viewer
contexttrace doctor
contexttrace config show
```

Evaluate an existing local RAG endpoint without installing the SDK in that app:

```bash
contexttrace eval \
  --dataset evals/questions.json \
  --endpoint http://localhost:8000/query \
  --method POST \
  --input-key question \
  --answer-path $.answer \
  --contexts-path $.contexts \
  --citations-path $.citations
```

## Local Architecture

```text
RAG app / agent
    |
    | SDK, integrations, or CLI endpoint eval
    v
packages/contexttrace
    |-- local SQLite store: .contexttrace/contexttrace.db
    |-- citation and failure diagnostics
    |-- HTML report generator
    |-- local viewer: http://localhost:8765
    |-- optional hosted/backend transport
```

Repository layout:

```text
packages/contexttrace   Python SDK, CLI, integrations, local SQLite store
apps/api                Optional FastAPI backend/local API mode
benchmarks              Reproducible benchmark runner and sample results
datasets/demo           Demo datasets for CLI and docs
docs                    Developer documentation
examples                SDK, integration, local report, and endpoint examples
```

The hosted Next.js dashboard has been removed from v1. Use `contexttrace report` and `contexttrace viewer` for local inspection.

## What Reports Show

- query and answer
- retrieved chunks and selected context
- citation verdicts and unsupported claims
- failure type, severity, root cause, and suggested fix
- reliability score with strengths and weaknesses
- token usage, cost, and latency when logged
- eval-run summaries for endpoint regression testing

## Failure Taxonomy

ContextTrace tracks RAG-specific failures such as `retrieval_miss`, `low_relevance_context`, `citation_mismatch`, `unsupported_answer`, `contradicted_answer`, `conflicting_sources`, `bad_chunking`, `over_compression`, `should_have_abstained`, and `query_needs_decomposition`.

## Integrations

- LangChain callback handler
- LlamaIndex callback handler
- FastAPI middleware
- LangGraph beta tracer
- OpenTelemetry export
- Bring-your-own RAG endpoint evaluation

See [docs](docs/) and [examples](examples/) for usage.

## Development

```bash
python -m pip install -e "./apps/api[test]"
python -m pip install -e "./packages/contexttrace[test]"
python -m pytest -q
```

Optional local services for backend/playground work:

```bash
docker compose up -d postgres qdrant
```

## Roadmap

- stronger local judge/provider configuration
- richer local viewer filtering and comparison pages
- more benchmark datasets
- packaged demo datasets
- hosted mode as an optional add-on, not the default

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Security reports should follow [SECURITY.md](SECURITY.md).
