# V19 independent confirmation set

V19 freezes a new balanced five-way confirmation set after the V18 candidate
artifact was committed. Candidate predictions were not generated or inspected
during construction.

## Sources and mapping

The set contains 125 cases, with 25 examples for each ContextTrace verdict.

| Source label | ContextTrace verdict | Cases |
|---|---|---:|
| AVeriTeC `Supported` | `supported` | 25 |
| WiCE `partially_supported` | `partially_supported` | 25 |
| AVeriTeC `Refuted` | `contradicted` | 25 |
| AVeriTeC `Not Enough Evidence` | `unsupported` | 25 |
| AVeriTeC `Conflicting Evidence/Cherrypicking` | `unverifiable` | 25 |

AVeriTeC development revision
`122e10f4e02168d18eb9e8cdb5abe44f530ce6a7` supplies 100 cases. Its source
file SHA-256 is
`499793726b4a5406780928a3d9dedc48d6dd53de778f22437d129cacdb08e300`
and its license is CC BY-NC 4.0. Previously unselected cases from the pinned
WiCE test source supply the partial-support slice. WiCE annotations are ODC-BY;
the upstream source-text terms continue to apply.

The AVeriTeC evidence consists only of its annotated question-answer content.
Justifications, verdicts, publisher metadata, and URLs are excluded from model
inputs. ContextTrace's existing label-blind local selector retains at most eight
evidence spans per claim.

## Disjointness and freeze

The builder scans prior repository datasets and case packs, plus both external
V13 partitions. It excludes matching case IDs and normalized claims before
stable SHA-256 selection. The resulting set has:

- 125 unique case IDs;
- no case-ID overlap with prior artifacts;
- no normalized-claim overlap with prior artifacts;
- nonempty selected evidence for every case; and
- no label or dataset field inside any model input.

The text-bearing dataset remains at
`/private/tmp/contexttrace_external_data/v19_confirmation.json`. Its canonical
JSON SHA-256 is
`2fa52ad909c62cee9b610191aea89d5ab74523446a411070c0a96c387f36050c`.
The committed audit stores source IDs, input hashes, label counts, and overlap
checks without claim or evidence text.

## Reproduce the frozen pack

```bash
PYTHONPATH=packages/contexttrace:. .venv/bin/python \
  -m benchmarks.requirement_alignment.build_v19_confirmation \
  --averitec /private/tmp/contexttrace_external_data/v19_sources/averitec_dev.json \
  --wice /private/tmp/contexttrace_external_data/v19_sources/wice_test.jsonl \
  --repository-root . \
  --exclude-dataset /private/tmp/contexttrace_external_data/v13_development.json \
  --exclude-dataset /private/tmp/contexttrace_external_data/v13_heldout.json \
  --dataset-output /private/tmp/contexttrace_external_data/v19_confirmation.json \
  --audit-output benchmarks/requirement_alignment/v19_confirmation_audit.json \
  --manifest-output benchmarks/requirement_alignment/v19_confirmation_manifest.json
```

Rebuilding produces byte-identical dataset, audit, and manifest files. The
manifest binds this set to the frozen V18 artifact SHA-256 and forbids
retraining, threshold changes, or case selection after predictions are
generated.

AVeriTeC `Not Enough Evidence` is mapped to `unsupported` because the supplied
evidence is insufficient for the claim; mixed or cherry-picked evidence is
reserved for `unverifiable`. This alignment and public-data pretraining
contamination are limitations that must accompany the final result.
