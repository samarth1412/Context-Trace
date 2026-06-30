from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
import sys
import zipfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
PACKAGE_ROOT = REPO_ROOT / "packages" / "contexttrace"
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

from contexttrace.verify.benchmark import benchmark_cases  # noqa: E402

try:
    from benchmarks.contexttrace_bench.artifact_runtime import repository_revision
except ModuleNotFoundError:  # pragma: no cover - direct script execution
    from artifact_runtime import repository_revision  # type: ignore


DEFAULT_OUTPUT_DIR = Path(__file__).with_name("out") / "arr_annotation"
SAFE_CONTEXT_METADATA = {
    "canonical",
    "canonical_source",
    "document_id",
    "freshness",
    "source",
    "source_authority",
    "source_name",
    "source_timestamp",
    "source_url",
    "source_version",
    "stale",
    "title",
    "url",
}
LABEL_KEYS = {
    "expected",
    "expected_labels",
    "expected_primary_root_cause",
    "expected_evidence_spans",
    "expected_citation_statuses",
    "expected_should_abstain",
    "predicted",
    "predictions",
    "note",
    "benchmark_note",
    "hallucination_labels",
}
REVIEW_BUNDLE_ROOT = "contexttrace-arr-review"
REVIEW_BUNDLE_TIMESTAMP = (2026, 1, 1, 0, 0, 0)
REVIEW_BUNDLE_MANIFEST = "BUNDLE_MANIFEST.json"
DEFAULT_PROTOCOL_PATH = Path(__file__).with_name("ARR_ANNOTATION_PROTOCOL.md")
DEFAULT_LABEL_GUIDE_PATH = Path(__file__).with_name("ARR_LABEL_GUIDE.md")
REVIEW_BUNDLE_REQUIRED = {
    "README.md",
    "annotation_packet.json",
    "ARR_ANNOTATION_PROTOCOL.md",
    "ARR_LABEL_GUIDE.md",
    REVIEW_BUNDLE_MANIFEST,
}
REVIEW_PACKET_FORBIDDEN_KEYS = {
    *LABEL_KEYS,
    "original_id",
    "expected_verdict_counts",
    "raw_predicted",
    "answer_label_projection",
}
REVIEW_BUNDLE_README = """# ARR Independent Annotation Bundle

This bundle contains a blinded annotation packet and the complete reviewer
protocol. It contains no expected labels, system predictions, original case
IDs, private key, or author identity.

1. Read `ARR_ANNOTATION_PROTOCOL.md` and `ARR_LABEL_GUIDE.md` before annotating.
2. Set packet-level `reviewer` to a stable pseudonymous ID.
3. Set `review_kind` to `independent` only if you are not an author and have not
   inspected predictions, expected labels, or the private key.
4. Complete every assigned case's `annotation` object in
   `annotation_packet.json` without changing case content or blind IDs.
5. Return only the completed `annotation_packet.json` to the study coordinator.

Do not inspect the project repository or run the system while labeling. Record
uncertainty in `notes` rather than inferring hidden retrieval or model state.
"""


