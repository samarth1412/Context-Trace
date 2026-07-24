# CAIN 2027 Phase 0 reproduction status

Status date: 2026-07-24

## Audited snapshots

### Public main

- Repository: `https://github.com/samarth1412/Context-Trace`
- Commit: `1f298adf202e0fb3b70032a73e4629bda14bb0ca`
- Verification: `git ls-remote origin refs/heads/main`
- Validation worktree:
  `/tmp/contexttrace-cain-phase0-main-20260724`
- Worktree mode: detached, initially clean

### Current local candidate

- Branch: `agent/unseen-v1-foundation`
- Commit: `b3ec0b45ae3386780bd6209a4a8e7f335ece02e2`
- Relation to public main: eight commits ahead
- Worktree state: 231 non-clean entries
- Most workshop/evaluation artifacts: untracked or ignored

## Host environment

- OS: macOS, Apple Silicon
- Isolated validation interpreter: CPython 3.14.6
- Project-supported versions: Python 3.10–3.13
- Packaging environment:
  `/tmp/contexttrace-cain-phase0-py314-20260724`

The available uv-managed Python 3.11 installation could not create a functional
virtual environment because its relocated base prefix resolved to `/install`.
This audit therefore does not certify Python 3.11 locally. The repository CI
defines Python 3.10–3.13 jobs, but this Phase 0 run did not rerun remote CI.

## Public-main validation results

### Tests and coverage

Command:

```bash
PYTHONWARNINGS='error::ResourceWarning' \
  /tmp/contexttrace-cain-phase0-py314-20260724/bin/python \
  -m pytest -q \
  --cov=contexttrace \
  --cov-report=term-missing \
  --cov-fail-under=80
```

Result:

- Exit: 0
- Tests: 483 passed
- Coverage: 85.90%
- Coverage gate: passed (80%)
- ResourceWarning count: 0
- Other warnings: one third-party `StarletteDeprecationWarning` from
  `fastapi.testclient`
- Runtime: 48.59 seconds

The previously reported SQLAlchemy resource-warning issue is not present on
public main under warnings-as-errors.

### Ruff

Command:

```bash
python -m ruff check --select E9,F601,F63,F7,F82 \
  packages/contexttrace/contexttrace packages/contexttrace/tests
```

Result: exit 0, all checks passed.

### Type check

Command:

```bash
python -m mypy --follow-imports=skip --ignore-missing-imports \
  packages/contexttrace/contexttrace/contracts.py \
  packages/contexttrace/contexttrace/privacy.py
```

Result: exit 0, no issues in two source files.

This is a narrow public-contract type check, not a whole-repository typing
guarantee.

### Dependency audit

Command:

```bash
python -m pip_audit
```

Result:

- Exit: 0
- Known vulnerabilities: none found
- Skipped: local unpublished `contexttrace-api==0.1.0`

### Wheel and sdist build

Command:

```bash
python -m build packages/contexttrace
```

Result:

- Exit: 0
- `contexttrace-1.1.0-py3-none-any.whl`
  - SHA-256:
    `f28ac4e906a23e83da29c0f3a9ced7edc50ffe2d3c0ee65de505e5a67298c631`
- `contexttrace-1.1.0.tar.gz`
  - SHA-256:
    `fb15ee1b9f7043b28c6911c2257e8abd97e4956bb68d0cbc0a42ab368538a518`

The hashes identify this audit build; timestamps make byte-for-byte rebuild
identity a separate reproducibility question.

### Clean wheel installation

Environment:

```text
/tmp/contexttrace-cain-wheel-venv-20260724
```

Commands exercised:

```bash
python -m pip install contexttrace-1.1.0-py3-none-any.whl
contexttrace --version
python -c "from contexttrace import ContextTrace, __version__, load_json_schema; ..."
contexttrace init
contexttrace demo --dataset refund_policy
contexttrace report --last
contexttrace doctor
```

Result:

- Exit: 0
- CLI version: 1.1.0
- Import version: 1.1.0
- TraceV1 packaged schema loaded
- Local initialization passed
- Refund-policy demo generated 10 traces and a report
- Doctor checks passed

The smoke environment used Python 3.14.6 and therefore does not replace the
supported-version CI matrix.

## Current dirty-worktree validation

Tests and quality checks were also run without changing source:

- Tests: 535 passed
- Coverage: 86.08%
- Coverage gate: passed
- ResourceWarning count: 0
- Other warnings: one third-party `StarletteDeprecationWarning`
- Runtime: 49.70 seconds
- Ruff: passed
- Narrow mypy check: passed
- Dependency audit: no known vulnerabilities; local API package skipped

