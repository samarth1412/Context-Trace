# Local verification quality experiment

This experiment compares the stable semantic verifier with an opt-in local
pipeline that adds claim decomposition, conservative relation rules, and the
repository's pinned local NLI model. It does not change provider selection or
the stable default. Normal verification does not download models or call a
remote service.

The development and held-out sets each contain 15 synthetic, author-labeled
cases. Their scenario families are disjoint, and the files were frozen before
the first held-out score. These labels are not independent human validation.
The ten Jev pilot cases were used only to diagnose failure mechanisms.

## Setup

Install the package and optional local NLI dependencies:

```bash
python -m pip install -e 'packages/contexttrace[nli,test]'
```

Model provisioning is a separate, explicit network operation. It downloads
only the eight files in the repository's artifact lock and verifies every hash:

```bash
PYTHONPATH=packages/contexttrace:. python -m \
  benchmarks.local_verification_quality.provision_model \
  --output .tmp-contexttrace-models/cross-encoder--nli-deberta-v3-small--fa280487
```

The pinned model is `cross-encoder/nli-deberta-v3-small` at revision
`fa2804872c3b4bd748f38c0185cc85775361e735`. The model card declares
Apache-2.0. The validated files occupy 578,732,649 bytes.

## Reproduce offline

After provisioning, disconnect the network if desired and force the Hugging
Face libraries into offline mode:

```bash
export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1
export TOKENIZERS_PARALLELISM=false

PYTHONPATH=packages/contexttrace:. python -m \
  benchmarks.local_verification_quality.run \
  --cases benchmarks/local_verification_quality/development_cases.json \
  --split development \
  --model-path .tmp-contexttrace-models/cross-encoder--nli-deberta-v3-small--fa280487 \
  --output /tmp/contexttrace-local-quality-development.json

PYTHONPATH=packages/contexttrace:. python -m \
  benchmarks.local_verification_quality.run \
  --cases benchmarks/local_verification_quality/heldout_cases.json \
  --split heldout \
  --model-path .tmp-contexttrace-models/cross-encoder--nli-deberta-v3-small--fa280487 \
  --output /tmp/contexttrace-local-quality-heldout-reproduction.json
```

Omit `--model-path` to compare the stable verifier with deterministic
decomposition and relation-rule ablations without neural dependencies.

The committed `results/heldout.json` is the untouched one-shot result. A rerun
after fixing the discovered `no later than` parsing bug is preserved separately
as `results/heldout_posthoc_regression.json`; it is not independent held-out
evidence.

## Experimental API

Import the path explicitly so its status is visible at the call site:

```python
from contexttrace.verify.local_quality import verify_trace_local_quality
from contexttrace.verify.semantic_core_v2.nli import build_pinned_nli

nli = build_pinned_nli(
    ".tmp-contexttrace-models/cross-encoder--nli-deberta-v3-small--fa280487"
)
result = verify_trace_local_quality(trace, nli=nli)
```

The report keeps support, real-world truth, and source condition separate. It
includes exact selected evidence spans and hashes, atomic assessments, backend
identity, review status, and whether a supported decision was automatic. The
reported confidence is an uncalibrated decision-strength signal. Raw NLI scores
are not probabilities that the final verdict is correct.

See [REPORT.md](REPORT.md) for the diagnostic audit, metrics, and adoption
recommendation.
