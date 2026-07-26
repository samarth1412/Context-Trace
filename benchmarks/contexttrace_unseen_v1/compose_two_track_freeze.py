"""Compose and privately freeze the two completed ContextTrace-Unseen-v1 tracks.

This is an offline Gate C operation. It performs no model, verifier, NLI,
annotation, scoring, publication, or release action.
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from benchmarks.contexttrace_unseen_v1.freeze_manifest import (
    BYTE_NORMALIZED_HASH,
    SEMANTIC_NORMALIZED_HASH,
    FreezeError,
    file_sha256,
    freeze_manifest,
    normalized_text_sha256,
    verify_frozen_manifest,
    write_frozen_manifest,
)


NATURAL_SOURCE_SHA256 = (
    "6508533e869ef99930a4b29bea699779438a79dd951a8dbf2d04c78804bd90cc"
)
TEMPORAL_SOURCE_SHA256 = (
    "6b3bbd4dff5ed7a2a80e26f87a7cf17a670be92083071526d33c2a3f60abf96e"
)
NATURAL_CASE_SHA256 = (
    "f3b94896f5b66cc725d25b4d85badb48d0411bb601f5aaa7d6b47907d4fa3e13"
)
TEMPORAL_CASE_SHA256 = (
    "e7b106530417f111148e4bda57dc55623cecc046b676b74be5f8109358525e7a"
)
NATURAL_FROZEN_PAYLOAD_SHA256 = (
    "4ac9270ad3ac056e605bd7ec4623493293d83e7c2bf8d2b1e71fb28292e92fa2"
)
TEMPORAL_PRIVATE_FREEZE_FILE_SHA256 = (
    "2d6fefc158c584a04fb484e16ee283faaa44926f1d9cc5968e5bd83a269cba91"
)
CALIBRATION_REGISTRY_SHA256 = (
    "8d071cc9857169e86df43843bd45fc2a93e66b28a802b5040ffffb23ff43efdb"
)
NATURAL_SCHEDULE_SHA256 = (
    "e850d3eb6d374547cdbc70b2c0da02e0db8d9ff043633a577d9319f3d69e1695"
)
TEMPORAL_SCHEDULE_SHA256 = (
    "b6250401aadaaf913d7a8e9a5f095d2816cb798f9d512340d0702b8bb233340d"
)
COMPOSITE_ONTOLOGY_VERSION = (
    "contexttrace-unseen-v1-composite-domain-ontology-1.0"
)


class CompositionError(RuntimeError):
    """A frozen-input or Gate C composition invariant failed."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CompositionError(f"Could not load {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise CompositionError(f"{path} must contain a JSON object.")
    return value


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(
        json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def require_hash(path: Path, expected: str, *, label: str) -> None:
    if not path.is_file() or file_sha256(path) != expected:
        raise CompositionError(f"{label} differs from its frozen SHA-256.")


def _validate_input_sets(
    natural_sources: Mapping[str, Any],
    temporal_sources: Mapping[str, Any],
    natural_cases: Mapping[str, Any],
    temporal_cases: Mapping[str, Any],
) -> None:
    natural_source_ids = {
        str(source["source_id"]) for source in natural_sources["sources"]
    }
    temporal_source_ids = {
        str(source["source_id"]) for source in temporal_sources["sources"]
    }
    natural_case_ids = {
        str(case["case_id"]) for case in natural_cases["cases"]
    }
    temporal_case_ids = {
        str(case["case_id"]) for case in temporal_cases["cases"]
    }
    if natural_source_ids & temporal_source_ids:
        raise CompositionError("Source IDs overlap between frozen tracks.")
    if natural_case_ids & temporal_case_ids:
        raise CompositionError("Case IDs overlap between frozen tracks.")
    if (
        len(natural_source_ids) != 36
        or len(temporal_source_ids) != 37
        or len(natural_case_ids) != 393
        or len(temporal_case_ids) != 100
    ):
        raise CompositionError("Frozen track counts changed.")
    if any(case["track"] != "natural_ood" for case in natural_cases["cases"]):
        raise CompositionError("Natural candidate manifest has another track.")
    if any(
        case["track"] != "temporal_source_condition"
        for case in temporal_cases["cases"]
    ):
        raise CompositionError("Temporal candidate manifest has another track.")
    for manifest in (natural_cases, temporal_cases):
        access = manifest["label_access"]
        if (
            access["labels_created"]
            or access["labels_accessible"]
            or access["first_accessed_at"] is not None
        ):
            raise CompositionError("Labels existed before two-track freeze.")
    if any(
        case["verifier_history"]
        for manifest in (natural_cases, temporal_cases)
        for case in manifest["cases"]
    ):
        raise CompositionError("A candidate case has verifier history.")


def _semantic_fingerprints(
    sources: Sequence[Mapping[str, Any]], root: Path
) -> dict[str, str]:
    return {
        str(source["source_id"]): normalized_text_sha256(
            root / str(source["normalized_text_path"])
        )
        for source in sources
    }


def _uniform_leakage_audit(
    *,
    project_root: Path,
    natural_sources: Mapping[str, Any],
    temporal_sources: Mapping[str, Any],
    calibration: Mapping[str, Any],
    natural_acquisition_root: Path,
    temporal_acquisition_root: Path,
) -> dict[str, Any]:
    natural = _semantic_fingerprints(
        natural_sources["sources"], natural_acquisition_root
    )
    temporal = _semantic_fingerprints(
        temporal_sources["sources"], temporal_acquisition_root
    )
    calibration_values = _semantic_fingerprints(
        calibration["sources"], project_root
    )
    candidate = {**natural, **temporal}
    if len(candidate) != len(natural) + len(temporal):
        raise CompositionError("Candidate source IDs collide.")
    by_hash: dict[str, list[str]] = {}
    for source_id, digest in candidate.items():
        by_hash.setdefault(digest, []).append(source_id)
    candidate_collisions = {
        digest: ids for digest, ids in by_hash.items() if len(ids) > 1
    }
    calibration_hashes = set(calibration_values.values())
    calibration_collisions = {
        source_id: digest
        for source_id, digest in candidate.items()
        if digest in calibration_hashes
    }
    if candidate_collisions or calibration_collisions:
        raise CompositionError(
            "Uniform semantic fingerprint leakage detected."
        )
    return {
        "method": SEMANTIC_NORMALIZED_HASH,
        "candidate_source_count": len(candidate),
        "unique_candidate_fingerprints": len(set(candidate.values())),
        "candidate_duplicate_groups": 0,
        "calibration_source_count": len(calibration_values),
        "candidate_calibration_collisions": 0,
    }


def _hardlink_verified(
    *,
    source_root: Path,
    relative_path: str,
    destination_root: Path,
    expected_sha256: str | None,
) -> None:
    relative = Path(relative_path)
    if relative.is_absolute() or ".." in relative.parts:
        raise CompositionError(f"Unsafe artifact path: {relative_path}")
    source = source_root / relative
    if not source.is_file():
        raise CompositionError(f"Missing frozen artifact: {source}")
    actual = file_sha256(source)
    if expected_sha256 is not None and actual != expected_sha256:
        raise CompositionError(f"Frozen artifact hash changed: {source}")
    destination = destination_root / relative
    if destination.is_file():
        if file_sha256(destination) != actual:
            raise CompositionError(
                f"Composite artifact collision: {relative_path}"
            )
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.link(source, destination)
    except OSError:
        shutil.copy2(source, destination)
    if file_sha256(destination) != actual:
        raise CompositionError(
            f"Composite artifact copy changed: {relative_path}"
        )


def _materialize_artifacts(
    *,
    artifact_root: Path,
    natural_sources: Mapping[str, Any],
    temporal_sources: Mapping[str, Any],
    natural_cases: Mapping[str, Any],
    temporal_cases: Mapping[str, Any],
    natural_acquisition_root: Path,
    temporal_acquisition_root: Path,
    natural_collection_root: Path,
    temporal_collection_root: Path,
) -> None:
    for manifest, root in (
        (natural_sources, natural_acquisition_root),
        (temporal_sources, temporal_acquisition_root),
    ):
        for source in manifest["sources"]:
            _hardlink_verified(
                source_root=root,
                relative_path=str(source["snapshot_path"]),
                destination_root=artifact_root,
                expected_sha256=str(source["snapshot_sha256"]),
            )
            _hardlink_verified(
                source_root=root,
                relative_path=str(source["normalized_text_path"]),
                destination_root=artifact_root,
                expected_sha256=None,
            )
    for manifest, root in (
        (natural_cases, natural_collection_root),
        (temporal_cases, temporal_collection_root),
    ):
        for case in manifest["cases"]:
            _hardlink_verified(
                source_root=root,
                relative_path=str(case["trace_artifact_path"]),
                destination_root=artifact_root,
                expected_sha256=str(case["trace_sha256"]),
            )


def _combined_source_manifest(
    natural: Mapping[str, Any],
    temporal: Mapping[str, Any],
    *,
    composed_at: str,
) -> dict[str, Any]:
    if natural["disjoint_dimensions"] != temporal["disjoint_dimensions"]:
        raise CompositionError("Track disjointness dimensions differ.")
    sources: list[dict[str, Any]] = []
    for track, manifest, hash_kind in (
        ("natural_ood", natural, SEMANTIC_NORMALIZED_HASH),
        ("temporal_source_condition", temporal, BYTE_NORMALIZED_HASH),
    ):
        for value in manifest["sources"]:
            source = copy.deepcopy(value)
            source["metadata"]["composite_origin_track"] = track
            source["metadata"]["normalized_content_hash_kind"] = hash_kind
            sources.append(source)
    return {
        "schema_version": "1.0",
        "manifest_kind": "contexttrace_unseen_v1_sources",
        "created_at": composed_at,
        "domain_ontology_version": COMPOSITE_ONTOLOGY_VERSION,
        "disjoint_dimensions": list(natural["disjoint_dimensions"]),
        "sources": sorted(sources, key=lambda source: source["source_id"]),
    }


def _combined_case_manifest(
    natural: Mapping[str, Any],
    temporal: Mapping[str, Any],
    *,
    composed_at: str,
) -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "manifest_kind": "contexttrace_unseen_v1_cases",
        "created_at": composed_at,
        "collection_protocol_version": (
            "contexttrace-unseen-two-track-composition-v1"
        ),
        "claim_policy_version": "contexttrace-unseen-claim-policy-v1",
        "label_access": {
            "labels_created": False,
            "labels_accessible": False,
            "first_accessed_at": None,
            "custodian": None,
        },
        "cases": sorted(
            [
                *copy.deepcopy(natural["cases"]),
                *copy.deepcopy(temporal["cases"]),
            ],
            key=lambda case: case["case_id"],
        ),
    }


def compose(args: argparse.Namespace) -> dict[str, Any]:
    project_root = args.project_root.resolve()
    base = project_root / "benchmarks/contexttrace_unseen_v1"
    output_root = args.output_root.resolve()
    output_root.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(output_root, 0o700)

    paths = {
        "natural_source": base / "candidate_source_manifest.json",
        "temporal_source": base / "temporal_source_manifest.json",
        "calibration": base / "calibration/registry.json",
        "natural_case": args.natural_collection_root
        / "candidate_case_manifest.json",
        "temporal_case": args.temporal_collection_root
        / "candidate_case_manifest.json",
        "natural_freeze": args.natural_collection_root
        / "frozen_unlabeled_manifest.json",
        "temporal_freeze": args.temporal_collection_root
        / "frozen/temporal_unlabeled_manifest.json",
    }
    for key, expected in (
        ("natural_source", NATURAL_SOURCE_SHA256),
        ("temporal_source", TEMPORAL_SOURCE_SHA256),
        ("calibration", CALIBRATION_REGISTRY_SHA256),
        ("natural_case", NATURAL_CASE_SHA256),
        ("temporal_case", TEMPORAL_CASE_SHA256),
        ("temporal_freeze", TEMPORAL_PRIVATE_FREEZE_FILE_SHA256),
    ):
        require_hash(paths[key], expected, label=key)
    natural_frozen = load_json(paths["natural_freeze"])
    verify_frozen_manifest(
        natural_frozen,
        expected_sha256=NATURAL_FROZEN_PAYLOAD_SHA256,
        artifact_root=args.natural_frozen_artifact_root,
    )
    temporal_frozen = load_json(paths["temporal_freeze"])
    if (
        temporal_frozen.get("schedule_sha256")
        != TEMPORAL_SCHEDULE_SHA256
        or temporal_frozen.get("candidate_case_manifest_sha256")
        != TEMPORAL_CASE_SHA256
        or temporal_frozen.get("labels_created") is not False
    ):
        raise CompositionError("Temporal private freeze boundary changed.")

    natural_sources = load_json(paths["natural_source"])
    temporal_sources = load_json(paths["temporal_source"])
    calibration = load_json(paths["calibration"])
    natural_cases = load_json(paths["natural_case"])
    temporal_cases = load_json(paths["temporal_case"])
    _validate_input_sets(
        natural_sources, temporal_sources, natural_cases, temporal_cases
    )
    uniform_audit = _uniform_leakage_audit(
        project_root=project_root,
        natural_sources=natural_sources,
        temporal_sources=temporal_sources,
        calibration=calibration,
        natural_acquisition_root=args.natural_acquisition_root,
        temporal_acquisition_root=args.temporal_acquisition_root,
    )

    lock_path = output_root / "composition_lock.json"
    if lock_path.is_file():
        lock = load_json(lock_path)
        composed_at = str(lock["composed_at"])
    else:
        composed_at = utc_now()
        lock = {
            "schema_version": "1.0",
            "record_kind": "contexttrace_unseen_v1_two_track_composition_lock",
            "composed_at": composed_at,
            "natural_source_manifest_sha256": NATURAL_SOURCE_SHA256,
            "temporal_source_manifest_sha256": TEMPORAL_SOURCE_SHA256,
            "natural_case_manifest_sha256": NATURAL_CASE_SHA256,
            "temporal_case_manifest_sha256": TEMPORAL_CASE_SHA256,
            "natural_frozen_payload_sha256": NATURAL_FROZEN_PAYLOAD_SHA256,
            "temporal_private_freeze_file_sha256": (
                TEMPORAL_PRIVATE_FREEZE_FILE_SHA256
            ),
            "calibration_registry_sha256": CALIBRATION_REGISTRY_SHA256,
            "natural_schedule_sha256": NATURAL_SCHEDULE_SHA256,
            "temporal_schedule_sha256": TEMPORAL_SCHEDULE_SHA256,
            "uniform_leakage_audit": uniform_audit,
            "labels_accessible": False,
            "verifier_or_nli_calls": 0,
            "evaluation_performed": False,
            "publication_authorized": False,
        }
        atomic_json(lock_path, lock)
    if lock.get("uniform_leakage_audit") != uniform_audit:
        raise CompositionError("Existing composition lock differs.")

    source_manifest = _combined_source_manifest(
        natural_sources, temporal_sources, composed_at=composed_at
    )
    case_manifest = _combined_case_manifest(
        natural_cases, temporal_cases, composed_at=composed_at
    )
    atomic_json(output_root / "combined_source_manifest.json", source_manifest)
    atomic_json(output_root / "combined_case_manifest.json", case_manifest)
    artifact_root = output_root / "artifacts"
    _materialize_artifacts(
        artifact_root=artifact_root,
        natural_sources=natural_sources,
        temporal_sources=temporal_sources,
        natural_cases=natural_cases,
        temporal_cases=temporal_cases,
        natural_acquisition_root=args.natural_acquisition_root,
        temporal_acquisition_root=args.temporal_acquisition_root,
        natural_collection_root=args.natural_collection_root,
        temporal_collection_root=args.temporal_collection_root,
    )
    frozen = freeze_manifest(
        source_manifest,
        case_manifest,
        calibration,
        artifact_root=artifact_root,
        frozen_at=composed_at,
    )
    frozen_path = output_root / "contexttrace_unseen_v1_frozen_unlabeled.json"
    digest = write_frozen_manifest(frozen, frozen_path)
    verified = verify_frozen_manifest(
        load_json(frozen_path),
        expected_sha256=digest,
        artifact_root=artifact_root,
    )
    record = {
        "schema_version": "1.0",
        "record_kind": "contexttrace_unseen_v1_gate_c_private_freeze",
        "status": "complete_verified_private_unlabeled",
        "completed_at": utc_now(),
        "frozen_payload_sha256": verified,
        "frozen_file_sha256": file_sha256(frozen_path),
        "combined_source_manifest_file_sha256": file_sha256(
            output_root / "combined_source_manifest.json"
        ),
        "combined_case_manifest_file_sha256": file_sha256(
            output_root / "combined_case_manifest.json"
        ),
        "composition": frozen["composition"],
        "source_count": frozen["source_count"],
        "case_count": frozen["case_count"],
        "uniform_leakage_audit": uniform_audit,
        "labels_created": False,
        "labels_accessible": False,
        "verifier_or_nli_calls": 0,
        "evaluation_performed": False,
        "publication_or_release_performed": False,
    }
    atomic_json(output_root / "gate_c_freeze_record.json", record)
    return record


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command", choices=("compose", "verify"), nargs="?", default="compose"
    )
    parser.add_argument("--project-root", type=Path, default=Path("."))
    parser.add_argument(
        "--natural-acquisition-root",
        type=Path,
        default=Path(".tmp-contexttrace-unseen-v1-acquisition"),
    )
    parser.add_argument(
        "--temporal-acquisition-root",
        type=Path,
        default=Path(".tmp-contexttrace-unseen-v1-temporal-acquisition"),
    )
    parser.add_argument(
        "--natural-collection-root",
        type=Path,
        default=Path(".tmp-contexttrace-unseen-v1-collection"),
    )
    parser.add_argument(
        "--temporal-collection-root",
        type=Path,
        default=Path(".tmp-contexttrace-unseen-v1-temporal-collection"),
    )
    parser.add_argument(
        "--natural-frozen-artifact-root",
        type=Path,
        default=Path(".tmp-contexttrace-unseen-v1-freeze-validation"),
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path(".tmp-contexttrace-unseen-v1-two-track-freeze"),
    )
    parser.add_argument("--expected-sha256")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "compose":
            result = compose(args)
        else:
            output_root = args.output_root.resolve()
            manifest_path = (
                output_root
                / "contexttrace_unseen_v1_frozen_unlabeled.json"
            )
            digest = verify_frozen_manifest(
                load_json(manifest_path),
                expected_sha256=args.expected_sha256,
                artifact_root=output_root / "artifacts",
            )
            result = {
                "status": "verified_private_unlabeled",
                "frozen_payload_sha256": digest,
            }
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except (CompositionError, FreezeError, OSError, ValueError) as exc:
        print(f"Two-track freeze stopped: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
