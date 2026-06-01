# Contributing

Thanks for helping improve ContextTrace. The project is early, so the best contributions are focused, tested, and easy to review.

## Development Setup

Clone the repo and install the Python packages:

```bash
cd ContextTrace
python -m pip install -e "apps/api[test]"
python -m pip install -e "packages/contexttrace[test]"
```

Install the web dependencies:

```bash
cd apps/web
npm install
```

Optional local infrastructure:

```bash
docker compose up -d postgres qdrant
cp .env.example .env
```

## Run Checks

```bash
python -m pytest -q
cd apps/web
npm run typecheck
npm run build
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
