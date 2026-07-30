"""Canonical hashing and lock validation shared by Phase 6 tools."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import platform
from pathlib import Path
from typing import Any, Mapping


class EvaluationIntegrityError(RuntimeError):
    """Raised before evaluation when any frozen identity is inconsistent."""


def canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_json(value)).hexdigest()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
    except OSError as exc:
        raise EvaluationIntegrityError(f"Could not hash {path}: {exc}") from exc
    return digest.hexdigest()


def load_json_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise EvaluationIntegrityError(f"Could not load {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise EvaluationIntegrityError(f"{path} must contain a JSON object.")
    return value


def verify_payload_hash(
    record: Mapping[str, Any],
    *,
    field: str = "payload_sha256",
) -> str:
    expected = record.get(field)
    if not isinstance(expected, str) or len(expected) != 64:
        raise EvaluationIntegrityError(f"Missing or invalid {field}.")
    identity = dict(record)
    identity.pop(field)
    actual = canonical_sha256(identity)
    if actual != expected:
        raise EvaluationIntegrityError(
            f"{field} mismatch: expected {expected}, computed {actual}."
        )
    return actual


def verify_implementation_sources(
    repository_root: Path,
    implementation_lock: Mapping[str, Any],
) -> None:
    manifest = implementation_lock.get("source_manifest")
    if not isinstance(manifest, list) or not manifest:
        raise EvaluationIntegrityError("Implementation source manifest is absent.")
    rows: list[dict[str, Any]] = []
    root = repository_root.resolve()
    for raw in manifest:
        if not isinstance(raw, Mapping):
            raise EvaluationIntegrityError("Implementation source row is invalid.")
        relative = Path(str(raw.get("path") or ""))
        target = (root / relative).resolve()
        if root != target and root not in target.parents:
            raise EvaluationIntegrityError("Implementation path escapes repository.")
        digest = file_sha256(target)
        size = target.stat().st_size
        if digest != raw.get("sha256") or size != raw.get("bytes"):
            raise EvaluationIntegrityError(
                f"Frozen implementation source changed: {relative}."
            )
        rows.append({"path": relative.as_posix(), "bytes": size, "sha256": digest})
    expected = implementation_lock.get("implementation", {}).get(
        "source_manifest_sha256"
    )
    if canonical_sha256(rows) != expected:
        raise EvaluationIntegrityError("Implementation source-manifest hash mismatch.")


def verify_phase6_locks(repository_root: Path) -> dict[str, dict[str, Any]]:
    research_root = repository_root / "research" / "cain2027"
    names = {
        "evaluation": "EVALUATION_CONFIG.json",
        "implementation": "IMPLEMENTATION_LOCK.json",
        "dependencies": "DEPENDENCY_LOCK.json",
        "ablations": "ABLATION_CONFIG.json",
    }
    records = {
        key: load_json_object(research_root / filename)
        for key, filename in names.items()
    }
    for record in records.values():
        verify_payload_hash(record)
    verify_implementation_sources(repository_root, records["implementation"])
    baseline_record = load_json_object(
        repository_root / "benchmarks/contexttrace_unseen_v1/BASELINE_RUN_RECORD.json"
    )
    verify_payload_hash(baseline_record, field="record_payload_sha256")
    dataset_freeze = load_json_object(
        repository_root
        / "benchmarks/contexttrace_unseen_v1/two_track_freeze_record.json"
    )
    phase3_lock = load_json_object(research_root / "PHASE3_INFRASTRUCTURE_LOCK.json")

    evaluation = records["evaluation"]
    implementation = records["implementation"]
    dependencies = records["dependencies"]
    ablations = records["ablations"]
    candidate = evaluation.get("candidate_system", {})
    frozen = implementation.get("frozen_boundaries", {})
    if candidate.get("implementation_source_manifest_sha256") != implementation.get(
        "implementation", {}
    ).get("source_manifest_sha256"):
        raise EvaluationIntegrityError("Evaluation and implementation locks disagree.")
    if candidate.get("output_schema_sha256") != frozen.get(
        "candidate_output_schema_sha256"
    ):
        raise EvaluationIntegrityError("Candidate output-schema locks disagree.")
    if dependencies.get("nli", {}).get("artifact_manifest_sha256") != frozen.get(
        "nli_artifact_manifest_sha256"
    ):
        raise EvaluationIntegrityError("NLI artifact locks disagree.")
    if dataset_freeze.get("artifact_chain", {}).get(
        "frozen_manifest_payload_sha256"
    ) != evaluation.get("dataset", {}).get("frozen_manifest_payload_sha256"):
        raise EvaluationIntegrityError("Dataset freeze and evaluation locks disagree.")
    annotation_schema = (
        repository_root / "benchmarks/contexttrace_unseen_v1/ANNOTATION_SCHEMA.json"
    )
    phase3_artifacts = {
        row.get("path"): row.get("sha256")
        for row in phase3_lock.get("artifacts", [])
        if isinstance(row, Mapping)
    }
    if file_sha256(annotation_schema) != phase3_artifacts.get(
        "benchmarks/contexttrace_unseen_v1/ANNOTATION_SCHEMA.json"
    ):
        raise EvaluationIntegrityError("Frozen annotation schema changed.")
    candidate_profile = ablations.get("candidate_profile", {})
    ablation_profiles = list(ablations.get("ablations", []))
    if (
        not isinstance(candidate_profile, Mapping)
        or not isinstance(candidate_profile.get("sha256"), str)
        or any(
            not isinstance(row, Mapping)
            or not isinstance(row.get("profile_sha256"), str)
            for row in ablation_profiles
        )
    ):
        raise EvaluationIntegrityError("Ablation profile lock is invalid.")
    return {
        **records,
        "baseline_run": baseline_record,
        "dataset_freeze": dataset_freeze,
        "phase3": phase3_lock,
    }


def verify_runtime_environment(
    repository_root: Path,
    dependency_lock: Mapping[str, Any],
) -> dict[str, Any]:
    runtime = dependency_lock.get("runtime", {})
    actual_python = platform.python_version()
    if actual_python != runtime.get("python"):
        raise EvaluationIntegrityError(
            f"Python lock mismatch: expected {runtime.get('python')}, "
            f"found {actual_python}."
        )
    pyproject = repository_root / "packages/contexttrace/pyproject.toml"
    if file_sha256(pyproject) != runtime.get("contexttrace_pyproject_sha256"):
        raise EvaluationIntegrityError("Frozen ContextTrace pyproject changed.")
    actual_packages: dict[str, str] = {}
    for package, expected in dependency_lock.get("packages", {}).items():
        try:
            actual = importlib.metadata.version(str(package))
        except importlib.metadata.PackageNotFoundError as exc:
            raise EvaluationIntegrityError(
                f"Frozen dependency is absent: {package}."
            ) from exc
        if actual != expected:
            raise EvaluationIntegrityError(
                f"Dependency lock mismatch for {package}: "
                f"expected {expected}, found {actual}."
            )
        actual_packages[str(package)] = actual
    return {
        "python": actual_python,
        "implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "packages": actual_packages,
    }


def require_execution_authorization(
    path: Path,
    evaluation_config: Mapping[str, Any],
    ablation_config: Mapping[str, Any],
    *,
    expected_source_manifest_sha256: str | None = None,
) -> dict[str, Any]:
    authorization = load_json_object(path)
    if authorization.get("record_kind") != (
        "contexttrace_cain2027_phase6_execution_authorization"
    ):
        raise EvaluationIntegrityError("Wrong Phase 6 authorization record kind.")
    if authorization.get("authorized") is not True:
        raise EvaluationIntegrityError("Phase 6 execution is not authorized.")
    dataset = evaluation_config["dataset"]
    candidate = evaluation_config["candidate_system"]
    expected = {
        "dataset_id": dataset["id"],
        "manifest_payload_sha256": dataset["frozen_manifest_payload_sha256"],
        "case_count": dataset["case_count"],
        "implementation_source_manifest_sha256": candidate[
            "implementation_source_manifest_sha256"
        ],
        "candidate_profile_sha256": candidate["profile_sha256"],
        "ablation_config_payload_sha256": ablation_config["payload_sha256"],
    }
    if expected_source_manifest_sha256 is not None:
        expected["source_manifest_file_sha256"] = expected_source_manifest_sha256
    for field, value in expected.items():
        if authorization.get(field) != value:
            raise EvaluationIntegrityError(
                f"Phase 6 authorization mismatch for {field}."
            )
    if authorization.get("one_time_sealed_run") is not True:
        raise EvaluationIntegrityError("Authorization must name the one-time run.")
    verify_payload_hash(authorization)
    return authorization
