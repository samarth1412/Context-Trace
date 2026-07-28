"""Build the blind, excluded-source ContextTrace annotation pilot package.

The builder uses only previously exposed calibration/development material. It
strips all gold, expected, rationale, category, prediction, and verifier fields
from the annotator-facing packet.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

from benchmarks.contexttrace_unseen_v1.freeze_manifest import (
    FORBIDDEN_LABEL_KEYS,
)


DEV_SOURCE = Path(
    "benchmarks/contexttrace_bench/naturalistic_gtg_dev/"
    "naturalistic_gtg_dev.json"
)
DEV_SOURCE_SHA256 = (
    "61dc688f1eba27cfd0d31196100cdd4013972ffa8085df29fb6ea07ebcbd1d18"
)
CALIBRATION_REGISTRY = Path(
    "benchmarks/contexttrace_unseen_v1/calibration/registry.json"
)
CALIBRATION_REGISTRY_SHA256 = (
    "8d071cc9857169e86df43843bd45fc2a93e66b28a802b5040ffffb23ff43efdb"
)
UNTOUCHED_PAYLOAD_SHA256 = (
    "8bf65cd7e2c95ccfcc12e78b580fc47e4157b0f808ba3fcace0a24bfcdc2e5f6"
)
REAL_TRACE_BLOBS = {
    "benchmarks/real_world_rag/traces/local_rag_chat_1.json": (
        "317666c1b3802720f5f3d4f863aaf1f182ae9309"
    ),
    "benchmarks/real_world_rag/traces/local_rag_chat_2.json": (
        "64d2dfa55cc4730516862d133b54c2c7f89989c7"
    ),
    "benchmarks/real_world_rag/traces/local_rag_chat_stress_1.json": (
        "3364536cd762e9c505034b0ca0500496b0a44f92"
    ),
    "benchmarks/real_world_rag/traces/ollama_hf_e2e_petmri.json": (
        "be7ae2f5911ab0f6d4d0e8db1b836ae509650e9e"
    ),
    "benchmarks/real_world_rag/traces/ollama_hf_rag_engine_1.json": (
        "8f0f38c017527a57be7b1503f69732eec8b5e58f"
    ),
    "benchmarks/real_world_rag/traces/ollama_hf_rag_engine_2.json": (
        "fc475fd191c892c732832aa8b2457ec9f33bae8e"
    ),
    "benchmarks/real_world_rag/traces/ollama_hf_rag_engine_stress_1.json": (
        "12111a7324e7266a2a9ea8414ef8ffca4b07e29c"
    ),
    "benchmarks/real_world_rag/traces/rag_chatbot_1.json": (
        "cfa30e908da0f8bf0c3150cc09e4f04c691d79e2"
    ),
    "benchmarks/real_world_rag/traces/rag_chatbot_2.json": (
        "13f7103d8a33db0d353be60d9784bcaacad690ba"
    ),
    "benchmarks/real_world_rag/traces/rag_chatbot_stress_1.json": (
        "c8a7d72a3ba51743fb9a0b13af107e67cc634018"
    ),
}
CREATED_AT = "2026-07-28T00:00:00Z"


class PilotBuildError(RuntimeError):
    """The excluded calibration pilot cannot be built safely."""


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PilotBuildError(f"Could not load {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise PilotBuildError(f"{path} must contain a JSON object.")
    return value


def git_blob_json(project_root: Path, blob: str) -> dict[str, Any]:
    result = subprocess.run(
        ["git", "cat-file", "blob", blob],
        cwd=project_root,
        check=True,
        capture_output=True,
    )
    try:
        value = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise PilotBuildError(f"Git blob {blob} is not valid JSON.") from exc
    if not isinstance(value, dict):
        raise PilotBuildError(f"Git blob {blob} is not a JSON object.")
    return value


def forbidden_paths(value: Any, *, path: str = "$") -> list[str]:
    result: list[str] = []
    if isinstance(value, Mapping):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            folded = str(key).casefold()
            if (
                folded in FORBIDDEN_LABEL_KEYS
                or folded.startswith("gold_")
                or folded.startswith("expected_")
                or "prediction" in folded
                or folded in {"category", "label_rationale"}
            ):
                result.append(child_path)
            result.extend(forbidden_paths(child, path=child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            result.extend(forbidden_paths(child, path=f"{path}[{index}]"))
    return result


def _blind_dev_cases(
    source: Mapping[str, Any],
    calibration: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    calibration_urls = {
        str(item["source_url"]) for item in calibration["sources"]
    }
    eligible: list[Mapping[str, Any]] = []
    for case in source["cases"]:
        urls = {
            str(context["url"])
            for context in case["retrieved_contexts"]
            if context.get("url")
        }
        if urls and urls <= calibration_urls:
            eligible.append(case)
    if len(eligible) != 12:
        raise PilotBuildError(
            f"Expected 12 registry-covered development cases; found {len(eligible)}."
        )
    cases: list[dict[str, Any]] = []
    provenance: list[dict[str, Any]] = []
    for case in eligible:
        identity = f"dev:{case['case_id']}"
        cases.append(
            {
                "_identity": identity,
                "query": case["query"],
                "answer": case["answer"],
                "contexts": case["retrieved_contexts"],
                "citations": case["citations"],
                "source_family": case["source_family"],
                "source_kind": "previously_exposed_development_case",
            }
        )
        provenance.append(
            {
                "identity": identity,
                "source_case_id": case["case_id"],
                "source_category": case["category"],
            }
        )
    return cases, provenance


def _blind_real_traces(
    project_root: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    cases: list[dict[str, Any]] = []
    provenance: list[dict[str, Any]] = []
    for source_path, blob in sorted(REAL_TRACE_BLOBS.items()):
        trace = git_blob_json(project_root, blob)
        identity = f"real:{source_path}"
        metadata = trace.get("metadata") or {}
        source_family = (
            metadata.get("project")
            or metadata.get("repo")
            or metadata.get("repo_url")
            or "registered-real-world-rag"
        )
        cases.append(
            {
                "_identity": identity,
                "query": trace["query"],
                "answer": trace["answer"],
                "contexts": trace["contexts"],
                "citations": trace.get("citations", []),
                "source_family": source_family,
                "source_kind": "previously_exposed_real_rag_trace",
            }
        )
        provenance.append(
            {
                "identity": identity,
                "source_path": source_path,
                "git_blob": blob,
            }
        )
    return cases, provenance


def build(project_root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    dev_path = project_root / DEV_SOURCE
    registry_path = project_root / CALIBRATION_REGISTRY
    if sha256_file(dev_path) != DEV_SOURCE_SHA256:
        raise PilotBuildError("Development source snapshot hash changed.")
    if sha256_file(registry_path) != CALIBRATION_REGISTRY_SHA256:
        raise PilotBuildError("Calibration registry hash changed.")
    dev = load_json(dev_path)
    calibration = load_json(registry_path)
    dev_cases, dev_provenance = _blind_dev_cases(dev, calibration)
    real_cases, real_provenance = _blind_real_traces(project_root)
    selected = [*dev_cases, *real_cases]
    if len(selected) != 22:
        raise PilotBuildError("Pilot must contain exactly 22 excluded cases.")
    selected.sort(
        key=lambda case: sha256_bytes(
            f"contexttrace-pilot-v1:{case['_identity']}".encode()
        )
    )
    output_cases: list[dict[str, Any]] = []
    identity_to_pilot: dict[str, str] = {}
    for index, case in enumerate(selected, start=1):
        identity = str(case.pop("_identity"))
        pilot_id = f"ctu1_pilot_{index:03d}"
        identity_to_pilot[identity] = pilot_id
        output_cases.append(
            {
                "pilot_case_id": pilot_id,
                "split": "excluded_calibration_pilot",
                "excluded_from_untouched_test": True,
                **case,
            }
        )
    packet = {
        "schema_version": "1.0",
        "package_kind": "contexttrace_excluded_calibration_pilot_inputs",
        "created_at": CREATED_AT,
        "untouched_manifest_payload_sha256": UNTOUCHED_PAYLOAD_SHA256,
        "case_count": len(output_cases),
        "blind_fields_removed": [
            "category",
            "expected_*",
            "gold_*",
            "label_rationale",
            "predictions",
            "verifier_outputs",
        ],
        "cases": output_cases,
    }
    findings = forbidden_paths(packet)
    if findings:
        raise PilotBuildError(
            "Blind packet contains forbidden fields: " + ", ".join(findings[:5])
        )
    provenance = sorted(
        [*dev_provenance, *real_provenance],
        key=lambda item: identity_to_pilot[str(item["identity"])],
    )
    for item in provenance:
        item["pilot_case_id"] = identity_to_pilot[str(item.pop("identity"))]
    lock = {
        "schema_version": "1.0",
        "record_kind": "contexttrace_excluded_calibration_pilot_lock",
        "created_at": CREATED_AT,
        "selection_rule": (
            "all 12 naturalistic development cases whose every source URL was "
            "already present in the frozen calibration registry, plus all 10 "
            "tracked real-world RAG traces at the exact recorded Git blobs; "
            "blind IDs ordered by SHA-256"
        ),
        "development_source_file_sha256": DEV_SOURCE_SHA256,
        "calibration_registry_file_sha256": CALIBRATION_REGISTRY_SHA256,
        "untouched_manifest_payload_sha256": UNTOUCHED_PAYLOAD_SHA256,
        "case_count": 22,
        "model_calls": 0,
        "verifier_or_nli_calls": 0,
        "untouched_cases_accessed": 0,
        "production_labels_created": False,
        "provenance": provenance,
        "pilot_packet_sha256": sha256_bytes(
            (
                json.dumps(packet, indent=2, ensure_ascii=False, sort_keys=True)
                + "\n"
            ).encode("utf-8")
        ),
    }
    return packet, lock


def write_new_or_identical(path: Path, value: Mapping[str, Any]) -> None:
    payload = (
        json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    ).encode("utf-8")
    if path.is_file():
        if path.read_bytes() != payload:
            raise PilotBuildError(f"Refusing to overwrite changed lock: {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("build", "verify"), nargs="?", default="build")
    parser.add_argument("--project-root", type=Path, default=Path("."))
    parser.add_argument(
        "--output-directory",
        type=Path,
        default=Path("benchmarks/contexttrace_unseen_v1/annotation_pilot"),
    )
    args = parser.parse_args(argv)
    try:
        packet, lock = build(args.project_root.resolve())
        output = args.output_directory
        packet_path = output / "pilot_inputs.json"
        lock_path = output / "pilot_lock.json"
        if args.command == "build":
            write_new_or_identical(packet_path, packet)
            write_new_or_identical(lock_path, lock)
        else:
            if (
                load_json(packet_path) != packet
                or load_json(lock_path) != lock
            ):
                raise PilotBuildError("Committed pilot package differs from rebuild.")
        print(
            json.dumps(
                {
                    "status": "valid_blind_excluded_calibration_pilot",
                    "case_count": 22,
                    "pilot_packet_sha256": lock["pilot_packet_sha256"],
                    "forbidden_field_count": 0,
                    "model_calls": 0,
                    "verifier_or_nli_calls": 0,
                    "untouched_cases_accessed": 0,
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0
    except (
        PilotBuildError,
        OSError,
        ValueError,
        subprocess.SubprocessError,
    ) as exc:
        print(f"Annotation pilot build stopped: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
