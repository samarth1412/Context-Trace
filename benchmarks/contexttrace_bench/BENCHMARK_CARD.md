# ContextTrace Benchmark Card

Last updated: 2026-06-30

## Scope

ContextTrace-Bench evaluates ContextTrace as a claim-level verifier and failure
diagnostic system. It does not evaluate retrieval or answer generation quality
and is not, by itself, evidence that a RAG stack is state of the art.

The evaluated outputs are failure labels, claim verdicts, root causes, citation
status, evidence spans, dangerous false greens, latency, and evaluator cost. See
[METHODOLOGY.md](METHODOLOGY.md) for definitions and scoring details.

## Current Evidence

| Track | Cases | Failure macro-F1 | Root-cause accuracy | Span overlap | Dangerous false green | Review status |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| ContextTrace-Bench | 500 | 1.000 | 1.000 | 0.862 | 0.000 | Regression benchmark |
| ContextTrace-Diag-150 | 150 | 1.000 | 1.000 | 0.950 | 0.000 | `review_pending` |
| RAGTruth test sample | 200 | 0.955 | 0.955 | 0.786 | 0.000 | `calibration_only`, assisted review |
| ARES NQ example | 200 | 0.995 | 0.995 | 1.000 | 0.000 | `review_pending` |
| CRAG Task 1 v5 | 200 | N/A | N/A | N/A | N/A | Grounding calibration, `review_pending` |

CRAG uses official gold answers as an unreviewed grounding proxy. Its reported
ContextTrace/RAGChecker comparison is evaluator agreement, not accuracy, so
failure metrics are intentionally not presented as benchmark quality.

## External Comparisons

- ContextTrace, RAGAS, and DeepEval have complete rows on the same 200 ARES IDs.
- ContextTrace and RAGChecker have complete rows on the same 200 CRAG IDs.
- ContextTrace and RAGAS have complete rows on the same 200 primary RAGTruth IDs.
  RAGAS `0.4.2` with `gpt-4.1-mini` scores failure macro-F1 `0.152`; unsupported
  root-cause, citation, and source-span diagnostics are `N/A`.
- A 50-case OpenAI judge smoke run remains calibration evidence only.
- Unsupported competitor diagnostics are serialized as `null` and rendered as
  `N/A`; they are not imputed from ContextTrace output.

See [BASELINES.md](BASELINES.md) for model versions, adapters, costs, and exact
commands.

## Data And Labels

- The 500-case default benchmark combines curated real-document cases with
  deterministic generated variants. Generated variants are regression pressure,
  not independent validation.
- ContextTrace-Diag-150 is a separate public-document holdout and is excluded
  from the default case set.
- RAGTruth preserves answer-side hallucination annotations and maps reviewed
  source evidence into the ContextTrace case-pack schema.
- ARES labels are projected into ContextTrace component labels and require
  independent review of mapping and source fairness.
- CRAG rows retain official archive provenance, selected-ID hashes, temporal
  metadata, and retrieved web pages.

Candidate input exports omit expected labels, root causes, verdicts, and evidence
spans. Release bundles record SHA256 checksums for frozen case packs, review
artifacts, scored results, reports, and candidate inputs.

## Uncertainty

Scored reports include deterministic 95% case-bootstrap confidence intervals.
Intervals describe uncertainty on the selected cases; they do not correct label
bias, assisted review, source truncation, dataset shift, or evaluator mapping
assumptions.

## Broad-SOTA Gate

Run the fail-closed project-level gate:

```bash
python benchmarks/contexttrace_bench/sota_gate.py
```

Use `--allow-not-ready` to refresh reports without a nonzero exit while review is
still pending. The current evidence passes 8 of 11 gates. The remaining blockers
are publishable external-review status, independent RAGTruth review, and
independent ContextTrace-Diag-150 sign-off.
See [SOTA_STATUS.md](SOTA_STATUS.md)
for the machine-generated result.

## Claim Policy

Allowed now:

> ContextTrace provides a benchmarked, local-first evidence-chain forensics layer
> for claim-level RAG and agent failure diagnosis.

Not allowed yet:

> ContextTrace is the state-of-the-art RAG evaluation framework.

Dataset licenses and upstream usage constraints still apply to external raw data.
Large raw archives and licensed corpus content are not redistributed in release
bundles unless their licenses permit it.
## Simulated Review Status

Three controlled LLM reviewer roles completed 1,410/1,410 annotation and RQ4
judgments with zero final parse failures. These outputs are protocol stress
tests, not independent human validation. They produced 214 unapplied label
suggestions; sensitivity analysis shows that substituting their majorities would
materially reduce measured performance. Human review and broad-SOTA gates remain
blocked. See `SIMULATED_REVIEW_STATUS.md` and `CORRECTION_POLICY.md`.
