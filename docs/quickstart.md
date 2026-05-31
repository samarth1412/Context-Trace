# ContextTrace Quickstart

ContextTrace adds evidence-level observability to existing RAG pipelines. It is not a chatbot framework: you keep your retriever, generator, and app code, then log the evidence and answer lifecycle to ContextTrace.

## 1. Start The Backend

```bash
docker compose up -d postgres qdrant
cp .env.example .env
cd apps/api
pip install -e ".[test]"
alembic upgrade head
uvicorn app.main:app --reload
```

The local API runs at `http://localhost:8000`. The default development API key is `ctx_test`.

## 2. Install The SDK

```bash
cd packages/contexttrace
pip install -e ".[test]"
```

For local-only usage without the backend:

```bash
contexttrace init
```

This creates `contexttrace.yaml` in local mode and stores traces under `.contexttrace`.

## 3. Trace A RAG Request

```python
from contexttrace import ContextTrace

ct = ContextTrace(mode="local", project="support-rag")

with ct.trace(query="What is the refund policy?") as trace:
    chunks = retriever.search("What is the refund policy?")
    trace.log_retrieval(chunks)
    trace.log_context(chunks[:5])
    answer = llm.generate("What is the refund policy?", chunks[:5])
    trace.log_answer(answer, model="gpt-4.1-mini", usage={"total_tokens": 1200})
    trace.log_citations([{"claim": "Refunds are available within 30 days.", "source_chunk_id": "chunk_12"}])
    result = trace.evaluate()
```

Use hosted mode with the same trace lifecycle:

```python
ct = ContextTrace(api_key="ctx_test", project="support-rag", base_url="http://localhost:8000")
```

## 4. Open The Dashboard

```bash
cd apps/web
npm install
npm run dev
```

Open `http://localhost:3000/dashboard`.

## 5. Generate A Local Report

```python
trace.export_report(path="report.html")
```

Reports include the query, retrieved chunks, selected context, answer, citations, support verdicts, failure diagnosis, token usage, and latency metadata.

From the CLI:

```bash
contexttrace trace list
contexttrace report --last --output report.html
```

## Data Shape

Chunks can be dictionaries or objects. ContextTrace reads these fields:

```python
{
    "chunk_id": "chunk_12",
    "content": "Customers can request refunds within 30 days.",
    "source": "refund-policy.md",
    "metadata": {"section": "refunds"},
    "relevance_score": 0.91,
}
```

Citations should reference logged chunk IDs:

```python
{
    "claim": "Refunds are available within 30 days.",
    "source_chunk_id": "chunk_12",
}
```

## Next Steps

Read [SDK Usage](sdk.md), [Citation Verification](citation_verification.md), and [Failure Taxonomy](failure_taxonomy.md).
