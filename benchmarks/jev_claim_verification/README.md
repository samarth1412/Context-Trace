# Jev claim-verification experiment

This experiment compares TypeSafe Jev with ContextTrace's stable claim verifier on the same locally selected evidence spans. It is isolated under `benchmarks/`: it does not register a production provider, change `build_judge_provider`, or change the default lexical verifier.

The five verdicts are ContextTrace's existing taxonomy:

- `supported`: the evidence entails every material part of the claim;
- `partially_supported`: some material parts are supported and others are missing;
- `unsupported`: the evidence is related but does not support the claim;
- `contradicted`: the evidence conflicts with the claim;
- `unverifiable`: the evidence is too ambiguous to decide.

The Jev adapter uses the documented TypeSafe Python SDK and one `Choice` question. It records the selected verdict, the complete five-label probability distribution, confidence, the resolved model version, request latency, and input/output token usage. It leaves explanation and fact fields empty because a `Choice` response does not supply them. See the official [Choice documentation](https://docs.typesafe.ai/primitives/choice), [Python SDK usage](https://docs.typesafe.ai/sdk/python/usage), and [citation-checking cookbook](https://docs.typesafe.ai/cookbooks/citation_check).

## Privacy and input boundary

Evidence selection runs locally with ContextTrace's existing `find_best_evidence`. Jev receives only three fields: `query`, `claim`, and the selected evidence span IDs/text. Context metadata, full source documents, expected verdicts, split names, and evaluation categories are excluded. Each result contains hashes and character counts that show which selected spans were used without copying their text into the result.

Jev is a remote provider. Live execution is blocked while ContextTrace resolves `local_only=true`, even if `--allow-remote` is supplied. A live run needs both `CONTEXTTRACE_LOCAL_ONLY=false` and the explicit `--allow-remote` flag.

## Install and run

Install the SDK in the project environment:

```bash
.venv/bin/python -m pip install -r benchmarks/jev_claim_verification/requirements.txt
```

Put the TypeSafe key in the ignored project `.env` as `TYPESAFE_API_KEY=...`, then load it into the shell. Do not commit `.env`.

Run development first:

```bash
set -a
source .env
set +a
CONTEXTTRACE_LOCAL_ONLY=false PYTHONPATH=packages/contexttrace .venv/bin/python -m benchmarks.jev_claim_verification.experiment \
  --cases benchmarks/jev_claim_verification/development_cases.json \
  --split development \
  --model jev-latest \
  --allow-remote \
  --output benchmarks/jev_claim_verification/results/jev_development.json
```

Use the development cases to check instructions and any decision threshold. Do not tune after opening the held-out result. Then run the held-out split once:

```bash
set -a
source .env
set +a
CONTEXTTRACE_LOCAL_ONLY=false PYTHONPATH=packages/contexttrace .venv/bin/python -m benchmarks.jev_claim_verification.experiment \
  --cases benchmarks/jev_claim_verification/heldout_cases.json \
  --split heldout \
  --model jev-latest \
  --allow-remote \
  --output benchmarks/jev_claim_verification/results/jev_heldout.json
```

To validate the local pipeline without credentials or remote traffic:

```bash
PYTHONPATH=packages/contexttrace .venv/bin/python -m benchmarks.jev_claim_verification.experiment \
  --cases benchmarks/jev_claim_verification/development_cases.json \
  --split development \
  --baseline-only \
  --output /tmp/contexttrace-jev-baseline.json
```

## Reading the result

`summary.baseline_jev_disagreements` lists every baseline/Jev disagreement. `summary.unsupported_false_supported_case_ids` is the narrow high-risk error requested here. `summary.dangerous_false_supported_case_ids` is broader and includes any non-supported gold label that Jev marks `supported`.

The completed ten-case run is reported in [`RESULTS.md`](RESULTS.md). It supports implementing an experimental `JevJudge` as an optional remote provider, kept off by default and confidence-gated. A larger labeled benchmark and repeated runs are still needed before making general performance claims.
