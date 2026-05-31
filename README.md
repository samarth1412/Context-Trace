# ContextTrace

ContextTrace is an SDK-first RAG reliability platform. It lets RAG developers trace existing pipelines, verify whether citations support answer claims, classify RAG failure modes, compare retrieval strategies, and export reliability reports.

It is not a LangSmith clone and not a RAG chatbot. The core product surface is evidence-level tracing and debugging for RAG systems.

## What ContextTrace Tracks

- Query and trace metadata
- Retrieved chunks and selected context
- Answers, citations, token usage, and latency
- Citation support verdicts
- RAG failure type, severity, root cause, and suggested fix
- Context policy decisions and retrieval strategy comparisons

## Repository Layout

```text
apps/api                  FastAPI backend
apps/web                  Next.js dashboard and playground
packages/contexttrace     Python SDK package
docs/                     Developer documentation
examples/                 SDK, integration, report, eval, and workflow examples
docker-compose.yml        Local PostgreSQL and Qdrant
```

## Installation

Start local infrastructure:

```bash
docker compose up -d postgres qdrant
cp .env.example .env
```

Install and run the API:

```bash
cd apps/api
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[test]"
alembic upgrade head
uvicorn app.main:app --reload
```

Install the SDK:

```bash
cd packages/contexttrace
pip install -e ".[test]"
```

Install and run the dashboard:

```bash
cd apps/web
npm install
npm run dev
```

The local API defaults to `http://localhost:8000` with API key `ctx_test`.

## 10-Line Quickstart

```python
from contexttrace import ContextTrace
ct = ContextTrace(api_key="ctx_test", project="support-rag")
with ct.trace(query="What is the refund policy?") as trace:
    chunks = retriever.search("What is the refund policy?")
    trace.log_retrieval(chunks)
    trace.log_context(chunks[:5])
    answer = llm.generate("What is the refund policy?", chunks[:5])
    trace.log_answer(answer, model="gpt-4.1-mini", usage={"total_tokens": 1200})
    trace.log_citations([{"claim": "Refunds are available within 30 days.", "source_chunk_id": "chunk_12"}])
    result = trace.evaluate()
```

## Dashboard Screenshots

Screenshots are intentionally left as placeholders until the UI stabilizes:

```text
docs/assets/dashboard-placeholder.png
docs/assets/trace-detail-placeholder.png
docs/assets/playground-placeholder.png
```

## Documentation

- [Quickstart](docs/quickstart.md)
- [SDK Usage](docs/sdk.md)
- [Failure Taxonomy](docs/failure_taxonomy.md)
- [Citation Verification](docs/citation_verification.md)
- [LangChain Integration](docs/langchain.md)
- [LlamaIndex Integration](docs/llamaindex.md)

## Examples

- `examples/custom_rag.py`
- `examples/langchain_rag.py`
- `examples/llamaindex_rag.py`
- `examples/local_report.py`
- `examples/batch_eval.py`
- `examples/contexttrace-rag-eval-workflow.yml`
- `examples/evals/questions.json`

## Hosted Playground

The playground accepts PDF, TXT, and Markdown uploads, chunks documents with token-aware overlap, embeds chunks through a provider abstraction, and stores vectors in Qdrant.

```env
CONTEXTTRACE_EMBEDDING_PROVIDER=hash
CONTEXTTRACE_ANSWER_PROVIDER=mock
CONTEXTTRACE_PLAYGROUND_VECTOR_STORE=qdrant
CONTEXTTRACE_QDRANT_URL=http://localhost:6333
```

The playground can run:

```text
dense_top_k
bm25_top_k
hybrid
hybrid_rerank
```

Context Policy Runtime can also select:

```text
dense_top_k
hybrid
hybrid_rerank
compressed_context
abstain_low_confidence
```

## CI RAG Evaluation

The SDK installs a `contexttrace` CLI:

```bash
contexttrace eval \
  --dataset evals/questions.json \
  --endpoint https://my-rag-api.com/query \
  --min-citation-support 0.80 \
  --max-unsupported-claim-rate 0.10 \
  --max-failure-rate 0.05
```

The CLI calls your RAG endpoint for each question, logs traces, runs ContextTrace evaluation, writes `contexttrace-eval-summary.md`, appends to `$GITHUB_STEP_SUMMARY`, and exits non-zero when thresholds fail.

## Main API Endpoints

```text
POST /v1/traces/start
POST /v1/traces/{trace_id}/retrieval
POST /v1/traces/{trace_id}/context
POST /v1/traces/{trace_id}/answer
POST /v1/traces/{trace_id}/citations
POST /v1/traces/{trace_id}/evaluate
GET  /v1/traces/{trace_id}
POST /v1/eval-sets
POST /v1/eval-sets/{id}/questions
POST /v1/eval-sets/{id}/runs
GET  /v1/eval-sets/{id}/summary
POST /v1/playground/documents
POST /v1/playground/query
POST /v1/playground/compare
```

Authenticate with:

```text
Authorization: Bearer ctx_test
```

or:

```text
X-API-Key: ctx_test
```

## Tests

```bash
pytest
```

Backend tests use SQLite in memory and mock judge providers. SDK tests use fake transports and do not require a running backend.

## Roadmap

- Persisted dashboard filters and project-level reliability trends
- Richer policy runtime configuration per project
- Dataset-driven hosted eval runs that execute RAG pipelines directly
- Trace diffing across retrieval strategies and prompts
- Additional judge providers and model-specific calibration
- Report exports for CI artifacts and compliance review
- Team/project access control beyond local API-key auth
