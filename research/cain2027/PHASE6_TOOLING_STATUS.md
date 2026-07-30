# ContextTrace CAIN 2027 Phase 6 tooling status

Status date: 2026-07-30

Implemented:

- hash-validating, label-free candidate and ablation runner;
- exact frozen-environment and local-NLI artifact checks;
- pure semantic-v1 compatibility adapter with recovered answer offsets;
- deterministic maximum-overlap claim and evidence alignment;
- fixed-taxonomy confusion, macro-F1, root accuracy, unverifiable F1,
  citation, abstention, evidence, false-green, calibration, selective-risk,
  route, availability, and latency metrics;
- stratified source-family cluster bootstrap;
- paired source-family randomization and Holm adjustment;
- sealed-zone scorer with aggregate/private output separation;
- synthetic integrity, edge-case, metric, and reproducibility tests.

Not performed:

- no semantic_core_v2 or ablation call on the 493 untouched cases;
- no sealed-gold read;
- no candidate/predecessor/gold join;
- no evaluation metric, confidence interval, p-value, table, or plot from the
  untouched corpus;
- no prediction inspection, tuning, publication, or release.

Next irreversible action: create an exact Phase 6 execution authorization, run
the frozen candidate and ablations once without labels, hash and preserve the
raw output, and transfer it unopened to SAR for sealed scoring.
