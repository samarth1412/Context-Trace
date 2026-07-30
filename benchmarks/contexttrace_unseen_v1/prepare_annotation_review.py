"""Prepare immutable submissions, agreement, and adjudication work for SAR."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from benchmarks.contexttrace_unseen_v1.AGREEMENT_ANALYSIS import (
    CATEGORICAL_FIELDS,
    MULTILABEL_FIELDS,
    analyze_agreement,
    render_markdown,
    validate_annotation,
)
from benchmarks.contexttrace_unseen_v1.freeze_manifest import canonical_sha256


ANNOTATORS = ("pul", "sid")
ADJUDICATED_FIELDS = (
    *CATEGORICAL_FIELDS,
    *MULTILABEL_FIELDS,
    "source_condition_basis",
    "evidence_spans",
)


class ReviewError(RuntimeError):
    """Raised when annotation review preparation must stop."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReviewError(f"Could not load {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ReviewError(f"{path} must contain a JSON object.")
    return value


def _write_json(path: Path, value: Any, *, mode: int = 0o400) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.chmod(path, mode)


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _write_sidecar(path: Path) -> str:
    digest = _file_sha256(path)
    sidecar = path.with_suffix(path.suffix + ".sha256")
    sidecar.write_text(f"{digest}  {path.name}\n", encoding="utf-8")
    os.chmod(sidecar, 0o400)
    return digest


def _assigned_case_ids(assignment: Mapping[str, Any]) -> list[str]:
    return [str(case["case_id"]) for case in assignment["cases"]]


def _load_case_fragments(
    work_directory: Path,
    expected_case_ids: Sequence[str],
) -> list[dict[str, Any]]:
    expected = set(expected_case_ids)
    actual_paths = {
        path.stem: path
        for path in work_directory.glob("*.json")
        if path.is_file()
    }
    if set(actual_paths) != expected:
        missing = sorted(expected - set(actual_paths))
        extra = sorted(set(actual_paths) - expected)
        raise ReviewError(
            f"Work directory case mismatch; missing={missing[:5]}, extra={extra[:5]}."
        )
    cases: list[dict[str, Any]] = []
    for case_id in sorted(expected):
        case = _load_json(actual_paths[case_id])
        if case.get("case_id") != case_id:
            raise ReviewError(f"Case filename/body mismatch: {case_id}.")
        if not case.get("completed_at"):
            raise ReviewError(f"Case {case_id} is not marked complete.")
        if not isinstance(case.get("claims"), list) or not case["claims"]:
            raise ReviewError(f"Case {case_id} has no annotated claims.")
        cases.append(case)
    return cases


def _build_submission(
    packet_root: Path,
    annotator_id: str,
    timestamp: str,
) -> dict[str, Any]:
    assignment = _load_json(packet_root / annotator_id / "ASSIGNMENT.json")
    if assignment.get("annotator_id") != annotator_id:
        raise ReviewError(f"Assignment identity mismatch for {annotator_id}.")
    assignment_hash = assignment.get("assignment_payload_sha256")
    payload = dict(assignment)
    payload.pop("assignment_payload_sha256", None)
    if assignment_hash != canonical_sha256(payload):
        raise ReviewError(f"Assignment seal mismatch for {annotator_id}.")
    cases = _load_case_fragments(
        packet_root / annotator_id / "work",
        _assigned_case_ids(assignment),
    )
    submission = {
        "schema_version": "1.0",
        "document_kind": "independent_annotation",
        "dataset_id": "ContextTrace-Unseen-v1",
        "manifest_sha256": assignment["manifest_sha256"],
        "guide_version": "1.0",
        "claim_policy_version": "1.0",
        "created_at": timestamp,
        "annotator_id": annotator_id,
        "assignment_id": assignment["assignment_id"],
        "assignment_sha256": assignment_hash,
        "independence_attestation": {
            "worked_independently": True,
            "no_system_predictions_seen": True,
            "no_other_annotations_seen": True,
            "all_assistance_disclosed": True,
            "signed_at": timestamp,
        },
        "model_assistance": {"used": False},
        "cases": cases,
    }
    validate_annotation(submission)
    return submission


def _claim_index(case: Mapping[str, Any]) -> dict[tuple[int, int], Mapping[str, Any]]:
    return {
        (int(claim["answer_start"]), int(claim["answer_end"])): claim
        for claim in case["claims"]
    }


def _trace_index(packet_root: Path) -> dict[str, dict[str, Any]]:
    traces: dict[str, dict[str, Any]] = {}
    for annotator in ANNOTATORS:
        directory = packet_root / annotator / "inputs" / "traces"
        for path in directory.glob("*.json"):
            if path.stem not in traces:
                traces[path.stem] = _load_json(path)
    return traces


def _disagreement(
    *,
    sequence: int,
    case_id: str,
    field: str,
    boundary: tuple[int, int] | None,
    left: Any,
    right: Any,
    trace: Mapping[str, Any],
    left_context: Mapping[str, Any] | None = None,
    right_context: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "disagreement_id": f"ctu1-disagreement-{sequence:06d}",
        "case_id": case_id,
        "field": field,
        "answer_boundary": (
            {"start": boundary[0], "end": boundary[1]}
            if boundary is not None
            else None
        ),
        "query": trace["query"],
        "answer": trace["answer"],
        "annotator_values": [
            {
                "annotator_id": "pul",
                "value": left,
                "claim_context": left_context,
            },
            {
                "annotator_id": "sid",
                "value": right,
                "claim_context": right_context,
            },
        ],
        "adjudication": {
            "selected_value": None,
            "disagreement_type": None,
            "evidence_considered": [],
            "rationale": "",
            "adjudicator_id": "sar",
            "adjudicated_at": None,
        },
    }


def _build_disagreements(
    submissions: Mapping[str, Mapping[str, Any]],
    traces: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    case_indexes = {
        annotator: {
            str(case["case_id"]): case for case in submission["cases"]
        }
        for annotator, submission in submissions.items()
    }
    shared = sorted(set(case_indexes["pul"]) & set(case_indexes["sid"]))
    disagreements: list[dict[str, Any]] = []

    def add(**kwargs: Any) -> None:
        disagreements.append(
            _disagreement(sequence=len(disagreements) + 1, **kwargs)
        )

    for case_id in shared:
        trace = traces[case_id]
        left_claims = _claim_index(case_indexes["pul"][case_id])
        right_claims = _claim_index(case_indexes["sid"][case_id])
        for boundary in sorted(set(left_claims) | set(right_claims)):
            left_claim = left_claims.get(boundary)
            right_claim = right_claims.get(boundary)
            if left_claim is None or right_claim is None:
                add(
                    case_id=case_id,
                    field="claim_boundary",
                    boundary=boundary,
                    left=left_claim,
                    right=right_claim,
                    trace=trace,
                )
                continue
            if left_claim["propositional"] != right_claim["propositional"]:
                add(
                    case_id=case_id,
                    field="claim_boundary",
                    boundary=boundary,
                    left=left_claim,
                    right=right_claim,
                    trace=trace,
                )
                continue
            if not left_claim["propositional"]:
                continue
            for field in ADJUDICATED_FIELDS:
                left_value = left_claim[field]
                right_value = right_claim[field]
                if left_value != right_value:
                    add(
                        case_id=case_id,
                        field=field,
                        boundary=boundary,
                        left=left_value,
                        right=right_value,
                        trace=trace,
                        left_context={
                            "claim_id": left_claim["claim_id"],
                            "claim_text": left_claim["claim_text"],
                            "rationale": left_claim["rationale"],
                        },
                        right_context={
                            "claim_id": right_claim["claim_id"],
                            "claim_text": right_claim["claim_text"],
                            "rationale": right_claim["rationale"],
                        },
                    )
    return disagreements


def prepare_review(
    *,
    packet_root: Path,
    output: Path,
    attestations_confirmed: bool,
) -> dict[str, Any]:
    if not attestations_confirmed:
        raise ReviewError("Independent-work attestations must be confirmed.")
    if output.exists():
        raise ReviewError(f"Output must not already exist: {output}")
    timestamp = _utc_now()
    submissions = {
        annotator: _build_submission(packet_root, annotator, timestamp)
        for annotator in ANNOTATORS
    }
    output.mkdir(parents=True, mode=0o700)
    raw_hashes: dict[str, str] = {}
    for annotator, submission in submissions.items():
        path = output / "raw" / f"{annotator}-independent-annotation.json"
        _write_json(path, submission)
        raw_hashes[annotator] = _write_sidecar(path)

    agreement = analyze_agreement(list(submissions.values()))
    agreement_json = output / "agreement" / "pre-adjudication-agreement.json"
    _write_json(agreement_json, agreement)
    agreement_markdown = output / "agreement" / "pre-adjudication-agreement.md"
    agreement_markdown.write_text(
        render_markdown(agreement),
        encoding="utf-8",
    )
    os.chmod(agreement_markdown, 0o400)

    disagreements = _build_disagreements(
        submissions,
        _trace_index(packet_root),
    )
    disagreement_packet = {
        "schema_version": "1.0",
        "record_kind": "contexttrace_blinded_disagreement_packet",
        "dataset_id": "ContextTrace-Unseen-v1",
        "manifest_sha256": next(iter(submissions.values()))["manifest_sha256"],
        "guide_version": "1.0",
        "created_at": timestamp,
        "raw_submission_sha256s": raw_hashes,
        "instructions": (
            "SAR completes every adjudication object without changing either "
            "raw submission. Do not add system predictions."
        ),
        "disagreements": disagreements,
    }
    _write_json(
        output / "disagreements" / "disagreement-packet.json",
        disagreement_packet,
        mode=0o600,
    )

    receipt = {
        "schema_version": "1.0",
        "record_kind": "contexttrace_annotation_review_preparation_receipt",
        "status": "ready_for_human_adjudication",
        "prepared_at": timestamp,
        "manifest_sha256": next(iter(submissions.values()))["manifest_sha256"],
        "raw_submission_sha256s": raw_hashes,
        "agreement_report_sha256": _file_sha256(agreement_json),
        "disagreement_packet_sha256": _file_sha256(
            output / "disagreements" / "disagreement-packet.json"
        ),
        "disagreement_count": len(disagreements),
    }
    _write_json(output / "REVIEW_RECEIPT.json", receipt)
    _write_sidecar(output / "REVIEW_RECEIPT.json")
    return {
        "status": "ready_for_human_adjudication",
        "receipt": str(output / "REVIEW_RECEIPT.json"),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packet-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--attestations-confirmed", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = prepare_review(
            packet_root=args.packet_root,
            output=args.output,
            attestations_confirmed=args.attestations_confirmed,
        )
    except (ReviewError, OSError, ValueError) as exc:
        raise SystemExit(f"Annotation review preparation stopped: {exc}") from exc
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
