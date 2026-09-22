# Jev v2 shared-input verification experiment

This experiment repairs the main comparison flaw in the original ten-case Jev
pilot. A shared local selector constructs one exact claim–evidence payload, then
the stable semantic verifier, experimental deterministic verifier, pinned local
NLI pipeline, and Jev receive that same claim and the same selected span texts.
The systems retain different internal decision procedures.

The experiment remains isolated under `benchmarks/` and does not alter the
stable default. ContextTrace now separately exposes Jev as an experimental,
explicitly opt-in runtime provider guarded by `local_only` and remote consent.

## Data tracks

The adapter supports two RAGTruth projections:

- `answer`: preserves RAGTruth's upstream human answer-level label. It is useful
  for end-to-end answer evaluation, but a multi-sentence answer is not a fair
  atomic-claim input.
- `sentence`: deterministically projects RAGTruth's human answer-side
  hallucination spans onto sentence units. Clean sentences become `supported`,
  sentences overlapping baseless spans become `partially_supported`, and
  sentences overlapping conflict spans become `contradicted`.

Sentence labels are derived projections, not independently annotated
ContextTrace claim labels. RAGTruth supplies no `unverifiable` class, and the
sampled sentence track has no `unsupported` examples. These limits are retained
in every case pack.

## Reproduce the adapter

```bash
PYTHONPATH=packages/contexttrace:. .venv/bin/python -m \
  benchmarks.jev_v2_verification.adapter \
  --source benchmarks/contexttrace_bench/out/arr_ragtruth_dev/inputs/ragtruth_dev_case_pack.json \
  --split development --unit sentence --per-label 5 \
  --output /tmp/ragtruth_sentence_development.json
```

Use the analogous frozen test pack and `--split heldout` for the held-out case
file. Sampling uses a stable SHA-256 order and keeps source response IDs disjoint
through the repository's existing RAGTruth split.

The larger extension additionally excludes every ID in the original two case
packs. Its frozen development split has 39 cases and its held-out split has 72:

```bash
PYTHONPATH=packages/contexttrace:. .venv/bin/python -m \
  benchmarks.jev_v2_verification.adapter \
  --source benchmarks/contexttrace_bench/out/arr_ragtruth_dev/inputs/ragtruth_dev_case_pack.json \
  --split development --unit sentence --per-label 13 --seed 20260921 \
  --exclude-case-pack benchmarks/jev_v2_verification/ragtruth_sentence_development.json \
  --exclude-case-pack benchmarks/jev_v2_verification/ragtruth_sentence_heldout.json \
  --output benchmarks/jev_v2_verification/ragtruth_sentence_extension_development.json
```

Use the frozen test source with `--split heldout --per-label 24` for the
extension held-out pack. [EXTENSION_RESULTS.md](EXTENSION_RESULTS.md) records
the executed results and statistical analysis.

## Run locally

```bash
export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1
export TOKENIZERS_PARALLELISM=false

PYTHONPATH=packages/contexttrace:. .venv/bin/python -m \
  benchmarks.jev_v2_verification.run \
  --cases benchmarks/jev_v2_verification/ragtruth_sentence_development.json \
  --split development \
  --model-path .tmp-contexttrace-models/cross-encoder--nli-deberta-v3-small--fa280487 \
  --output /tmp/ragtruth_sentence_development_local.json
```

No model is downloaded during this command. The model directory must already
pass the repository's pinned artifact hashes.

## Run Jev explicitly

Put `TYPESAFE_API_KEY` in the ignored `.env`. Jev is remote, so both the
configuration override and CLI opt-in are required:

```bash
CONTEXTTRACE_LOCAL_ONLY=false \
PYTHONPATH=packages/contexttrace:. \
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
.venv/bin/python -m benchmarks.jev_v2_verification.run \
  --cases benchmarks/jev_v2_verification/ragtruth_sentence_development.json \
  --split development \
  --model-path .tmp-contexttrace-models/cross-encoder--nli-deberta-v3-small--fa280487 \
  --run-jev --allow-remote --env-file .env \
  --jev-model jev-latest --jev-review-threshold 0.60 \
  --write-threshold-calibration /tmp/jev-threshold.json \
  --output /tmp/ragtruth_sentence_development_jev.json
```

The runner sends only `query`, `claim`, and `selected_evidence`. It records the
exact shared payload and hash, verdict, complete Choice probabilities,
confidence, requested and resolved model, latency, and token usage. Gold labels
and projection metadata are never included in model state. Explanation and fact
fields remain empty because Jev Choice does not return them.

See [RESULTS.md](RESULTS.md) for the frozen development and held-out findings.

## Local-first cascade

The cascade study replays the saved stable and Jev predictions. Calibration
reads the extension development result only, writes a content-hashed policy,
and the evaluator applies that frozen policy to another split:

```bash
PYTHONPATH=packages/contexttrace:. .venv/bin/python -m \
  benchmarks.jev_v2_verification.cascade calibrate \
  --development-result benchmarks/jev_v2_verification/results/ragtruth_sentence_extension_development_jev.json \
  --policy-output benchmarks/jev_v2_verification/results/cascade_policy.json \
  --analysis-output benchmarks/jev_v2_verification/results/cascade_development.json
```

See [CASCADE_RESULTS.md](CASCADE_RESULTS.md) for the frozen policy, held-out
replay, operational measurements, and limits.

