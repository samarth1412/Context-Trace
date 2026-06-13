# ContextTrace Quickstart

ContextTrace is local-first. You can trace a RAG pipeline, evaluate citation support, and generate reports without running a backend server.

## 1. Install

```bash
pip install contexttrace
contexttrace init
contexttrace demo --dataset refund_policy
contexttrace report --last --open
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

Capture one live response as portable verification JSON:

```bash
contexttrace capture endpoint \
  --endpoint http://localhost:8000/query \
  --query "What is the refund policy?" \
  --out traces/refund_trace.json \
  --verify \
  --report
```

Or capture a saved response JSON from a failing run:

```bash
contexttrace capture response response.json \
  --query "What is the refund policy?" \
  --out traces/refund_trace.json \
  --verify \
  --report
```

Run a full dataset through the same endpoint:

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

These commands map your endpoint response fields, create local traces or portable trace JSON, run diagnostics, and write local HTML reports.

Inspect a portable trace before deeper debugging:

```bash
contexttrace inspect traces/refund_trace.json
```

Localize the likely root cause:

```bash
contexttrace diagnose traces/refund_trace.json --report --fail-on any_issue
```

Agent traces can use the same command:

```bash
contexttrace diagnose examples/diagnose_agent_trace.json --report --fail-on high_risk
```

Run the complete evidence QA workflow:

```bash
contexttrace qa traces/refund_trace.json --corpus docs/ --report
```

## 6. Run A Regression Benchmark

```bash
contexttrace benchmark \
  --dataset datasets/demo/refund_policy \
  --fail-on "failure_rate>0.25" \
  --fail-on "citation_support<0.80"
```

This writes `benchmark_results.json`, `benchmark_summary.md`, and `benchmark_report.html` under `.contexttrace/benchmarks/`.

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

Read [SDK Usage](sdk.md), [Local Mode](local-mode.md), [Demo Datasets](demo-datasets.md), [Bring Your Own RAG Endpoint](byo-rag-endpoint.md), [Regression Testing](regression-testing.md), [Citation Verification](citation-verification.md), and [Failure Taxonomy](failure-taxonomy.md).
