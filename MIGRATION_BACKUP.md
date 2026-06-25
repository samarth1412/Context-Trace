# Migration Backup Notes

This repository includes the source tree plus selected generated artifacts needed
to continue ContextTrace work from a new laptop.

Included backup artifacts:

- `benchmarks/contexttrace_bench/out/` benchmark outputs, RAGTruth release
  bundles, reviewed case packs, calibration reports, and independent-review
  handoff files.
- `.contexttrace/contexttrace.db`, `.contexttrace/reports/`,
  `.contexttrace/suites/`, and `.contexttrace/traces/`.
- `benchmarks/real_world_rag/reports/`, `benchmarks/real_world_rag/traces/`,
  and current real-world RAG result JSON files.
- `.tmp-ragtruth-review/run_assisted_review.py`.
- `packages/contexttrace/dist/` package build artifacts.

Intentionally not included:

- `.env`, because it can contain secrets. Recreate it from `.env.example` on the
  new laptop and fill in API keys locally.
- `node_modules/`, Python caches, pytest caches, build temp directories, and
  cloned third-party repos under `.contexttrace/real_world_repos/`.

After cloning on the new laptop, install dependencies normally and recreate
`.env` from `.env.example`.
