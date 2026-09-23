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

Build the direct, human-labeled ContractNLI development set without accessing
its test split:

```bash
PYTHONPATH=packages/contexttrace:. .venv/bin/python \
  -m benchmarks.requirement_alignment.build_development \
  --source-zip /private/tmp/contexttrace_external_data/contract-nli.zip \
  --dataset-output benchmarks/requirement_alignment/development.json \
  --audit-output benchmarks/requirement_alignment/development_audit.json \
  --manifest-output benchmarks/requirement_alignment/development_manifest.json \
  --cases-per-relation 80
```

Compare the frozen v1 and v2 artifacts at their committed thresholds:

```bash
PYTHONPATH=packages/contexttrace:. .venv/bin/python \
  -m benchmarks.requirement_alignment.analyze_development \
  --dataset benchmarks/requirement_alignment/development.json \
  --v1-model-path .tmp-contexttrace-models/contexttrace-requirement-alignment-v1 \
  --v1-manifest benchmarks/requirement_alignment/results/model_manifest.json \
  --v2-model-path .tmp-contexttrace-models/contexttrace-requirement-alignment-v2 \
  --v2-manifest benchmarks/requirement_alignment/results/model_v2_manifest.json \
  --output benchmarks/requirement_alignment/results/development_analysis.json \
  --batch-size 8
```

`DEVELOPMENT_SET.md` documents provenance and limitations.
`DEVELOPMENT_RESULTS.md` records the transfer failure and the frozen v3 design.

Build the mixed three-way v3 training artifact:

```bash
PYTHONPATH=packages/contexttrace:. .venv/bin/python \
  -m benchmarks.requirement_alignment.build_v3_training \
  --contract-source-zip /private/tmp/contexttrace_external_data/contract-nli.zip \
  --wice-dataset benchmarks/requirement_alignment/dataset.json \
  --dataset-output benchmarks/requirement_alignment/v3_training.json \
  --audit-output benchmarks/requirement_alignment/v3_training_audit.json \
  --manifest-output benchmarks/requirement_alignment/v3_training_manifest.json \
  --cases-per-relation 700
```

Run the fixed two-epoch, dual-gate v3 experiment:

```bash
PYTHONPATH=packages/contexttrace:. .venv/bin/python \
  -m benchmarks.requirement_alignment.train_v3 \
  --training-dataset benchmarks/requirement_alignment/v3_training.json \
  --contract-development benchmarks/requirement_alignment/development.json \
  --wice-dataset benchmarks/requirement_alignment/dataset.json \
  --base-model-path .tmp-contexttrace-models/cross-encoder--nli-deberta-v3-small--fa280487 \
  --output-dir .tmp-contexttrace-models/contexttrace-requirement-alignment-v3 \
  --report-output benchmarks/requirement_alignment/results/training_v3_report.json \
  --model-manifest-output benchmarks/requirement_alignment/results/model_v3_manifest.json \
  --epochs 2 \
  --batch-size 8 \
  --learning-rate 1e-5
```

Reproduce the post-hoc fine-threshold diagnostic:

```bash
PYTHONPATH=packages/contexttrace:. .venv/bin/python \
  -m benchmarks.requirement_alignment.diagnose_v3_threshold \
  --model-path .tmp-contexttrace-models/contexttrace-requirement-alignment-v3 \
  --model-manifest benchmarks/requirement_alignment/results/model_v3_manifest.json \
  --contract-development benchmarks/requirement_alignment/development.json \
  --wice-dataset benchmarks/requirement_alignment/dataset.json \
  --output benchmarks/requirement_alignment/results/v3_threshold_diagnostic.json
```

`TRAINING_V3_RESULTS.md` records the substantial improvement, failed promotion
gate, and decision to stop tuning the same small checkpoint.

Evaluate the three fixed hierarchical evidence policies without changing v3:

```bash
PYTHONPATH=packages/contexttrace:. .venv/bin/python \
  -m benchmarks.requirement_alignment.evaluate_v4_aggregation \
  --model-path .tmp-contexttrace-models/contexttrace-requirement-alignment-v3 \
  --model-manifest benchmarks/requirement_alignment/results/model_v3_manifest.json \
  --contract-development benchmarks/requirement_alignment/development.json \
  --wice-dataset benchmarks/requirement_alignment/dataset.json \
  --output benchmarks/requirement_alignment/results/v4_aggregation_report.json \
  --batch-size 8
```

`V4_AGGREGATION_RESULTS.md` records the negative aggregation result and decision
to move to one stronger local backbone.

Run the fixed v5 stronger-backbone experiment with the exact v3 data and gates:

