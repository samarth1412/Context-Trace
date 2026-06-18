# ContextTrace-Diag-150

ContextTrace-Diag-150 is the 150-case public diagnostic benchmark track for
claim-level RAG failure attribution. It is implemented as the `public_holdout`
case set and remains outside the default `all` benchmark so public-holdout
regressions do not invalidate the main 500-case leaderboard.

## Current Milestone

- Status: 150 of 150 target cases assembled; freeze pending human audit sign-off.
- Case set: `public_holdout`.
- Inclusion policy: excluded from `--case-set all` so the default 500-case
  regression leaderboard remains stable.
- Source families: OpenTelemetry, Weaviate, LlamaIndex, Milvus, LangChain,
  Haystack, Qdrant, Pinecone, Chroma, RAGAS, DeepEval, LangSmith, Phoenix,
  TruLens, DSPy, LanceDB, Elasticsearch, Redis, pgvector, OpenSearch, MongoDB
  Vector Search, Azure AI Search, Vespa, OpenAI Evals, and Guardrails public
  docs.
- Label mix: supported claims, partial support, contradictions, missing-context
  abstention, and wrong-source citations.

## Latest 150-Case Results

| System | Cases | Failure Macro-F1 | Root Cause Accuracy | Citation Error F1 | Span Overlap |
| --- | ---: | ---: | ---: | ---: | ---: |
| ContextTrace semantic verifier | 150 | 1.000 | 1.000 | 1.000 | 0.950 |
| OpenAI diagnostic judge `gpt-4.1-mini` | 150 | 0.931 | 0.953 | 1.000 | 0.921 |

The OpenAI diagnostic judge row completed all 150 rows with zero row errors. It
reported root cause for 150/150 rows, citation status for 103/150 rows, and
evidence spans for 149/150 rows.

Human audit criteria are tracked in [AUDIT.md](AUDIT.md). Do not describe the
split as frozen until that checklist is complete.

Generate the reviewer packet and structural validator output with:

```bash
python benchmarks/contexttrace_bench/audit_diag150.py \
  --output-dir benchmarks/contexttrace_bench/out/public_holdout
```

The packet includes every case, source URL, expected label, root-cause label,
evidence span, benchmark prediction, and blank human sign-off fields. The
validator checks structural consistency, source URL presence, evidence-span
grounding, candidate-input label leakage, case counts, and artifact alignment.

## Publication Policy

Do not describe this as a broad state-of-the-art result until all are true:

- The full 150-case public diagnostic split receives human audit sign-off.
- External baseline rows are rerun on the frozen split.
- Confidence intervals or bootstrap intervals are reported.
- Missing diagnostic coverage is shown explicitly as `N/A` or coverage counts.
