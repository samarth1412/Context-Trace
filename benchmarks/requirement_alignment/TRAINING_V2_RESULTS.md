# Requirement-alignment v2 training results

## Decision

Hard-positive margin training is the best v2 intervention, but the model remains
experimental. On the common 164-case human-labeled internal validation set, it
raises positive recall from **23.19% to 27.54%** while holding the false-positive
rate at **3.16%**. Macro F1 rises from **0.5652 to 0.5970**.

The predeclared promotion target was at least 50% positive recall with no more
than 5% false positives. The selected model does not meet it, so no new disjoint
confirmation pack should be consumed and no stable verifier default should
change.

## Fixed protocol

- The exact v1 artifact was verified against its committed file hashes before
  use.
- All variants started from v1 model ID
  `5eceacb75b2c16b2dad6a68a94a71113d7dd9c3545422ff0edd75252fe8b9bc1`.
- Training used only the 2,654 training examples. Selection used the same 164
  human-labeled internal validation cases for every variant.
- No existing development, held-out, or confirmation pack was used for fitting
  or selection.
- Each intervention ran for one epoch on CPU with batch size 8, learning rate
  `5e-6`, seed `20260927`, and only the final two encoder layers, pooler, and
  classifier trainable.
- Thresholds came from a fixed 0.05 grid. The rule maximized positive recall,
  then macro F1, subject to false-positive rate at or below 5%. Threshold 1.00
  represents full abstention when no lower threshold is safe.

## Common human validation results

| Model | Threshold | Positive recall | FPR | Macro F1 | ROC AUC | Average precision |
|---|---:|---:|---:|---:|---:|---:|
| v1 baseline | 0.90 | 0.2319 | 0.0316 | 0.5652 | 0.8130 | 0.7509 |
| Confidence-filtered | 1.00 | 0.0000 | 0.0000 | 0.3668 | 0.8174 | 0.7548 |
| Focal loss | 0.80 | 0.2174 | 0.0316 | 0.5542 | 0.8142 | 0.7511 |
| **Hard-positive margin** | **0.90** | **0.2754** | **0.0316** | **0.5970** | **0.8163** | **0.7522** |

The selected variant changes the common-set confusion counts from 16 true
positives, 3 false positives, and 53 false negatives to 19 true positives, 3
false positives, and 50 false negatives. This is a gain of three supported
cases with no added false support on this internal set.

## Intervention findings

The confidence-filtered variant removed 128 weak synthetic negatives whose v1
support probability was at least 0.70. Its ranking metrics improved slightly,
but its scores became too aggressive: every threshold below 1.00 exceeded the
false-positive cap. It therefore collapsed to full abstention under the safety
policy. Filtering these uncertain negatives is not suitable by itself.

Focal loss retained all training cases with gamma 2.0 and positive alpha 0.65.
It slightly reduced safe recall and macro F1 relative to v1, so this weighting
did not address the limiting error.

Hard-positive margin training duplicated the 156 positive training examples
that v1 scored below 0.50 and added a pairwise margin of 0.50 at weight 0.25.
Across all 464 internal validation examples, it increased positive recall from
0.1392 to 0.1646 and macro F1 from 0.5240 to 0.5449 at the same 0.0163 FPR.
On the weakly labeled requirement-alignment subset, positive recall moved only
from 0.0674 to 0.0787. Direct requirement coverage remains the main bottleneck.

## Artifact and next experiment

The selected local artifact is
`.tmp-contexttrace-models/contexttrace-requirement-alignment-v2`, with model ID
`0e8dfe9da3e40d91c1285dd41bf4e4bb3eb3ce84ed97117f423e4e49ef2484ff`.
The model files remain outside version control; their hashes and full run record
are committed in `results/model_v2_manifest.json` and
`results/training_v2_report.json`.

The next training experiment should target requirement-level positives rather
than adjust the global decision loss again. The evidence suggests the current
weak requirement labels and low requirement-positive recall are constraining
claim completeness. A small, independently reviewed requirement-alignment
development set should be created for error analysis before fixing a third
training recipe. This v2 result should remain a research checkpoint, not a
product provider.
