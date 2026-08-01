# External baseline development comparisons

This directory provides the fail-closed Stage 6 comparison layer. It uses
visible external development data and cached same-ID baseline outputs. It does
not use the sealed ContextTrace-Unseen labels and cannot establish an untouched
or state-of-the-art claim.

The lock includes locally available runs for RAGAS 0.4.2 and RAGChecker 0.1.9.
RefChecker 0.2.17 and MiniCheck are recorded as unavailable because no pinned,
same-ID local outputs exist. An unavailable system receives no invented score.

## Reproduce the artifact audit

Point `--artifact-root` at the existing `contexttrace_bench/out` cache:

```bash
.venv/bin/python -m benchmarks.external_baselines.run_comparison \
  --artifact-root /path/to/contexttrace_bench/out \
  --audit-only \
  --output /tmp/contexttrace-stage6-audit.json
```

The audit verifies every artifact SHA-256, unique and identical IDs, complete
coverage, zero baseline row errors, exact regeneration of normalized candidates
from raw results, and the strongest input binding supported by each raw format.
RAGChecker preserves and is checked against exact query, response, and retrieved
contexts. The older RAGAS output preserves IDs and retrieved-context counts but
not the input text, so it cannot provide the stronger content-level binding.

## Reproduce the local comparison

The model path must contain the hash-locked artifact expected by
`verify_nli_artifact`. The command does not download a model or call a provider:

```bash
.venv/bin/python -m benchmarks.external_baselines.run_comparison \
  --artifact-root /path/to/contexttrace_bench/out \
  --model-path /private/models/nli-deberta-v3-small \
  --output benchmarks/external_baselines/stage6-comparison-v1.json
```

## Current result

The checked-in report has SHA-256
`46794f22db04881278956b19b89c59c7de4b8ae6a58793cff44576db7bcc3438`.
All three comparisons contain 200 unique same-ID cases and zero runtime failures.

| Development comparison | ContextTrace macro-F1 | Baseline macro-F1 | Difference | Dangerous false green | NLI claim rate | Interpretation |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| RAGTruth / RAGAS | 0.106 | 0.152 | -0.046 | 0.000 | 0.639 | ContextTrace loses this visible comparison and routes too often. |
| ARES NQ / RAGAS | 0.912 | 0.471 | +0.441 | 0.085 | 0.006 | Large quality gain, but the safety gate fails. |
| CRAG / RAGChecker | N/A | N/A | N/A | N/A | 0.410 | Proxy agreement only: 0.710; this is not labeled accuracy. |

CRAG uses correct/gold answers and official-answer references, but those are not
labels that the retrieved contexts support each answer. Its macro-F1 fields in
the raw report are retained for schema compatibility and must not be interpreted
as accuracy. ContextTrace flags 119 cases, RAGChecker flags 107, and their binary
decisions agree on 142 of 200 cases.

## Engineering implications

Stage 6 exposes two immediate development targets:

1. ARES has 17 unsafe false greens. Every one is a short answer fragment such as
   a name, number, date, or single term. The verifier needs query-conditioned
   subject reconstruction for fragments without weakening the false-green guard.
2. RAGTruth invokes NLI on 961 of 1,505 claims and over-predicts partial support.
   The selective router needs better long-answer aggregation and a materially
   lower call rate before another external comparison.

RefChecker and MiniCheck remain required for a complete Stage 6 matrix. They
must be pinned by package/source revision and model artifact, then run over the
exact locked IDs. Adding them may require compute or provider authorization; it
must not silently reuse unmatched published scores.

Official implementations:

- <https://github.com/amazon-science/RefChecker>
- <https://github.com/Liyan06/MiniCheck>
- <https://github.com/amazon-science/RAGChecker>
- <https://github.com/vibrantlabsai/ragas>
