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

## V8: contradiction-aware guard

V8 calibrates a deterministic contradiction veto only on the frozen SciFact
development split. Jev is run on every development case so routing thresholds
can be compared against the same semantic judgments. The SciFact evaluation
split is excluded from selection.

```bash
PYTHONPATH=packages/contexttrace:. .venv/bin/python \
  -m benchmarks.requirement_alignment.v8_guard score-local \
  --dataset benchmarks/requirement_alignment/v7_scifact_development.json \
  --v3-model-path .tmp-contexttrace-models/contexttrace-requirement-alignment-v3 \
  --v3-manifest benchmarks/requirement_alignment/results/model_v3_manifest.json \
  --v5-model-path .tmp-contexttrace-models/contexttrace-requirement-alignment-v5 \
  --v5-manifest benchmarks/requirement_alignment/results/model_v5_manifest.json \
  --output benchmarks/requirement_alignment/results/v8_scifact_development_local_scores.json

CONTEXTTRACE_LOCAL_ONLY=false PYTHONPATH=packages/contexttrace:. .venv/bin/python \
  -m benchmarks.requirement_alignment.v8_guard run-jev \
  --dataset benchmarks/requirement_alignment/v7_scifact_development.json \
  --local-scores benchmarks/requirement_alignment/results/v8_scifact_development_local_scores.json \
  --output benchmarks/requirement_alignment/results/v8_scifact_development_jev.json \
  --model jev-latest --env-file .env --allow-remote

PYTHONPATH=packages/contexttrace:. .venv/bin/python \
  -m benchmarks.requirement_alignment.v8_guard calibrate \
  --dataset benchmarks/requirement_alignment/v7_scifact_development.json \
  --local-scores benchmarks/requirement_alignment/results/v8_scifact_development_local_scores.json \
  --jev-result benchmarks/requirement_alignment/results/v8_scifact_development_jev.json \
  --policy-output benchmarks/requirement_alignment/results/v8_scifact_guard_policy.json \
  --analysis-output benchmarks/requirement_alignment/results/v8_scifact_guard_calibration.json
```

`V8_GUARD_RESULTS.md` reports the development selection and the explicitly
post-hoc regression check on the consumed V7 evaluation. The guard passes its
quality gates but misses its remote-call target, so it is not promoted.

## V9: local meta-router candidate

Before touching the frozen holdout, V9 uses only SciFact development to add the
already pinned local NLI model and a document-grouped out-of-fold router. Score
the auxiliary group and sentence inputs entirely offline:

```bash
PYTHONPATH=packages/contexttrace:. .venv/bin/python \
  -m benchmarks.requirement_alignment.score_v9_auxiliary \
  --dataset benchmarks/requirement_alignment/v7_scifact_development.json \
  --v3-model-path .tmp-contexttrace-models/contexttrace-requirement-alignment-v3 \
  --v3-manifest benchmarks/requirement_alignment/results/model_v3_manifest.json \
  --v5-model-path .tmp-contexttrace-models/contexttrace-requirement-alignment-v5 \
  --v5-manifest benchmarks/requirement_alignment/results/model_v5_manifest.json \
  --pinned-nli-path .tmp-contexttrace-models/cross-encoder--nli-deberta-v3-small--fa280487 \
  --output benchmarks/requirement_alignment/results/v9_scifact_development_auxiliary_scores.json

PYTHONPATH=packages/contexttrace:. .venv/bin/python \
  -m benchmarks.requirement_alignment.v9_router \
  --dataset benchmarks/requirement_alignment/v7_scifact_development.json \
  --local-scores benchmarks/requirement_alignment/results/v8_scifact_development_local_scores.json \
  --auxiliary-scores benchmarks/requirement_alignment/results/v9_scifact_development_auxiliary_scores.json \
  --jev-result benchmarks/requirement_alignment/results/v8_scifact_development_jev.json \
  --v8-policy benchmarks/requirement_alignment/results/v8_scifact_guard_policy.json \
  --policy-output benchmarks/requirement_alignment/results/v9_scifact_router_policy.json \
  --analysis-output benchmarks/requirement_alignment/results/v9_scifact_router_calibration.json
```

