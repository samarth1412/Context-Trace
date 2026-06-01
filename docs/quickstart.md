# ContextTrace Quickstart

ContextTrace is local-first. You can trace a RAG pipeline, evaluate citation support, and generate reports without running a backend server.

## 1. Install

```bash
pip install contexttrace
contexttrace init
```

For repo development:

```bash
pip install -e "./packages/contexttrace[test]"
```

## 2. Trace A RAG Request

```python
from contexttrace import ContextTrace

ct = ContextTrace(project="support-rag")

with ct.trace(query="What is the refund policy?") as trace:
    chunks = retriever.search("What is the refund policy?")
    trace.log_retrieval(chunks)
    trace.log_context(chunks[:5])
    answer = llm.generate("What is the refund policy?", chunks[:5])
    trace.log_answer(answer, model="gpt-4.1-mini", usage={"total_tokens": 1200})
    trace.log_citations([{"claim": "Refunds are available within 30 days.", "source_chunk_id": "chunk_12"}])
    result = trace.evaluate()
```

Traces are stored in `.contexttrace/contexttrace.db` by default.

## 3. Generate A Report

```bash
contexttrace report --last --open
```

Reports include query, retrieved chunks, selected context, answer, citations, support verdicts, failure diagnosis, token usage, and latency metadata.

## 4. Use The Local Viewer

```bash
contexttrace viewer
```

Open `http://localhost:8765` to inspect local traces, eval runs, and reports.

## 5. Evaluate A RAG Endpoint

```bash
contexttrace eval \
  --dataset evals/sample_questions.json \
  --endpoint http://localhost:8000/query \
  --method POST \
  --input-key question \
  --answer-path $.answer \
  --contexts-path $.contexts \
  --citations-path $.citations
```

This calls your endpoint, maps the response fields, creates local traces, runs diagnostics, and writes an HTML eval report.

## Optional Backend

The FastAPI backend remains available for local API mode and compatibility work:

```bash
docker compose up -d postgres qdrant
pip install -e "./apps/api[test]"
cd apps/api
alembic upgrade head
uvicorn app.main:app --reload
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

Read [SDK Usage](sdk.md), [Local Mode](local-mode.md), [Bring Your Own RAG Endpoint](byo-rag-endpoint.md), [Citation Verification](citation_verification.md), and [Failure Taxonomy](failure_taxonomy.md).
