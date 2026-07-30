# ContextTrace-Unseen-v1 Baseline Protocol

Status: frozen input and adapter protocol; no gold labels accessed.

## Boundary

Every baseline receives the same immutable candidate view: case ID, query, generated
answer, ordered retrieved chunks, and ordered selected contexts. The view is derived
from the manifest whose payload SHA-256 is
`8bf65cd7e2c95ccfcc12e78b580fc47e4157b0f808ba3fcace0a24bfcdc2e5f6`.
The adapter verifies the frozen trace file hash, case ID, chunk IDs, ordering, and
selection before execution. Label, disagreement, adjudication, and gold files are
not accepted inputs.

## Reporting rules

1. Preserve case IDs and candidate-input hashes in every raw output.
2. Preserve raw tool output and record failures without repair or reruns that alter
   prompts or inputs.
3. Report wall latency, model-call count, and cost per case.
4. Keep deterministic local, local-model, and remote-judge results separate.
5. A score is not a failure label. A failure label is not a root cause.
6. Unsupported fields are `not available`; they are never encoded as zero.
7. Thresholds may be selected only on the declared development corpus and must be
   frozen before sealed scoring.
8. Remote methods require a separately frozen model/API revision, prompt, decoding
   configuration, and cost authorization. They are unavailable until then.
9. RAGChecker reference-answer metrics may run only inside the sealed scoring zone
   after a reference-answer construction policy is preregistered.
10. No baseline output may be manually edited or improved.

## Confirmatory roles

`semantic_v1_calibrated` is the required predecessor comparator and must remain
unchanged. `lexical_evidence_overlap_v1` is a deterministic sanity baseline.
`minilm_cosine_support_v1` is a pinned local embedding sanity baseline. Neither
sanity baseline produces failure labels or observable root causes, so primary
failure-label and root-cause metrics are not available for them.

RAGAS and DeepEval have identity-safe reference-free input adapters, but model-backed
execution is not authorized by this lock. RAGChecker is conditional on a sealed-zone
reference answer. RAGXplain has no reproducible implementation artifact frozen here.
TRAIL is an agent-trace method and remains the separately scoped secondary transfer
experiment.

## Output retention

Permitted outputs must be written below a run-specific private directory, using
append-only run receipts and immutable raw-output files. The scoring zone, not the
implementation repository, joins baseline outputs to sealed gold labels.