`V9_ROUTER_RESULTS.md` records the positive development result and the decision
to freeze this candidate before Climate-FEVER scoring.

## V9: frozen Climate-FEVER holdout

V9 freezes 240 real-world Climate-FEVER cases before any model scoring: 60 each
for support, refutation, insufficient evidence, and disputed evidence. The
official source file is verified by SHA-256. Because its official page does not
state an explicit redistribution license, source text and the generated
evaluation pack stay outside Git.

```bash
curl -L --fail --show-error --create-dirs \
  --output /private/tmp/contexttrace_external_data/climate_fever/climate-fever-dataset-r1.jsonl \
  'https://www.sustainablefinance.uzh.ch/dam/jcr%3Adf02e448-baa1-4db8-921a-58507be4838e/climate-fever-dataset-r1.jsonl'

PYTHONPATH=packages/contexttrace:. .venv/bin/python \
  -m benchmarks.requirement_alignment.build_v9_climate_fever \
  --source /private/tmp/contexttrace_external_data/climate_fever/climate-fever-dataset-r1.jsonl \
  --evaluation-output /private/tmp/contexttrace_external_data/climate_fever/v9_climate_fever_evaluation.json \
  --selection-output benchmarks/requirement_alignment/v9_climate_fever_selection.json \
  --audit-output benchmarks/requirement_alignment/v9_climate_fever_audit.json \
  --manifest-output benchmarks/requirement_alignment/v9_climate_fever_manifest.json

PYTHONPATH=packages/contexttrace:. .venv/bin/python \
  -m benchmarks.requirement_alignment.v9_holdout score-local \
  --dataset /private/tmp/contexttrace_external_data/climate_fever/v9_climate_fever_evaluation.json \
  --v3-model-path .tmp-contexttrace-models/contexttrace-requirement-alignment-v3 \
  --v3-manifest benchmarks/requirement_alignment/results/model_v3_manifest.json \
  --v5-model-path .tmp-contexttrace-models/contexttrace-requirement-alignment-v5 \
  --v5-manifest benchmarks/requirement_alignment/results/model_v5_manifest.json \
  --pinned-nli-path .tmp-contexttrace-models/cross-encoder--nli-deberta-v3-small--fa280487 \
  --local-output /private/tmp/contexttrace_external_data/climate_fever/v9_local_scores.json \
  --auxiliary-output /private/tmp/contexttrace_external_data/climate_fever/v9_auxiliary_scores.json

PYTHONPATH=packages/contexttrace:. .venv/bin/python \
  -m benchmarks.requirement_alignment.v9_holdout route \
  --dataset /private/tmp/contexttrace_external_data/climate_fever/v9_climate_fever_evaluation.json \
  --local-scores /private/tmp/contexttrace_external_data/climate_fever/v9_local_scores.json \
  --auxiliary-scores /private/tmp/contexttrace_external_data/climate_fever/v9_auxiliary_scores.json \
  --v8-policy benchmarks/requirement_alignment/results/v8_scifact_guard_policy.json \
  --v9-policy benchmarks/requirement_alignment/results/v9_scifact_router_policy.json \
  --output /private/tmp/contexttrace_external_data/climate_fever/v9_routes.json

CONTEXTTRACE_LOCAL_ONLY=false PYTHONPATH=packages/contexttrace:. .venv/bin/python \
  -m benchmarks.requirement_alignment.v9_holdout run-jev \
  --dataset /private/tmp/contexttrace_external_data/climate_fever/v9_climate_fever_evaluation.json \
  --routes /private/tmp/contexttrace_external_data/climate_fever/v9_routes.json \
  --output /private/tmp/contexttrace_external_data/climate_fever/v9_jev.json \
  --model jev-latest --env-file .env --allow-remote

PYTHONPATH=packages/contexttrace:. .venv/bin/python \
  -m benchmarks.requirement_alignment.v9_holdout evaluate \
  --dataset /private/tmp/contexttrace_external_data/climate_fever/v9_climate_fever_evaluation.json \
  --routes /private/tmp/contexttrace_external_data/climate_fever/v9_routes.json \
  --jev-result /private/tmp/contexttrace_external_data/climate_fever/v9_jev.json \
  --output benchmarks/requirement_alignment/results/v9_climate_fever_holdout.json
```

