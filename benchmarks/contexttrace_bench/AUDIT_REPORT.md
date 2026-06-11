# ContextTrace-Diag-150 Automated Audit Report

Date: 2026-06-11
Commit audited: `bff8d37` plus candidate-input leakage fix
Scope: `public_holdout` 150-case machine-assisted audit
Status: Automated checks passed; human sign-off still required before frozen-split language.

## Automated Checks

| Check | Result |
| --- | --- |
| Case count | 150 |
| Unique case IDs | 150 / 150 |
| Source contexts | 170 |
| Unique source URLs checked | 87 |
| Source URL failures | 0 |
| Candidate input rows | 150 |
| Candidate leakage keys | 0 |
| ContextTrace benchmark passes | 150 / 150 |
| ContextTrace benchmark misses | 0 |

Candidate input leakage check recursively searched exported
`candidate_inputs.jsonl` keys for expected/predicted labels, verdicts, root
causes, evidence spans, citation statuses, and notes. The export no longer
includes benchmark `note` fields.

## Label Distribution

| Label | Count |
| --- | ---: |
| `no_failure_detected` | 73 |
| `partial_support` | 26 |
| `contradicted_answer` | 29 |
| `should_have_abstained` | 30 |
| `citation_mismatch` | 21 |
| `unsupported_answer` | 1 |

Case label sets:

| Label Set | Count |
| --- | ---: |
| `no_failure_detected` | 73 |
| `partial_support` | 26 |
| `contradicted_answer` + `should_have_abstained` | 29 |
| `citation_mismatch` | 21 |
| `should_have_abstained` + `unsupported_answer` | 1 |

## Source Family Balance

Top source families by context count:

| Source Family | Contexts |
| --- | ---: |
| `docs.langchain.com` | 16 |
| `qdrant.tech` | 11 |
| `github.com` | 11 |
| `docs.pinecone.io` | 10 |
| `docs.haystack.deepset.ai` | 9 |
| `opentelemetry.io` | 8 |
| `docs.weaviate.io` | 8 |
| `developers.llamaindex.ai` | 8 |
| `milvus.io` | 8 |
| `docs.trychroma.com` | 8 |
| `arize.com` | 6 |
| `trulens.org` | 6 |

## Reproducibility Results

ContextTrace semantic verifier on `public_holdout`:

- Cases: `150`
- Failure macro-F1: `1.000`
- Claim-verdict macro-F1: `1.000`
- Root-cause accuracy: `1.000`
- Citation error F1: `1.000`
- Evidence span overlap: `0.950`

OpenAI diagnostic judge `gpt-4.1-mini`:

- Submitted and matched predictions: `150 / 150`
- Raw row errors: `0`
- Failure macro-F1: `0.931`
- Root-cause accuracy: `0.953`
- Citation error F1: `1.000`
- Evidence span overlap: `0.921`
- Diagnostic coverage: root cause `150/150`, citation status `103/150`,
  evidence spans `149/150`

## Remaining Human Audit

The automated audit does not verify that every context excerpt is semantically
fair, that every expected label is the best human label, or that every evidence
span is minimal. Complete the human checklist in [AUDIT.md](AUDIT.md) before
calling ContextTrace-Diag-150 frozen.
