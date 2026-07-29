"""Build deterministic, label-free production annotation packets."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from benchmarks.contexttrace_unseen_v1.freeze_manifest import (
    FreezeError,
    canonical_sha256,
    file_sha256,
    normalized_text_sha256,
    verify_frozen_manifest,
)


PACKET_VERSION = "contexttrace-production-annotation-packet-v1"
ANNOTATORS = ("pul", "sid")
DOUBLE_NATURAL_COUNT = 24


class PacketError(RuntimeError):
    """Raised when safe packet construction cannot continue."""


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PacketError(f"Could not load {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise PacketError(f"{path} must contain a JSON object.")
    return value


def _write_json(path: Path, value: Any, *, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.chmod(path, mode)


def _case_rank(case_id: str) -> str:
    return hashlib.sha256(
        f"{PACKET_VERSION}:{case_id}".encode("utf-8")
    ).hexdigest()


def _select_double_natural(
    natural_cases: Sequence[Mapping[str, Any]],
) -> list[Mapping[str, Any]]:
    by_domain: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for case in natural_cases:
        by_domain[str(case["domain_group"])].append(case)
    if set(by_domain) != {
        "software_product_documentation",
        "policy_regulatory",
        "support_operational",
    }:
        raise PacketError("Natural cases do not cover the three frozen domains.")

    selected: list[Mapping[str, Any]] = []
    per_domain = DOUBLE_NATURAL_COUNT // len(by_domain)
    for domain in sorted(by_domain):
        candidates = list(by_domain[domain])
        seen: dict[str, set[Any]] = {
            "retrieval": set(),
            "generator": set(),
            "reranking": set(),
            "chunk_size": set(),
            "source_family": set(),
        }
        domain_selected: list[Mapping[str, Any]] = []
        while len(domain_selected) < per_domain:
            if not candidates:
                raise PacketError(f"Could not select {per_domain} cases for {domain}.")

            def score(case: Mapping[str, Any]) -> tuple[int, str]:
                values = {
                    "retrieval": case["retrieval"]["family"],
                    "generator": case["generator"]["model_family"],
                    "reranking": case["reranking"]["enabled"],
                    "chunk_size": case["chunking"]["size"],
                    "source_family": case["source_family"],
                }
                weights = {
                    "retrieval": 8,
                    "generator": 6,
                    "reranking": 4,
                    "chunk_size": 2,
                    "source_family": 1,
                }
                coverage = sum(
                    weights[key]
                    for key, value in values.items()
                    if value not in seen[key]
                )
                return (-coverage, _case_rank(str(case["case_id"])))

            chosen = min(candidates, key=score)
            candidates.remove(chosen)
            domain_selected.append(chosen)
            seen["retrieval"].add(chosen["retrieval"]["family"])
            seen["generator"].add(chosen["generator"]["model_family"])
            seen["reranking"].add(chosen["reranking"]["enabled"])
            seen["chunk_size"].add(chosen["chunking"]["size"])
            seen["source_family"].add(chosen["source_family"])
        selected.extend(domain_selected)
    return sorted(selected, key=lambda case: str(case["case_id"]))


def build_assignment_plan(
    cases: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    natural = [case for case in cases if case["track"] == "natural_ood"]
    temporal = [
        case for case in cases if case["track"] == "temporal_source_condition"
    ]
    if len(natural) != 393 or len(temporal) != 100:
        raise PacketError(
            f"Expected 393 natural and 100 temporal cases; got "
            f"{len(natural)} and {len(temporal)}."
        )

    double_natural = _select_double_natural(natural)
    double_ids = {
        str(case["case_id"]) for case in [*double_natural, *temporal]
    }
    single_cases = [
        case for case in natural if str(case["case_id"]) not in double_ids
    ]
    single_cases.sort(
        key=lambda case: (
            str(case["domain_group"]),
            str(case["retrieval"]["family"]),
            str(case["generator"]["model_family"]),
            str(case["source_family"]),
            _case_rank(str(case["case_id"])),
        )
    )

    assignments: dict[str, set[str]] = {
        annotator: set(double_ids) for annotator in ANNOTATORS
    }
    single_counts = {annotator: 0 for annotator in ANNOTATORS}
    for case in single_cases:
        minimum = min(single_counts.values())
        eligible = [
            annotator
            for annotator in ANNOTATORS
            if single_counts[annotator] == minimum
        ]
        if len(eligible) == 1:
            annotator = eligible[0]
        else:
            annotator = eligible[
                int(_case_rank(str(case["case_id"]))[0], 16) % len(eligible)
            ]
        assignments[annotator].add(str(case["case_id"]))
        single_counts[annotator] += 1

    case_assignments = {
        str(case["case_id"]): sorted(
            annotator
            for annotator in ANNOTATORS
            if str(case["case_id"]) in assignments[annotator]
        )
        for case in cases
    }
    if set(case_assignments) != {str(case["case_id"]) for case in cases}:
        raise PacketError("Assignment plan dropped a case.")
    if any(not annotators for annotators in case_assignments.values()):
        raise PacketError("Assignment plan contains an unassigned case.")
    if sum(len(value) == 2 for value in case_assignments.values()) != 124:
        raise PacketError("Assignment plan must double-annotate exactly 124 cases.")
    if any(len(case_assignments[str(case["case_id"])]) != 2 for case in temporal):
        raise PacketError("Every temporal case must be double-annotated.")

    plan: dict[str, Any] = {
        "schema_version": "1.0",
        "record_kind": "contexttrace_production_annotation_assignment_plan",
        "packet_version": PACKET_VERSION,
        "dataset_id": "ContextTrace-Unseen-v1",
        "case_count": len(cases),
        "double_annotated_case_count": 124,
        "double_annotated_fraction": 124 / len(cases),
        "all_temporal_cases_double_annotated": True,
        "double_natural_case_count": len(double_natural),
        "annotator_case_counts": {
            annotator: len(assignments[annotator]) for annotator in ANNOTATORS
        },
        "case_assignments": case_assignments,
    }
    plan["assignment_plan_payload_sha256"] = canonical_sha256(plan)
    return plan


def _safe_artifact(artifact_root: Path, relative: str) -> Path:
    candidate = Path(relative)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise PacketError(f"Unsafe artifact path: {relative}")
    root = artifact_root.resolve()
    resolved = (root / candidate).resolve()
    if root not in resolved.parents or not resolved.is_file():
        raise PacketError(f"Missing or escaping artifact path: {relative}")
    return resolved


def _source_view(source: Mapping[str, Any], packet_path: str) -> dict[str, Any]:
    return {
        "source_id": source["source_id"],
        "source_document_id": source["source_document_id"],
        "document_lineage_id": source["document_lineage_id"],
        "source_family": source["source_family"],
        "domain_group": source["domain_group"],
        "domain_id": source["domain_id"],
        "canonical_identifier": source["canonical_identifier"],
        "source_url": source["source_url"],
        "published_at": source["published_at"],
        "publication_window": source["publication_window"],
        "source_conditions": source["source_conditions"],
        "authority_basis": source["authority_basis"],
        "normalized_content_sha256": source["normalized_content_sha256"],
        "text_path": packet_path,
    }


def _case_view(
    case: Mapping[str, Any],
    *,
    trace_path: str,
    source_views: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    return {
        "case_id": case["case_id"],
        "track": case["track"],
        "domain_group": case["domain_group"],
        "domain_id": case["domain_id"],
        "source_family": case["source_family"],
        "publication_window": case["publication_window"],
        "trace_path": trace_path,
        "trace_sha256": case["trace_sha256"],
        "selected_context_ids": case["selected_context_ids"],
        "retrieved_chunk_ids": case["retrieved_chunk_ids"],
        "source_condition_pair": case.get("source_condition_pair"),
        "sources": list(source_views),
    }


def _copy_input(source: Path, destination: Path, expected_sha256: str) -> None:
    if file_sha256(source) != expected_sha256:
        raise PacketError(f"Source hash mismatch: {source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)
    os.chmod(destination, 0o400)


def _copy_source_text(
    source: Path,
    destination: Path,
    expected_sha256: str,
    hash_kind: str,
) -> None:
    digest = (
        file_sha256(source)
        if hash_kind == "file_bytes_sha256_v1"
        else normalized_text_sha256(source)
    )
    if digest != expected_sha256:
        raise PacketError(f"Normalized source hash mismatch: {source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)
    os.chmod(destination, 0o400)


def _iter_files(root: Path) -> Iterable[Path]:
    return sorted(path for path in root.rglob("*") if path.is_file())


def _packet_manifest(packet_root: Path) -> dict[str, Any]:
    files = {
        str(path.relative_to(packet_root)): file_sha256(path)
        for path in _iter_files(packet_root)
        if path.name != "PACKET_MANIFEST.json"
    }
    manifest: dict[str, Any] = {
        "schema_version": "1.0",
        "record_kind": "contexttrace_annotation_packet_file_manifest",
        "packet_version": PACKET_VERSION,
        "files": files,
    }
    manifest["payload_sha256"] = canonical_sha256(manifest)
    return manifest


def _readme(annotator_id: str, case_count: int) -> str:
    return f"""# ContextTrace production annotation packet: {annotator_id}

