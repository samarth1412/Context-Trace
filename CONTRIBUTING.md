# Contributing

Contributions should be focused, tested, and easy to review.

## Development Setup

Clone the repo and install the Python packages:

```bash
cd ContextTrace
python -m pip install -e "apps/api[test]"
python -m pip install -e "packages/contexttrace[test]"
```

Optional local infrastructure:

```bash
docker compose up -d postgres qdrant
cp .env.example .env
```

## Run Checks

```bash
python -m pytest -q
python benchmarks/contexttrace_bench/run_contexttrace.py --mode semantic --case-set all --enforce-sota-gates
bash scripts/release_check.sh
```

On Windows, run the release check with PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/release_check.ps1
```

## Contribution Guidelines

- Keep SDK and API code decoupled.
- Use provider abstractions for LLM judges, embeddings, and answer generation.
- Do not hardcode vendor calls inside business logic.
- Keep reliability outputs explainable and do not hide raw metrics.
- Add tests for new SDK, API, dashboard, integration, or benchmark behavior.
- Update docs and examples when developer-facing APIs change.

## Pull Requests

Before opening a pull request:

1. Keep the change scoped to one feature or fix.
2. Add or update tests.
3. Run the checks above.
4. Update documentation if behavior or APIs changed.
5. Fill out the pull request template.

## Issues

Use issues for bugs, feature requests, docs gaps, and design discussion. For security issues, follow [SECURITY.md](SECURITY.md) instead of opening a public issue.
