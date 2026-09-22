"""Explicitly provision the pinned optional NLI model for offline evaluation."""

from __future__ import annotations

import argparse
from pathlib import Path

from contexttrace.verify.semantic_core_v2.constants import (
    NLI_MODEL_ID,
    NLI_MODEL_REVISION,
)
from contexttrace.verify.semantic_core_v2.nli import (
    NLI_ARTIFACT_FILES,
    verify_nli_artifact,
)


DEFAULT_OUTPUT = Path(
    ".tmp-contexttrace-models/cross-encoder--nli-deberta-v3-small--fa280487"
)


def provision(output: str | Path) -> dict[str, object]:
    """Download only the locked files, then validate every file hash."""

    try:
        from huggingface_hub import snapshot_download
    except ImportError as exc:
        raise RuntimeError(
            "Model provisioning requires the optional NLI dependencies. "
            "Install with: python -m pip install -e 'packages/contexttrace[nli]'"
        ) from exc

    destination = Path(output)
    destination.mkdir(parents=True, exist_ok=True)
    snapshot_download(
        repo_id=NLI_MODEL_ID,
        revision=NLI_MODEL_REVISION,
        local_dir=str(destination),
        allow_patterns=sorted(NLI_ARTIFACT_FILES),
    )
    return verify_nli_artifact(destination)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Explicitly download and verify the pinned local NLI artifact."
    )
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args(argv)
    receipt = provision(args.output)
    print("verified %s at %s" % (receipt["model_id"], Path(args.output).resolve()))
    print("revision: %s" % receipt["model_revision"])
    print("artifact manifest: %s" % receipt["artifact_manifest_sha256"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
