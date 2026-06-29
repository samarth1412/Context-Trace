from __future__ import annotations

import subprocess
from pathlib import Path


ANONYMOUS_REVISION = "anonymous_artifact"


def repository_revision(repo_root: str | Path) -> str:
    root = Path(repo_root).resolve()
    try:
        discovered = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=root,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        if Path(discovered).resolve() != root:
            return ANONYMOUS_REVISION
        return subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    except (FileNotFoundError, subprocess.CalledProcessError):
        return ANONYMOUS_REVISION
