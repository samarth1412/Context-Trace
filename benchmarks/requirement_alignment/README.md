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
