# Evidence And Claim Readiness

ContextTrace keeps product releases separate from broad benchmark claims. A
stable SDK release may ship while external review is pending; the project must
not claim broad state-of-the-art performance until every evidence gate passes.

## Current Status

The machine-readable gate currently passes `8/10` checks. Product release is
allowed, but a broad SOTA claim is not.

Passed evidence includes:

- three external tracks with reproducible adapters and scored artifacts
- RAGTruth failure macro-F1 `0.955`
- RAGTruth root-cause accuracy `0.955`
- RAGTruth evidence-span overlap `0.786`
- dangerous false-green rate `0.000`
- deterministic confidence intervals and same-ID competitor coverage

Open evidence requirements:

1. Independent review of the 88-row primary RAGTruth review set.
2. Independent sign-off on all 150 ContextTrace-Diag-150 cases.

Until both are complete, use the positioning "benchmarked, local-first
evidence-chain forensics" and do not describe ContextTrace as broadly SOTA.

## Run The Gate

Benchmark outputs are generated artifacts and are not committed to the source
tree. Download the versioned evidence archive from the matching GitHub release,
extract it at the repository root, then run:

```bash
python benchmarks/contexttrace_bench/sota_gate.py --allow-not-ready
```

For v1.0.0, the archive is:

```text
https://github.com/samarth1412/Context-Trace/releases/download/v1.0.0/contexttrace-benchmark-evidence-v1.0.0.zip
```

The current checked-in snapshot is
[`SOTA_STATUS.md`](../benchmarks/contexttrace_bench/SOTA_STATUS.md). The gate
validates bundle checksums, external dataset count, review status, metric
thresholds, confidence intervals, competitor ID coverage, and Diag-150 sign-off.

## Claim Policy

- Product documentation may describe implemented and tested behavior.
- Dataset-specific metrics must identify the dataset, sample, and review state.
- Assisted or review-pending results are calibration evidence.
- Broad SOTA claims require a `claim_ready` gate result.
- Grounding means support from supplied evidence, not independent truth.
