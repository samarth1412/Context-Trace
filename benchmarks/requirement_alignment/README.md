# Requirement-alignment training data

This directory builds the next local complete-support training dataset from the
official WiCE **training split only**. It does not use development or held-out
examples for training construction.

The builder emits two related tasks:

- `requirement_alignment`: decide whether an evidence group covers one exact
  requirement substring from a claim;
- `claim_group_completeness`: decide whether one evidence group completely
  covers the full claim.

Positive examples inherit WiCE's complete-support annotation. Negative examples
include human-labeled partial support, deterministic removal of one annotated
sentence, and high-overlap same-document sentences outside all annotated
support groups. Every example records its construction and label strength so
weak synthetic supervision can be ablated.

Reproduce the frozen dataset:

```bash
PYTHONPATH=packages/contexttrace:. .venv/bin/python \
  -m benchmarks.requirement_alignment.build \
  --source /private/tmp/contexttrace_external_data/wice_train.jsonl \
  --exclude-case-pack benchmarks/external_fiveway_confirmation/development_cases.json \
  --exclude-case-pack benchmarks/external_fiveway_confirmation/completeness_development_cases.json \
  --exclude-case-pack benchmarks/external_fiveway_confirmation/completeness_development_extension_cases.json \
  --exclude-case-pack benchmarks/external_fiveway_confirmation/confirmation_cases.json \
  --exclude-case-pack benchmarks/external_fiveway_confirmation/confirmation_v2_cases.json \
  --exclude-case-pack benchmarks/jev_claim_verification/development_cases.json \
  --exclude-case-pack benchmarks/jev_claim_verification/heldout_cases.json \
  --exclude-case-pack benchmarks/jev_v2_verification/ragtruth_development.json \
  --exclude-case-pack benchmarks/jev_v2_verification/ragtruth_heldout.json \
  --exclude-case-pack benchmarks/jev_v2_verification/ragtruth_sentence_development.json \
  --exclude-case-pack benchmarks/jev_v2_verification/ragtruth_sentence_heldout.json \
  --exclude-case-pack benchmarks/jev_v2_verification/ragtruth_sentence_extension_development.json \
  --exclude-case-pack benchmarks/jev_v2_verification/ragtruth_sentence_extension_heldout.json \
  --exclude-case-pack benchmarks/local_verification_quality/development_cases.json \
  --exclude-case-pack benchmarks/local_verification_quality/heldout_cases.json \
  --dataset-output benchmarks/requirement_alignment/dataset.json \
  --audit-output benchmarks/requirement_alignment/audit.json \
  --manifest-output benchmarks/requirement_alignment/manifest.json
```

The dataset is a training artifact, not a reported model result. The existing
60-case extension has already informed research decisions and cannot serve as a
new untouched confirmation set. A new disjoint validation pack must be frozen
before promoting a trained model.

Train the three fixed local cross-encoder variants:

```bash
PYTHONPATH=packages/contexttrace:. .venv/bin/python \
  -m benchmarks.requirement_alignment.train \
  --dataset benchmarks/requirement_alignment/dataset.json \
  --base-model-path .tmp-contexttrace-models/cross-encoder--nli-deberta-v3-small--fa280487 \
  --output-dir .tmp-contexttrace-models/contexttrace-requirement-alignment-v1 \
  --report-output benchmarks/requirement_alignment/results/training_report.json \
  --model-manifest-output benchmarks/requirement_alignment/results/model_manifest.json \
  --epochs 2 \
  --batch-size 8 \
  --learning-rate 1e-5
```

`TRAINING_RESULTS.md` records the fixed-variant comparison and stopping
decision. The selected model remains experimental and is not packaged or wired
into the stable verifier.

Improve safe positive recall from the frozen, hash-verified v1 artifact with
three training-only interventions:

```bash
PYTHONPATH=packages/contexttrace:. .venv/bin/python \
  -m benchmarks.requirement_alignment.train_v2 \
  --dataset benchmarks/requirement_alignment/dataset.json \
  --source-model-path .tmp-contexttrace-models/contexttrace-requirement-alignment-v1 \
  --source-manifest benchmarks/requirement_alignment/results/model_manifest.json \
  --output-dir .tmp-contexttrace-models/contexttrace-requirement-alignment-v2 \
  --report-output benchmarks/requirement_alignment/results/training_v2_report.json \
  --model-manifest-output benchmarks/requirement_alignment/results/model_v2_manifest.json \
  --epochs 1 \
  --batch-size 8 \
  --learning-rate 5e-6
```

The v2 comparison uses confidence-filtered weak negatives, focal loss, and
hard-positive margin training. Variant and threshold selection maximize recall
under a five-percent false-positive-rate cap on the common human-labeled
internal validation set. No prior development or held-out evaluation pack is
used for training or selection. `TRAINING_V2_RESULTS.md` records the positive
but below-target outcome and the decision to keep v2 experimental.
