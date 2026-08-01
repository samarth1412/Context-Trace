# ContextTrace product-safety development baseline

This benchmark is the repeatable engineering loop for the v1.2 safety branch. It
does not replace CAIN, the sealed gold labels, or a future untouched evaluation.

It combines:

- fourteen controlled fixtures for expected support, source-condition, citation,
  abstention, failure-label, and root-cause behavior; and
- the existing 150-case public holdout, which is now treated as visible
  development data.

The runner uses `deterministic_only_v2`. An `unresolved` route therefore measures
the claims that would need the selective local-NLI stage, without downloading a
model or making a model call.

Run it from the repository root:

```bash
.venv/bin/python benchmarks/product_safety/run_baseline.py \
  --output benchmarks/product_safety/baseline-semantic-core-v2.json
```

Add `--enforce` only after the v1.2 targets have been reached. Before then, a
missed target is expected to produce a useful baseline rather than block the
measurement command.

To measure the opt-in v2.1 selective cascade, first place the exact pinned model
revision in a local directory, then run:

```bash
.venv/bin/python benchmarks/product_safety/run_baseline.py \
  --model-path /private/models/nli-deberta-v3-small \
  --output benchmarks/product_safety/candidate-selective-v2.1.json
```

The command verifies every locked artifact hash before loading the model and
records only its public identity, revision, and manifest hash. It never records
the local model path.

The dangerous-false-green metric is case-level: an unsafe case is one whose
visible development label expects abstention, contradiction, unsupported, or
unverifiable; it is a false green only when the entire result is green. Because
unknown source metadata can conservatively suppress green, the benchmark also
reports dangerous safe classifications: unsafe cases whose claims were all
classified as supported. The abstention metric checks whether the verifier emits
`must_abstain`, independently of whether the answer itself abstained.

## Dedicated-checker hard negatives

The deterministic hard-negative pack is development-only. It contains paired
positive controls and mutations for numbers, dates, versions, negation, reversed
relations, identifiers, paths, status, condition omission, scope omission,
numeric boundaries, and temporal boundaries.

Rebuild and verify the generated corpus:

```bash
.venv/bin/python benchmarks/product_safety/build_hard_negatives.py
.venv/bin/python benchmarks/product_safety/build_hard_negatives.py --check
```

Compare the exact pinned generic NLI artifact with the dedicated checker:

```bash
.venv/bin/python benchmarks/product_safety/run_hard_negative_benchmark.py \
  --model-path /private/models/nli-deberta-v3-small \
  --output benchmarks/product_safety/hard-negative-benchmark-v1.json \
  --enforce
```

This pack is a mechanism and regression test, not independent research evidence.
It must never be reported as an external benchmark or untouched result.

## Learned support-risk gate

The generated checker-development corpus contains 144 synthetic paired cases
across the same 12 conflict categories. Its train, validation, and
held-out-development source families are disjoint. Rebuild it or verify that the
checked-in artifact is current:

```bash
.venv/bin/python benchmarks/product_safety/build_checker_development_corpus.py
.venv/bin/python benchmarks/product_safety/build_checker_development_corpus.py --check
```

Train the tiny logistic support-risk gate with the exact pinned local NLI model:

```bash
.venv/bin/python benchmarks/product_safety/train_support_risk_model.py \
  --model-path /private/models/nli-deberta-v3-small
```

The command writes a hash-locked package artifact and a training report with
accuracy, false-entailment rate, ECE, AURC, selective coverage, and selective
risk. The gate is deliberately narrow: it can intervene only when observable
contradiction or omission signals exist, while the deterministic checker remains
a fallback. The corpus and every resulting metric are development-only and must
not be described as external, untouched, or SOTA evidence.

## Source-condition reasoning

The source-condition pack exercises explicit status, typed booleans,
replacement relations, within-lineage version and timestamp comparisons,
authority labels, and observable conflicts between authoritative sources. Its
development and held-out-development source families are disjoint.

```bash
.venv/bin/python benchmarks/product_safety/build_source_condition_corpus.py
.venv/bin/python benchmarks/product_safety/build_source_condition_corpus.py --check
.venv/bin/python benchmarks/product_safety/run_source_condition_benchmark.py
```

The report compares frozen v2 with the opt-in v2.1 reasoner using
source-condition accuracy, macro-F1, and dangerous false-green rate. These are
templated mechanism tests. Their held-out-development split is not an untouched
test and cannot support an external-generalization or SOTA claim.

## Hierarchical evidence attribution

The attribution pack contains exact labels for minimal support, complementary
spans within and across documents, refuting spans, duplicate evidence,
unsupported cases, and Unicode offsets. Rebuild it, verify it, and compare
frozen v2 with v2.1:

```bash
.venv/bin/python benchmarks/product_safety/build_evidence_attribution_corpus.py
.venv/bin/python benchmarks/product_safety/build_evidence_attribution_corpus.py --check
.venv/bin/python benchmarks/product_safety/run_evidence_attribution_benchmark.py
```

The report records exact-span precision/recall/F1, character IoU, complete-case
rate, over-attribution, role accuracy, and answer/source offset integrity. The
pack is templated development data and cannot support an external span-quality
or SOTA claim.

## External baseline development comparisons

The Stage 6 fail-closed runner, artifact lock, reproducibility commands, and
current visible-development findings are documented in
`benchmarks/external_baselines/README.md`. Those results are not untouched
evaluation evidence and do not replace the locked Stage 7 protocol.

The v2.1 unitizer also treats short names, dates, numbers, and terms as exact-
offset query-conditioned answer-fragment claims. This prevents an otherwise
insufficient-input trace from being projected as green while preserving fillers
such as acknowledgements as non-claims.
