# Direct requirement development results

## Finding

The v2 gain on WiCE-derived internal validation does not transfer to the new
ContractNLI direct-requirement development set. At their locked 0.90 thresholds,
both v1 and v2 classify all 240 cases as `missing`. They produce no false
support, but recall none of the 80 entailments.

| Frozen model | Positive recall | FPR | Macro F1 | ROC AUC | Average precision | Brier score |
|---|---:|---:|---:|---:|---:|---:|
| v1 | 0.0000 | 0.0000 | 0.4000 | 0.6541 | 0.5141 | 0.3396 |
| v2 hard-positive margin | 0.0000 | 0.0000 | 0.4000 | 0.6102 | 0.4759 | 0.3654 |

V2 lowers ROC AUC by 0.0439 and average precision by 0.0382. This means its
small in-domain recall gain came with weaker cross-domain ranking and worse
probability quality. V2 remains an experimental checkpoint and should not be
integrated into the product.

## Relation separation

At the locked v2 threshold, mean covered probabilities are:

| Upstream relation | Target | Mean covered probability |
|---|---|---:|
| Entailment | covered | 0.7255 |
| Contradiction | missing | 0.7094 |
| Not mentioned | missing | 0.6839 |

The 0.0161 mean gap between entailment and contradiction is the main safety
problem. The model often recognizes topical alignment but does not reliably
distinguish permission, prohibition, and other polarity changes.

Because this is development data, a threshold-only diagnostic was also run on
the fixed 0.05 grid under the same 5% false-positive cap. V2 selects 0.85 and
reaches only 10% positive recall with 1.25% FPR and 0.4940 macro F1. It recovers
eight entailments but incorrectly marks two annotated contradictions as
covered:

- `contractnli_dev_595_nda-20`, permissible post-agreement possession;
- `contractnli_dev_7_nda-17`, permissible copying.

These are IDs and upstream hypothesis descriptions, not generated error
explanations. Exact probabilities and annotated evidence-span indexes are in
`results/development_analysis.json`.

## V3 decision

V3 should add direct relation supervision rather than apply another binary loss
or threshold adjustment. The fixed experiment should:

1. Build training examples from the ContractNLI **training split only**, using
   annotated spans for entailment and contradiction and the same deterministic
   selector for not-mentioned cases.
2. Retain the upstream three-way relation during training so contradiction is
   not collapsed into ordinary absence. Convert to `covered` versus `missing`
   only at the ContextTrace interface.
3. Mix direct-relation batches with the existing WiCE training examples to
   limit legal-domain overfitting.
4. Select on two development gates: this 240-case direct-requirement set and
   the existing 164-case human WiCE group set.
5. Require at least 50% entailment recall and no more than 5% combined false
   support here, while allowing no more than a five-point absolute recall
   regression on the WiCE internal set.
6. Keep the ContractNLI test split untouched until the model, thresholds, and
   decision mapping are frozen.

Jev should not create training or evaluation labels for v3. It can later serve
as a separately reported disagreement baseline on the same selected evidence.
This keeps ContextTrace local-first and avoids treating an external provider as
ground truth.
