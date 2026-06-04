# Public RAG App Validation Notes

Use this file to summarize public-source application runs that exercise ContextTrace.

## Template

```text
App:
Repository:
Commit:
Setup:
Question:
Response mapping:
Trace:
Verify report:
Audit report:
Verification summary:
Audit summary:
What ContextTrace diagnosed:
What was missing or noisy:
Follow-up:
```

## Current Harnesses

The reproducible scripts live under `benchmarks/real_world_rag/`:

- `run_real_world_validation.py`: smoke validation over public-source app response shapes.
- `run_ollama_hf_e2e.py`: local end-to-end LangChain/Ollama/FAISS run against a public RAG repository.

Generated outputs are intentionally ignored. When a run becomes part of the published validation pack, copy only the minimal trace/report summaries needed to explain the finding.
