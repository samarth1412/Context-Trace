"""Pinned local-NLI artifact validation and construction."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from contexttrace.verify.local_nli import LocalNLIError, LocalNLIJudge

from .constants import (
    NLI_ARTIFACT_MANIFEST_SHA256,
    NLI_MAX_LENGTH,
    NLI_MODEL_ID,
    NLI_MODEL_REVISION,
)


NLI_ARTIFACT_FILES = {
    "README.md": "a9aa108025ad1984374c5e80365406bafe331aea5abc30239e1796ec0a7c267d",
    "added_tokens.json": "a4b6bfe668f2b3cf6f0cd535e98a0663d2d0d4a4a15f13075ad3597d33985a23",
    "config.json": "885d0dceae8fa5c136da9209121ec9eb11160488e840de3bc1f29353674e5712",
    "model.safetensors": "ebc79588dd73ccfb6a3f6078519cfbf512c5305384c5ea1845bc71cd32216e86",
    "special_tokens_map.json": "ed7c099c988dbb414b18a6980d20cb57b91b7cd119f6f6941eb364b0e892e712",
    "spm.model": "c679fbf93643d19aab7ee10c0b99e460bdbc02fedf34b92b05af343b4af586fd",
    "tokenizer.json": "5124ef2ead1a10a717703bc436de7f353da76d6340e4587719b42b1693707964",
    "tokenizer_config.json": "f3eecd07c370ef0bf7dd3780d3cd68cf9c8b00c267e21a208ddcd8f82bfec1a6",
}


class V2NLIArtifactError(LocalNLIError):
    """Raised when the frozen v2 NLI artifact differs from its lock."""


def verify_nli_artifact(model_path: str | Path) -> dict[str, Any]:
    root = Path(model_path)
    if not root.is_dir():
        raise V2NLIArtifactError("The v2 NLI model path must be a local directory.")
    rows: list[dict[str, Any]] = []
    for relative, expected in sorted(NLI_ARTIFACT_FILES.items()):
        path = root / relative
        if not path.is_file():
            raise V2NLIArtifactError(f"Frozen NLI artifact is missing {relative}.")
        digest = _file_sha256(path)
        if digest != expected:
            raise V2NLIArtifactError(f"Frozen NLI artifact hash mismatch: {relative}.")
        rows.append(
            {
                "path": relative,
                "bytes": path.stat().st_size,
                "sha256": digest,
            }
        )
    manifest_hash = hashlib.sha256(
        json.dumps(rows, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    if manifest_hash != NLI_ARTIFACT_MANIFEST_SHA256:
        raise V2NLIArtifactError("Frozen NLI artifact manifest hash mismatch.")
    return {
        "model_id": NLI_MODEL_ID,
        "model_revision": NLI_MODEL_REVISION,
        "artifact_manifest_sha256": manifest_hash,
        "files": rows,
    }


def build_pinned_nli(model_path: str | Path) -> LocalNLIJudge:
    verify_nli_artifact(model_path)
    return LocalNLIJudge(
        model_path=str(model_path),
        tokenizer_path=str(model_path),
        backend="transformers",
        max_length=NLI_MAX_LENGTH,
    )


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()
