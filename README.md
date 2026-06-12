# ContextTrace

[![Build](https://github.com/samarth1412/Context-Trace/actions/workflows/ci.yml/badge.svg)](https://github.com/samarth1412/Context-Trace/actions)
[![PyPI](https://img.shields.io/pypi/v/contexttrace.svg)](https://pypi.org/project/contexttrace/)
[![Python](https://img.shields.io/badge/python-3.8%2B-blue)](packages/contexttrace/pyproject.toml)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

**Local-first evidence-chain debugging for RAG and AI agents.**

ContextTrace shows where an answer stopped being grounded in the evidence you gave it:

```text
query -> retrieved context -> answer claims -> citations -> verdicts -> root cause
```

It is a Python SDK and CLI, not a hosted dashboard. Traces, reports, judge cache, and SQLite state stay local by default.

## Install

```bash
pip install contexttrace
contexttrace init
```

Install from source for unreleased changes:

```bash
git clone https://github.com/samarth1412/Context-Trace.git
cd Context-Trace
pip install -e packages/contexttrace
```

## Quickstart

```bash
contexttrace verify-demo unsupported_claim --report
contexttrace demo --dataset refund_policy
contexttrace report --last --open
```

Default local storage:

```text
.contexttrace/contexttrace.db
```

## Verify A RAG Trace

Create a portable trace with a query, answer, retrieved contexts, and optional citations:

```json
{
  "query": "How long does refund processing take?",
  "answer": "Refunds are processed within 5 business days.",
  "contexts": [
    {
      "id": "policy",
      "text": "Customers may request refunds within 30 days of purchase."
    }
  ]
}
```

Run local evidence checks:

```bash
contexttrace inspect trace.json
contexttrace verify trace.json --report
contexttrace qa trace.json --corpus docs/ --report
```

ContextTrace classifies each claim as `supported`, `partially_supported`, `unsupported`, `unverifiable`, or `contradicted`, then exposes separate statuses for support, truth, source freshness, citation quality, and likely fix.

Important: `supported` means grounded by the selected evidence span. It does not mean independently true, current, or authoritative.

## Local Verification Modes

| Mode | Use When |
| --- | --- |
| `lexical` | Fast default checks with no optional dependencies. |
| `semantic` | Local paraphrase and role-aware contradiction checks. |
| `local_ml` | Offline hash-embedding similarity, optionally backed by a local SentenceTransformers model. |
| `nli` | Local claim+span entailment or contradiction with a local Transformers or ONNX NLI model. |
| `judge` | Higher-accuracy local LLM judging through Ollama, LM Studio, vLLM, or a local OpenAI-compatible server. The judge sees selected evidence spans, not the full answer prose. |

Run the stronger local non-LLM verifier:

```bash
contexttrace verify trace.json --mode local_ml --report
contexttrace verify-benchmark --mode local_ml --case-set all
```

Optional neural local-ML support never downloads models automatically:

```bash
pip install "contexttrace[local-ml]"
set CONTEXTTRACE_LOCAL_ML_MODEL_PATH=C:/models/bge-small-en-v1.5
```

Run local NLI when you want mechanical claim-versus-span entailment:

```bash
pip install "contexttrace[nli]"
set CONTEXTTRACE_NLI_MODEL_PATH=C:/models/deberta-v3-nli
contexttrace verify trace.json --mode nli --report
contexttrace nli-calibrate --case-set all --report
```

Run a local judge with Ollama:

```bash
set CONTEXTTRACE_JUDGE_PROVIDER=ollama
set CONTEXTTRACE_JUDGE_MODEL=llama3.1

contexttrace verify trace.json --mode judge --report
contexttrace judge-calibrate --case-set all --report
```

Remote judges are blocked while `local_only: true` is active. To use a remote judge, explicitly disable local-only mode and configure the provider/API key.

## Diagnose And Regression-Test

```bash
# Find whether support existed elsewhere in the corpus.
contexttrace audit trace.json --corpus docs/ --report

# Compare a baseline and current answer after a prompt, model, or retriever change.
contexttrace compare baseline.json current.json --report

# Turn saved failures into replayable endpoint tests.
contexttrace suite create traces/failure.json --out contexttrace-suite.json
contexttrace suite run contexttrace-suite.json --endpoint http://localhost:8000/query --report
```

Common root causes include `retrieval_miss`, `reranking_failure`, `chunking_issue`, `corpus_gap`, `answer_overreach`, `stale_source`, `citation_mismatch`, and `should_have_abstained`.

`support_status`, `truth_status`, and `source_status` stay separate so a claim can be grounded by a source while the source itself remains stale, wrong, or unassessed.

Source metadata can include `source_authority`, `source_timestamp`, `source_version`, `canonical`, or `canonical_source`. ContextTrace uses those local fields to flag `grounded_but_stale`, `grounded_but_conflicted`, `grounded_by_low_authority_source`, or `supported_by_canonical_source`.

## ContextTrace-Bench

ContextTrace-Bench is the repo-level benchmark for claim-level failure attribution,
root-cause diagnosis, citation-error detection, and evidence-span localization.

```bash
python benchmarks/contexttrace_bench/run_contexttrace.py \
  --mode semantic \
  --case-set all \
  --enforce-sota-gates
```

It writes reproducible JSON, Markdown, leaderboard, and static HTML artifacts to
`benchmarks/contexttrace_bench/out/`. The default run targets 500 cases by adding
deterministic generated variants to the curated real-doc cases. Reports include
deterministic 95% case-bootstrap confidence intervals and per-label breakdowns
for the headline verifier metrics.

Run the separate public-doc holdout without generated variants:

```bash
python benchmarks/contexttrace_bench/run_contexttrace.py \
  --mode semantic \
  --case-set public_holdout \
  --no-generated-cases \
  --output-dir benchmarks/contexttrace_bench/out/public_holdout
```

Current 150-case holdout status is tracked in the baseline runbook. The holdout
is kept outside the default 500-case run so it can expose external validation
gaps without invalidating the main leaderboard rows.

`candidate_inputs.jsonl` gives external evaluators the exact trace payloads to
score. Candidate prediction JSON files can then be scored with `--candidate` to
compare ContextTrace against external evaluators or internal baselines on the
same labeled cases. Use `benchmarks/contexttrace_bench/adapt_candidate.py` to
normalize generic evaluator output into the candidate schema.

For external dataset scaffolding, `benchmarks/contexttrace_bench/ragtruth_adapter.py`
builds a ContextTrace-style case pack from RAGTruth `response.jsonl` and
`source_info.jsonl`. Treat that output as review input until answer-side
hallucination spans are manually mapped to source evidence spans.

Methodology and baseline runbooks live in
[`benchmarks/contexttrace_bench/METHODOLOGY.md`](benchmarks/contexttrace_bench/METHODOLOGY.md)
and [`benchmarks/contexttrace_bench/BASELINES.md`](benchmarks/contexttrace_bench/BASELINES.md).
The public holdout track is documented in
[`benchmarks/contexttrace_bench/DIAG150.md`](benchmarks/contexttrace_bench/DIAG150.md).
Human audit criteria for calling that split frozen are in
[`benchmarks/contexttrace_bench/AUDIT.md`](benchmarks/contexttrace_bench/AUDIT.md).
The Week 1 readiness checklist is in [`docs/sota-readiness.md`](docs/sota-readiness.md).
Treat the default 500-case run as verifier-readiness evidence; publish full
competitor rows and independent external dataset results before making broad
state-of-the-art claims.

## Capture Existing Systems

Capture one live endpoint response:

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

Or capture artifacts from Python:

```python
from contexttrace import capture_rag_trace, write_rag_trace

trace = capture_rag_trace(
    query=question,
    answer=answer,
    contexts=retrieved_docs,
    metadata={"system": "support-rag"},
)
write_rag_trace(trace, "trace.json")
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

## Integrations

```bash
pip install "contexttrace[langchain]"
pip install "contexttrace[llamaindex]"
pip install "contexttrace[fastapi]"
pip install "contexttrace[langgraph]"
pip install "contexttrace[otel]"
pip install "contexttrace[all]"
```

Includes LangChain, LlamaIndex, FastAPI, LangGraph, and OpenTelemetry hooks.

## Privacy

ContextTrace makes no network calls unless you point it at an endpoint or configure a judge provider. Local controls include:

- `local_only: true`
- `log_chunk_text: false`
- `log_answer_text: false`
- `storage_path`
- `judge_cache_enabled: true`
- `judge_cache_path: .contexttrace/judge_cache.json`

## Limits

ContextTrace is a diagnostic tool, not a correctness proof. It verifies grounding against provided evidence; it does not certify real-world truth. Claim extraction is rule-based, contradiction detection is conservative, and high-stakes outputs still need human review.

## Links

- PyPI: https://pypi.org/project/contexttrace/
- Docs: [docs](docs)
- Issues: https://github.com/samarth1412/Context-Trace/issues
- Changelog: [CHANGELOG.md](CHANGELOG.md)