`V9_HOLDOUT_PROTOCOL.md` defines the frozen label mapping, binary release gates,
disputed-evidence challenge, leakage controls, and redistribution boundary.
`V9_HOLDOUT_RESULTS.md` records the one-time negative confirmation result. The
candidate preserved false-support safety but failed support-recall and
disputed-review gates, so it is not eligible for release.

## V10: leakage-controlled climate development data

V10 excludes every consumed V9 claim and freezes balanced four-way training
and development partitions. Exact evidence-connected components cannot cross
the two partitions. Text-bearing files remain in external storage.

```bash
PYTHONPATH=packages/contexttrace:. .venv/bin/python \
  -m benchmarks.requirement_alignment.build_v10_climate_development \
  --source /private/tmp/contexttrace_external_data/climate_fever/climate-fever-dataset-r1.jsonl \
  --consumed-v9-selection benchmarks/requirement_alignment/v9_climate_fever_selection.json \
  --training-output /private/tmp/contexttrace_external_data/climate_fever/v10_climate_training.json \
  --development-output /private/tmp/contexttrace_external_data/climate_fever/v10_climate_development.json \
  --selection-output benchmarks/requirement_alignment/v10_climate_selection.json \
  --audit-output benchmarks/requirement_alignment/v10_climate_audit.json \
  --manifest-output benchmarks/requirement_alignment/v10_climate_manifest.json \
  --training-per-label 75 --development-per-label 15
```

`V10_DEVELOPMENT_SET.md` documents the split boundary, redistribution policy,
and intended four-way local-model experiment.

Score each generated V10 partition with the frozen local models, then run the
four-way feature screen:

```bash
PYTHONPATH=packages/contexttrace:. .venv/bin/python \
  -m benchmarks.requirement_alignment.score_v10_features \
  --dataset /private/tmp/contexttrace_external_data/climate_fever/v10_climate_training.json \
  --split climate_fever_v10_training \
  --v3-model-path .tmp-contexttrace-models/contexttrace-requirement-alignment-v3 \
  --v3-manifest benchmarks/requirement_alignment/results/model_v3_manifest.json \
  --v5-model-path .tmp-contexttrace-models/contexttrace-requirement-alignment-v5 \
  --v5-manifest benchmarks/requirement_alignment/results/model_v5_manifest.json \
  --pinned-nli-path .tmp-contexttrace-models/cross-encoder--nli-deberta-v3-small--fa280487 \
  --local-output /private/tmp/contexttrace_external_data/climate_fever/v10_training_local_scores.json \
  --auxiliary-output /private/tmp/contexttrace_external_data/climate_fever/v10_training_auxiliary_scores.json

PYTHONPATH=packages/contexttrace:. .venv/bin/python \
  -m benchmarks.requirement_alignment.score_v10_features \
  --dataset /private/tmp/contexttrace_external_data/climate_fever/v10_climate_development.json \
  --split climate_fever_v10_development \
  --v3-model-path .tmp-contexttrace-models/contexttrace-requirement-alignment-v3 \
  --v3-manifest benchmarks/requirement_alignment/results/model_v3_manifest.json \
  --v5-model-path .tmp-contexttrace-models/contexttrace-requirement-alignment-v5 \
  --v5-manifest benchmarks/requirement_alignment/results/model_v5_manifest.json \
  --pinned-nli-path .tmp-contexttrace-models/cross-encoder--nli-deberta-v3-small--fa280487 \
  --local-output /private/tmp/contexttrace_external_data/climate_fever/v10_development_local_scores.json \
  --auxiliary-output /private/tmp/contexttrace_external_data/climate_fever/v10_development_auxiliary_scores.json

PYTHONPATH=packages/contexttrace:. .venv/bin/python \
  -m benchmarks.requirement_alignment.v10_fourway \
  --training-dataset /private/tmp/contexttrace_external_data/climate_fever/v10_climate_training.json \
  --training-local-scores /private/tmp/contexttrace_external_data/climate_fever/v10_training_local_scores.json \
  --training-auxiliary-scores /private/tmp/contexttrace_external_data/climate_fever/v10_training_auxiliary_scores.json \
  --development-dataset /private/tmp/contexttrace_external_data/climate_fever/v10_climate_development.json \
  --development-local-scores /private/tmp/contexttrace_external_data/climate_fever/v10_development_local_scores.json \
  --development-auxiliary-scores /private/tmp/contexttrace_external_data/climate_fever/v10_development_auxiliary_scores.json \
  --output benchmarks/requirement_alignment/results/v10_fourway_feature_screen.json
```