Assigned cases: {case_count}

This packet contains unlabeled RAG traces and source material. Open
`ASSIGNMENT.json`, then process every listed case independently.

For each case:

1. Open its `inputs/traces/<case-id>.json` file.
2. Inspect the query, answer, citations, and retrieved chunks.
3. Use the listed files under `inputs/sources/` when source condition,
   freshness, authority, corpus coverage, or a non-retrieved reference must be
   checked.
4. Read `ANNOTATION_MANUAL.md` before labeling.
5. Fill the corresponding `work/<case-id>.json` file. Segment every answer
   into atomic claims and complete every required claim field.
6. Do not use ContextTrace, system predictions, an LLM, web search, or another
   annotator's work.
7. When finished, give the entire `work/` directory only to `sar`.

Do not edit files under `inputs/` or another annotator's packet.
"""


def _sar_readme(case_counts: Mapping[str, int]) -> str:
    return f"""# Production annotation handoff

This is the main human research task.

1. Give the complete `pul/` folder only to `pul`.
2. Give the complete `sid/` folder only to `sid`.
3. They work independently and fill every JSON file under their own `work/`
   directory.
4. They return only their completed `work/` directory to `sar`.
5. `sar` keeps the two submissions separate and does not send their contents
   to the implementation team.

Workload:

