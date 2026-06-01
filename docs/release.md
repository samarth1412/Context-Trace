# PyPI Release Checklist

This checklist is for preparing the `contexttrace` Python package for PyPI. Do not publish until every preflight item passes.

## Package Metadata

Verify [packages/contexttrace/pyproject.toml](../packages/contexttrace/pyproject.toml):

- package name is `contexttrace`
- version matches `contexttrace.__version__`
- description matches the local-first SDK/CLI positioning
- `README.md` is the PyPI long description
- Python support is `>=3.8`
- license is MIT
- classifiers include development status, audience, license, and supported Python versions
- runtime dependencies are minimal: `click`, `httpx`, `typing-extensions`
- optional extras cover LangChain, LlamaIndex, FastAPI, LangGraph, OpenTelemetry, and `all`
- project URLs point to the GitHub repository, docs, issues, and changelog
- CLI entrypoint is `contexttrace = contexttrace.cli:main`

## Package Data

ContextTrace currently keeps required runtime assets inside the package:

- HTML report templates and CSS are embedded in `contexttrace.report`
- demo datasets are embedded in `contexttrace.demo_data`
- default config generation is embedded in `contexttrace.config`
- type marker is `contexttrace/py.typed`

The package manifest is [packages/contexttrace/MANIFEST.in](../packages/contexttrace/MANIFEST.in). It includes package sources and excludes local/private artifacts such as:

- `.contexttrace/`
- local SQLite databases
- `.env`
- build outputs
- caches
- logs
- test outputs

## Local Build

Use the scripted check from the repository root.

PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/release_check.ps1
```

macOS/Linux shell:

```bash
bash scripts/release_check.sh
```

The script cleans previous build outputs, builds the package, runs `twine check`, installs the built wheel in a fresh virtual environment, and verifies:

- `contexttrace --version`
- package imports
- `contexttrace init`
- `contexttrace demo --dataset refund_policy`
- `contexttrace report --last`
- `contexttrace doctor`

Manual equivalent:

```bash
cd packages/contexttrace
rm -rf dist build *.egg-info
python -m pip install --upgrade build twine
python -m build
python -m twine check dist/*
```

This writes:

```text
packages/contexttrace/dist/contexttrace-0.1.0.tar.gz
packages/contexttrace/dist/contexttrace-0.1.0-py3-none-any.whl
```

## Artifact Inspection

Inspect the built wheel and source distribution before publishing:

```bash
python - <<'PY'
import tarfile
import zipfile
from pathlib import Path

dist = Path("packages/contexttrace/dist")
for path in sorted(dist.iterdir()):
    print(path.name)
    if path.suffix == ".whl":
        with zipfile.ZipFile(path) as zf:
            for name in zf.namelist():
                print(" ", name)
    elif path.suffixes[-2:] == [".tar", ".gz"]:
        with tarfile.open(path) as tf:
            for name in tf.getnames():
                print(" ", name)
PY
```

Confirm no local/private files are present.

## Installed Wheel Smoke Test

Use a clean virtual environment:

```bash
python -m venv .venv-smoke
.venv-smoke\Scripts\python -m pip install packages\contexttrace\dist\contexttrace-0.1.0-py3-none-any.whl
.venv-smoke\Scripts\contexttrace --version
.venv-smoke\Scripts\contexttrace init
.venv-smoke\Scripts\contexttrace demo --dataset refund_policy
.venv-smoke\Scripts\contexttrace report --last
.venv-smoke\Scripts\contexttrace doctor
.venv-smoke\Scripts\python -c "from contexttrace import ContextTrace, __version__; print(__version__, ContextTrace)"
```

On macOS or Linux, replace `.venv-smoke\Scripts\...` with `.venv-smoke/bin/...`.

## TestPyPI

Recommended first publish:

1. Run the local release check:

```bash
bash scripts/release_check.sh
```

2. Upload to TestPyPI only after the local check passes:

```bash
cd packages/contexttrace
python -m twine upload --repository testpypi dist/*
```

3. Install from TestPyPI in a clean environment:

```bash
python -m venv .venv-testpypi
.venv-testpypi\Scripts\python -m pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ contexttrace
.venv-testpypi\Scripts\contexttrace --version
.venv-testpypi\Scripts\contexttrace init
.venv-testpypi\Scripts\contexttrace demo --dataset refund_policy
.venv-testpypi\Scripts\contexttrace report --last
.venv-testpypi\Scripts\contexttrace doctor
.venv-testpypi\Scripts\python -c "from contexttrace import ContextTrace, __version__; print(__version__, ContextTrace)"
```

On macOS or Linux, replace `.venv-testpypi\Scripts\...` with `.venv-testpypi/bin/...`.

These commands verify package imports, CLI entrypoint, demo dataset loading, and local report generation from the TestPyPI package.

If using GitHub trusted publishing instead of local upload:

1. Configure Trusted Publishing for this repository on TestPyPI.
2. Create a GitHub environment named `testpypi`.
3. Run the `Release Python SDK` workflow manually.
4. Select `publish_target=testpypi`.

## PyPI

For production publishing:

1. Run the local release check:

```bash
bash scripts/release_check.sh
```

PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/release_check.ps1
```

2. Upload to real PyPI:

```bash
cd packages/contexttrace
python -m twine upload dist/*
```

When prompted:

- username: `__token__`
- password: your PyPI API token

3. Verify the published package from PyPI in a fresh environment:

```bash
python -m venv .venv-pypi
.venv-pypi\Scripts\python -m pip install contexttrace
.venv-pypi\Scripts\contexttrace --version
.venv-pypi\Scripts\contexttrace init
.venv-pypi\Scripts\contexttrace demo --dataset refund_policy
.venv-pypi\Scripts\contexttrace report --last --open
.venv-pypi\Scripts\contexttrace doctor
.venv-pypi\Scripts\python -c "from contexttrace import ContextTrace, __version__; print(__version__, ContextTrace)"
```

On macOS or Linux, replace `.venv-pypi\Scripts\...` with `.venv-pypi/bin/...`.

If using GitHub trusted publishing instead of local upload:

1. Configure PyPI Trusted Publishing for this repository.
2. Create a GitHub environment named `pypi`.
3. Confirm the version in `pyproject.toml` and `contexttrace.__version__`.
4. Confirm `CHANGELOG.md` has release notes.
5. Run the `Release Python SDK` workflow manually.
6. Select `publish_target=pypi`.

The publish jobs use OpenID Connect trusted publishing, so no PyPI API token needs to be stored in repository secrets.

## GitHub Release And Tag

After PyPI publish and verification:

```bash
git tag v0.1.0
git push origin v0.1.0
```

Create a GitHub release from the `v0.1.0` tag using [release/v0.1.0.md](../release/v0.1.0.md) as the release notes.

## Final Preflight

- `python -m pytest`
- clean user install: `pip install -e packages/contexttrace`
- `contexttrace --version`
- `contexttrace init`
- `contexttrace demo --dataset refund_policy`
- `contexttrace report --last`
- `contexttrace doctor`
- post-publish PyPI install works in a fresh environment
- `twine check` passes
- built artifacts contain no `.env`, `.contexttrace`, local databases, reports, caches, logs, or API keys
- publishing is performed only after release checks and artifact inspection pass
