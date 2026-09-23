# V9 Climate-FEVER holdout protocol

## Status

The V9 holdout was frozen before any local or remote model scoring. It contains
240 real-world climate claims sampled deterministically from the official
Climate-FEVER release: 60 `SUPPORTS`, 60 `REFUTES`, 60 `NOT_ENOUGH_INFO`, and 60
`DISPUTED` claims. Every case retains all five upstream retrieved and
human-annotated evidence sentences.

The frozen evaluation SHA-256 is
`d582c53e6a87d800e3bf293c3d597e7e11ee0fb5dff0a79f31be5e2395e26858`.
No V8 threshold, prompt, route, or model was selected using this holdout.

## Why Climate-FEVER

Climate-FEVER contains real-world claims rather than synthetically altered
claims. It tests a new domain and includes insufficient and conflicting evidence
in addition to support and refutation. This directly exercises the two remaining
V8 weaknesses: excessive remote routing and unsafe certainty when evidence is
mixed.

The official release has 1,535 claims and 7,675 evidence sentences. The source
snapshot used here has SHA-256
`8a4b9032d861be482ffb49dddfd283ffa6089e654f1e968040011882c5eb6e0b`.

## Frozen mapping

| Upstream label | ContextTrace relation | Evaluation target | Cases |
| --- | --- | --- | ---: |
| `SUPPORTS` | Entailment | `covered` | 60 |
| `REFUTES` | Contradiction | `missing` | 60 |
| `NOT_ENOUGH_INFO` | NotMentioned | `missing` | 60 |
| `DISPUTED` | Disputed | `review` | 60 |

Selection sorts each upstream label independently by SHA-256 of
`contexttrace-climate-fever-v9|claim_label|claim_id` and takes the first 60.
The committed selection contains IDs and aggregate counts only. Model outputs
played no part in selection.

## Evaluation contract

The 180 non-disputed cases form the primary binary verification evaluation. V8
must meet every existing release gate:

- support recall of at least 50%;
- overall and local-only false-positive rates of at most 5%;
- zero contradiction false supports; and
- remote routing of at most 30%.

The 60 disputed cases are a separate ambiguity challenge and are excluded from
binary metrics. They require zero automatic supported decisions and at least 90%
review or abstention coverage. These rules are frozen before scoring and cannot
be relaxed from the observed results.

## Privacy and leakage controls

- Labels, votes, entropy, article metadata, and evaluation targets remain outside
  model inputs.
- Local scoring uses only the claim and the same five rendered evidence texts.
- Any Jev request may contain only the claim and those selected evidence items.
- `local_only` continues to block all network calls.
- The V8 policy remains frozen and stable defaults remain unchanged.
- Results from this holdout may evaluate V8 once; they cannot be used to retune
  V8 and still be described as held out.

## Redistribution

The official Climate-FEVER page describes the dataset as publicly available but
does not state an explicit redistribution license. ContextTrace therefore does
not commit the source claims, evidence text, or generated evaluation pack. The
builder verifies the official file hash and reconstructs the exact pack in
external storage. The repository contains only code, selected claim IDs,
aggregate audits, and cryptographic hashes.

## Reproduction

```bash
curl -L --fail --show-error --create-dirs \
  --output /private/tmp/contexttrace_external_data/climate_fever/climate-fever-dataset-r1.jsonl \
  'https://www.sustainablefinance.uzh.ch/dam/jcr%3Adf02e448-baa1-4db8-921a-58507be4838e/climate-fever-dataset-r1.jsonl'

PYTHONPATH=packages/contexttrace:. .venv/bin/python \
  -m benchmarks.requirement_alignment.build_v9_climate_fever \
  --source /private/tmp/contexttrace_external_data/climate_fever/climate-fever-dataset-r1.jsonl \
  --evaluation-output /private/tmp/contexttrace_external_data/climate_fever/v9_climate_fever_evaluation.json \
  --selection-output benchmarks/requirement_alignment/v9_climate_fever_selection.json \
  --audit-output benchmarks/requirement_alignment/v9_climate_fever_audit.json \
  --manifest-output benchmarks/requirement_alignment/v9_climate_fever_manifest.json
```