```bash
PYTHONPATH=packages/contexttrace:. .venv/bin/python \
  -m benchmarks.requirement_alignment.train_v5 \
  --training-dataset benchmarks/requirement_alignment/v3_training.json \
  --contract-development benchmarks/requirement_alignment/development.json \
  --wice-dataset benchmarks/requirement_alignment/dataset.json \
  --base-model-path .tmp-contexttrace-models/moritzlaurer--deberta-v3-base-mnli-fever-anli--6f5cf0a2 \
  --output-dir .tmp-contexttrace-models/contexttrace-requirement-alignment-v5 \
  --report-output benchmarks/requirement_alignment/results/training_v5_report.json \
  --model-manifest-output benchmarks/requirement_alignment/results/model_v5_manifest.json \
  --epochs 2 \
  --batch-size 8 \
  --learning-rate 1e-5
```

The source model is locked to full Hugging Face revision
`6f5cf0a2b59cabb106aca4c287eed12e357e90eb`. The script verifies each local
source file before loading it and resolves relation IDs from the checkpoint's
semantic label mapping. It does not access ContractNLI test or change the
stable verifier.

Reproduce the post-hoc fine-threshold diagnostic:

```bash
PYTHONPATH=packages/contexttrace:. .venv/bin/python \
  -m benchmarks.requirement_alignment.diagnose_v5_threshold \
  --model-path .tmp-contexttrace-models/contexttrace-requirement-alignment-v5 \
  --model-manifest benchmarks/requirement_alignment/results/model_v5_manifest.json \
  --contract-development benchmarks/requirement_alignment/development.json \
  --wice-dataset benchmarks/requirement_alignment/dataset.json \
  --output benchmarks/requirement_alignment/results/v5_threshold_diagnostic.json \
  --batch-size 8
```

`TRAINING_V5_RESULTS.md` records the ranking improvement, failed joint gate,
fine-threshold diagnostic, and decision not to promote the larger model.

Build the two disjoint v6 cascade partitions from ContractNLI train pairs that
were not used to train v3 or v5:

```bash
PYTHONPATH=packages/contexttrace:. .venv/bin/python \
  -m benchmarks.requirement_alignment.build_v6_cascade_cases \
  --contract-source-zip /private/tmp/contexttrace_external_data/contract-nli.zip \
  --v3-training-dataset benchmarks/requirement_alignment/v3_training.json \
  --calibration-output benchmarks/requirement_alignment/v6_calibration.json \
  --evaluation-output benchmarks/requirement_alignment/v6_evaluation.json \
  --audit-output benchmarks/requirement_alignment/v6_cascade_audit.json \
  --manifest-output benchmarks/requirement_alignment/v6_cascade_manifest.json \
  --cases-per-relation-per-split 30
```

Score a partition locally with the hash-verified v3 and v5 artifacts:

```bash
PYTHONPATH=packages/contexttrace:. .venv/bin/python \
  -m benchmarks.requirement_alignment.score_v6_cascade \
  --dataset benchmarks/requirement_alignment/v6_calibration.json \
  --split cascade_calibration \
  --v3-model-path .tmp-contexttrace-models/contexttrace-requirement-alignment-v3 \
  --v3-manifest benchmarks/requirement_alignment/results/model_v3_manifest.json \
  --v5-model-path .tmp-contexttrace-models/contexttrace-requirement-alignment-v5 \
  --v5-manifest benchmarks/requirement_alignment/results/model_v5_manifest.json \
  --output benchmarks/requirement_alignment/results/v6_calibration_local_scores.json
```

The Jev phase is explicitly remote and remains blocked by `local_only`. For
calibration, call Jev once on all cases, then freeze the policy:

```bash
CONTEXTTRACE_LOCAL_ONLY=false PYTHONPATH=packages/contexttrace:. .venv/bin/python \
  -m benchmarks.requirement_alignment.v6_cascade run-jev \
  --dataset benchmarks/requirement_alignment/v6_calibration.json \
  --local-scores benchmarks/requirement_alignment/results/v6_calibration_local_scores.json \
  --split cascade_calibration \
  --output benchmarks/requirement_alignment/results/v6_calibration_jev.json \
  --all-cases --model jev-latest --allow-remote --env-file .env

PYTHONPATH=packages/contexttrace:. .venv/bin/python \
  -m benchmarks.requirement_alignment.v6_cascade calibrate \
  --dataset benchmarks/requirement_alignment/v6_calibration.json \
  --local-scores benchmarks/requirement_alignment/results/v6_calibration_local_scores.json \
  --jev-result benchmarks/requirement_alignment/results/v6_calibration_jev.json \
  --policy-output benchmarks/requirement_alignment/results/v6_cascade_policy.json \
  --analysis-output benchmarks/requirement_alignment/results/v6_cascade_calibration.json
```

Score `v6_evaluation.json` with `score_v6_cascade`, changing the split to
`cascade_evaluation`. Then run only the cases selected by the frozen policy and
evaluate:

