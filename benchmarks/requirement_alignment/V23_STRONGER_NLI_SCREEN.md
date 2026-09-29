# V23 stronger local NLI screen

**V25 qualification:** [the input audit](V25_INPUT_AND_REPRESENTATION_RESULTS.md)
found that some selected QA evidence omits the answers needed for the inherited
labels. Interpret this screen as pipeline diagnostics, not a clean estimate of
verifier limitations or release quality.

V23 isolates whether a stronger local NLI base repairs the V22 transfer
failure. It uses the pinned MIT-licensed
`MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli` checkpoint at revision
`6f5cf0a2b59cabb106aca4c287eed12e357e90eb`. The six local files are
hash-verified by
[`results/v23_stronger_nli_manifest.json`](results/v23_stronger_nli_manifest.json),
and inference runs with network access disabled.

Two controlled development-only ablations reuse the V22 folds, classifiers,
policy search, and gates:

| Signal configuration | Direct accuracy | Direct macro-F1 | Safe support recall | False-support rate | Review recall | Review rate |
|---|---:|---:|---:|---:|---:|---:|
| V22 compact relation + atomic + multi-span | 41.4% | 0.4104 | 0.0% | 0.0% | 73.5% | 49.6% |
| Strong relation; compact atomic + multi-span | 44.4% | 0.4275 | 2.0% | 0.0% | 80.5% | 50.0% |
| Strong relation + atomic; compact multi-span | 45.4% | 0.4402 | 1.0% | 0.0% | 77.5% | 49.6% |

The stronger model improves direct five-way classification, including V22
macro-F1 by 0.0298 in the strongest ablation. It does not solve safe support:
the policy must reject 98–99% of truly supported claims to hold false supports
at zero. Upgrading the atomic signal also loses the review-recall gate.

The full multi-span rescore was stopped before running. It would evaluate
6,208 evidence combinations with a model that is already much slower: relation
scoring took 168.74 seconds for 2,624 spans, and atomic scoring took 144.06
seconds for 565 requirements. The cheaper ablations did not show a credible
path from 1–2% to the required 50% safe support recall.

## Decision

Do not promote V23, package the checkpoint, or spend a fresh confirmation set.
The positive result is that a stronger local relation model improves direct
classification and reaches the review gate in one ablation. The blocking
result is support calibration under the false-support constraint. The next
development experiment should train an explicit support-risk or abstention
objective, instead of adding another general classifier or threshold search.

Jev remains an optional research/review signal. Existing Jev evidence is on a
different three-label RAGTruth slice and does not justify a remote default.
`local_only` and the stable verifier remain unchanged.

Machine-readable ablations:

- [`results/v23_stronger_nli_screen.json`](results/v23_stronger_nli_screen.json)
- [`results/v23_stronger_nli_atomic_screen.json`](results/v23_stronger_nli_atomic_screen.json)

## Reproduce the stronger relation screen

```bash
PYTHONPATH=packages/contexttrace:. HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
  .venv/bin/python -m benchmarks.requirement_alignment.score_v13_relations \
  --dataset /private/tmp/contexttrace_external_data/v21_development.json \
  --split external_fiveway_v21_development \
  --model-path /path/to/DeBERTa-v3-base-mnli-fever-anli \
  --model-manifest benchmarks/requirement_alignment/results/v23_stronger_nli_manifest.json \
  --output /private/tmp/contexttrace_external_data/v23_relation_scores.json \
  --batch-size 16

PYTHONPATH=packages/contexttrace:. .venv/bin/python \
  -m benchmarks.requirement_alignment.v22_domain_candidate \
  --development /private/tmp/contexttrace_external_data/v21_development.json \
  --relation-scores /private/tmp/contexttrace_external_data/v23_relation_scores.json \
  --atomic-scores /private/tmp/contexttrace_external_data/v21_atomic_scores.json \
  --multispan-scores /private/tmp/contexttrace_external_data/v21_multispan_scores.json \
  --experiment contexttrace_v23_stronger_nli_screen \
  --output benchmarks/requirement_alignment/results/v23_stronger_nli_screen.json
```