`V10_VERIFIER_SCREEN.md` records the negative result and the bounded local
architecture checks. No candidate met every promotion gate, so stable defaults
remain unchanged and V10 is not eligible for release.

## V11: high-consensus evidence relations and explicit conflict

V11 expands evidence-level supervision while keeping the V10 development set
fixed. It selects only zero-entropy annotations outside every V9 claim and V10
development evidence component.

```bash
PYTHONPATH=packages/contexttrace:. .venv/bin/python \
  -m benchmarks.requirement_alignment.build_v11_span_training \
  --source /private/tmp/contexttrace_external_data/climate_fever/climate-fever-dataset-r1.jsonl \
  --consumed-v9-selection benchmarks/requirement_alignment/v9_climate_fever_selection.json \
  --v10-selection benchmarks/requirement_alignment/v10_climate_selection.json \
  --training-output /private/tmp/contexttrace_external_data/climate_fever/v11_span_training.json \
  --selection-output benchmarks/requirement_alignment/v11_span_selection.json \
  --audit-output benchmarks/requirement_alignment/v11_span_audit.json \
  --manifest-output benchmarks/requirement_alignment/v11_span_manifest.json

PYTHONPATH=packages/contexttrace:. HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
  .venv/bin/python -m benchmarks.requirement_alignment.train_v11_relation_conflict \
  --training-dataset /private/tmp/contexttrace_external_data/climate_fever/v11_span_training.json \
  --development-dataset /private/tmp/contexttrace_external_data/climate_fever/v10_climate_development.json \
  --base-model-path .tmp-contexttrace-models/cross-encoder--nli-deberta-v3-small--fa280487 \
  --output-dir /private/tmp/contexttrace_external_data/climate_fever/v11_relation_candidate \
  --report-output benchmarks/requirement_alignment/results/v11_relation_conflict_training.json \
  --manifest-output benchmarks/requirement_alignment/results/v11_relation_model_manifest.json \
  --epochs 3 --batch-size 16 --learning-rate 1e-5
```

`V11_RELATION_CONFLICT.md` records the positive development improvement and
the failed promotion decision. Four-way macro-F1 improved to 0.5960, but no
safety-compatible routing policy met the support-recall and disputed-review
gates. The model remains a research artifact outside the package.

## V12: disputed-evidence conflict ranking

V12 tests learned claim-level and pairwise conflict rankers over the selected
V11 relation model. The text-bearing training data and local score files remain
external.

```bash
PYTHONPATH=packages/contexttrace:. .venv/bin/python \
  -m benchmarks.requirement_alignment.build_v12_conflict_training \
  --source /private/tmp/contexttrace_external_data/climate_fever/climate-fever-dataset-r1.jsonl \
  --consumed-v9-selection benchmarks/requirement_alignment/v9_climate_fever_selection.json \
  --v10-selection benchmarks/requirement_alignment/v10_climate_selection.json \
  --training-output /private/tmp/contexttrace_external_data/climate_fever/v12_conflict_training.json \
  --selection-output benchmarks/requirement_alignment/v12_conflict_selection.json \
  --audit-output benchmarks/requirement_alignment/v12_conflict_audit.json \
  --manifest-output benchmarks/requirement_alignment/v12_conflict_manifest.json

PYTHONPATH=packages/contexttrace:. HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
  .venv/bin/python -m benchmarks.requirement_alignment.score_v12_relations \
  --dataset /private/tmp/contexttrace_external_data/climate_fever/v12_conflict_training.json \
  --split climate_fever_v12_conflict_training \
  --model-path /private/tmp/contexttrace_external_data/climate_fever/v11_relation_candidate \
  --model-manifest benchmarks/requirement_alignment/results/v11_relation_model_manifest.json \
  --output /private/tmp/contexttrace_external_data/climate_fever/v12_training_relation_scores.json

PYTHONPATH=packages/contexttrace:. HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
  .venv/bin/python -m benchmarks.requirement_alignment.score_v12_relations \
  --dataset /private/tmp/contexttrace_external_data/climate_fever/v10_climate_development.json \
  --split climate_fever_v10_development \
  --model-path /private/tmp/contexttrace_external_data/climate_fever/v11_relation_candidate \
  --model-manifest benchmarks/requirement_alignment/results/v11_relation_model_manifest.json \
  --output /private/tmp/contexttrace_external_data/climate_fever/v12_development_relation_scores.json

PYTHONPATH=packages/contexttrace:. .venv/bin/python \
  -m benchmarks.requirement_alignment.v12_conflict_ranker \
  --training-dataset /private/tmp/contexttrace_external_data/climate_fever/v12_conflict_training.json \
  --training-scores /private/tmp/contexttrace_external_data/climate_fever/v12_training_relation_scores.json \
  --development-dataset /private/tmp/contexttrace_external_data/climate_fever/v10_climate_development.json \
  --development-scores /private/tmp/contexttrace_external_data/climate_fever/v12_development_relation_scores.json \
  --output benchmarks/requirement_alignment/results/v12_conflict_ranker.json
```