def build_blinded_annotation_artifacts(
    *,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    case_set: str = "public_holdout",
    case_pack_path: str | Path | None = None,
    seed: int = 20260704,
) -> dict[str, str]:
    records = load_annotation_records(case_set=case_set, case_pack_path=case_pack_path)
    shuffled = list(records)
    random.Random(seed).shuffle(shuffled)
    packet_cases: list[dict[str, Any]] = []
    key_cases: list[dict[str, Any]] = []
    for index, record in enumerate(shuffled, start=1):
        blind_id = "ARR-%04d" % index
        packet_cases.append(_blinded_case(blind_id, record["input"]))
        key_cases.append(
            {
                "blind_id": blind_id,
                "original_id": record["id"],
                **record["expected"],
            }
        )
    dataset = _dataset_name(case_set=case_set, case_pack_path=case_pack_path)
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    packet = {
        "schema_version": 1,
        "packet_type": "blinded_evidence_chain_annotation",
        "dataset": dataset,
        "seed": seed,
        "generated_at": generated_at,
        "case_count": len(packet_cases),
        "review_kind": "",
        "reviewer": "",
        "instructions": [
            "Annotate without consulting ContextTrace predictions or the private key.",
            "Use no_failure_detected when every material claim is supported.",
            "Select minimal source spans and copy their exact text.",
            "Record uncertainty in notes instead of inferring missing evidence.",
        ],
        "cases": packet_cases,
    }
    key = {
        "schema_version": 1,
        "packet_type": "private_annotation_key",
        "dataset": dataset,
        "seed": seed,
        "generated_at": generated_at,
        "case_count": len(key_cases),
        "commit": _git_commit(),
        "cases": key_cases,
    }
    validation = validate_blinded_packet(packet)
    if validation["status"] != "passed":
        raise ValueError("Generated blinded packet failed leakage validation: %s" % validation["errors"])

    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    packet_path = destination / "annotation_packet.json"
    key_path = destination / "annotation_key.private.json"
    validation_path = destination / "annotation_packet_validation.json"
    packet_path.write_text(json.dumps(packet, indent=2, sort_keys=True), encoding="utf-8")
    key_path.write_text(json.dumps(key, indent=2, sort_keys=True), encoding="utf-8")
    validation_path.write_text(json.dumps(validation, indent=2, sort_keys=True), encoding="utf-8")
    return {
        "packet": str(packet_path),
        "private_key": str(key_path),
        "validation": str(validation_path),
    }


def load_annotation_records(
    *,
    case_set: str = "public_holdout",
    case_pack_path: str | Path | None = None,
) -> list[dict[str, Any]]:
    return _case_pack_records(case_pack_path) if case_pack_path else _builtin_records(case_set)


def validate_blinded_packet(packet: dict[str, Any]) -> dict[str, Any]:
    errors: list[dict[str, Any]] = []
    cases = packet.get("cases")
    if not isinstance(cases, list) or not cases:
        errors.append({"name": "cases", "message": "Packet must contain at least one case."})
        cases = []
    blind_ids = [str(case.get("blind_id") or "") for case in cases if isinstance(case, dict)]
    if any(not blind_id for blind_id in blind_ids) or len(blind_ids) != len(set(blind_ids)):
        errors.append({"name": "blind_ids", "message": "Blind IDs must be non-empty and unique."})
    for index, case in enumerate(cases):
        if not isinstance(case, dict):
            errors.append({"name": "case_type", "case_index": index})
            continue
        leaked = sorted(key for key in case if key in LABEL_KEYS)
        if leaked:
            errors.append({"name": "label_leakage", "blind_id": case.get("blind_id"), "keys": leaked})
        if "original_id" in case:
            errors.append({"name": "identity_leakage", "blind_id": case.get("blind_id")})
        annotation = case.get("annotation")
        if not isinstance(annotation, dict):
            errors.append({"name": "annotation_template", "blind_id": case.get("blind_id")})
    return {
        "status": "passed" if not errors else "failed",
        "case_count": len(cases),
        "errors": errors,
    }