## Evidence-availability ablation

RAGTruth does not publish human-mapped source-side evidence spans. The follow-up
diagnostic therefore does **not** claim an oracle condition. It compares the
same local verifiers under two conditions: the shared selector's top spans and
all deterministic spans from the complete source. This tests whether the
top-eight preselection cap visibly removes useful information. LocalQualityJudge
still performs its documented internal selection in both conditions.

```bash
PYTHONPATH=packages/contexttrace:. \
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 TOKENIZERS_PARALLELISM=false \
.venv/bin/python -m benchmarks.jev_v2_verification.evidence_ablation \
  --cases benchmarks/jev_v2_verification/ragtruth_sentence_development.json \
  --split development \
  --model-path .tmp-contexttrace-models/cross-encoder--nli-deberta-v3-small--fa280487 \
  --output /tmp/ragtruth_sentence_development_evidence_ablation.json
```

Run the analogous command with the frozen held-out case pack only for post-hoc
diagnosis. The runner makes no remote request and does not run Jev because a
complete source is not minimal selected evidence. A causal oracle comparison
still requires independent source-side evidence annotation.

## MiniCheck grounding baseline

MiniCheck is evaluated on its documented binary task: whether a sentence is
supported by a grounding document. ContextTrace's `supported` label is the
positive class; every other existing verdict is grouped as `not_supported`.
These binary metrics must not be compared to the five-way macro F1 above.

The experiment uses official MiniCheck source commit
`b58b9fa69acbd1015ec970fa65dd752413a053d2`. It supports two pinned official
checkpoints: the stronger `MiniCheck-Flan-T5-Large` and the smaller
`MiniCheck-RoBERTa-Large`. Dependency installation and model acquisition are
separate from inference:

```bash
.venv/bin/python -m pip install --no-deps \
  -r benchmarks/jev_v2_verification/requirements-minicheck.txt

HF_XET_HIGH_PERFORMANCE=1 \
.venv/bin/hf download lytang/MiniCheck-Flan-T5-Large \
  --revision 96eafd01cee2d16cf81aaa2fb226b14f422a37b3 \
  --cache-dir .tmp-contexttrace-models/minicheck-cache

HF_XET_HIGH_PERFORMANCE=1 \
.venv/bin/hf download lytang/MiniCheck-RoBERTa-Large \
  --revision 74c8919647e61ed0f71bc177d94f10930f090068 \
  --cache-dir .tmp-contexttrace-models/minicheck-roberta-cache

curl -L --fail -o /tmp/contexttrace-punkt.zip \
  https://raw.githubusercontent.com/nltk/nltk_data/550b6625bcef1f2abff2ff770a5a0d272c9c6b2a/packages/tokenizers/punkt.zip
curl -L --fail -o /tmp/contexttrace-punkt_tab.zip \
  https://raw.githubusercontent.com/nltk/nltk_data/550b6625bcef1f2abff2ff770a5a0d272c9c6b2a/packages/tokenizers/punkt_tab.zip
mkdir -p .tmp-contexttrace-models/nltk_data/tokenizers
unzip -q -o /tmp/contexttrace-punkt.zip \
  -d .tmp-contexttrace-models/nltk_data/tokenizers
unzip -q -o /tmp/contexttrace-punkt_tab.zip \
  -d .tmp-contexttrace-models/nltk_data/tokenizers
```

The Flan weight is 3,132,786,242 bytes with published SHA-256
`41291881e13c6235ed47149cec903bee9493e45d9d7325587a9fa2e266c526c0`.
The RoBERTa weight is 1,421,577,710 bytes with published SHA-256
`67af45a2d5a2706283821049232c7d7c81cea22e81dfdbb7097487a98bc61b53`.
The runner verifies the selected weight, pins the offline `main` cache
reference to its exact snapshot, and then forces Transformers and Hugging Face
Hub offline. This command runs the smaller RoBERTa development baseline:

```bash
PYTHONPATH=packages/contexttrace:. \
.venv/bin/python -m benchmarks.jev_v2_verification.minicheck_baseline \
  --cases benchmarks/jev_v2_verification/ragtruth_sentence_development.json \
  --split development \
  --model roberta-large \
  --cache-dir .tmp-contexttrace-models/minicheck-roberta-cache \
  --nltk-data .tmp-contexttrace-models/nltk_data \
  --threshold 0.5 \
  --baseline-results benchmarks/jev_v2_verification/results/ragtruth_sentence_development_jev.json \
  --output benchmarks/jev_v2_verification/results/ragtruth_sentence_development_minicheck_roberta.json
```

The query is used only by the existing shared evidence selector. MiniCheck sees
the same selected evidence text and atomic claim as the other baselines. Output
contains both binary probabilities, latency, input-token count, hashed chunk
records, and resolved source/model revisions. It contains no generated
explanation, evidence span, or matched fact. When `--baseline-results` is
provided, the runner first verifies matching case IDs and selected-input hashes,
then records binary disagreements with the stable verifier and Jev.

Execution status, RoBERTa development and held-out results, and the exact
reproduction command are recorded in [MINICHECK_STATUS.md](MINICHECK_STATUS.md).
The stronger Flan model remains unexecuted until its pinned 3.1 GB weight passes
the same size and SHA-256 checks.