```bash
CONTEXTTRACE_LOCAL_ONLY=false PYTHONPATH=packages/contexttrace:. .venv/bin/python \
  -m benchmarks.requirement_alignment.v6_cascade run-jev \
  --dataset benchmarks/requirement_alignment/v6_evaluation.json \
  --local-scores benchmarks/requirement_alignment/results/v6_evaluation_local_scores.json \
  --split cascade_evaluation \
  --output benchmarks/requirement_alignment/results/v6_evaluation_jev.json \
  --policy benchmarks/requirement_alignment/results/v6_cascade_policy.json \
  --model jev-latest --allow-remote --env-file .env

PYTHONPATH=packages/contexttrace:. .venv/bin/python \
  -m benchmarks.requirement_alignment.v6_cascade evaluate \
  --dataset benchmarks/requirement_alignment/v6_evaluation.json \
  --local-scores benchmarks/requirement_alignment/results/v6_evaluation_local_scores.json \
  --jev-result benchmarks/requirement_alignment/results/v6_evaluation_jev.json \
  --policy benchmarks/requirement_alignment/results/v6_cascade_policy.json \
  --output benchmarks/requirement_alignment/results/v6_cascade_evaluation.json
```

`V6_CASCADE_RESULTS.md` records the safe abstention result, optional Jev cost,
failed non-regression gate, and decision not to change stable behavior.

## V7: cross-domain SciFact transfer

V7 transfers the frozen V6 policy to the official SciFact scientific
claim-verification dataset without using SciFact for training, prompt selection,
threshold selection, or routing-policy selection. Download the official archive,
then freeze the development and evaluation packs before model scoring:

```bash
curl -L --fail --show-error \
  --output /private/tmp/contexttrace_external_data/scifact/data.tar.gz \
  https://scifact.s3-us-west-2.amazonaws.com/release/latest/data.tar.gz
tar -xzf /private/tmp/contexttrace_external_data/scifact/data.tar.gz \
  -C /private/tmp/contexttrace_external_data/scifact
PYTHONPATH=packages/contexttrace:. .venv/bin/python \
  -m benchmarks.requirement_alignment.build_v7_scifact \
  --source-dir /private/tmp/contexttrace_external_data/scifact/data \
  --source-archive /private/tmp/contexttrace_external_data/scifact/data.tar.gz \
  --development-output benchmarks/requirement_alignment/v7_scifact_development.json \
  --evaluation-output benchmarks/requirement_alignment/v7_scifact_evaluation.json \
  --audit-output benchmarks/requirement_alignment/v7_scifact_audit.json \
  --manifest-output benchmarks/requirement_alignment/v7_scifact_manifest.json
```

Score the frozen evaluation with the local artifacts, then run the optional Jev
route only with explicit remote opt-in:

```bash
PYTHONPATH=packages/contexttrace:. .venv/bin/python \
  -m benchmarks.requirement_alignment.v7_scifact score-local \
  --dataset benchmarks/requirement_alignment/v7_scifact_evaluation.json \
  --v3-model-path .tmp-contexttrace-models/contexttrace-requirement-alignment-v3 \
  --v3-manifest benchmarks/requirement_alignment/results/model_v3_manifest.json \
  --v5-model-path .tmp-contexttrace-models/contexttrace-requirement-alignment-v5 \
  --v5-manifest benchmarks/requirement_alignment/results/model_v5_manifest.json \
  --output benchmarks/requirement_alignment/results/v7_scifact_evaluation_local_scores.json

CONTEXTTRACE_LOCAL_ONLY=false PYTHONPATH=packages/contexttrace:. .venv/bin/python \
  -m benchmarks.requirement_alignment.v7_scifact run-jev \
  --dataset benchmarks/requirement_alignment/v7_scifact_evaluation.json \
  --local-scores benchmarks/requirement_alignment/results/v7_scifact_evaluation_local_scores.json \
  --policy benchmarks/requirement_alignment/results/v6_cascade_policy.json \
  --output benchmarks/requirement_alignment/results/v7_scifact_evaluation_jev.json \
  --model jev-latest --env-file .env --allow-remote

PYTHONPATH=packages/contexttrace:. .venv/bin/python \
  -m benchmarks.requirement_alignment.v7_scifact evaluate \
  --dataset benchmarks/requirement_alignment/v7_scifact_evaluation.json \
  --local-scores benchmarks/requirement_alignment/results/v7_scifact_evaluation_local_scores.json \
  --jev-result benchmarks/requirement_alignment/results/v7_scifact_evaluation_jev.json \
  --policy benchmarks/requirement_alignment/results/v6_cascade_policy.json \
  --output benchmarks/requirement_alignment/results/v7_scifact_evaluation.json
```

`V7_SCIFACT_RESULTS.md` records the positive cross-domain improvement, failed
promotion gate, privacy audit, and next research decision.
