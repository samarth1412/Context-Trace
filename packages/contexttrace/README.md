# ContextTrace

ContextTrace is an SDK-first reliability layer for RAG and agent applications. It helps developers trace retrieved context, selected evidence, answers, citations, token usage, failure types, and actionable fixes.

Core SDK features:

- trace query, retrieved chunks, selected context, answer, citations, token usage, and metadata
- run citation verification through the ContextTrace backend
- export local HTML reports
- run CLI evals against an existing RAG endpoint
- use local mode without a backend
- integrate with LangChain, LlamaIndex, FastAPI, LangGraph, and OpenTelemetry

## Install

```bash
pip install contexttrace
contexttrace --version
contexttrace init
```

Optional extras:

```bash
pip install "contexttrace[langchain]"
pip install "contexttrace[llamaindex]"
pip install "contexttrace[local]"
pip install "contexttrace[otel]"
pip install "contexttrace[all]"
```

## Quickstart

```python
from contexttrace import ContextTrace

ct = ContextTrace(mode="local", project="support-rag")

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
    trace.export_report("report.html")
```

## Links

- Repository: https://github.com/samarth1412/Context-Trace
- Documentation: https://github.com/samarth1412/Context-Trace/tree/main/docs
- Issues: https://github.com/samarth1412/Context-Trace/issues
