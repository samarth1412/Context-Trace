# V10 Climate-FEVER development data

V10 creates a new local-training and policy-development resource after the V9
router failed cross-domain support recall. It uses only Climate-FEVER claims
that were not part of the consumed 240-case V9 holdout.

## Partitions

| Partition | Support | Refutation | Insufficient evidence | Disputed | Total |
|---|---:|---:|---:|---:|---:|
| Training | 75 | 75 | 75 | 75 | 300 |
| Development | 15 | 15 | 15 | 15 | 60 |

All 240 V9 claim IDs are excluded. Training and development claim IDs are
disjoint, and no exact rendered evidence sentence appears in both partitions.
Development selection uses one claim from each evidence-connected component,
which also prevents duplicate evidence groups within the development set.
Selection is deterministic from claim IDs and labels and does not use any model
output.

Climate-FEVER has only one public collection. Exact evidence from some V10
claims also appeared with different claims in the already consumed V9 holdout.
This does not permit V9 to be reported again as held-out evidence. V9 will never
be reused for tuning or confirmation, and the next confirmation must use a
different dataset frozen after the V10 policy is selected.

## Redistribution

The official Climate-FEVER page does not state an explicit redistribution
license. The generated text-bearing training and development JSON files remain
in external storage. Git contains only the deterministic builder, selected
claim IDs, aggregate audits, and cryptographic hashes.

## Intended use

The 300-case training partition will support an explicit four-way local model
for support, contradiction, insufficient evidence, and disputed evidence. The
60-case development partition may be used for model and threshold selection.
Neither partition is release evidence.