`V12_CONFLICT_RANKER.md` records the negative result. The selected ranker
matched V11 disputed coverage rather than improving it, and the pairwise hard-
negative model performed worse. V12 is not eligible for release.

## V13: independent five-way transfer

V13 freezes balanced development and held-out resources from the existing
WiCE, VitaminC, and AmbiEnt case packs, then applies V11 and its thresholds
unchanged. The generated text-bearing datasets and raw relation scores remain
external.

```bash
PYTHONPATH=packages/contexttrace:. .venv/bin/python \
  -m benchmarks.requirement_alignment.build_v13_independent \
  --development-source benchmarks/external_fiveway_confirmation/development_cases.json \
  --heldout-source benchmarks/external_fiveway_confirmation/confirmation_cases.json \
  --development-output /private/tmp/contexttrace_external_data/v13_development.json \
  --heldout-output /private/tmp/contexttrace_external_data/v13_heldout.json \
  --audit-output benchmarks/requirement_alignment/v13_independent_audit.json \
  --manifest-output benchmarks/requirement_alignment/v13_independent_manifest.json

PYTHONPATH=packages/contexttrace:. HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
  .venv/bin/python -m benchmarks.requirement_alignment.score_v13_relations \
  --dataset /private/tmp/contexttrace_external_data/v13_development.json \
  --split external_fiveway_v13_development \
  --model-path /private/tmp/contexttrace_external_data/climate_fever/v11_relation_candidate \
  --model-manifest benchmarks/requirement_alignment/results/v11_relation_model_manifest.json \
  --output /private/tmp/contexttrace_external_data/v13_development_scores.json

PYTHONPATH=packages/contexttrace:. HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
  .venv/bin/python -m benchmarks.requirement_alignment.score_v13_relations \
  --dataset /private/tmp/contexttrace_external_data/v13_heldout.json \
  --split external_fiveway_v13_heldout \
  --model-path /private/tmp/contexttrace_external_data/climate_fever/v11_relation_candidate \
  --model-manifest benchmarks/requirement_alignment/results/v11_relation_model_manifest.json \
  --output /private/tmp/contexttrace_external_data/v13_heldout_scores.json

PYTHONPATH=packages/contexttrace:. .venv/bin/python \
  -m benchmarks.requirement_alignment.analyze_v13_independent \
  --development /private/tmp/contexttrace_external_data/v13_development.json \
  --development-scores /private/tmp/contexttrace_external_data/v13_development_scores.json \
  --heldout /private/tmp/contexttrace_external_data/v13_heldout.json \
  --heldout-scores /private/tmp/contexttrace_external_data/v13_heldout_scores.json \
  --v11-report benchmarks/requirement_alignment/results/v11_relation_conflict_training.json \
  --v13-manifest benchmarks/requirement_alignment/v13_independent_manifest.json \
  --output benchmarks/requirement_alignment/results/v13_independent_transfer.json
```

