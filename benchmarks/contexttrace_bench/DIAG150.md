# ContextTrace-Diag-150

ContextTrace-Diag-150 is the planned frozen public diagnostic benchmark for
claim-level RAG failure attribution. It is tracked through the `public_holdout`
case set until the full 150-case target is complete.

## Current Milestone

- Status: 75 of 150 target cases.
- Case set: `public_holdout`.
- Inclusion policy: excluded from `--case-set all` so the default 500-case
  regression leaderboard remains stable.
- Source families: OpenTelemetry, Weaviate, LlamaIndex, Milvus, LangChain,
  Haystack, Qdrant, Pinecone, Chroma, RAGAS, and DeepEval public docs.
- Label mix: supported claims, partial support, contradictions, missing-context
  abstention, and wrong-source citations.

## Latest 75-Case Results

| System | Cases | Failure Macro-F1 | Root Cause Accuracy | Citation Error F1 | Span Overlap |
| --- | ---: | ---: | ---: | ---: | ---: |
| ContextTrace semantic verifier | 75 | 1.000 | 1.000 | 1.000 | 0.944 |
| OpenAI diagnostic judge `gpt-4.1-mini` | 75 | 0.869 | 0.973 | 1.000 | 0.905 |

The OpenAI diagnostic judge row completed all 75 rows with zero row errors. It
reported root cause for 75/75 rows, citation status for 51/75 rows, and evidence
spans for 74/75 rows.

## Publication Policy

Do not describe this as a broad state-of-the-art result until all are true:

- The full 150-case public diagnostic split is frozen.
- Case labels receive a human audit pass.
- External baseline rows are rerun on the frozen split.
- Confidence intervals or bootstrap intervals are reported.
- Missing diagnostic coverage is shown explicitly as `N/A` or coverage counts.

