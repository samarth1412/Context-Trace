# External five-way confirmation

This benchmark is a frozen, balanced set of 125 public test cases with 25 cases
for each ContextTrace verdict. Its purpose is to test the existing stable
verifier, Jev, and the already frozen local-first cascade on labels that were
created independently of ContextTrace.

The mapping is deliberately narrow:

| Public label | ContextTrace verdict | Why it is compatible |
| --- | --- | --- |
| WiCE `supported` | `supported` | The cited evidence supports the complete natural claim. |
| WiCE `partially_supported` | `partially_supported` | The evidence supports only part of the natural claim. |
| WiCE `not_supported` | `unsupported` | The cited, topically related source does not support the claim. |
| VitaminC real-revision `REFUTES` | `contradicted` | The supplied revision evidence conflicts with the claim. |
| AmbiEnt pair with two or more plausible NLI labels | `unverifiable` | Linguists validated multiple readings with different entailment relations. |

VitaminC synthetic revisions and ordinary single-label NLI `neutral` cases are
excluded. The former are unnecessary for the natural contradiction slice; the
latter do not establish the related ambiguity required by ContextTrace's
`unverifiable` policy.

## Reproduce the freeze

Acquire the exact upstream files into a temporary directory:

```bash
PYTHONPATH=packages/contexttrace:. .venv/bin/python -m \
  benchmarks.external_fiveway_confirmation.acquire \
  --output-dir /tmp/contexttrace_external_data
```

Rebuild the case pack:

```bash
PYTHONPATH=packages/contexttrace:. .venv/bin/python -m \
  benchmarks.external_fiveway_confirmation.adapter \
  --wice /tmp/contexttrace_external_data/wice_test.jsonl \
  --vitaminc /tmp/contexttrace_external_data/vitaminc.zip \
  --ambient /tmp/contexttrace_external_data/ambient_test.jsonl \
  --output /tmp/confirmation_cases.json
```

The rebuilt file must have the SHA-256 recorded in `freeze_manifest.json`.
Verify the repository freeze and its code dependencies with:

```bash
PYTHONPATH=packages/contexttrace:. .venv/bin/python -m \
  benchmarks.external_fiveway_confirmation.freeze verify \
  --manifest benchmarks/external_fiveway_confirmation/freeze_manifest.json
```

Run the leakage and retrieval audit:

```bash
PYTHONPATH=packages/contexttrace:. .venv/bin/python -m \
  benchmarks.external_fiveway_confirmation.audit \
  --cases benchmarks/external_fiveway_confirmation/confirmation_cases.json \
  --prior-case-pack benchmarks/jev_claim_verification/development_cases.json \
  --prior-case-pack benchmarks/jev_claim_verification/heldout_cases.json \
  --prior-case-pack benchmarks/jev_v2_verification/ragtruth_sentence_extension_development.json \
  --prior-case-pack benchmarks/jev_v2_verification/ragtruth_sentence_extension_heldout.json
```

## Run the experiment

The existing shared-input runner applies the same label-blind local evidence
selector to every system. Evaluation labels, upstream labels, evidence
annotations, and dataset metadata are excluded from model inputs.

Local run:

```bash
PYTHONPATH=packages/contexttrace:. \
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 TOKENIZERS_PARALLELISM=false \
.venv/bin/python -m benchmarks.jev_v2_verification.run \
  --cases benchmarks/external_fiveway_confirmation/confirmation_cases.json \
  --split heldout \
  --model-path .tmp-contexttrace-models/cross-encoder--nli-deberta-v3-small--fa280487 \
  --output benchmarks/external_fiveway_confirmation/results/local.json
```

Explicit Jev run using the ignored `.env` file:

```bash
CONTEXTTRACE_LOCAL_ONLY=false \
PYTHONPATH=packages/contexttrace:. \
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 TOKENIZERS_PARALLELISM=false \
.venv/bin/python -m benchmarks.jev_v2_verification.run \
  --cases benchmarks/external_fiveway_confirmation/confirmation_cases.json \
  --split heldout \
  --model-path .tmp-contexttrace-models/cross-encoder--nli-deberta-v3-small--fa280487 \
  --run-jev --allow-remote --env-file .env --jev-model jev-latest \
  --jev-review-threshold 0.60 \
  --output benchmarks/external_fiveway_confirmation/results/jev.json
```

This remote command sends only the empty query field, claim, and the selected
evidence text and IDs for each case. ContextTrace remains local-first: Jev is
opt-in, `local_only` still blocks it by default, and the stable verifier and
provider defaults are unchanged.

Apply the development-frozen cascade without recalibration:

```bash
PYTHONPATH=packages/contexttrace:. .venv/bin/python -m \
  benchmarks.jev_v2_verification.cascade evaluate \
  --result benchmarks/external_fiveway_confirmation/results/jev.json \
  --policy benchmarks/jev_v2_verification/results/cascade_policy.json \
  --expected-split heldout \
  --output benchmarks/external_fiveway_confirmation/results/cascade.json
```

This is public-test external validation. It is stronger than the earlier
retrospective replay because its cases and labels were not inspected during
cascade selection, but public benchmark contamination in model pretraining
cannot be ruled out.

## Reproduce the ambiguity follow-up

Fit the local meta-gate on the development signals and validate it without
using either held-out confirmation pack:

```bash
PYTHONPATH=packages/contexttrace:. .venv/bin/python -m \
  benchmarks.external_fiveway_confirmation.learned_ambiguity_gate \
  --result benchmarks/external_fiveway_confirmation/results/development_ambiguity_features.json \
  --policy-output benchmarks/external_fiveway_confirmation/results/development_learned_gate_policy.json \
  --analysis-output benchmarks/external_fiveway_confirmation/results/development_learned_gate_analysis.json
```

Verify the second freeze before inspecting its results:

```bash
PYTHONPATH=packages/contexttrace:. .venv/bin/python -m \
  benchmarks.external_fiveway_confirmation.freeze_v2 verify \
  --manifest benchmarks/external_fiveway_confirmation/confirmation_v2_freeze_manifest.json
```

The successful held-out run used:

```bash
CONTEXTTRACE_LOCAL_ONLY=false PYTHONPATH=packages/contexttrace:. \
.venv/bin/python -m benchmarks.external_fiveway_confirmation.ambiguity_features run \
  --cases benchmarks/external_fiveway_confirmation/confirmation_v2_cases.json \
  --output benchmarks/external_fiveway_confirmation/results/confirmation_v2_ambiguity_features.json \
  --env-file .env --allow-remote --model jev-latest --expected-split heldout

PYTHONPATH=packages/contexttrace:. .venv/bin/python -m \
  benchmarks.external_fiveway_confirmation.learned_ambiguity_gate \
  --result benchmarks/external_fiveway_confirmation/results/confirmation_v2_ambiguity_features.json \
  --policy benchmarks/external_fiveway_confirmation/results/development_learned_gate_policy.json \
  --applied-output benchmarks/external_fiveway_confirmation/results/confirmation_v2_learned_gate.json
```

The learned gate runs locally over the returned typed probabilities and adds no
remote request. It remains an experiment; ContextTrace's stable verifier,
provider default, and `local_only` behavior are unchanged.
