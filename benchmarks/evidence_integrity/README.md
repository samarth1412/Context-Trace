# Evidence-integrity acceptance benchmark

This offline benchmark freezes the deterministic contract shipped by ContextTrace
1.3. It measures whether captured source-to-selection lineage reports the exact
observed issue, leaves missing or invalid capture unknown, and avoids a passing
result when a declared loss is present.

The development and held-out case IDs are disjoint. Both files are SHA-256 locked
in `manifest.json`. Expected outcomes live beside each trace for scoring, but the
runner constructs `RAGTrace` from the `trace` object alone. It rejects nested
`expected` or `label` keys in that object. No model or network provider is used.

The cases are fictional contract tests, not a natural-traffic quality study or a
SOTA benchmark. The LangChain and LlamaIndex slices represent traces produced by
the public bindings; separate package tests exercise installed framework objects.

Run development while changing the benchmark runner:

```bash
PYTHONPATH=packages/contexttrace python -m benchmarks.evidence_integrity.run \
  --cases benchmarks/evidence_integrity/development_cases.json \
  --split development \
  --manifest benchmarks/evidence_integrity/manifest.json
```

Run the frozen release gate:

```bash
PYTHONPATH=packages/contexttrace python -m benchmarks.evidence_integrity.run \
  --cases benchmarks/evidence_integrity/heldout_cases.json \
  --split heldout \
  --manifest benchmarks/evidence_integrity/manifest.json \
  --output benchmarks/evidence_integrity/results/heldout_report.json
```

The gate requires 100% exact case outcomes, zero dangerous false greens, 100%
exact handling of unknown cases, and zero model or network calls. Per-issue and
per-framework metrics are included in the report.
