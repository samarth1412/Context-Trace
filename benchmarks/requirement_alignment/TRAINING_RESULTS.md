# Local requirement-alignment training results

## Decision

The first local DeBERTa requirement-alignment model is a promising ranker but
does not meet the internal supported-recall gate. The artifact is frozen as a
development baseline. It must not be integrated into the stable verifier or
evaluated on a newly reserved confirmation pack yet.

The selected multi-task variant reached 0.8130 ROC AUC and 0.7509 average
precision on the common human-labeled internal-validation slice. Under the
prespecified 5% false-positive cap, its threshold of 0.90 produced 23.19%
positive recall, 96.84% negative recall, 3.16% false positives, and 56.52%
macro F1. The required positive recall is at least 50%.

## Fixed variants

All variants started from the same pinned local
`cross-encoder/nli-deberta-v3-small` artifact. Training updated only the last
two encoder layers, pooler, and binary classifier for two epochs on CPU.

| Variant | Training examples | Common ROC AUC | Average precision | Positive recall | False-positive rate | Macro F1 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Human claim-group labels | 929 | 0.7893 | 0.7448 | 20.29% | 1.05% | 55.19% |
| Group model with weak negatives | 1,622 | 0.8096 | 0.7501 | 15.94% | 0% | 52.06% |
| Multi-task group + requirement model | 2,654 | **0.8130** | **0.7509** | **23.19%** | 3.16% | **56.52%** |

Weak negatives improved ranking but did not by themselves improve the safe
operating point. Adding requirement examples recovered some positive recall
and produced the best common-slice ranking and macro F1, so the fixed selection
rule chose the multi-task model.

## Task diagnostics

On the selected model's broader internal-validation data, claim-group
completeness reached 0.8726 ROC AUC and 61.76% macro F1. Requirement alignment
reached 0.7128 ROC AUC but only 6.74% positive recall at the shared safe
threshold. This shows that the group-level signal is useful while individual
requirement probabilities remain poorly calibrated.

The three variants trained in 811 seconds total on CPU. Training and inference
were offline. No Jev request, development example, or held-out example was used.

## Frozen artifact

The selected local model ID is
`5eceacb75b2c16b2dad6a68a94a71113d7dd9c3545422ff0edd75252fe8b9bc1`.
The 576 MB runtime artifact remains under the ignored local model directory;
the repository records hashes and sizes for all four files in
`results/model_manifest.json`.

## Next experiment

The next training iteration should focus on the safe-recall frontier rather
than adding more threshold searches. The fixed ablations should test positive
hard-example mining, a margin or focal loss, and removal of weak negatives that
conflict with high-scoring human positives. Model and threshold selection must
remain inside the training/internal-validation protocol. A new disjoint
confirmation pack should be frozen only after internal positive recall reaches
50% under the 5% false-positive cap.
