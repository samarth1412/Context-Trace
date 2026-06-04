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

## Claim-Level Evidence Verification

Verify a portable RAG trace artifact without a hosted dashboard:

```bash
contexttrace verify-demo unsupported_claim --report
contexttrace verify trace.json
contexttrace verify trace.json --json
contexttrace verify trace.json --report --out reports/example.html
contexttrace verify trace.json --mode semantic
contexttrace verify trace.json --fail-on unsupported --fail-on citation_mismatch
contexttrace verify-benchmark --mode semantic
contexttrace verify-benchmark --mode semantic --report
contexttrace verify-benchmark --case-set external --mode semantic --report
contexttrace compare baseline.json current.json
contexttrace compare baseline.json current.json --report
contexttrace compare baseline.json current.json --fail-on new_failure
contexttrace audit trace.json --corpus docs/
contexttrace audit trace.json --corpus docs/ --report
contexttrace audit trace.json --corpus docs/ --fail-on retrieval_miss
```

Input requires `query`, `answer`, and `contexts` with `id` and `text`. Optional `citations` are checked to catch cited sources that do not actually support the matched claim.

`verify-demo` uses bundled demo traces, so it works immediately after `pip install contexttrace`. Available demos include `unsupported_claim`, `partial_support`, `citation_mismatch`, `should_abstain`, and `supported_answer`.

Use `--mode semantic` for local paraphrase-aware matching, and `verify-benchmark` to inspect bundled precision/recall metrics. The default benchmark includes 32 real ContextTrace docs and release-artifact cases. `--case-set external` adds public OSS documentation and GitHub issue cases from Qdrant, Chroma, Haystack, and LangChain, while `--case-set all` runs both packs. `--report` writes an HTML report with misses to inspect.

Verification output includes evidence span offsets, stable span hashes, multiple supporting spans, typed matched/missing facts, and claim-level root causes so partial support failures are easier to inspect.

ContextTrace verifies whether each generated claim is actually supported by retrieved evidence. Instead of only showing a trace or a score, it tells you where the evidence chain broke: unsupported claim, citation mismatch, retrieval miss, answer overreach, conflicting context, or should-have-abstained.

Use `contexttrace compare baseline.json current.json` to diff two portable traces or saved `verify --json` outputs. It reports support-rate deltas, new unsupported claims, citation regressions, should-abstain flips, and new root causes, with `--fail-on` gates for CI.

Use `contexttrace audit trace.json --corpus docs/` to diagnose whether an unsupported claim failed because retrieval missed evidence, chunking omitted the supporting span, the corpus lacks coverage, or generation overclaimed.

The v0.5.0 verifier uses local lexical heuristics by default. Claim extraction is rule-based, contradiction detection is conservative, and semantic or LLM-judge support can be added later.

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