- `pul`: {case_counts["pul"]} cases
- `sid`: {case_counts["sid"]} cases
- 124 cases are independently annotated by both
- every one of the 100 temporal/source-condition cases is annotated by both

The annotators start with each folder's `README.md` and `ASSIGNMENT.json`.
"""


def build_packets(
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
    cases = list(manifest["cases"])
    case_index = {str(case["case_id"]): case for case in cases}
    source_index = {
        str(source["source_id"]): source for source in manifest["sources"]
    }
    plan = build_assignment_plan(cases)

    output.mkdir(parents=True, mode=0o700)
    _write_json(output / "SAR_ASSIGNMENT_PLAN.json", plan, mode=0o400)
    (output / "00-SAR-READ-ME.md").write_text(
        _sar_readme(plan["annotator_case_counts"]),
        encoding="utf-8",
    )
    os.chmod(output / "00-SAR-READ-ME.md", 0o400)

    material_names = (
        "ANNOTATION_MANUAL.md",
        "ANNOTATION_SCHEMA.json",
        "ANNOTATOR_TRAINING.md",
    )
    for annotator in ANNOTATORS:
        packet_root = output / annotator
        packet_root.mkdir(mode=0o700)
        assigned_ids = sorted(
            case_id
            for case_id, assigned in plan["case_assignments"].items()
            if annotator in assigned
        )
        source_ids = sorted(
            {
                str(source_id)
                for case_id in assigned_ids
                for source_id in case_index[case_id]["source_ids"]
            }
        )
        source_views: dict[str, dict[str, Any]] = {}
        for source_id in source_ids:
            source = source_index[source_id]
            packet_relative = f"inputs/sources/{source_id}.txt"
            _copy_source_text(
                _safe_artifact(
                    artifact_root, str(source["normalized_text_path"])
                ),
                packet_root / packet_relative,
                str(source["normalized_content_sha256"]),
                str(source["metadata"]["normalized_content_hash_kind"]),
            )
            source_views[source_id] = _source_view(source, packet_relative)

        assignment_cases: list[dict[str, Any]] = []
        for case_id in assigned_ids:
            case = case_index[case_id]
            trace = _safe_artifact(
                artifact_root, str(case["trace_artifact_path"])
            )
            trace_relative = f"inputs/traces/{case_id}.json"
            _copy_input(
                trace,
                packet_root / trace_relative,
                str(case["trace_sha256"]),
            )
            trace_payload = _load_json(trace)
            assignment_cases.append(
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
                packet_root / "work" / f"{case_id}.json",
                {
                    "case_id": case_id,
                    "answer_sha256": hashlib.sha256(
                        str(trace_payload["answer"]).encode("utf-8")
                    ).hexdigest(),
                    "claims": [],
                    "completed_at": None,
                    "case_notes": "",
                },
            )

        assignment: dict[str, Any] = {
            "schema_version": "1.0",
            "record_kind": "contexttrace_independent_annotation_assignment",
            "packet_version": PACKET_VERSION,
            "dataset_id": "ContextTrace-Unseen-v1",
            "manifest_sha256": manifest_sha256,
            "annotator_id": annotator,
            "assignment_id": f"ctu1-production-{annotator}-v1",
            "case_count": len(assignment_cases),
            "cases": assignment_cases,
        }
        assignment["assignment_payload_sha256"] = canonical_sha256(assignment)
        _write_json(packet_root / "ASSIGNMENT.json", assignment, mode=0o400)
        (packet_root / "README.md").write_text(
            _readme(annotator, len(assignment_cases)),
            encoding="utf-8",
        )
        os.chmod(packet_root / "README.md", 0o400)
        for material_name in material_names:
            source = materials_root / material_name
            shutil.copyfile(source, packet_root / material_name)
            os.chmod(packet_root / material_name, 0o400)
        shutil.copyfile(claim_policy_path, packet_root / "CLAIM_POLICY.md")
        os.chmod(packet_root / "CLAIM_POLICY.md", 0o400)
        _write_json(
            packet_root / "PACKET_MANIFEST.json",
            _packet_manifest(packet_root),
            mode=0o400,
        )

    summary = {
        "status": "production_annotation_packets_built",
        "manifest_sha256": manifest_sha256,
        "assignment_plan_sha256": plan["assignment_plan_payload_sha256"],
        "double_annotated_case_count": plan["double_annotated_case_count"],
        "annotator_case_counts": plan["annotator_case_counts"],
        "output": str(output),
    }
    _write_json(output / "BUILD_RECEIPT.json", summary, mode=0o400)
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--artifact-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--materials-root", type=Path, required=True)
    parser.add_argument("--claim-policy", type=Path, required=True)
    parser.add_argument("--expected-manifest-sha256", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = build_packets(
            manifest_path=args.manifest,
            artifact_root=args.artifact_root,
            output=args.output,
            materials_root=args.materials_root,
            claim_policy_path=args.claim_policy,
            expected_manifest_sha256=args.expected_manifest_sha256,
        )
    except (FreezeError, PacketError, OSError, ValueError) as exc:
        raise SystemExit(f"Packet construction stopped: {exc}") from exc
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