`V13_INDEPENDENT_TRANSFER.md` records the failed transfer. V11 incorrectly
accepted 45 of 100 held-out non-support cases, including 11 contradictions and
5 unsupported claims. The result consumes this held-out pack for V11 and keeps
the candidate outside ContextTrace 1.3.

## V14: development-only five-way policy

V14 derives local relation and lexical features from V13 development and
compares five-way classifiers using stratified out-of-fold predictions. It
does not load the consumed V13 held-out split.

```bash
PYTHONPATH=packages/contexttrace:. .venv/bin/python \
  -m benchmarks.requirement_alignment.v14_fiveway_policy \
  --development /private/tmp/contexttrace_external_data/v13_development.json \
  --scores /private/tmp/contexttrace_external_data/v13_development_scores.json \
  --output benchmarks/requirement_alignment/results/v14_fiveway_policy.json
```

`V14_FIVEWAY_POLICY.md` records the rejected development candidate. Out-of-fold
macro-F1 reached 0.6549, false supports fell to 2%, and contradiction recall
reached 92%, but support recall was only 20% and the 50% release gate failed.
No candidate is promoted or packaged.

## V15: atomic completeness fusion

V15 scores deterministic atomic requirements with the frozen V11 model, then
fuses those label-blind signals with V14 out-of-fold probabilities. Both steps
accept only V13 development artifacts.

```bash
PYTHONPATH=packages/contexttrace:. HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
  .venv/bin/python -m benchmarks.requirement_alignment.score_v15_atomic \
  --dataset /private/tmp/contexttrace_external_data/v13_development.json \
  --model-path /private/tmp/contexttrace_external_data/climate_fever/v11_relation_candidate \
  --model-manifest benchmarks/requirement_alignment/results/v11_relation_model_manifest.json \
  --output /private/tmp/contexttrace_external_data/v15_atomic_scores.json

PYTHONPATH=packages/contexttrace:. .venv/bin/python \
  -m benchmarks.requirement_alignment.v15_atomic_completeness \
  --development /private/tmp/contexttrace_external_data/v13_development.json \
  --relation-scores /private/tmp/contexttrace_external_data/v13_development_scores.json \
  --v14-report benchmarks/requirement_alignment/results/v14_fiveway_policy.json \
  --atomic-scores /private/tmp/contexttrace_external_data/v15_atomic_scores.json \
  --output benchmarks/requirement_alignment/results/v15_atomic_completeness.json
```

`V15_ATOMIC_COMPLETENESS.md` records a positive but ineligible result. Macro-F1
reached 0.7005, support recall doubled to 40%, false supports remained at 4%,
and four of five release gates passed. The remaining support-recall gate needs
three additional correct cases, so no model artifact is retained.

## V16: support-failure audit

V16 diagnoses the V15 support boundary using only the already-consumed V13
development artifacts. It audits all missed supports and false-support guard
cases, then enumerates the exact threshold frontier without loading held-out
data or training another model.

```bash
PYTHONPATH=packages/contexttrace:. .venv/bin/python \
  -m benchmarks.requirement_alignment.v16_support_failure_audit \
  --development /private/tmp/contexttrace_external_data/v13_development.json \
  --relation-scores /private/tmp/contexttrace_external_data/v13_development_scores.json \
  --atomic-scores /private/tmp/contexttrace_external_data/v15_atomic_scores.json \
  --v14-report benchmarks/requirement_alignment/results/v14_fiveway_policy.json \
  --v15-report benchmarks/requirement_alignment/results/v15_atomic_completeness.json \
  --output benchmarks/requirement_alignment/results/v16_support_failure_audit.json
```

`V16_SUPPORT_FAILURE_AUDIT.md` records the diagnostic result. No one-dimensional
threshold policy passes all gates: the safest frontier remains at 40% support
recall, while reaching 52% raises false supports to 9% and admits a
contradiction. The next experiment targets claim decomposition and evidence
combination while retaining the existing safety guards.

## V17: decomposition and multi-span completeness

Score the three deterministic decomposition candidates and all singleton,
pair, and triple combinations of up to four selected evidence spans. The raw
text-free score artifact remains in external local storage.

