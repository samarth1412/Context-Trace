# ContextTrace-Diag-150 Automated Audit Report

Date: 2026-06-23
Commit audited: `a2f44be`
Scope: `public_holdout` 150-case machine-checkable audit packet
Status: Passed automated validation; independent human sign-off still required.

## Generated Artifacts

| Artifact | Path |
| --- | --- |
| `baseline_results_json` | `benchmarks\contexttrace_bench\out\public_holdout\baseline_results.json` |
| `candidate_inputs_jsonl` | `benchmarks\contexttrace_bench\out\public_holdout\candidate_inputs.jsonl` |
| `error_analysis_json` | `benchmarks\contexttrace_bench\out\public_holdout\error_analysis.json` |
| `error_analysis_md` | `benchmarks\contexttrace_bench\out\public_holdout\error_analysis.md` |
| `json` | `benchmarks\contexttrace_bench\out\public_holdout\contexttrace_bench_results.json` |
| `leaderboard_md` | `benchmarks\contexttrace_bench\out\public_holdout\leaderboard.md` |
| `report_html` | `benchmarks\contexttrace_bench\out\public_holdout\report.html` |
| `results_md` | `benchmarks\contexttrace_bench\out\public_holdout\results.md` |

## Automated Checks

| Check | Severity | Result | Details |
| --- | --- | --- | --- |
| `case_set_public_holdout` | `error` | `passed` | `public_holdout` |
| `case_count` | `error` | `passed` | `{"actual": 150, "expected": 150}` |
| `unique_case_ids` | `error` | `passed` |  |
| `no_generated_cases` | `error` | `passed` | `0` |
| `required_label_coverage` | `error` | `passed` |  |
| `root_cause_taxonomy` | `error` | `passed` |  |
| `source_urls_present` | `error` | `passed` |  |
| `evidence_spans_grounded_in_context` | `error` | `passed` |  |
| `contexttrace_benchmark_passes` | `error` | `passed` |  |
| `result_case_ids_match_packet` | `error` | `passed` |  |
| `result_summary_case_count` | `error` | `passed` | `{"packet_cases": 150, "summary_cases": 150}` |
| `candidate_input_count` | `error` | `passed` | `{"candidate_inputs": 150, "packet_cases": 150}` |
| `candidate_input_ids_match_packet` | `error` | `passed` |  |
| `candidate_inputs_hide_labels` | `error` | `passed` |  |
| `human_review_blockers` | `error` | `passed` |  |
| `independent_human_signoff_complete` | `warning` | `failed` | `{"required": 150, "signed_off": 0}` |

## Label Distribution

| Label | Count |
| --- | ---: |
| `citation_mismatch` | 21 |
| `contradicted_answer` | 29 |
| `no_failure_detected` | 73 |
| `partial_support` | 26 |
| `should_have_abstained` | 30 |
| `unsupported_answer` | 1 |

## Source Family Balance

| Source Family | Contexts |
| --- | ---: |
| `docs.langchain.com` | 16 |
| `github.com` | 11 |
| `qdrant.tech` | 11 |
| `docs.pinecone.io` | 10 |
| `docs.haystack.deepset.ai` | 9 |
| `developers.llamaindex.ai` | 8 |
| `docs.trychroma.com` | 8 |
| `docs.weaviate.io` | 8 |
| `milvus.io` | 8 |
| `opentelemetry.io` | 8 |
| `arize.com` | 6 |
| `developers.openai.com` | 6 |
| `docs.lancedb.com` | 6 |
| `docs.opensearch.org` | 6 |
| `docs.vespa.ai` | 6 |
| `elastic.co` | 6 |
| `learn.microsoft.com` | 6 |
| `mongodb.com` | 6 |
| `redis.io` | 6 |
| `trulens.org` | 6 |
| `dspy.ai` | 5 |
| `deepeval.com` | 3 |
| `docs.ragas.io` | 3 |
| `guardrailsai.com` | 2 |

## Reproducibility Results

ContextTrace semantic verifier on `public_holdout`:

- Cases: `150`
- Failure macro-F1: `1.000`
- Claim-verdict macro-F1: `1.000`
- Root-cause accuracy: `1.000`
- Citation error F1: `1.000`
- Evidence span overlap: `0.950`

## Remaining Human Audit

The validator proves structural consistency, label leakage prevention, source URL presence, evidence-span grounding, and artifact alignment. It does not prove every label is the best human label or every source excerpt is semantically fair. Complete the case-level packet review before using frozen-split language.