def build_reviewer_bundle(
    *,
    packet_path: str | Path,
    output_path: str | Path,
    protocol_path: str | Path = DEFAULT_PROTOCOL_PATH,
    label_guide_path: str | Path = DEFAULT_LABEL_GUIDE_PATH,
) -> dict[str, Any]:
    packet = _load_json_object(Path(packet_path))
    packet_validation = validate_blinded_packet(packet)
    if packet_validation["status"] != "passed":
        raise ValueError("Reviewer packet failed leakage validation: %s" % packet_validation["errors"])
    if str(packet.get("reviewer") or "").strip() or str(packet.get("review_kind") or "").strip():
        raise ValueError("Reviewer bundle source must be an unassigned blank packet.")

    payload = {
        "README.md": REVIEW_BUNDLE_README.encode("utf-8"),
        "annotation_packet.json": (json.dumps(packet, indent=2, sort_keys=True) + "\n").encode("utf-8"),
        "ARR_ANNOTATION_PROTOCOL.md": Path(protocol_path).read_text(encoding="utf-8").encode("utf-8"),
        "ARR_LABEL_GUIDE.md": Path(label_guide_path).read_text(encoding="utf-8").encode("utf-8"),
    }
    manifest = {
        "schema_version": 1,
        "bundle_type": "blinded_independent_annotation",
        "archive_root": REVIEW_BUNDLE_ROOT,
        "dataset": packet.get("dataset"),
        "case_count": packet.get("case_count"),
        "seed": packet.get("seed"),
        "files": [
            {
                "path": path,
                "bytes": len(content),
                "sha256": _sha256_bytes(content),
            }
            for path, content in sorted(payload.items())
        ],
    }
    payload[REVIEW_BUNDLE_MANIFEST] = (
        json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    _write_reviewer_zip(destination, payload)
    validation = validate_reviewer_bundle(destination)
    if validation["status"] != "passed":
        destination.unlink(missing_ok=True)
        raise ValueError("Reviewer bundle validation failed: %s" % validation["errors"])
    bundle_sha = _sha256_file(destination)
    checksum_path = destination.with_suffix(destination.suffix + ".sha256")
    validation_path = destination.with_suffix(destination.suffix + ".validation.json")
    checksum_path.write_text("%s  %s\n" % (bundle_sha, destination.name), encoding="ascii")
    validation_path.write_text(json.dumps(validation, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {
        "bundle": str(destination),
        "sha256": bundle_sha,
        "checksum": str(checksum_path),
        "validation": str(validation_path),
        "dataset": packet.get("dataset"),
        "case_count": packet.get("case_count"),
        "file_count": validation["file_count"],
    }


def validate_reviewer_bundle(path: str | Path) -> dict[str, Any]:
    archive_path = Path(path)
    errors: list[dict[str, Any]] = []
    payload: dict[str, bytes] = {}
    try:
        with zipfile.ZipFile(archive_path, "r") as archive:
            infos = archive.infolist()
            names = [info.filename for info in infos]
            if names != sorted(names):
                errors.append({"name": "archive_order", "message": "ZIP entries are not sorted."})
            if len(names) != len(set(names)):
                errors.append({"name": "duplicate_paths", "message": "ZIP contains duplicate paths."})
            for info in infos:
                relative = _review_bundle_relative_path(info.filename)
                if relative is None:
                    errors.append({"name": "archive_path", "path": info.filename})
                    continue
                if info.date_time != REVIEW_BUNDLE_TIMESTAMP:
                    errors.append({"name": "timestamp", "path": relative})
                lowered = relative.lower()
                if "annotation_key" in lowered or ".private" in lowered or "private_key" in lowered:
                    errors.append({"name": "private_material", "path": relative})
                payload[relative] = archive.read(info)
    except (OSError, zipfile.BadZipFile) as exc:
        return {
            "status": "failed",
            "file_count": 0,
            "case_count": 0,
            "errors": [{"name": "archive_read", "message": str(exc)}],
        }

    missing = sorted(REVIEW_BUNDLE_REQUIRED - set(payload))
    if missing:
        errors.append({"name": "required_files", "missing": missing})
    unexpected = sorted(set(payload) - REVIEW_BUNDLE_REQUIRED)
    if unexpected:
        errors.append({"name": "unexpected_files", "paths": unexpected})
    packet: dict[str, Any] = {}
    packet_bytes = payload.get("annotation_packet.json")
    if packet_bytes is not None:
        try:
            parsed = json.loads(packet_bytes.decode("utf-8-sig"))
            if not isinstance(parsed, dict):
                raise ValueError("packet must be a JSON object")
            packet = parsed
            packet_validation = validate_blinded_packet(packet)
            errors.extend(
                {"name": "packet_%s" % item.get("name"), **{k: v for k, v in item.items() if k != "name"}}
                for item in packet_validation["errors"]
            )
            leaked_keys = sorted(_find_forbidden_keys(packet, REVIEW_PACKET_FORBIDDEN_KEYS))
            if leaked_keys:
                errors.append({"name": "packet_leakage", "keys": leaked_keys})
            if str(packet.get("reviewer") or "").strip() or str(packet.get("review_kind") or "").strip():
                errors.append({"name": "packet_assignment", "message": "Bundle packet must be unassigned."})
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
            errors.append({"name": "packet_json", "message": str(exc)})
    _validate_reviewer_manifest(payload, packet, errors)
    return {
        "status": "passed" if not errors else "failed",
        "file_count": len(payload),
        "case_count": len(packet.get("cases") or []),
        "errors": errors,
    }


def score_annotation_files(
    *,
    key_path: str | Path,
    annotation_paths: list[str | Path],
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
) -> dict[str, Any]:
    if not annotation_paths:
        raise ValueError("At least one completed annotation file is required.")
    key = json.loads(Path(key_path).read_text(encoding="utf-8-sig"))
    key_index = {str(case["blind_id"]): case for case in key.get("cases") or []}
    reviewers = [_load_completed_annotations(path, key_index) for path in annotation_paths]
    reviewer_reports = [_score_reviewer(reviewer, key_index) for reviewer in reviewers]
    pairwise = [
        _pairwise_agreement(reviewers[left], reviewers[right])
        for left in range(len(reviewers))
        for right in range(left + 1, len(reviewers))
    ]
    disagreements = _disagreement_rows(reviewers, key_index)
    report = {
        "schema_version": 1,
        "dataset": key.get("dataset"),
        "case_count": len(key_index),
        "reviewers": reviewer_reports,
        "pairwise_agreement": pairwise,
        "disagreement_cases": len(disagreements),
        "adjudication_required": bool(disagreements),
        "claim_policy": (
            "Author-only review is author-audited calibration evidence. Independent validation requires "
            "at least one reviewer who is not an author and explicit review_kind=independent."
        ),
    }
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    report_path = destination / "annotation_report.json"
    markdown_path = destination / "annotation_report.md"
    disagreements_path = destination / "audit_disagreements.jsonl"
    corrections_path = destination / "audit_corrections.jsonl"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    markdown_path.write_text(render_annotation_report(report), encoding="utf-8")
    disagreements_path.write_text(_jsonl(disagreements), encoding="utf-8")
    corrections_path.write_text(
        _jsonl([{**row, "adjudicated": False, "correction": {}} for row in disagreements]),
        encoding="utf-8",
    )
    return {
        **report,
        "outputs": {
            "report": str(report_path),
            "markdown": str(markdown_path),
            "disagreements": str(disagreements_path),
            "corrections": str(corrections_path),
        },
    }


def render_annotation_report(report: dict[str, Any]) -> str:
    lines = [
        "# ARR Annotation Report",
        "",
        "Dataset: `%s`" % report.get("dataset"),
        "",
        "Cases: `%s`" % report.get("case_count"),
        "",
        "## Reviewer Results",
        "",
        "| Reviewer | Kind | Complete | Failure exact | Root cause | Span F1 |",
        "| --- | --- | ---: | ---: | ---: | ---: |",
    ]
    for reviewer in report.get("reviewers") or []:
        lines.append(
            "| %s | %s | %s/%s | %s | %s | %s |"
            % (
                reviewer.get("reviewer"),
                reviewer.get("review_kind"),
                reviewer.get("completed_cases"),
                reviewer.get("case_count"),
                _metric(reviewer.get("failure_label_exact_match")),
                _metric(reviewer.get("primary_root_cause_accuracy")),
                _metric(reviewer.get("evidence_span_token_f1")),
            )
        )
    if report.get("pairwise_agreement"):
        lines.extend(["", "## Pairwise Agreement", ""])
        for pair in report["pairwise_agreement"]:
            lines.append(
                "- %s vs %s: failure exact `%s`, root kappa `%s`, span F1 `%s`."
                % (
                    pair.get("reviewer_a"),
                    pair.get("reviewer_b"),
                    _metric(pair.get("failure_label_exact_agreement")),
                    _metric(pair.get("primary_root_cause_kappa")),
                    _metric(pair.get("evidence_span_token_f1")),
                )
            )
    lines.extend(
        [
            "",
            "Disagreement cases requiring adjudication: `%s`." % report.get("disagreement_cases"),
            "",
            str(report.get("claim_policy") or ""),
            "",
        ]
    )
    return "\n".join(lines)


def _builtin_records(case_set: str) -> list[dict[str, Any]]:
    records = []
    for case in benchmark_cases(case_set=case_set):
        records.append(
            {
                "id": case.id,
                "input": {
                    "query": case.trace.query,
                    "answer": case.trace.answer,
                    "contexts": [context.to_dict() for context in case.trace.contexts],
                    "citations": [citation.to_dict() for citation in case.trace.citations],
                    "source_reference": case.source,
                },
                "expected": {
                    "expected_labels": sorted(case.expected_labels),
                    "expected_primary_root_cause": case.expected_primary_root_cause,
                    "expected_evidence_spans": list(case.expected_evidence_spans),
                    "expected_citation_statuses": list(case.expected_citation_statuses),
                    "expected_should_abstain": case.expected_should_abstain,
                },
            }
        )
    return records


def _case_pack_records(path: str | Path | None) -> list[dict[str, Any]]:
    if path is None:
        raise ValueError("case_pack_path is required.")
    payload = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    records = []
    for item in payload.get("cases") or []:
        if not isinstance(item, dict):
            continue
        records.append(
            {
                "id": str(item.get("id") or ""),
                "input": {
                    "query": str(item.get("query") or ""),
                    "answer": str(item.get("answer") or ""),
                    "contexts": list(item.get("contexts") or []),
                    "citations": list(item.get("citations") or []),
                    "source_reference": str(item.get("source") or payload.get("dataset") or ""),
                },
                "expected": {
                    "expected_labels": list(item.get("expected_labels") or item.get("expected") or []),
                    "expected_primary_root_cause": str(item.get("expected_primary_root_cause") or ""),
                    "expected_evidence_spans": list(item.get("expected_evidence_spans") or []),
                    "expected_citation_statuses": list(item.get("expected_citation_statuses") or []),
                    "expected_should_abstain": item.get("expected_should_abstain"),
                },
            }
        )
    if not records:
        raise ValueError("Case pack contains no annotation cases.")
    return records


def _blinded_case(blind_id: str, input_row: dict[str, Any]) -> dict[str, Any]:
    return {
        "blind_id": blind_id,
        "query": str(input_row.get("query") or ""),
        "answer": str(input_row.get("answer") or ""),
        "contexts": [
            {
                "id": str(context.get("id") or ""),
                "text": str(context.get("text") or context.get("content") or ""),
                "metadata": {
                    key: value
                    for key, value in dict(context.get("metadata") or {}).items()
                    if key in SAFE_CONTEXT_METADATA
                },
            }
            for context in input_row.get("contexts") or []
            if isinstance(context, dict)
        ],
        "citations": [
            {
                key: value
                for key, value in citation.items()
                if key in {"claim", "source_id", "source_chunk_id", "chunk_id"}
            }
            for citation in input_row.get("citations") or []
            if isinstance(citation, dict)
        ],
        "source_reference": str(input_row.get("source_reference") or ""),
        "annotation": {
            "failure_labels": [],
            "primary_root_cause": "",
            "citation_statuses": [],
            "should_abstain": None,
            "evidence_spans": [],
            "confidence": None,
            "notes": "",
        },
    }


def _load_completed_annotations(
    path: str | Path,
    key_index: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    reviewer = str(payload.get("reviewer") or "").strip()
    review_kind = str(payload.get("review_kind") or "").strip()
    if not reviewer:
        raise ValueError("Completed annotation file must name a reviewer.")
    if review_kind not in {"independent", "blinded_author"}:
        raise ValueError("review_kind must be independent or blinded_author.")
    cases: dict[str, dict[str, Any]] = {}
    for item in payload.get("cases") or []:
        blind_id = str(item.get("blind_id") or "")
        if blind_id not in key_index:
            raise ValueError("Unknown blind ID in annotation file: %s" % blind_id)
        if blind_id in cases:
            raise ValueError("Repeated blind ID in annotation file: %s" % blind_id)
        cases[blind_id] = dict(item.get("annotation") or {})
    return {
        "reviewer": reviewer,
        "review_kind": review_kind,
        "cases": cases,
        "path": str(path),
    }


def _score_reviewer(
    reviewer: dict[str, Any],
    key_index: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    rows = []
    for blind_id, expected in key_index.items():
        annotation = reviewer["cases"].get(blind_id) or {}
        completed = bool(annotation.get("failure_labels")) and bool(annotation.get("primary_root_cause"))
        expected_labels = set(expected.get("expected_labels") or [])
        actual_labels = set(annotation.get("failure_labels") or [])
        rows.append(
            {
                "completed": completed,
                "failure_match": actual_labels == expected_labels if completed else None,
                "failure_f1": _set_f1(expected_labels, actual_labels) if completed else None,
                "root_match": (
                    str(annotation.get("primary_root_cause") or "")
                    == str(expected.get("expected_primary_root_cause") or "")
                )
                if completed and expected.get("expected_primary_root_cause")
                else None,
                "abstention_match": (
                    annotation.get("should_abstain") == expected.get("expected_should_abstain")
                )
                if completed and expected.get("expected_should_abstain") is not None
                else None,
                "span_f1": _span_f1(
                    expected.get("expected_evidence_spans") or [],
                    annotation.get("evidence_spans") or [],
                )
                if completed and expected.get("expected_evidence_spans")
                else None,
            }
        )
    return {
        "reviewer": reviewer["reviewer"],
        "review_kind": reviewer["review_kind"],
        "case_count": len(rows),
        "completed_cases": sum(1 for row in rows if row["completed"]),
        "failure_label_exact_match": _average(row["failure_match"] for row in rows),
        "failure_label_set_f1": _average(row["failure_f1"] for row in rows),
        "primary_root_cause_accuracy": _average(row["root_match"] for row in rows),
        "abstention_accuracy": _average(row["abstention_match"] for row in rows),
        "evidence_span_token_f1": _average(row["span_f1"] for row in rows),
    }


def _pairwise_agreement(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    shared = sorted(set(left["cases"]).intersection(right["cases"]))
    rows = [
        (left["cases"][blind_id], right["cases"][blind_id])
        for blind_id in shared
        if left["cases"][blind_id].get("failure_labels")
        and right["cases"][blind_id].get("failure_labels")
    ]
    left_roots = [str(a.get("primary_root_cause") or "") for a, _ in rows]
    right_roots = [str(b.get("primary_root_cause") or "") for _, b in rows]
    return {
        "reviewer_a": left["reviewer"],
        "reviewer_b": right["reviewer"],
        "shared_completed_cases": len(rows),
        "failure_label_exact_agreement": _average(
            set(a.get("failure_labels") or []) == set(b.get("failure_labels") or [])
            for a, b in rows
        ),
        "primary_root_cause_agreement": _average(a == b for a, b in zip(left_roots, right_roots)),
        "primary_root_cause_kappa": _cohen_kappa(left_roots, right_roots),
        "abstention_agreement": _average(
            a.get("should_abstain") == b.get("should_abstain") for a, b in rows
        ),
        "evidence_span_token_f1": _average(
            _span_f1(a.get("evidence_spans") or [], b.get("evidence_spans") or [])
            for a, b in rows
        ),
    }


def _disagreement_rows(
    reviewers: list[dict[str, Any]],
    key_index: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    rows = []
    for blind_id, expected in key_index.items():
        annotations = [
            {
                "reviewer": reviewer["reviewer"],
                "review_kind": reviewer["review_kind"],
                "annotation": reviewer["cases"].get(blind_id) or {},
            }
            for reviewer in reviewers
        ]
        completed = [item for item in annotations if item["annotation"].get("failure_labels")]
        expected_labels = set(expected.get("expected_labels") or [])
        mismatch = any(
            set(item["annotation"].get("failure_labels") or []) != expected_labels
            or (
                expected.get("expected_primary_root_cause")
                and str(item["annotation"].get("primary_root_cause") or "")
                != str(expected.get("expected_primary_root_cause") or "")
            )
            for item in completed
        )
        inter_reviewer = len(
            {
                (
                    tuple(sorted(item["annotation"].get("failure_labels") or [])),
                    str(item["annotation"].get("primary_root_cause") or ""),
                )
                for item in completed
            }
        ) > 1
        if mismatch or inter_reviewer:
            rows.append(
                {
                    "blind_id": blind_id,
                    "original_id": expected.get("original_id"),
                    "expected": {
                        key: value for key, value in expected.items() if key.startswith("expected_")
                    },
                    "annotations": annotations,
                    "inter_reviewer_disagreement": inter_reviewer,
                }
            )
    return rows


def _span_f1(expected: list[Any], actual: list[Any]) -> float | None:
    expected_text = " ".join(_span_text(item) for item in expected).strip()
    actual_text = " ".join(_span_text(item) for item in actual).strip()
    if not expected_text and not actual_text:
        return None
    expected_tokens = Counter(_tokens(expected_text))
    actual_tokens = Counter(_tokens(actual_text))
    overlap = sum((expected_tokens & actual_tokens).values())
    if not overlap:
        return 0.0
    precision = overlap / sum(actual_tokens.values()) if actual_tokens else 0.0
    recall = overlap / sum(expected_tokens.values()) if expected_tokens else 0.0
    return round(2 * precision * recall / (precision + recall), 3) if precision + recall else 0.0


def _span_text(item: Any) -> str:
    if isinstance(item, dict):
        return str(item.get("text") or "")
    return str(item or "")


def _tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", str(text or "").lower())


def _set_f1(expected: set[str], actual: set[str]) -> float:
    if not expected and not actual:
        return 1.0
    overlap = len(expected.intersection(actual))
    precision = overlap / len(actual) if actual else 0.0
    recall = overlap / len(expected) if expected else 0.0
    return round(2 * precision * recall / (precision + recall), 3) if precision + recall else 0.0


def _cohen_kappa(left: list[str], right: list[str]) -> float | None:
    if not left or len(left) != len(right):
        return None
    observed = sum(a == b for a, b in zip(left, right)) / len(left)
    labels = set(left).union(right)
    expected = sum(
        (left.count(label) / len(left)) * (right.count(label) / len(right))
        for label in labels
    )
    if expected == 1.0:
        return 1.0 if observed == 1.0 else 0.0
    return round((observed - expected) / (1.0 - expected), 3)


def _average(values: Any) -> float | None:
    filtered = [float(value) for value in values if value is not None]
    return round(sum(filtered) / len(filtered), 3) if filtered else None


def _metric(value: Any) -> str:
    return "N/A" if value is None else "%.3f" % float(value)


def _jsonl(rows: list[dict[str, Any]]) -> str:
    return "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows)


def _load_json_object(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError("Expected a JSON object: %s" % path)
    return payload


def _write_reviewer_zip(destination: Path, payload: dict[str, bytes]) -> None:
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for relative_path, content in sorted(payload.items()):
            info = zipfile.ZipInfo(
                "%s/%s" % (REVIEW_BUNDLE_ROOT, relative_path),
                date_time=REVIEW_BUNDLE_TIMESTAMP,
            )
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, content)


def _review_bundle_relative_path(path: str) -> str | None:
    pure = PurePosixPath(path)
    parts = pure.parts
    if len(parts) != 2 or parts[0] != REVIEW_BUNDLE_ROOT:
        return None
    if any(part in {"", ".", ".."} for part in parts):
        return None
    return parts[1]


def _find_forbidden_keys(value: Any, forbidden: set[str]) -> set[str]:
    found: set[str] = set()
    if isinstance(value, dict):
        for key, nested in value.items():
            if str(key) in forbidden:
                found.add(str(key))
            found.update(_find_forbidden_keys(nested, forbidden))
    elif isinstance(value, list):
        for nested in value:
            found.update(_find_forbidden_keys(nested, forbidden))
    return found


def _validate_reviewer_manifest(
    payload: dict[str, bytes],
    packet: dict[str, Any],
    errors: list[dict[str, Any]],
) -> None:
    raw_manifest = payload.get(REVIEW_BUNDLE_MANIFEST)
    if raw_manifest is None:
        return
    try:
        manifest = json.loads(raw_manifest.decode("utf-8-sig"))
        records = manifest.get("files") if isinstance(manifest, dict) else None
        if not isinstance(records, list):
            raise ValueError("manifest files must be a list")
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        errors.append({"name": "manifest_json", "message": str(exc)})
        return

    for key, expected in (
        ("archive_root", REVIEW_BUNDLE_ROOT),
        ("dataset", packet.get("dataset")),
        ("case_count", packet.get("case_count")),
        ("seed", packet.get("seed")),
    ):
        if manifest.get(key) != expected:
            errors.append(
                {
                    "name": "manifest_metadata",
                    "field": key,
                    "expected": expected,
                    "actual": manifest.get(key),
                }
            )

    indexed = {
        str(record.get("path")): record
        for record in records
        if isinstance(record, dict) and record.get("path")
    }
    expected_paths = set(payload) - {REVIEW_BUNDLE_MANIFEST}
    if set(indexed) != expected_paths:
        errors.append(
            {
                "name": "manifest_paths",
                "missing": sorted(expected_paths - set(indexed)),
                "extra": sorted(set(indexed) - expected_paths),
            }
        )
    for path in sorted(expected_paths & set(indexed)):
        content = payload[path]
        record = indexed[path]
        if int(record.get("bytes") or -1) != len(content):
            errors.append({"name": "manifest_bytes", "path": path})
        if record.get("sha256") != _sha256_bytes(content):
            errors.append({"name": "manifest_sha256", "path": path})


def _sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _dataset_name(*, case_set: str, case_pack_path: str | Path | None) -> str:
    if not case_pack_path:
        return case_set
    payload = json.loads(Path(case_pack_path).read_text(encoding="utf-8-sig"))
    return str(payload.get("dataset") or Path(case_pack_path).stem)


def _git_commit() -> str:
    return repository_revision(REPO_ROOT)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build and score blinded ARR annotation packets.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    build = subparsers.add_parser("build")
    build.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    build.add_argument("--case-set", default="public_holdout", choices=["contexttrace", "external", "public_holdout", "all"])
    build.add_argument("--case-pack", default=None)
    build.add_argument("--seed", type=int, default=20260704)
    bundle = subparsers.add_parser("bundle")
    bundle.add_argument("--packet", required=True)
    bundle.add_argument("--output", required=True)
    bundle.add_argument("--protocol", default=str(DEFAULT_PROTOCOL_PATH))
    bundle.add_argument("--label-guide", default=str(DEFAULT_LABEL_GUIDE_PATH))
    score = subparsers.add_parser("score")
    score.add_argument("--key", required=True)
    score.add_argument("--annotations", nargs="+", required=True)
    score.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    args = parser.parse_args(argv)
    if args.command == "build":
        paths = build_blinded_annotation_artifacts(
            output_dir=args.output_dir,
            case_set=args.case_set,
            case_pack_path=args.case_pack,
            seed=args.seed,
        )
        print("Packet: %s" % paths["packet"])
        print("Private key: %s" % paths["private_key"])
        print("Validation: %s" % paths["validation"])
        return 0
    if args.command == "bundle":
        result = build_reviewer_bundle(
            packet_path=args.packet,
            output_path=args.output,
            protocol_path=args.protocol,
            label_guide_path=args.label_guide,
        )
        print("Bundle: %s" % result["bundle"])
        print("SHA256: %s" % result["sha256"])
        print("Dataset: %s" % result["dataset"])
        print("Cases: %s" % result["case_count"])
        print("Validation: %s" % result["validation"])
        return 0
    report = score_annotation_files(
        key_path=args.key,
        annotation_paths=args.annotations,
        output_dir=args.output_dir,
    )
    print("Reviewers: %s" % len(report["reviewers"]))
    print("Disagreements: %s" % report["disagreement_cases"])
    print("Report: %s" % report["outputs"]["report"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
