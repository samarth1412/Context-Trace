#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PACKAGE_DIR="$ROOT_DIR/packages/contexttrace"
SMOKE_DIR="$ROOT_DIR/.tmp-release-check"
PYTHON_BIN="${PYTHON:-python}"

echo "==> Cleaning previous builds"
rm -rf "$PACKAGE_DIR/dist" "$PACKAGE_DIR/build" "$PACKAGE_DIR"/*.egg-info "$SMOKE_DIR"

echo "==> Installing build tools"
"$PYTHON_BIN" -m pip install --upgrade build twine

echo "==> Building package"
(
  cd "$PACKAGE_DIR"
  "$PYTHON_BIN" -m build
  "$PYTHON_BIN" -m twine check dist/*
)

echo "==> Creating wheel smoke-test environment"
"$PYTHON_BIN" -m venv "$SMOKE_DIR/venv"

if [[ -x "$SMOKE_DIR/venv/Scripts/python.exe" ]]; then
  VENV_PY="$SMOKE_DIR/venv/Scripts/python.exe"
  VENV_CONTEXTTRACE="$SMOKE_DIR/venv/Scripts/contexttrace.exe"
else
  VENV_PY="$SMOKE_DIR/venv/bin/python"
  VENV_CONTEXTTRACE="$SMOKE_DIR/venv/bin/contexttrace"
fi

WHEEL_PATH="$(ls "$PACKAGE_DIR"/dist/contexttrace-*.whl | head -n 1)"

echo "==> Installing built wheel"
"$VENV_PY" -m pip install "$WHEEL_PATH"

echo "==> Running installed-package smoke test"
mkdir -p "$SMOKE_DIR/work"
(
  cd "$SMOKE_DIR/work"
  "$VENV_CONTEXTTRACE" --version
  "$VENV_PY" -c "from contexttrace import ContextTrace, __version__; print(__version__, ContextTrace.__name__)"
  "$VENV_CONTEXTTRACE" init
  "$VENV_CONTEXTTRACE" demo --dataset refund_policy
  "$VENV_CONTEXTTRACE" report --last
  "$VENV_CONTEXTTRACE" doctor
)

echo "==> Release check passed"
