# ContextTrace

**Debug RAG failures before users find them.**

ContextTrace is a local-first Python SDK and CLI for evaluating existing RAG and AI agent systems. It records retrieved chunks, selected context, answer claims, citations, token usage, latency, and agent events, then writes local traces and HTML reports without requiring a hosted dashboard.

## Install

```bash
pip install contexttrace
contexttrace --version
contexttrace init
```

Optional integrations:

```bash
pip install "contexttrace[langchain]"
pip install "contexttrace[llamaindex]"
pip install "contexttrace[fastapi]"
pip install "contexttrace[langgraph]"
pip install "contexttrace[otel]"
pip install "contexttrace[all]"
```

## Quickstart

```bash
contexttrace init
contexttrace demo --dataset refund_policy
contexttrace report --last
contexttrace doctor
```

By default, traces are stored locally in:

```text
.contexttrace/contexttrace.db
```

## SDK Example

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

    result = trace.evaluate()
    print(result["failure"]["failure_type"])
```

## BYO RAG Endpoint

Evaluate a running local or hosted RAG API without adding SDK code:

```bash
contexttrace eval \
  --dataset evals/questions.json \
  --endpoint http://localhost:8000/query \
  --method POST \
  --input-key question \
  --answer-path $.answer \
  --contexts-path $.contexts \
  --citations-path $.citations \
  --fail-on "failure_rate>0.25"
```

## What It Catches

- `retrieval_miss`
- `citation_mismatch`
- `unsupported_answer`
- `contradicted_answer`
- `conflicting_sources`
- `should_have_abstained`
- agent failures such as `stale_memory_used` and `tool_error`

## Privacy

Local mode is the default. ContextTrace makes no network calls unless you configure an LLM judge provider or evaluate a RAG endpoint you provide.

## Links

- Repository: https://github.com/samarth1412/Context-Trace
- Documentation: https://github.com/samarth1412/Context-Trace/tree/main/docs
- Issues: https://github.com/samarth1412/Context-Trace/issues
