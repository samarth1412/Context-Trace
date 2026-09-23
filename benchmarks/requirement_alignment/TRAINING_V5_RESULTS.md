# Stronger-backbone verifier v5 results

## Decision

The stronger DeBERTa-v3-base backbone improves ranking but does not satisfy the
predeclared joint promotion gate. V5 remains a research artifact. The stable
ContextTrace verifier, default behavior, and local-only policy remain unchanged.

At the selected fixed-grid threshold of 0.90, v5 reaches **40.00% entailment
recall**, **1.87% false-positive rate**, **0.7084 macro F1**, and **0.8880 ROC
AUC** on the 240-case ContractNLI development set. On the 164-case WiCE
internal set, it reaches **14.49% positive recall** at **3.16% false-positive
rate**. The gate requires at least 50% ContractNLI recall, no more than 5% FPR
on either set, and at least 22.54% WiCE recall.

## Fixed experiment

The run uses `MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli` at full revision
`6f5cf0a2b59cabb106aca4c287eed12e357e90eb`. Six downloaded model and tokenizer
files are byte-locked under source artifact hash
`4c94466fb55da3fc09e5cb48b4c7da3303008ac8903b9400f55d4eabd46f24f6`.
The MIT-licensed source checkpoint has 184,424,451 parameters and is loaded in
FP32 for CPU training.

V5 reuses the exact frozen v3 training artifact: 4,754 examples from
ContractNLI train and WiCE train-derived cases. Its two epochs, batch size 8,
learning rate `1e-5`, maximum length 256, class-balanced cross entropy, and
last-two-layer transfer scope match the predeclared design. The runner resolves
the checkpoint's semantic mapping rather than assuming class positions:
entailment 0, neutral 1, contradiction 2.

ContractNLI test was not accessed. No Jev or other API output supplied labels,
training data, thresholds, or predictions.

## Results by checkpoint

| Epoch | Threshold | Contract recall | Contract FPR | Contract AUC | WiCE recall | WiCE FPR | Gates met |
|---:|---:|---:|---:|---:|---:|---:|---|
| 0, native NLI | 0.85 | 0.0000 | 0.0125 | 0.4328 | 0.1739 | 0.0421 | No |
| 1 | 0.80 | 0.2000 | 0.0063 | 0.8327 | 0.2464 | 0.0421 | No |
| **2** | **0.90** | **0.4000** | **0.0187** | **0.8880** | **0.1449** | **0.0316** | **No** |

Epoch 2 is selected by the frozen policy, which first maximizes ContractNLI
recall among checkpoints satisfying both FPR caps. Compared with v3, v5 raises
ContractNLI ROC AUC from 0.8200 to 0.8880 and average precision from 0.7994 to
0.8442. Its thresholded Contract recall falls from 47.50% to 40.00%, however,
and WiCE recall falls from 23.19% to 14.49%.

## Error and threshold diagnostic

At threshold 0.90, v5 correctly abstains on all 80 contradictions and marks 32
of 80 entailments supported. Its three ContractNLI false supports are all
`NotMentioned` cases. This gives better relation ranking but a worse shared
safe operating point than v3.

A post-hoc scan from 0.800 through 0.950 in increments of 0.001 finds 15
thresholds that satisfy both FPR caps and the WiCE recall floor. The best is
0.873: ContractNLI recall is 43.75% at 1.87% FPR, and WiCE recall is 24.64% at
3.16% FPR. It still misses the 50% Contract target. The three Contract false
supports at that diagnostic threshold are recorded by identifier, probability,
and source evidence indexes in `results/v5_threshold_diagnostic.json`; no
explanation or matched fact was generated. Because the scan is post-hoc, it
cannot change the promotion result.

## Local cost

The selected artifact is 746,064,118 bytes, compared with 575,943,362 bytes for
v3. On this CPU run it processes about 15 examples per second: 16.052 seconds
for ContractNLI and 10.897 seconds for WiCE. The comparable v3 concatenated
measurements were 7.517 and 5.136 seconds, so v5 is about twice as slow while
failing the quality gate. These timings describe this machine and are not a
portable latency benchmark.

## Next research step

Another round of fine-tuning the same encoder family is not justified by these
results. The useful signal is v5's stronger ranking alongside its cross-domain
calibration failure. The next bounded experiment should predeclare and evaluate
a different local verification family or a training-only calibrated cascade,
with v3 retained as the product baseline. Jev may remain an optional external
research comparator or uncertainty route, but it must not provide ground truth
or weaken `local_only` behavior.

The selected local artifact is
`.tmp-contexttrace-models/contexttrace-requirement-alignment-v5`, model ID
`7e655679c82637cb2f125c72e7812ab0ca47240295af247538940488a6c0a38f`.
Its weights remain outside version control; committed manifests contain the
hashes needed to verify it.
