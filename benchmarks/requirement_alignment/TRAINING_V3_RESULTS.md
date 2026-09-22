# Three-way requirement model v3 results

## Decision

Explicit entailment, contradiction, and neutral supervision substantially
improves direct requirement verification, but the selected v3 checkpoint misses
the predeclared promotion gate by two entailment cases. It remains experimental
and stable ContextTrace behavior must not change.

At threshold 0.90 on the 240-case ContractNLI development set, v3 reaches
**47.50% entailment recall**, **0.63% false-positive rate**, **0.7598 macro F1**,
and **0.8200 ROC AUC**. On the 164-case WiCE internal set, it retains **23.19%
positive recall** at **4.21% false-positive rate**. The fixed gates required at
least 50% ContractNLI recall, no more than 5% FPR on either set, and at least
22.54% WiCE recall.

## Fixed experiment

V3 starts from the pinned native three-way DeBERTa NLI checkpoint rather than
the binary v2 head. The training artifact contains 4,754 examples:

| Source | Examples | Supervision |
|---|---:|---|
| ContractNLI train | 2,100 | 700 each entailment, contradiction, and not mentioned |
| WiCE train-derived partition | 2,654 | positives to entailment; incomplete cases to neutral |

Training used class-balanced cross entropy for two epochs, batch size 8,
learning rate `1e-5`, seed `20260930`, maximum length 256, and the final two
encoder layers, pooler, and three-way classifier as trainable parameters. No
Jev or other API labels were used. ContractNLI development and test examples
were absent from training, and the test split remains untouched.

One threshold had to satisfy both development sets. Selection used a fixed 0.05
grid and the predeclared safety and recall gates.

## Results by checkpoint

| Epoch | Threshold | Contract recall | Contract FPR | Contract AUC | WiCE recall | WiCE FPR | Gates met |
|---:|---:|---:|---:|---:|---:|---:|---|
| 0, native NLI | 1.00 | 0.0000 | 0.0000 | 0.6342 | 0.0000 | 0.0000 | No |
| 1 | 0.80 | 0.1750 | 0.0063 | 0.7377 | 0.2464 | 0.0421 | No |
| **2** | **0.90** | **0.4750** | **0.0063** | **0.8200** | **0.2319** | **0.0421** | **No** |

Epoch 2 is the selected checkpoint. Compared with binary v2 on the same direct
development set, recall rises from 0% at its locked threshold, or 10% under its
development-only threshold diagnostic, to 47.5%. ROC AUC rises from 0.6102 to
0.8200.

## Relation separation

V3 fixes the earlier contradiction-separation failure. At the selected
checkpoint, mean entailment probabilities are:

| Human relation | Mean entailment probability | Predicted covered rate |
|---|---:|---:|
| Entailment | 0.6139 | 0.4750 |
| Contradiction | 0.0511 | 0.0000 |
| Not mentioned | 0.2468 | 0.0125 |

None of the 80 contradictions is marked covered. The sole ContractNLI false
support is `contractnli_dev_605_nda-11`, a not-mentioned case using deterministic
retrieval for the “No reverse engineering” hypothesis. This identifier,
probability, and evidence indexes come directly from the frozen analysis; no
explanation or matched fact was generated.

## Fine-threshold diagnostic

A post-hoc scan from 0.800 through 0.950 in increments of 0.001 found 14
thresholds that preserve both FPR caps and the WiCE recall floor. The best still
achieves only 47.5% ContractNLI recall at 0.900. Therefore the missed gate is not
an artifact of the original 0.05 threshold grid. This diagnostic cannot change
the promotion decision.

## Next research step

The explicit three-way objective is validated, while further tuning of this
small checkpoint should stop under the predeclared rule. The next experiment
should retain the same labels and gates but use a stronger local architecture,
preferably one that aggregates evidence spans before the final relation
decision. It should compare against this v3 checkpoint and may include Jev as a
separate external baseline on the exact same selected evidence. Jev should not
provide ground-truth or training labels.

The selected local artifact is
`.tmp-contexttrace-models/contexttrace-requirement-alignment-v3`, model ID
`98b6c1642c615b21d67527ca0b79ffa7a0385e003793c5db89de3d0d52846718`.
Its files remain outside version control; hashes are committed in
`results/model_v3_manifest.json`.
