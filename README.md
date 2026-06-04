# ContextTrace

[![Build](https://github.com/samarth1412/Context-Trace/actions/workflows/ci.yml/badge.svg)](https://github.com/samarth1412/Context-Trace/actions)
[![PyPI](https://img.shields.io/pypi/v/contexttrace.svg)](https://pypi.org/project/contexttrace/)
[![Python](https://img.shields.io/badge/python-3.8%2B-blue)](packages/contexttrace/pyproject.toml)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

**Local-first evidence-chain debugging for RAG and AI agents.**

ContextTrace helps developers find where a generated answer stopped being grounded in retrieved evidence. It is not a hosted dashboard and it is not a generic observability platform. It is a local SDK and CLI for inspecting the path from query to retrieved context to answer claims, citations, verdicts, and root causes.

```text
query -> retrieved contexts -> answer -> claims -> evidence verdicts -> root cause
```

## Why It Exists

RAG answers can look correct while still being unsupported:

- the retriever misses the source that answers the question
- the generator adds facts that are not in the context
- citations point to sources that do not support the claim
- stale or conflicting documents leak into the answer
- the system should have abstained but answered anyway

ContextTrace turns those failures into local JSON and HTML reports that say what broke and what to fix.

## Install

```bash
pip install contexttrace
contexttrace --version
contexttrace init
```

For the latest unreleased features from this repository:

```bash
git clone https://github.com/samarth1412/Context-Trace.git
cd Context-Trace
pip install -e packages/contexttrace
```

## Quickstart

Run a bundled claim-level verification demo:

```bash
contexttrace verify-demo unsupported_claim --report
```

Run the local SDK demo and open a report:

```bash
contexttrace init
contexttrace demo --dataset refund_policy
contexttrace report --last --open
```

By default, ContextTrace stores data locally in:

```text
.contexttrace/contexttrace.db
```

## Core Workflows

### 1. Verify Claim-Level Evidence

Use `verify` when you already have a portable RAG artifact with a query, answer, retrieved contexts, and optional citations.

```bash
contexttrace verify trace.json
contexttrace verify trace.json --json
contexttrace verify trace.json --report
contexttrace verify trace.json --fail-on unsupported --fail-on citation_mismatch
```

Minimal input:

```json
{
  "query": "How long does refund processing take?",
  "answer": "Refunds are processed within 5 business days.",
  "contexts": [
    {
      "id": "policy_2026",
      "text": "Customers may request refunds within 30 days of purchase."
    }
  ]
}
```

ContextTrace splits the answer into claims and classifies each claim as:

- `supported`
- `partially_supported`
- `unsupported`
- `unverifiable`
- `contradicted`

Capture RAG artifacts directly from common document objects:

```python
from contexttrace import capture_rag_trace, write_rag_trace

trace = capture_rag_trace(
    query=question,
    answer=answer,
    contexts=retrieved_docs,  # dicts or LangChain-style Documents
    metadata={"system": "my-rag-app"},
)
write_rag_trace(trace, "trace.json")
```

It also checks citation status:

- `citation_ok`
- `cited_source_missing`
- `cited_source_does_not_support_claim`
- `claim_supported_by_different_source`
- `claim_has_no_citation`

### 2. Compare Two Verification Runs

Use `compare` when you want to know whether a prompt, retriever, chunking, or model change made grounding worse.

```bash
contexttrace compare baseline.json current.json
contexttrace compare baseline.json current.json --json
contexttrace compare baseline.json current.json --report
contexttrace compare baseline.json current.json --fail-on new_failure
```

Run the bundled source-checkout example:

```bash
contexttrace compare examples/verify/compare_baseline.json examples/verify/compare_current_regression.json --report
```

The comparison report shows support-rate deltas, new unsupported claims, citation regressions, resolved failures, and new root causes.

### 3. Audit Retrieval Failures

Use `audit` when a claim failed and you want to know whether the evidence existed elsewhere in the corpus. The audit output includes a failure stage, evidence status, diagnostic signals, and prioritized next actions so you can tell whether the fix belongs in retrieval, reranking, chunking, generation, corpus coverage, or source freshness.

```bash
contexttrace audit trace.json --corpus docs/
contexttrace audit trace.json --corpus docs/ --json
contexttrace audit trace.json --corpus docs/ --report
contexttrace audit trace.json --corpus docs/ --fail-on retrieval_miss
```

Run the bundled source-checkout example:

```bash
contexttrace audit examples/audit/retrieval_miss_trace.json --corpus examples/audit/corpus --report
```

Check the audit labels against bundled public-source OSS cases:

```bash
contexttrace audit-benchmark --case-set real --mode semantic --report
```

Audit labels:

- `retrieval_miss`: supporting evidence exists in the corpus but was not retrieved
- `reranking_failure`: a related source was retrieved too low in the context list
- `chunking_issue`: a retrieved source is related, but the chunk omitted the supporting span
- `corpus_gap`: neither retrieved contexts nor the broader corpus support the claim
- `answer_overreach`: evidence supports part of the claim, but the answer added unsupported detail
- `stale_source`: retrieved or corpus evidence conflicts with the answer
- `insufficient_context`: available evidence is related but too weak or ambiguous

`audit` is available in ContextTrace v0.5.0 and later.

### 4. Evaluate An Existing RAG Endpoint

Use `capture endpoint` when you want to inspect one live response from a running RAG API and save it as portable `contexttrace verify` JSON:

```bash
contexttrace capture endpoint \
  --endpoint http://localhost:8000/query \
  --query "What is the refund policy?" \
  --answer-path $.answer \
  --contexts-path $.contexts \
  --citations-path $.citations \
  --out traces/refund_trace.json \
  --verify \
  --report
```

If you already saved the RAG response JSON from logs or a failing run:

```bash
contexttrace capture response response.json \
  --query "What is the refund policy?" \
  --answer-path $.answer \
  --contexts-path $.contexts \
  --out traces/refund_trace.json \
  --verify \
  --report
```

Use `eval` when you want ContextTrace to call your RAG API across a dataset and create local traces:

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

Expected endpoint shape:

```json
{
  "answer": "Refunds are available within 30 days.",
  "contexts": [
    {
      "id": "refund_policy_1",
      "text": "Customers may request a refund within 30 days of purchase."
    }
  ],
  "citations": [
    {
      "claim": "Refunds are available within 30 days.",
      "source_id": "refund_policy_1"
    }
  ]
}
```

### 5. Instrument With The SDK

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

## What ContextTrace Catches

| Failure | What It Means |
| --- | --- |
| `unsupported_answer` | The answer contains a claim no retrieved context supports. |
| `citation_mismatch` | The cited source does not support the cited claim. |
| `should_have_abstained` | The answer gives a factual response when context is insufficient. |
| `retrieval_miss` | Supporting evidence exists in the corpus but was not retrieved. |
| `answer_overreach` | Retrieved context supports part of the answer, but the model added unsupported detail. |
| `conflicting_sources` | Retrieved sources conflict with the generated claim. |

## Reports

ContextTrace writes self-contained local HTML reports. No CDN, hosted dashboard, or external service is required.

```bash
contexttrace verify-demo unsupported_claim --report --out reports/verify.html
contexttrace compare examples/verify/compare_baseline.json examples/verify/compare_current_regression.json --report
contexttrace viewer
```

The local viewer reads from `.contexttrace/contexttrace.db` and serves pages at:

```text
http://localhost:8765
```

## Integrations

- LangChain callback handler
- LlamaIndex callback handler
- FastAPI middleware and endpoint evaluation
- LangGraph beta tracer
- OpenTelemetry export

Install optional integrations:

```bash
pip install "contexttrace[langchain]"
pip install "contexttrace[llamaindex]"
pip install "contexttrace[fastapi]"
pip install "contexttrace[langgraph]"
pip install "contexttrace[otel]"
pip install "contexttrace[all]"
```

## Privacy

Local mode is the default. ContextTrace does not require a hosted dashboard and does not make network calls unless you configure an external judge provider or point it at an endpoint you control.

Privacy controls include:

- `local_only: true`
- `log_chunk_text: false`
- `log_answer_text: false`
- custom `storage_path`

## Limitations

- ContextTrace is diagnostic, not a guarantee of correctness.
- Current verification uses local lexical heuristics by default.
- Semantic mode uses local normalization, not embeddings or LLM reasoning.
- Contradiction detection is conservative.
- Claim extraction is rule-based.
- Human review is still required for high-stakes domains.

## Repository Layout

```text
packages/contexttrace   Python SDK, CLI, integrations, local SQLite store
apps/api                Optional FastAPI API mode
datasets/demo           Demo datasets
benchmarks              Benchmark helpers
docs                    Documentation and release assets
examples                SDK, endpoint, verify, compare, and audit examples
```

## Links

- GitHub: https://github.com/samarth1412/Context-Trace
- PyPI: https://pypi.org/project/contexttrace/
- Issues: https://github.com/samarth1412/Context-Trace/issues
- Changelog: [CHANGELOG.md](CHANGELOG.md)

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Security reports should follow [SECURITY.md](SECURITY.md).