```bash
PYTHONPATH=packages/contexttrace:. HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
  .venv/bin/python -m benchmarks.requirement_alignment.score_v17_multispan \
  --dataset /private/tmp/contexttrace_external_data/v13_development.json \
  --model-path /private/tmp/contexttrace_external_data/climate_fever/v11_relation_candidate \
  --model-manifest benchmarks/requirement_alignment/results/v11_relation_model_manifest.json \
  --output /private/tmp/contexttrace_external_data/v17_multispan_scores.json

PYTHONPATH=packages/contexttrace:. .venv/bin/python \
  -m benchmarks.requirement_alignment.v17_multispan_completeness \
  --development /private/tmp/contexttrace_external_data/v13_development.json \
  --relation-scores /private/tmp/contexttrace_external_data/v13_development_scores.json \
  --v14-report benchmarks/requirement_alignment/results/v14_fiveway_policy.json \
  --v15-atomic-scores /private/tmp/contexttrace_external_data/v15_atomic_scores.json \
  --v15-report benchmarks/requirement_alignment/results/v15_atomic_completeness.json \
  --v17-scores /private/tmp/contexttrace_external_data/v17_multispan_scores.json \
  --output benchmarks/requirement_alignment/results/v17_multispan_completeness.json
```

`V17_MULTISPAN_COMPLETENESS.md` records the first five-gate development
candidate. The frozen targeted rescue reaches 52% support recall, retains a 4%
false-support rate with zero contradiction false supports, and reduces review
volume to 45.6%. It remains ineligible for packaging until it passes a newly
frozen untouched confirmation set.

## V18: frozen confirmation candidate

Fit the selected V14 and V15 estimator configurations on all consumed V13
development cases, then freeze them with the unchanged V17 rescue policy before
accessing new confirmation data.

```bash
PYTHONPATH=packages/contexttrace:. LOKY_MAX_CPU_COUNT=8 .venv/bin/python \
  -m benchmarks.requirement_alignment.freeze_v18_candidate \
  --development /private/tmp/contexttrace_external_data/v13_development.json \
  --relation-scores /private/tmp/contexttrace_external_data/v13_development_scores.json \
  --v14-report benchmarks/requirement_alignment/results/v14_fiveway_policy.json \
  --atomic-scores /private/tmp/contexttrace_external_data/v15_atomic_scores.json \
  --v15-report benchmarks/requirement_alignment/results/v15_atomic_completeness.json \
  --v17-report benchmarks/requirement_alignment/results/v17_multispan_completeness.json \
  --artifact-output /private/tmp/contexttrace_external_data/v18_frozen_candidate.joblib \
  --manifest-output benchmarks/requirement_alignment/results/v18_frozen_candidate_manifest.json
```

`V18_FROZEN_CANDIDATE.md` records the protocol boundary. The external artifact
rebuilds byte-for-byte with its committed SHA-256 manifest. Full-development
fit outputs are not evaluation evidence; the next valid result must come from
one untouched confirmation run with no retraining or policy changes.

## V19: independent five-way confirmation set

Build and freeze 25 cases per verdict from pinned AVeriTeC development data and
previously unselected WiCE partial-support cases. The builder excludes every
prior repository claim plus both external V13 partitions before label-only
stable selection.

```bash
PYTHONPATH=packages/contexttrace:. .venv/bin/python \
  -m benchmarks.requirement_alignment.build_v19_confirmation \
  --averitec /private/tmp/contexttrace_external_data/v19_sources/averitec_dev.json \
  --wice /private/tmp/contexttrace_external_data/v19_sources/wice_test.jsonl \
  --repository-root . \
  --exclude-dataset /private/tmp/contexttrace_external_data/v13_development.json \
  --exclude-dataset /private/tmp/contexttrace_external_data/v13_heldout.json \
  --dataset-output /private/tmp/contexttrace_external_data/v19_confirmation.json \
  --audit-output benchmarks/requirement_alignment/v19_confirmation_audit.json \
  --manifest-output benchmarks/requirement_alignment/v19_confirmation_manifest.json
```

`V19_CONFIRMATION_SET.md` documents source provenance, label alignment, and
limitations. The committed manifest is frozen before V18 scoring and forbids
retraining or selection after confirmation predictions are generated.
