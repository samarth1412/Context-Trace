# V21 domain-diverse development set

V21 creates a larger development-only collection for repairing the V19
transfer failure. It is not a held-out set and cannot support a confirmation or
state-of-the-art claim.

## Composition

The set contains 500 cases, balanced at 100 cases per ContextTrace verdict.
AVeriTeC training data supplies supported, contradicted, unsupported, and
unverifiable examples. Previously unselected WiCE cases supply partial support.

| Source label | ContextTrace verdict | Cases |
|---|---|---:|
| AVeriTeC `Supported` | `supported` | 100 |
| WiCE `partially_supported` | `partially_supported` | 100 |
| AVeriTeC `Refuted` | `contradicted` | 100 |
| AVeriTeC `Not Enough Evidence` | `unsupported` | 100 |
| AVeriTeC `Conflicting Evidence/Cherrypicking` | `unverifiable` | 100 |

The AVeriTeC source is pinned to revision
`122e10f4e02168d18eb9e8cdb5abe44f530ce6a7`; its training-file SHA-256 is
`ae5eda7c42ddf1695ef185a7ba1bc716928f5adf57103e4f78aae5f9afe00f9c`.
The WiCE source retains the V19 pinned revision and file hash.

## Isolation and privacy

The builder excludes case IDs and normalized claims from repository case packs,
both external V13 partitions, and the consumed V19 confirmation set before
selection. The resulting 500 IDs and claims are disjoint from those inputs.

Only locally selected evidence reaches scoring. Labels and source metadata are
outside model inputs. The text-bearing dataset is stored at
`/private/tmp/contexttrace_external_data/v21_development.json`, with canonical
JSON SHA-256
`b9422ebb87ee69c13e1e52a2244210177fa7affafa73f63db3a0a68bb3b2ea70`.
The committed audit contains hashes, IDs, counts, and provenance without claim
or evidence text.

## Limitations

The partial-support label comes only from WiCE, creating source-label
correlation. Labels are aligned from upstream tasks rather than independently
annotated for ContextTrace. Public-data pretraining contamination cannot be
ruled out. These limitations require a separate, newly frozen confirmation
source after candidate development.

## Reproduce

```bash
PYTHONPATH=packages/contexttrace:. .venv/bin/python \
  -m benchmarks.requirement_alignment.build_v21_development \
  --averitec-train /private/tmp/contexttrace_external_data/v19_sources/averitec_train.json \
  --wice /private/tmp/contexttrace_external_data/v19_sources/wice_test.jsonl \
  --repository-root . \
  --exclude-dataset /private/tmp/contexttrace_external_data/v13_development.json \
  --exclude-dataset /private/tmp/contexttrace_external_data/v13_heldout.json \
  --exclude-dataset /private/tmp/contexttrace_external_data/v19_confirmation.json \
  --dataset-output /private/tmp/contexttrace_external_data/v21_development.json \
  --audit-output benchmarks/requirement_alignment/v21_development_audit.json \
  --manifest-output benchmarks/requirement_alignment/v21_development_manifest.json
```

Rebuilding produces byte-identical dataset, audit, and manifest files.
