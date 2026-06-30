from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from benchmarks.contexttrace_bench.arr_annotation import (
    REVIEW_BUNDLE_ROOT,
    REVIEW_BUNDLE_TIMESTAMP,
    build_blinded_annotation_artifacts,
    build_reviewer_bundle,
    validate_reviewer_bundle,
)


def test_reviewer_bundle_is_deterministic_complete_and_leak_free(tmp_path):
    packet_path = _build_fixture_packet(tmp_path)

    first = build_reviewer_bundle(
        packet_path=packet_path,
        output_path=tmp_path / "first.zip",
    )
    second = build_reviewer_bundle(
        packet_path=packet_path,
        output_path=tmp_path / "second.zip",
    )

    assert first["sha256"] == second["sha256"]
    assert first["case_count"] == 1
    assert validate_reviewer_bundle(first["bundle"])["status"] == "passed"
    with zipfile.ZipFile(first["bundle"], "r") as archive:
        names = archive.namelist()
        assert names == sorted(names)
        assert "%s/annotation_packet.json" % REVIEW_BUNDLE_ROOT in names
        assert "%s/ARR_ANNOTATION_PROTOCOL.md" % REVIEW_BUNDLE_ROOT in names
        assert "%s/ARR_LABEL_GUIDE.md" % REVIEW_BUNDLE_ROOT in names
        assert not any("private" in name.lower() or "annotation_key" in name.lower() for name in names)
        packet_text = archive.read("%s/annotation_packet.json" % REVIEW_BUNDLE_ROOT).decode("utf-8")
        assert '"original_id"' not in packet_text
        assert '"expected_labels"' not in packet_text
        assert '"predicted"' not in packet_text


def test_reviewer_bundle_validator_rejects_original_id_leak(tmp_path):
    packet_path = _build_fixture_packet(tmp_path)
    result = build_reviewer_bundle(packet_path=packet_path, output_path=tmp_path / "good.zip")
    bad_path = tmp_path / "bad.zip"
    with zipfile.ZipFile(result["bundle"], "r") as source:
        payload = {name: source.read(name) for name in source.namelist()}
    packet_name = "%s/annotation_packet.json" % REVIEW_BUNDLE_ROOT
    packet = json.loads(payload[packet_name])
    packet["cases"][0]["original_id"] = "secret-case-id"
    payload[packet_name] = json.dumps(packet, sort_keys=True).encode("utf-8")
    with zipfile.ZipFile(bad_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in sorted(payload.items()):
            info = zipfile.ZipInfo(name, date_time=REVIEW_BUNDLE_TIMESTAMP)
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, content)

    validation = validate_reviewer_bundle(bad_path)

    assert validation["status"] == "failed"
    assert {error["name"] for error in validation["errors"]}.issuperset(
        {"packet_identity_leakage", "packet_leakage", "manifest_bytes", "manifest_sha256"}
    )


def test_reviewer_bundle_rejects_assigned_packet(tmp_path):
    packet_path = _build_fixture_packet(tmp_path)
    packet = json.loads(Path(packet_path).read_text(encoding="utf-8"))
    packet["reviewer"] = "reviewer-a"
    Path(packet_path).write_text(json.dumps(packet), encoding="utf-8")

    with pytest.raises(ValueError, match="unassigned blank packet"):
        build_reviewer_bundle(packet_path=packet_path, output_path=tmp_path / "assigned.zip")


def test_reviewer_bundle_validator_rejects_unexpected_file(tmp_path):
    packet_path = _build_fixture_packet(tmp_path)
    result = build_reviewer_bundle(packet_path=packet_path, output_path=tmp_path / "good.zip")
    bad_path = tmp_path / "extra.zip"
    with zipfile.ZipFile(result["bundle"], "r") as source:
        payload = {name: source.read(name) for name in source.namelist()}
    payload["%s/extra.txt" % REVIEW_BUNDLE_ROOT] = b"undeclared"
    with zipfile.ZipFile(bad_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in sorted(payload.items()):
            info = zipfile.ZipInfo(name, date_time=REVIEW_BUNDLE_TIMESTAMP)
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, content)

    validation = validate_reviewer_bundle(bad_path)

    assert validation["status"] == "failed"
    assert "unexpected_files" in {error["name"] for error in validation["errors"]}


def test_annotation_protocol_references_only_safe_label_guide():
    protocol = Path("benchmarks/contexttrace_bench/ARR_ANNOTATION_PROTOCOL.md").read_text(
        encoding="utf-8"
    )

    assert "ARR_LABEL_GUIDE.md" in protocol
    assert "never send reviewers `labels.json`" in protocol


def _build_fixture_packet(tmp_path: Path) -> str:
    case_pack = {
        "dataset": "fixture",
        "cases": [
            {
                "id": "internal-case-id",
                "source": "fixture-source",
                "query": "What is the refund window?",
                "answer": "Refunds are available within 30 days.",
                "contexts": [
                    {
                        "id": "policy",
                        "text": "Refunds are available within 30 days.",
                    }
                ],
                "expected_labels": ["no_failure_detected"],
                "expected_primary_root_cause": "no_failure_detected",
                "expected_evidence_spans": ["Refunds are available within 30 days."],
            }
        ],
    }
    case_pack_path = tmp_path / "case_pack.json"
    case_pack_path.write_text(json.dumps(case_pack), encoding="utf-8")
    artifacts = build_blinded_annotation_artifacts(
        output_dir=tmp_path / "packet",
        case_pack_path=case_pack_path,
        seed=7,
    )
    return artifacts["packet"]
