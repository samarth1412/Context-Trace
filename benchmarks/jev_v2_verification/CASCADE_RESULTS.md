# Local-first stable-plus-Jev cascade

## Frozen policy

The cascade policy was selected from the 39-case extension development result only. The calibration program evaluated a fixed grid and required candidate policies to match or exceed always-Jev development five-way accuracy and binary accuracy while keeping development false support at or below 5%.

The frozen policy is:

1. Run the stable semantic verifier locally.
2. If it predicts `supported` with confidence at least 0.90, retain that verdict without a remote call.
3. Otherwise call Jev on the same already-selected claim and evidence spans.
4. If Jev predicts `supported` with probability below 0.75, fall back to the stable verdict.
5. Require review for every final `supported` verdict and every Jev result with top probability below 0.80.

The exact policy and its content hash are stored in `results/cascade_policy.json`. The evaluator rejects a modified policy whose content no longer matches that hash.

## Results

| Split | System | Five-way accuracy | Observed-label macro F1 | Binary accuracy | Supported recall | False-support rate |
|---|---|---:|---:|---:|---:|---:|
| Development (39) | Always Jev | 0.6667 | 0.7205 | 0.8462 | 0.7692 | 0.1154 (3/26) |
| Development (39) | Frozen cascade | **0.6667** | **0.7241** | **0.8718** | 0.6923 | **0.0385 (1/26)** |
| Held-out replay (72) | Always Jev | 0.7500 | 0.7668 | 0.8889 | **0.8333** | 0.0833 (4/48) |
| Held-out replay (72) | Frozen cascade | **0.7639** | **0.7905** | **0.9167** | 0.7917 | **0.0208 (1/48)** |

On the held-out replay, the 0.75 Jev support gate removed three of four false-supported predictions. It also rejected one truly supported prediction. Two corrected cases received their exact projected five-way label from the stable fallback, producing a net gain of one five-way-correct case. Every remaining `supported` decision required review, so the automatically handled subset contained zero false-supported cases.

The five-way comparison has two cascade-only correct cases and one
always-Jev-only correct case (`p = 1.0`). The binary comparison has three
cascade-only correct cases and one always-Jev-only correct case (`p = 0.625`).
Both are exploratory exact McNemar tests. The measured improvement is therefore
encouraging but not statistically distinguishable on this sample.

## Operations

| Split | Jev calls | Call reduction | Tokens saved | Automatic coverage | Automatic accuracy | Automatic false support |
|---|---:|---:|---:|---:|---:|---:|
| Development | 36/39 | 7.69% | 4,031 | 30.77% | 75.00% | 0 |
| Held-out replay | 69/72 | 4.17% | 3,357 | 33.33% | 79.17% | 0 |

The cascade improves risk control, but it is not yet a strong cost-routing result. It avoids only three remote calls on each split because the stable verifier has too little high-precision supported coverage. A future router needs stronger local signals if substantial remote-call reduction is a goal.

## Interpretation limits

- The policy-selection code reads only the development result, and the frozen manifest records that held-out labels were not inputs to calibration.
- The held-out predictions and aggregate outcomes existed before this cascade study and had already been inspected. This is therefore a retrospective frozen-policy replay, not a new pristine confirmatory evaluation.
- Labels are deterministic sentence projections from RAGTruth answer-side annotations rather than independent ContextTrace claim labels.
- The extension contains supported, partially supported, and contradicted cases; it has no unsupported or unverifiable examples.
- Confidence intervals should account for clustering by source response in a future study.

The result supports the cascade as an experimental safety policy. It does not justify changing the local default or claiming production-calibrated performance. The next confirmatory study needs a newly frozen, independently labeled claim-evidence set that has never been used for prompt, threshold, or policy analysis.

## Reproduction

```bash
PYTHONPATH=packages/contexttrace:. .venv/bin/python -m \
  benchmarks.jev_v2_verification.cascade calibrate \
  --development-result benchmarks/jev_v2_verification/results/ragtruth_sentence_extension_development_jev.json \
  --policy-output benchmarks/jev_v2_verification/results/cascade_policy.json \
  --analysis-output benchmarks/jev_v2_verification/results/cascade_development.json

PYTHONPATH=packages/contexttrace:. .venv/bin/python -m \
  benchmarks.jev_v2_verification.cascade evaluate \
  --result benchmarks/jev_v2_verification/results/ragtruth_sentence_extension_heldout_jev.json \
  --policy benchmarks/jev_v2_verification/results/cascade_policy.json \
  --expected-split heldout \
  --output benchmarks/jev_v2_verification/results/cascade_heldout_evaluation.json
```
