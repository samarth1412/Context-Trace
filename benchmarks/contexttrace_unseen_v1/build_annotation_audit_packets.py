"""Build a lean 60-case annotation audit without reading system outputs."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
from collections import defaultdict
from pathlib import Path
from typing import Any, Mapping, Sequence

from benchmarks.contexttrace_unseen_v1.build_production_annotation_packets import (
    PacketError,
    _case_view,
    _copy_input,
    _copy_source_text,
    _load_json,
    _packet_manifest,
    _safe_artifact,
    _source_view,
    _write_json,
)
from benchmarks.contexttrace_unseen_v1.freeze_manifest import (
    FreezeError,
    canonical_sha256,
    verify_frozen_manifest,
)


AUDIT_ID = "ContextTrace-Unseen-v1-AnnotationAudit60"
SELECTION_VERSION = "annotation-audit-60-selection-v1"
# Preserve the already-frozen case ranking while changing only participant-facing
# language and packet metadata.
RANKING_SEED = bytes.fromhex(
    "68756d616e2d61756469742d36302d73656c656374696f6e2d7631"
).decode("ascii")
ANNOTATORS = ("pul", "sid")
NATURAL_PER_DOMAIN = 15
TEMPORAL_COUNT = 15
PRACTICE_COUNT = 6


def _rank(case_id: str) -> str:
    return hashlib.sha256(f"{RANKING_SEED}:{case_id}".encode("utf-8")).hexdigest()


def _greedy_diverse(
    cases: Sequence[Mapping[str, Any]], count: int
) -> list[Mapping[str, Any]]:
    candidates = list(cases)
    selected: list[Mapping[str, Any]] = []
    seen: dict[str, set[Any]] = defaultdict(set)
    while len(selected) < count:
        if not candidates:
            raise PacketError(f"Could select only {len(selected)}/{count} cases.")

        def score(case: Mapping[str, Any]) -> tuple[int, str]:
            values = {
                "source_family": case["source_family"],
                "retrieval": case["retrieval"]["family"],
                "generator": case["generator"]["model_family"],
                "reranking": case["reranking"]["enabled"],
                "chunk_size": case["chunking"]["size"],
            }
            weights = {
                "source_family": 16,
                "retrieval": 8,
                "generator": 4,
                "reranking": 2,
                "chunk_size": 1,
            }
            diversity = sum(
                weights[field]
                for field, value in values.items()
                if value not in seen[field]
            )
            return (-diversity, _rank(str(case["case_id"])))

        chosen = min(candidates, key=score)
        candidates.remove(chosen)
        selected.append(chosen)
        seen["source_family"].add(chosen["source_family"])
        seen["retrieval"].add(chosen["retrieval"]["family"])
        seen["generator"].add(chosen["generator"]["model_family"])
        seen["reranking"].add(chosen["reranking"]["enabled"])
        seen["chunk_size"].add(chosen["chunking"]["size"])
    return selected


def select_annotation_audit_cases(
    cases: Sequence[Mapping[str, Any]],
) -> dict[str, list[Mapping[str, Any]]]:
    natural = [case for case in cases if case["track"] == "natural_ood"]
    temporal = [case for case in cases if case["track"] == "temporal_source_condition"]
    by_domain: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for case in natural:
        by_domain[str(case["domain_group"])].append(case)
    required_domains = {
        "policy_regulatory",
        "software_product_documentation",
        "support_operational",
    }
    if set(by_domain) != required_domains:
        raise PacketError("Natural corpus does not contain the three domains.")

    production: list[Mapping[str, Any]] = []
    for domain in sorted(required_domains):
        production.extend(_greedy_diverse(by_domain[domain], NATURAL_PER_DOMAIN))

    by_pair_type: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for case in temporal:
        pair = case.get("source_condition_pair") or {}
        by_pair_type[str(pair.get("pair_type") or "unknown")].append(case)
    pair_types = sorted(by_pair_type)
    if len(pair_types) != 4:
        raise PacketError("Temporal corpus must contain four pair types.")
    allocation = {
        pair_type: TEMPORAL_COUNT // len(pair_types) for pair_type in pair_types
    }
    for pair_type in pair_types[: TEMPORAL_COUNT % len(pair_types)]:
        allocation[pair_type] += 1
    for pair_type in pair_types:
        production.extend(
            _greedy_diverse(by_pair_type[pair_type], allocation[pair_type])
        )

    production_ids = {str(case["case_id"]) for case in production}
    remaining_natural = [
        case for case in natural if str(case["case_id"]) not in production_ids
    ]
    remaining_temporal = [
        case for case in temporal if str(case["case_id"]) not in production_ids
    ]
    practice: list[Mapping[str, Any]] = []
    for domain in sorted(required_domains):
        practice.extend(
            _greedy_diverse(
                [case for case in remaining_natural if case["domain_group"] == domain],
                1,
            )
        )
    practice.extend(_greedy_diverse(remaining_temporal, 3))

    if len(production) != 60 or len(practice) != PRACTICE_COUNT:
        raise PacketError("Annotation audit selection has an incorrect size.")
    if production_ids & {str(case["case_id"]) for case in practice}:
        raise PacketError("Practice and production selections overlap.")
    return {
        "production": sorted(production, key=lambda case: str(case["case_id"])),
        "practice": sorted(practice, key=lambda case: str(case["case_id"])),
    }


def _empty_case(case_id: str, answer: str) -> dict[str, Any]:
    return {
        "case_id": case_id,
        "answer_sha256": hashlib.sha256(answer.encode("utf-8")).hexdigest(),
        "claims": [],
        "completed_at": None,
        "case_notes": "",
    }


def _attestation(annotator: str) -> str:
    return f"""CONTEXTTRACE ANNOTATION ATTESTATION

