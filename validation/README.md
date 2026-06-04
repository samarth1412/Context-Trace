# ContextTrace Validation Pack

This folder is for reproducible validation notes and fixtures from public-source RAG applications or saved endpoint responses.

The goal is to show the full debugging path:

```text
capture -> inspect -> verify -> audit -> report
```

Do not add invented response fixtures here. Keep generated traces and reports under `.contexttrace/` or another ignored output directory unless they are intentionally checked in as a documented validation artifact.

## Public App Validation

Use the existing public app harness when you want to reproduce the current validation workflow:

```bash
python benchmarks/real_world_rag/run_real_world_validation.py
python benchmarks/real_world_rag/run_ollama_hf_e2e.py
```

The harness writes generated outputs under `benchmarks/real_world_rag/traces/`, `benchmarks/real_world_rag/reports/`, and result JSON files that are ignored by git.

## Saved Response Validation

When a RAG app returns JSON with answer and context fields, capture it into a portable ContextTrace trace:

```bash
contexttrace capture response path/to/response.json \
  --query "The user question that produced the response" \
  --answer-path $.answer \
  --contexts-path $.contexts \
  --citations-path $.citations \
  --out .contexttrace/traces/public_app_trace.json \
  --verify \
  --report \
  --report-out .contexttrace/reports/public_app_verify.html
```

Then inspect and audit:

```bash
contexttrace inspect .contexttrace/traces/public_app_trace.json
contexttrace audit .contexttrace/traces/public_app_trace.json \
  --corpus path/to/corpus \
  --report \
  --out .contexttrace/reports/public_app_audit.html
```

## What To Record

For each validation run, record:

- app repository URL and commit SHA
- command used to run the app or produce the response JSON
- response field mapping
- ContextTrace commands used
- verification summary
- audit summary
- which diagnosis was useful or wrong
- limitations or setup issues

## Acceptance Bar

A validation case is useful when it demonstrates at least one of:

- a supported answer with clean evidence
- an unsupported answer
- a citation mismatch
- a retrieval miss
- a chunking or reranking issue
- a corpus gap
- answer overreach
- stale or conflicting source evidence