This result is not independently reproducible because 231 worktree entries are
not represented by the local commit.

## Frozen verifier verification

- Declared version: `semantic_v1_calibrated`
- Frozen implementation:
  `packages/contexttrace/contexttrace/verify/facts.py`
- Observed SHA-256:
  `4fa507db2126423c8d0787811e78d0d6ffecf5d7603828b6a6d9b23ca8207bc4`
- Expected test SHA-256: identical
- Legacy rule-pack SHA-256 declaration: identical
- Successor boundary:
  `packages/contexttrace/contexttrace/verify/semantic_core/__init__.py`
- Successor boundary content: documentation-only scaffold
- Successor implementation found: no

The frozen implementation was not modified.

## Schema and compatibility verification

- Public schemas found:
  - TraceV1
  - ClaimVerificationV1
  - DiagnosisV1
  - RepairPlanV1
  - RegressionCaseV1
- Golden trace fixture:
  `packages/contexttrace/tests/fixtures/trace-v1.0.json`
- Fixture SHA-256:
  `13898a738cb44f634b84275f56ed7c7f6dff553a8b0c1f922da406066f6e7804`
- Golden round trip, Draft 2020-12 schema validation, and provenance-preservation
  tests passed as part of the suite.

## Paper compilation

### Public-main ARR manuscript

Compilation sequence:

```bash
pdflatex -interaction=nonstopmode -halt-on-error -output-directory=build main.tex
bibtex build/main
pdflatex -interaction=nonstopmode -halt-on-error -output-directory=build main.tex
pdflatex -interaction=nonstopmode -halt-on-error -output-directory=build main.tex
```

Result:

- Exit: 0
- Pages: 8
- PDF bytes: 234,855
- Audit-build SHA-256:
  `f3d9c4c61282134943f682045a6eea85030b7b22f93c9e5f5757701e8590cf83`
- Undefined citations/references: none found in the final log scan
- Overfull boxes: none found
- Underfull box warnings: present

### Current GroundLM-style manuscript

The dirty current paper was copied to an isolated temporary directory without
auxiliary/build files and compiled with the same four-pass sequence.

Result:

- Exit: 0
- Pages: 9 total
- PDF bytes: 180,714
- Audit-build SHA-256:
  `2012ba00e6ce9dce690e16b5c5400fadb1f0ed5172b578aca56db7c8dcc54a61`
- Undefined citations/references: none found in the final log scan
- Overfull boxes: none found
- Underfull box warnings: present

The repository's existing anonymous `paper/main.pdf` is also nine pages but has
a different build hash. The author-identified
`paper/contexttrace_preprint.pdf` is nine pages and contains author, affiliation,
and email metadata.

## Submission-audit limitation

`paper/audit_submission.py` could not run end to end because this host lacks the
external `pdfinfo` and `pdftotext` executables:

```text
FileNotFoundError: [Errno 2] No such file or directory: 'pdfinfo'
```

Independent fallback checks using `pypdf` confirmed page counts. The script's
anonymity scanner, invoked directly on the clean public-main roots, reported:

- status: passed
- searchable files scanned: 39
- blocking findings: 0

This fallback is not equivalent to the complete PDF text/page audit. Installing
Poppler or running the audit in CI remains required before submission.

## Reproduction blockers

1. The current research candidate is not a clean commit.
2. Most headline workshop datasets and outputs are untracked or ignored.
3. The GroundLM receipt/identifier and final decision are absent; archival
   status is confirmed and the exact submitted PDF is identified by SHA-256
   `ab8f211dc0102a12fbc6691135aecb11a8fe38dc638a4973cac1f3fbab6957ca`.
4. The REALM submission is absent.
5. Python 3.10–3.13 was not locally revalidated in this Phase 0 host.
6. Full submission audit is blocked by missing Poppler tools.
7. `pip-audit` cannot audit the unpublished local API package by PyPI identity.
8. No ContextTrace-Unseen-v1 manifest or data exists.

## Reproduction conclusion

The released public-main engineering surface is healthy on the available host:
tests, coverage, warnings-as-errors for ResourceWarning, Ruff, narrow mypy,
dependency audit, package build, clean install, and paper compilation pass.

The current workshop/research worktree is test-clean but not publication-clean.
Its evidence cannot be treated as a stable CAIN artifact until it is reduced to
an intentional, reviewable, licensed, checksummed snapshot.
