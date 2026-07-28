from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

from benchmarks.contexttrace_unseen_v1.build_annotation_pilot import (
    UNTOUCHED_PAYLOAD_SHA256,
    build,
    forbidden_paths,
    sha256_bytes,
)


ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "benchmarks/contexttrace_unseen_v1/annotation_pilot"


def test_committed_pilot_rebuilds_exactly_and_has_no_label_fields() -> None:
    packet, lock = build(ROOT)
    committed_packet = json.loads(
        (BASE / "pilot_inputs.json").read_text(encoding="utf-8")
    )
    committed_lock = json.loads(
        (BASE / "pilot_lock.json").read_text(encoding="utf-8")
    )
    assert committed_packet == packet
    assert committed_lock == lock
    assert forbidden_paths(packet) == []
    payload = (
        json.dumps(packet, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    ).encode()
    assert sha256_bytes(payload) == lock["pilot_packet_sha256"]


def test_pilot_schema_and_exclusion_boundary_are_exact() -> None:
    packet = json.loads(
        (BASE / "pilot_inputs.json").read_text(encoding="utf-8")
    )
    schema = json.loads(
        (BASE / "pilot_inputs.schema.json").read_text(encoding="utf-8")
    )
    errors = list(
        Draft202012Validator(
            schema, format_checker=FormatChecker()
        ).iter_errors(packet)
    )
    assert errors == []
    assert packet["case_count"] == 22
    assert packet["untouched_manifest_payload_sha256"] == UNTOUCHED_PAYLOAD_SHA256
    assert len({case["pilot_case_id"] for case in packet["cases"]}) == 22
    assert all(
        case["split"] == "excluded_calibration_pilot"
        and case["excluded_from_untouched_test"] is True
        for case in packet["cases"]
    )


def test_pilot_lock_records_only_calibration_inputs_and_no_calls() -> None:
    lock = json.loads(
        (BASE / "pilot_lock.json").read_text(encoding="utf-8")
    )
    assert lock["case_count"] == 22
    assert lock["model_calls"] == 0
    assert lock["verifier_or_nli_calls"] == 0
    assert lock["untouched_cases_accessed"] == 0
    assert lock["production_labels_created"] is False
    assert len(lock["provenance"]) == 22
    assert sum("source_case_id" in item for item in lock["provenance"]) == 12
    assert sum("git_blob" in item for item in lock["provenance"]) == 10
