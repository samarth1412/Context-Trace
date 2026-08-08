# External baseline development comparisons

This directory provides the fail-closed Stage 6 comparison layer. It uses
visible external development data and cached same-ID baseline outputs. It does
not use the sealed ContextTrace-Unseen labels and cannot establish an untouched
or state-of-the-art claim.

The lock includes locally available runs for RAGAS 0.4.2, RAGChecker 0.1.9,
MiniCheck, and RefChecker 0.2.17. MiniCheck and RefChecker are executed locally
with source revisions, model snapshots, dependencies, and inference settings
fixed by `competitor-runtime-lock.json`. An unavailable or unauditable system
receives no invented score.

## Reproduce the local competitor outputs

Install each runner's locked dependencies in a separate environment using
`requirements-minicheck.txt` or `requirements-refchecker.txt`. Clone the
official repositories at the exact revisions in `competitor-runtime-lock.json`,
and supply model and NLTK directories containing the exact files and hashes in
that lock. RefChecker can instead audit the exact official PyPI wheel and every
installed package file against that wheel when a Git checkout is unavailable.
Both runners verify the full runtime before inference and fail closed on changed
source, files, dependencies, inputs, output checkpoints, or resume state:

```bash
python -m benchmarks.external_baselines.run_minicheck \
  --candidate-inputs /path/to/candidate_inputs.jsonl \
  --dataset RAGTruth \
  --source-dir /path/to/MiniCheck \
  --model-dir /path/to/MiniCheck-Flan-T5-Large \
  --nltk-data-dir /path/to/nltk_data \
  --raw-output /path/to/minicheck_raw_results.json \
  --candidate-output /path/to/minicheck_predictions.json \
  --device mps --batch-size 8

python -m benchmarks.external_baselines.run_refchecker \
  --candidate-inputs /path/to/candidate_inputs.jsonl \
  --dataset RAGTruth \
  --source-dir /path/to/RefChecker \
  --package-wheel /path/to/refchecker-0.2.17-py3-none-any.whl \
  --nli-model-dir /path/to/refchecker-nli \
  --raw-output /path/to/refchecker_raw_results.json \
  --candidate-output /path/to/refchecker_predictions.json \
  --device mps --batch-size 4
```

The RefChecker run uses its official triplet extractor and NLI checker. Triplet
extraction is served by the lock-pinned local Gemma model through Ollama, so no
provider or paid API is called. Retrieved contexts are passed as separate
reference passages, divided with RefChecker's official 200-token
sentence-boundary segmenter, and merged with its claim-level passage rule; they
are not concatenated into one truncation-prone NLI input. This is a reproducible
local configuration, not a reproduction of RefChecker's strongest published
provider-backed setting.

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
`19fb7b1beb85d07ba656e89b49e5be3067882390d4fcd0f57626a78db3115cfc`.
All nine comparisons contain 200 unique same-ID cases and zero runtime failures.
ContextTrace is run once on each 200-case dataset and its exact predictions are
reused for the three same-ID competitor rows.

| Visible labeled development comparison | ContextTrace macro-F1 | Baseline macro-F1 | Difference | ContextTrace false green | Baseline false green |
| --- | ---: | ---: | ---: | ---: | ---: |
| RAGTruth / RAGAS | 0.561 | 0.152 | +0.409 | 0.000 | 0.300 |
| RAGTruth / MiniCheck | 0.561 | 0.248 | +0.313 | 0.000 | 0.035 |
| RAGTruth / RefChecker | 0.561 | 0.328 | +0.233 | 0.000 | 0.100 |
| ARES NQ / RAGAS | 0.995 | 0.471 | +0.524 | 0.000 | 0.030 |
| ARES NQ / MiniCheck | 0.995 | 0.897 | +0.098 | 0.000 | 0.010 |
| ARES NQ / RefChecker | 0.995 | 0.724 | +0.271 | 0.000 | 0.060 |

CRAG uses correct/gold answers and official-answer references, but those are not
labels that the retrieved contexts support each answer. Its macro-F1 fields in
the raw report are retained for schema compatibility and must not be interpreted
as accuracy.

| CRAG grounding proxy | Agreement with ContextTrace | ContextTrace flagged | Baseline flagged |
| --- | ---: | ---: | ---: |
| RAGChecker | 0.740 | 125 | 107 |
| MiniCheck | 0.825 | 125 | 122 |
| RefChecker | 0.575 | 125 | 60 |

## Engineering implications

Stage 6 establishes three development findings:

1. ARES previously had 17 unsafe false greens, all short answer fragments. Exact-
   offset query-conditioned fragment claims now reduce that count to zero while
   raising macro-F1 from 0.912 to 0.995.
2. RAGTruth now uses 560 physical NLI invocations for 1,506 claims (`0.372`),
   down from 961 (`0.638`). Complete, same-source material-fact claims may share
   one conservative NLI call; 272 groups cover 673 claims. A group-level result
   is accepted only as high-confidence entailment, while every other outcome is
   unresolved rather than force-attributed. Oversized source-bearing queries are
   omitted from the NLI premise instead of being prefix-truncated ahead of the
   evidence. The RAGTruth adapter projects the verifier's native claim verdicts
   transparently: any contradiction maps to `contradicted_answer`, all-supported
   maps to `no_failure_detected`, all-unsupported maps to `unsupported`, and
   every other mixture maps to `partial_support`. Each candidate row retains
   `native_claim_verdicts` for audit. This corrects the earlier lossy projection
   that mapped all `should_have_abstained` diagnoses to partial support.
   Macro-F1 is `0.561`, exact match is `0.480`, and the dangerous false-green
   rate remains zero.
3. The complete same-ID matrix places the strongest competitor at `0.328`
   macro-F1 on RAGTruth (RefChecker) and `0.897` on ARES (MiniCheck), versus
   ContextTrace at `0.561` and `0.995`, respectively. RefChecker's result uses
   the reproducible local configuration described above, not its strongest
   provider-backed configuration.

The RAGTruth lead is visible development evidence from a label-inspected corpus.
It does not establish external generalization or SOTA. That requires the sealed
Stage 7 evaluation and preregistered metrics. MiniCheck's published evaluation
also includes RAGTruth, so this track must not be described as untouched
competitor transfer.

Official implementations:

- <https://github.com/amazon-science/RefChecker>
- <https://github.com/Liyan06/MiniCheck>
- <https://github.com/amazon-science/RAGChecker>
- <https://github.com/vibrantlabsai/ragas>
