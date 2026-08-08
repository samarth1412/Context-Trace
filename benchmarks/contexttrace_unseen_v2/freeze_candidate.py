"""Create the fail-closed semantic-core v2.1 candidate freeze record."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import sys
from importlib.metadata import version
from pathlib import Path
from typing import Any

from contexttrace.verify.semantic_core_v2 import TAXONOMY_VERSION, verify_nli_artifact
from contexttrace.verify.semantic_core_v2_1 import (
    ATOMIC_CLAIM_UNITIZER_VERSION,
    COMPLEX_FACT_GUARD_VERSION,
    EVIDENCE_ATTRIBUTION_VERSION,
    GROUPED_CLAIM_NLI_VERSION,
    MAX_IDENTIFIER_SCOPE_TERMS,
    MAX_SCOPE_SEPARATORS,
    OBSERVABLE_CONFLICT_GUARD_VERSION,
    RISK_FEATURE_VERSION,
    SELECTIVE_V2_1_PROFILE,
    SOURCE_CONDITION_REASONER_VERSION,
)

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
METRICS = HERE / "METRICS.json"
PREREGISTRATION = HERE / "PREREGISTRATION.md"
OUTPUT_SCHEMA = (
    REPO_ROOT
    / "packages"
    / "contexttrace"
    / "contexttrace"
    / "schemas"
    / "claim-verification-v2.schema.json"
)
RISK_MODEL = (
    REPO_ROOT
    / "packages"
    / "contexttrace"
    / "contexttrace"
    / "verify"
    / "semantic_core_v2_1"
    / "artifacts"
    / "support-risk-v1.json"
)
SOURCE_ROOTS = (
    "packages/contexttrace/contexttrace/verify/semantic_core_v2",
    "packages/contexttrace/contexttrace/verify/semantic_core_v2_1",
)
SOURCE_FILES = (
    "packages/contexttrace/contexttrace/contracts.py",
    "packages/contexttrace/contexttrace/schemas/claim-verification-v2.schema.json",
    "packages/contexttrace/contexttrace/verify/citations.py",
    "packages/contexttrace/contexttrace/verify/claims.py",
    "packages/contexttrace/contexttrace/verify/evidence.py",
    "packages/contexttrace/contexttrace/verify/facts.py",
    "packages/contexttrace/contexttrace/verify/judges.py",
    "packages/contexttrace/contexttrace/verify/local_ml.py",
    "packages/contexttrace/contexttrace/verify/local_nli.py",
    "packages/contexttrace/contexttrace/verify/schema.py",
    "packages/contexttrace/contexttrace/verify/semantic_normalization.py",
    "packages/contexttrace/contexttrace/verify/spans.py",
    "packages/contexttrace/contexttrace/verify/verdicts.py",
    "benchmarks/contexttrace_unseen_v2/METRICS.json",
    "benchmarks/contexttrace_unseen_v2/PREREGISTRATION.md",
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-path", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    record = freeze_candidate(model_path=args.model_path, output_path=args.output)
    print(
        json.dumps(
            {
                "candidate_commit": record["candidate"]["git_commit"],
                "freeze_payload_sha256": record["freeze_payload_sha256"],
                "profile_sha256": record["candidate"]["profile_sha256"],
            },
            sort_keys=True,
        )
    )
    return 0


def freeze_candidate(*, model_path: Path, output_path: Path) -> dict[str, Any]:
    if (
        output_path.exists()
        or output_path.with_suffix(output_path.suffix + ".sha256").exists()
    ):
        raise FileExistsError("Candidate freeze output already exists.")
    _require_clean_git_tree()
    commit = _git("rev-parse", "HEAD")
    tree = _git("rev-parse", "HEAD^{tree}")
    source_rows = _source_rows()
    model_lock = verify_nli_artifact(model_path)
    metrics = _read_object(METRICS)
    record: dict[str, Any] = {
        "schema_version": "1.0",
        "record_kind": "contexttrace_unseen_v2_candidate_freeze",
        "status": "candidate_frozen_before_unseen_v2_acquisition",
        "candidate": {
            "id": "semantic_core_v2_1_stage7_candidate",
            "git_commit": commit,
            "git_tree": tree,
            "source_manifest_sha256": _canonical_sha256(source_rows),
            "source_files": source_rows,
            "profile_id": SELECTIVE_V2_1_PROFILE.id,
            "profile_sha256": SELECTIVE_V2_1_PROFILE.sha256,
            "profile": SELECTIVE_V2_1_PROFILE.to_dict(),
            "taxonomy_version": TAXONOMY_VERSION,
            "output_schema_sha256": _file_sha256(OUTPUT_SCHEMA),
            "support_risk_artifact_sha256": _file_sha256(RISK_MODEL),
            "complex_fact_guard": {
                "version": COMPLEX_FACT_GUARD_VERSION,
                "max_identifier_scope_terms": MAX_IDENTIFIER_SCOPE_TERMS,
                "max_scope_separators": MAX_SCOPE_SEPARATORS,
            },
            "component_versions": {
                "atomic_claim_unitizer": ATOMIC_CLAIM_UNITIZER_VERSION,
                "complex_fact_guard": COMPLEX_FACT_GUARD_VERSION,
                "evidence_attribution": EVIDENCE_ATTRIBUTION_VERSION,
                "grouped_claim_nli": GROUPED_CLAIM_NLI_VERSION,
                "observable_conflict_guard": OBSERVABLE_CONFLICT_GUARD_VERSION,
                "risk_features": RISK_FEATURE_VERSION,
                "source_condition_reasoner": SOURCE_CONDITION_REASONER_VERSION,
            },
        },
        "nli": {
            "model_id": model_lock["model_id"],
            "model_revision": model_lock["model_revision"],
            "artifact_manifest_sha256": model_lock["artifact_manifest_sha256"],
            "files": model_lock["files"],
        },
        "preregistration": {
            "document_sha256": _file_sha256(PREREGISTRATION),
            "metrics_file_sha256": _file_sha256(METRICS),
            "metrics_payload_sha256": _canonical_sha256(metrics),
            "statistics": metrics["statistics"],
            "sota_candidate_gates": metrics["sota_candidate_gates"],
        },
        "runtime": {
            "python": platform.python_version(),
            "python_implementation": platform.python_implementation(),
            "torch": version("torch"),
            "transformers": version("transformers"),
            "platform": sys.platform,
        },
        "boundaries": {
            "corpus_acquired": False,
            "candidate_executed_on_unseen_v2": False,
            "labels_created": False,
            "labels_accessed": False,
            "annotation_authorized": False,
            "evaluation_authorized": False,
            "release_authorized": False,
        },
    }
    record["freeze_payload_sha256"] = _canonical_sha256(record)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    rendered = json.dumps(record, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    output_path.write_text(rendered, encoding="utf-8")
    sidecar = output_path.with_suffix(output_path.suffix + ".sha256")
    sidecar.write_text(
        f"{_file_sha256(output_path)}  {output_path.name}\n", encoding="utf-8"
    )
    return record


def _source_rows() -> list[dict[str, Any]]:
    relative_paths = set(SOURCE_FILES)
    for root_name in SOURCE_ROOTS:
        root = REPO_ROOT / root_name
        relative_paths.update(
            str(path.relative_to(REPO_ROOT))
            for path in root.rglob("*")
            if path.is_file() and "__pycache__" not in path.parts
        )
    rows = [
        {
            "path": relative,
            "bytes": (REPO_ROOT / relative).stat().st_size,
            "sha256": _file_sha256(REPO_ROOT / relative),
        }
        for relative in sorted(relative_paths)
    ]
    if not rows:
        raise ValueError("Candidate source manifest is empty.")
    return rows


def _require_clean_git_tree() -> None:
    status = _git("status", "--porcelain", "--untracked-files=normal")
    if status:
        raise ValueError("Candidate freeze requires a completely clean Git tree.")


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _read_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"Expected a JSON object: {path}.")
    return value


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _canonical_sha256(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
