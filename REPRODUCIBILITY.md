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

## One-Command Harness Check

Generate all four reviewer tables with one command:

```bash
python benchmarks/contexttrace_bench/reproduce_arr_tables.py --quick
```

This writes external evaluation, cumulative ablation, same-ID baseline, and
error-analysis tables plus a machine-readable manifest under
`benchmarks/contexttrace_bench/out/arr_reproduction/`. When the ignored
RAGTruth release bundle is available, quick mode selects a deterministic 25-case
subset and scores the matching RAGAS predictions. Missing external artifacts are
reported as unavailable, never as zero-valued evidence.

## Ablation Harness Check

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

After the full dataset pack and matched baseline predictions are available, run
the one-command paper candidate workflow:

```bash
python benchmarks/contexttrace_bench/reproduce_arr_tables.py \
  --ragtruth-case-pack PATH \
  --candidate PATH
```

Full mode fails unless the RAGTruth pack and at least one same-ID candidate are
available. Its output remains a pre-review paper candidate until independent
review reports pass. To run only the frozen matrix without `--quick`:

```bash
python benchmarks/contexttrace_bench/arr_ablation.py \
  --case-set all \
  --output-dir benchmarks/contexttrace_bench/out/arr_ablations_paper
```

After a complete full run, record its claim-safe checksummed snapshot with:

```bash
python benchmarks/contexttrace_bench/arr_snapshot.py
```

The snapshot command rejects quick runs, missing cases, incomplete baseline
coverage, altered inputs, missing raw outputs, non-frozen bootstrap seeds,
class-sensitive intervals with fewer than 95% valid draws, or any run incorrectly
marked paper eligible. Ablation intervals must retain all 400 requested draws.

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

The diagnosis-actionability study is separate. Build its quick harness packet
with `python benchmarks/contexttrace_bench/arr_actionability.py build --quick`
and follow `ARR_ACTIONABILITY_PROTOCOL.md`. Send only
`actionability_packet.json`; keep the condition key private.

## Determinism And Cost

The frozen ablation seed is in `ARR_EXPERIMENTS.json`. Profiles must see identical
ordered case IDs. Local lexical and semantic modes have no API cost. Judge, NLI,
and external evaluator runs are sensitivity or baseline studies and must record
provider, model revision, parameters, retries, token usage, and observed cost.
Hardware and library differences can affect latency, so report the measurement
machine and do not compare latency across unmatched environments.

## Anonymous Artifact

Build the deterministic supplementary ZIP with the licensed RAGTruth pack and
matching candidate predictions:

```bash
python scripts/build_anonymous_artifact.py
```

The builder uses a tracked-file allowlist, replaces project-owned public links,
excludes git history and private/ignored outputs, includes third-party licensing,
and fails on identity markers, user paths, secrets, unsafe ZIP paths, or manifest
checksum mismatches. Validate an existing ZIP with
`python scripts/build_anonymous_artifact.py --validate-only PATH`.
