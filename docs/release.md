# PyPI Release

This document describes the release path for the `contexttrace` Python SDK package.

## Package Metadata

The package metadata lives in [packages/contexttrace/pyproject.toml](../packages/contexttrace/pyproject.toml).

Important fields:

- package name: `contexttrace`
- version source: `packages/contexttrace/pyproject.toml` and `contexttrace.__version__`
- PyPI README: `packages/contexttrace/README.md`
- Python support: `>=3.8`
- license: MIT
- console script: `contexttrace = contexttrace.cli:main`

Optional extras:

```bash
pip install "contexttrace[langchain]"
pip install "contexttrace[llamaindex]"
pip install "contexttrace[local]"
pip install "contexttrace[otel]"
pip install "contexttrace[all]"
```

`local` is intentionally dependency-light because local mode uses the SDK's built-in JSON store and HTML report generator.

## Local Build

From the repository root:

```bash
python -m pip install --upgrade build twine
python -m build packages/contexttrace
python -m twine check packages/contexttrace/dist/*
```

This writes:

```text
packages/contexttrace/dist/contexttrace-<version>.tar.gz
packages/contexttrace/dist/contexttrace-<version>-py3-none-any.whl
```

## Local Wheel Smoke Test

Use a clean virtual environment:

```bash
python -m venv .venv-smoke
.venv-smoke\Scripts\python -m pip install --upgrade pip
.venv-smoke\Scripts\python -m pip install packages\contexttrace\dist\contexttrace-0.1.0-py3-none-any.whl
.venv-smoke\Scripts\contexttrace --version
.venv-smoke\Scripts\python -c "from contexttrace import ContextTrace, __version__; print(__version__, ContextTrace)"
```

On macOS or Linux, replace `.venv-smoke\Scripts\python` with `.venv-smoke/bin/python`.

## TestPyPI

The release workflow is [`.github/workflows/release.yml`](../.github/workflows/release.yml).

Recommended first publish:

1. Configure Trusted Publishing for this repository on TestPyPI.
2. Create a GitHub environment named `testpypi`.
3. Run the `Release Python SDK` workflow manually.
4. Select `publish_target=testpypi`.
5. Install from TestPyPI in a clean environment:

```bash
python -m pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ contexttrace
contexttrace --version
```

## PyPI

For production publishing:

1. Configure PyPI Trusted Publishing for this repository.
2. Create a GitHub environment named `pypi`.
3. Confirm the version in `pyproject.toml` and `contexttrace.__version__`.
4. Run the `Release Python SDK` workflow manually.
5. Select `publish_target=pypi`.

The publish jobs use OpenID Connect trusted publishing, so no PyPI API token needs to be stored in repository secrets.

## Version Checklist

Before publishing:

- update `packages/contexttrace/pyproject.toml`
- update `packages/contexttrace/contexttrace/_version.py`
- update `CHANGELOG.md`
- run `python -m pytest -q`
- run `python -m build packages/contexttrace`
- smoke install the built wheel
