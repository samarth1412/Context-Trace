# Release Runbook

ContextTrace releases the Python SDK from `packages/contexttrace` and publishes
wheel and source distributions to PyPI.

## Prepare

1. Update the version in `packages/contexttrace/pyproject.toml` and
   `packages/contexttrace/contexttrace/_version.py`.
2. Update the package version assertion, changelog, and `release/vX.Y.Z.md`.
3. Confirm generated state remains ignored: `.contexttrace/`, `out/`, build
   directories, temporary environments, logs, and local secrets.
4. Run the full test suite and frontend checks.

## Build And Smoke Test

PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/release_check.ps1
```

macOS/Linux:

```bash
bash scripts/release_check.sh
```

The script builds wheel and sdist artifacts, runs `twine check`, installs the
wheel in a fresh environment, and exercises the CLI, imports, demo, report, and
doctor commands.

Inspect the distributions before publication:

```bash
python -m zipfile -l packages/contexttrace/dist/contexttrace-X.Y.Z-py3-none-any.whl
python -m tarfile -l packages/contexttrace/dist/contexttrace-X.Y.Z.tar.gz
```

No secret, database, report, cache, benchmark output, or local environment file
may appear in either archive.

## Publish

The `Release Python SDK` GitHub Actions workflow uses PyPI trusted publishing.
Run it manually with `publish_target=testpypi` for a release candidate, then
with `publish_target=pypi` after verification.

Tag the exact tested commit:

```bash
git tag vX.Y.Z
git push origin vX.Y.Z
```

Create a GitHub release from that tag using `release/vX.Y.Z.md` and attach the
built wheel, source distribution, and versioned benchmark evidence archive.

Build the evidence archive from the canonical local bundles with:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/package_benchmark_evidence.ps1 -Version X.Y.Z
```

## Verify

Install from PyPI in a new virtual environment and run:

```bash
python -m pip install contexttrace==X.Y.Z
contexttrace --version
contexttrace init
contexttrace demo --dataset refund_policy
contexttrace report --last
contexttrace doctor
python -c "from contexttrace import ContextTrace, __version__; print(__version__, ContextTrace.__name__)"
```

The GitHub tag, GitHub release, PyPI version, package metadata, and CLI version
must all match before the release is complete.
