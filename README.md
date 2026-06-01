# ContextTrace: Local-first RAG reliability SDK

[![Build](https://github.com/samarth1412/Context-Trace/actions/workflows/ci.yml/badge.svg)](https://github.com/samarth1412/Context-Trace/actions)
[![PyPI](https://img.shields.io/badge/pypi-coming_soon-blue)](https://pypi.org/project/contexttrace/)
[![Python](https://img.shields.io/badge/python-3.8%2B-blue)](packages/contexttrace/pyproject.toml)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

Debug retrieval misses, unsupported claims, citation mismatches, and context failures without uploading your data.

ContextTrace is an SDK and CLI for RAG and agent developers. It stores traces locally in SQLite, evaluates citation support, classifies RAG failure modes, and generates local HTML reports you can share in issues, PRs, and regression reviews.

## Why ContextTrace?

RAG systems often fail silently:

- retrievers miss the source that answers the question
- selected context drops the most relevant chunk
- citations point to evidence that does not support the claim
- archived or conflicting sources leak into answers
- agents reuse stale memory or irrelevant tool output

ContextTrace records the evidence path and turns it into an actionable local report.

## Quickstart

```bash
pip install contexttrace
contexttrace init
contexttrace demo --dataset refund_policy
contexttrace report --last --open
```

This creates `.contexttrace/contexttrace.db`, runs a synthetic demo RAG flow, and writes an HTML report under `.contexttrace/reports/`.

## SDK Usage

```python
from contexttrace import ContextTrace

ct = ContextTrace(project="support-rag")

with ct.trace(query="What is the refund policy?") as trace:
    chunks = retriever.search("What is the refund policy?")
    trace.log_retrieval(chunks)
    trace.log_context(chunks[:5])
    answer = llm.generate("What is the refund policy?", chunks[:5])
    trace.log_answer(answer, usage={"total_tokens": 1200})
    trace.log_citations([
        {"claim": "Refunds are available within 30 days.", "source_chunk_id": "chunk_12"}
    ])
    trace.evaluate()
```

No backend server is required unless you explicitly configure one.

## BYO RAG Endpoint

Evaluate an existing API without adding SDK code:

```bash
contexttrace eval \
  --dataset evals/questions.json \
  --endpoint http://localhost:8000/query \
  --method POST \
  --input-key question \
  --answer-path $.answer \
  --contexts-path $.contexts \
  --citations-path $.citations \
  --fail-on "failure_rate>0.25" \
  --fail-on "citation_support<0.80"
```

ContextTrace calls your endpoint, maps the JSON response, creates local traces, evaluates them, and writes a report.

## Failure Taxonomy

RAG failure labels include:

- `retrieval_miss`
- `low_relevance_context`
- `citation_mismatch`
- `unsupported_answer`
- `contradicted_answer`
- `conflicting_sources`
- `bad_chunking`
- `over_compression`
- `should_have_abstained`
- `query_needs_decomposition`

Each report includes severity, root cause, and suggested fix.

## Local Reports

Reports include:

- executive summary and reliability score
- query, answer, retrieved chunks, and selected context
- citation verdicts and unsupported claims
- failure breakdown and suggested fixes
- token, cost, and latency metrics when logged

Placeholder assets live in [docs/assets](docs/assets/) until final screenshots are captured.

## CLI Commands

```bash
contexttrace init
contexttrace status
contexttrace demo --dataset refund_policy
contexttrace traces list
contexttrace traces show <trace_id>
contexttrace report --last --open
contexttrace viewer
contexttrace benchmark --dataset datasets/demo/refund_policy
contexttrace eval --dataset evals/questions.json --endpoint http://localhost:8000/query
contexttrace doctor
```

## Integrations

- LangChain callback handler
- LlamaIndex callback handler
- FastAPI middleware and endpoint evaluation
- LangGraph beta tracer
- OpenTelemetry export

## Privacy And Local Mode

Local mode is the default. Trace data is written to `.contexttrace/contexttrace.db`. ContextTrace makes no network calls unless you configure an LLM judge provider or point the CLI at your RAG endpoint.

Privacy controls:

- `local_only: true`
- `log_chunk_text: false`
- `log_answer_text: false`
- `storage_path: /custom/contexttrace.db`

## Regression Testing And GitHub Action

Run local regression checks:

```bash
contexttrace benchmark \
  --dataset datasets/demo/refund_policy \
  --fail-on "failure_rate>0.25" \
  --fail-on "citation_support<0.80"
```

Use the bundled composite action:

```yaml
- uses: ./.github/actions/contexttrace-rag-eval
  with:
    dataset_path: datasets/demo/refund_policy
    fail_on: |
      failure_rate>0.25
      citation_support<0.80
```

The action uploads the HTML report and writes a GitHub markdown summary.

## Architecture

```text
RAG app / agent / endpoint
    |
    | SDK, integrations, or CLI eval
    v
packages/contexttrace
    |-- local SQLite store: .contexttrace/contexttrace.db
    |-- citation and failure diagnostics
    |-- HTML report generator
    |-- local viewer: http://localhost:8765
    |-- optional API transport
```

Repository layout:

```text
packages/contexttrace   Python SDK, CLI, integrations, local SQLite store
apps/api                Optional FastAPI API mode
datasets/demo           Synthetic public demo datasets
benchmarks              Deterministic benchmark helpers
docs                    Developer documentation
examples                SDK and endpoint examples
```

## Roadmap

- stronger configurable local judge providers
- richer local viewer filtering
- more public demo datasets
- packaged benchmark fixtures
- optional hosted mode as an add-on, not a requirement

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Security reports should follow [SECURITY.md](SECURITY.md).
