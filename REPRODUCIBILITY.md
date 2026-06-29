# Reproducibility

This runbook reproduces the ContextTrace ARR experiment harness. It does not by
itself reproduce independent human review or paid external baselines.

## Environment

Run from the repository root with the supported Python version and the locked
project dependencies. Record the Python version, operating system, commit SHA,
dependency lock hash, dataset source hashes, model identifiers, and environment
variables for every paper run. Never commit API keys or private annotation keys.

Install and verify the package:

```bash
python -m pip install -e packages/contexttrace
python -m pytest
```

## Harness Check

Run the fast cumulative ablation check:

```bash
python benchmarks/contexttrace_bench/arr_ablation.py \
  --quick \
  --case-set all \
  --output-dir benchmarks/contexttrace_bench/out/arr_ablations_quick
```

The output is marked `paper_result_eligible=false`, uses 50 bootstrap samples,
and only validates execution, metric masking, case alignment, and artifact
generation. It must not be reported as a paper result.

## Frozen Paper Run

After dataset review is complete, run the frozen matrix without `--quick`:

```bash
python benchmarks/contexttrace_bench/arr_ablation.py \
  --case-set all \
  --output-dir benchmarks/contexttrace_bench/out/arr_ablations_paper
```

For a frozen external pack, pass `--case-pack PATH` and use a new output
directory. Preserve `ablation_results.json`, `ablation_table.md`,
`experiment_matrix.json`, and every profile's raw outputs. The aggregate records
the commit, runtime, ordered-case hash, bootstrap seed, and claim policy.

## Human Review

Generate blinded annotation artifacts with:

```bash
python benchmarks/contexttrace_bench/arr_annotation.py build \
  --case-set public_holdout \
  --output-dir benchmarks/contexttrace_bench/out/arr_annotation_diag150
```

Follow `ARR_ANNOTATION_PROTOCOL.md`. Send only the packet to reviewers. Generated
experiment outputs are ignored by Git; archive paper artifacts in controlled
storage with hashes and publish only de-identified, license-compatible files.

## Determinism And Cost

The frozen ablation seed is in `ARR_EXPERIMENTS.json`. Profiles must see identical
ordered case IDs. Local lexical and semantic modes have no API cost. Judge, NLI,
and external evaluator runs are sensitivity or baseline studies and must record
provider, model revision, parameters, retries, token usage, and observed cost.
Hardware and library differences can affect latency, so report the measurement
machine and do not compare latency across unmatched environments.
