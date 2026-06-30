# ContextTrace ARR Artifact

This anonymous supplementary artifact contains the ContextTrace verifier,
benchmark harness, frozen ARR protocols, tests, and licensed RAGTruth evaluation
inputs needed for the submitted experiments. It intentionally contains no git
history, author identity, public project repository link, package-index link, or
private annotation key.

## Environment

- Python 3.10 or newer is recommended.
- Core quick runs require no network API and incur no API cost.
- Commands are run from the extracted artifact root.

```bash
python -m pip install -e "packages/contexttrace[test]"
python -m pytest -q
```

## Reproduce Reviewer Tables

Generate the frozen full experiment outputs:

```bash
python benchmarks/contexttrace_bench/reproduce_arr_tables.py --full
```

For a faster non-paper harness check:

```bash
python benchmarks/contexttrace_bench/reproduce_arr_tables.py --quick
```

Both commands write external evaluation, ablation, same-ID baseline, and error
analysis under `benchmarks/contexttrace_bench/out/`. Quick output is marked
ineligible for paper claims. The artifact also includes the frozen compact full
outputs used to generate the draft tables.

Regenerate TeX and Markdown paper tables with:

```bash
python paper/generate_tables.py
```

## Inspect Frozen Protocols

- `benchmarks/contexttrace_bench/ARR_EXPERIMENTS.json`: machine-readable study plan.
- `benchmarks/contexttrace_bench/ARR_EXPERIMENT_PROTOCOL.md`: evaluation protocol.
- `benchmarks/contexttrace_bench/ARR_ANNOTATION_PROTOCOL.md`: independent label review.
- `benchmarks/contexttrace_bench/ARR_ACTIONABILITY_PROTOCOL.md`: blinded RQ4 study.
- `REPRODUCIBILITY.md`: commands, seeds, environment, and artifact rules.

## Human Studies

Human response files and private condition/label keys are not distributed.
Reviewers can validate the packet builders without creating human results:

```bash
python benchmarks/contexttrace_bench/arr_annotation.py build --case-set public_holdout
python benchmarks/contexttrace_bench/arr_actionability.py build --quick
```

Generated files are written under ignored `out/` directories. Quick packets are
workflow checks, not annotations or study outcomes.

## Inspect Repair Planning

Build an evidence-backed repair plan for the bundled agent failure example:

```bash
contexttrace repair examples/diagnose_agent_trace.json --out repair_plan.md --json-out repair_plan.json
```

For a portable RAG trace, add `--corpus PATH` to distinguish retrieval misses,
reranking failures, chunking issues, corpus gaps, answer overreach, and stale or
conflicting evidence. Generated suite commands must be run only after the fix is
applied and a passing trace is recaptured.

## Data And Claims

The included RAGTruth-derived pack is assisted calibration evidence pending
independent review. The bundled RAGAS predictions are scored only on overlapping
outputs; unsupported diagnostics remain `N/A`. ContextTrace-Diag-150 is a public
document holdout pending independent review. Neither track alone establishes a
broad state-of-the-art claim.

RAGTruth data is redistributed under its MIT license. See
`THIRD_PARTY_LICENSES/RAGTruth-LICENSE.txt` and
`THIRD_PARTY_LICENSES/README.md`.

## Integrity

`ARTIFACT_MANIFEST.json` lists every payload file, byte size, and SHA-256 digest.
The companion `.sha256` file authenticates the ZIP. Validate an archive with:

```bash
python scripts/build_anonymous_artifact.py --validate-only PATH_TO_ZIP
```