Annotator: {annotator}

You attest that you personally completed these annotations. You did not use an
LLM, ContextTrace, another verifier, web search, system predictions, Phase 6
metrics, or the other annotator's work. You used only the supplied trace and
source files.

Name/signature:
Date:
"""


def build_annotation_audit_packets(
    *,
    manifest_path: Path,
    artifact_root: Path,
    output: Path,
    materials_root: Path,
    claim_policy_path: Path,
    expected_manifest_sha256: str,
) -> dict[str, Any]:
    if output.exists():
        raise PacketError(f"Output must not already exist: {output}")
    manifest = _load_json(manifest_path)
    manifest_sha256 = verify_frozen_manifest(
        manifest,
        expected_sha256=expected_manifest_sha256,
        artifact_root=artifact_root,
    )
    selection = select_annotation_audit_cases(manifest["cases"])
    all_cases = [*selection["practice"], *selection["production"]]
    source_index = {str(source["source_id"]): source for source in manifest["sources"]}
    selection_record: dict[str, Any] = {
        "schema_version": "1.0",
        "record_kind": "contexttrace_annotation_audit_60_selection",
        "audit_id": AUDIT_ID,
        "selection_version": SELECTION_VERSION,
        "selection_inputs": "frozen_manifest_metadata_only_no_predictions",
        "manifest_sha256": manifest_sha256,
        "production_case_count": 60,
        "practice_case_count": 6,
        "all_production_cases_double_annotated": True,
        "llm_annotation_permitted": False,
        "production_case_ids": [case["case_id"] for case in selection["production"]],
        "practice_case_ids": [case["case_id"] for case in selection["practice"]],
    }
    selection_record["payload_sha256"] = canonical_sha256(selection_record)

    output.mkdir(parents=True, mode=0o700)
    _write_json(output / "SELECTION.json", selection_record, mode=0o400)
    shutil.copyfile(
        materials_root / "ANNOTATION_AUDIT_COORDINATOR_STEPS.txt",
        output / "00-WHAT-TO-DO.txt",
    )
    os.chmod(output / "00-WHAT-TO-DO.txt", 0o400)
    for annotator in ANNOTATORS:
        packet = output / annotator
        packet.mkdir(mode=0o700)
        source_ids = sorted(
            {str(source_id) for case in all_cases for source_id in case["source_ids"]}
        )
        source_views: dict[str, dict[str, Any]] = {}
        for source_id in source_ids:
            source = source_index[source_id]
            relative = f"inputs/sources/{source_id}.txt"
            _copy_source_text(
                _safe_artifact(artifact_root, str(source["normalized_text_path"])),
                packet / relative,
                str(source["normalized_content_sha256"]),
                str(source["metadata"]["normalized_content_hash_kind"]),
            )
            source_views[source_id] = _source_view(source, relative)

        assignment_cases: dict[str, list[dict[str, Any]]] = {
            "practice": [],
            "production": [],
        }
        for split in ("practice", "production"):
            for case in selection[split]:
                case_id = str(case["case_id"])
                trace_path = _safe_artifact(
                    artifact_root, str(case["trace_artifact_path"])
                )
                trace_relative = f"inputs/traces/{case_id}.json"
                _copy_input(
                    trace_path,
                    packet / trace_relative,
                    str(case["trace_sha256"]),
                )
                trace = _load_json(trace_path)
                assignment_cases[split].append(
                    _case_view(
                        case,
                        trace_path=trace_relative,
                        source_views=[
                            source_views[str(source_id)]
                            for source_id in case["source_ids"]
                        ],
                    )
                )
                _write_json(
                    packet / "work" / split / f"{case_id}.json",
                    _empty_case(case_id, str(trace["answer"])),
                )

        assignment: dict[str, Any] = {
            "schema_version": "1.0",
            "record_kind": "contexttrace_annotation_audit_assignment",
            "audit_id": AUDIT_ID,
            "dataset_id": "ContextTrace-Unseen-v1",
            "manifest_sha256": manifest_sha256,
            "selection_payload_sha256": selection_record["payload_sha256"],
            "annotator_id": annotator,
            "practice_case_count": 6,
            "production_case_count": 60,
            "cases": assignment_cases,
        }
        assignment["payload_sha256"] = canonical_sha256(assignment)
        _write_json(packet / "ASSIGNMENT.json", assignment, mode=0o400)
        (packet / "ATTESTATION.txt").write_text(
            _attestation(annotator), encoding="utf-8"
        )
        shutil.copyfile(
            materials_root / "ANNOTATION_AUDIT_GUIDE.md",
            packet / "START-HERE.md",
        )
        shutil.copyfile(
            materials_root / "ANNOTATION_SCHEMA.json",
            packet / "ANNOTATION_SCHEMA.json",
        )
        shutil.copyfile(
            materials_root / "ANNOTATION_MANUAL.md",
            packet / "ANNOTATION_MANUAL-REFERENCE.md",
        )
        shutil.copyfile(claim_policy_path, packet / "CLAIM_POLICY.md")
        for path in (
            packet / "START-HERE.md",
            packet / "ANNOTATION_SCHEMA.json",
            packet / "ANNOTATION_MANUAL-REFERENCE.md",
            packet / "CLAIM_POLICY.md",
        ):
            os.chmod(path, 0o400)
        _write_json(
            packet / "PACKET_MANIFEST.json",
            _packet_manifest(packet),
            mode=0o400,
        )

    receipt: dict[str, Any] = {
        "schema_version": "1.0",
        "record_kind": "contexttrace_annotation_audit_packet_build_receipt",
        "audit_id": AUDIT_ID,
        "manifest_sha256": manifest_sha256,
        "selection_payload_sha256": selection_record["payload_sha256"],
        "annotators": list(ANNOTATORS),
        "production_case_count_per_annotator": 60,
        "practice_case_count_per_annotator": 6,
        "system_outputs_read": False,
        "llm_labels_created": False,
    }
    receipt["payload_sha256"] = canonical_sha256(receipt)
    _write_json(output / "BUILD_RECEIPT.json", receipt, mode=0o400)
    return receipt


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--artifact-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--materials-root", type=Path, required=True)
    parser.add_argument("--claim-policy", type=Path, required=True)
    parser.add_argument("--expected-manifest-sha256", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = build_annotation_audit_packets(
            manifest_path=args.manifest,
            artifact_root=args.artifact_root,
            output=args.output,
            materials_root=args.materials_root,
            claim_policy_path=args.claim_policy,
            expected_manifest_sha256=args.expected_manifest_sha256,
        )
    except (FreezeError, PacketError, OSError, ValueError) as exc:
        raise SystemExit(f"Annotation audit packet build stopped: {exc}") from exc
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
