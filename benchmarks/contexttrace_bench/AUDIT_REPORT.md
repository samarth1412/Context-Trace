# ContextTrace-Diag-150 Automated Audit Report

Date: 2026-06-11
Commit audited: `512e138` plus source-review pass
Scope: `public_holdout` 150-case machine-assisted audit and assisted source review
Status: Automated checks and assisted source review passed; independent human
sign-off still required before frozen-split language.

## Machine-Checkable Packet

ContextTrace-Diag-150 now has a reproducible audit packet generator:

```bash
python benchmarks/contexttrace_bench/audit_diag150.py \
  --output-dir benchmarks/contexttrace_bench/out/public_holdout
```

It writes `diag150_audit_packet.json`, `diag150_audit_packet.md`,
`diag150_human_review_template.json`, `diag150_audit_validation.json`, and an
artifact-local `AUDIT_REPORT.md`.
The validator checks case count, unique case IDs, generated-case exclusion,
required label coverage, root-cause taxonomy, source URL presence,
evidence-span grounding in context text, benchmark pass status, candidate-input
ID alignment, candidate-input label leakage, review blockers, and independent
sign-off completeness. By default, incomplete human sign-off is a warning; use
`--review-file ... --require-human-signoff` to make it a hard frozen-split gate.

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

## Source Excerpt Review

The source-review pass fetched public documentation pages and compared each
context excerpt against the fetched page text with normalized exact matching,
token containment, and shingle matching.

| Check | Result |
| --- | ---: |
| Context excerpts reviewed | 170 |
| Exact normalized page matches | 54 |
| Fuzzy acceptable matches | 84 |
| Assisted-review contexts | 32 |
| Source-review blockers | 0 |

The 32 assisted-review contexts were either tight paraphrases of current public
documentation, snippets whose page text is heavily transformed by the docs
renderer, or Milvus pages that block direct scraper content fetches with a
redirect challenge. The Milvus pages remain official public documentation URLs
and were discoverable through public search results during this review.

No source, label, or evidence-span changes were made from this pass. This is
still not an independent human review of source fairness.

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
