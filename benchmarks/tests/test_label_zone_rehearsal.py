from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest

from benchmarks.contexttrace_unseen_v1 import label_zone_rehearsal as rehearsal


EXPECTED = "8" * 64


def _args(
    tmp_path: Path,
    *,
    all_attested: bool,
) -> argparse.Namespace:
    manifest = tmp_path / "manifest.json"
    manifest.write_text("{}\n", encoding="utf-8")
    return argparse.Namespace(
        zone=tmp_path / "label-zone",
        candidate_id="sar",
        manifest=manifest,
        expected_sha256=EXPECTED,
        receipt=tmp_path / "receipt.json",
        implementation_denial_attested=all_attested,
        training_attested=all_attested,
        pilot_attested=all_attested,
        duties_attested=all_attested,
    )


def _zone_args(tmp_path: Path) -> argparse.Namespace:
    return argparse.Namespace(
        zone=tmp_path / "label-zone",
        candidate_id="sar",
        receipt=tmp_path / "zone-receipt.json",
        implementation_denial_attested=True,
        duties_attested=True,
    )


def test_staged_zone_rehearsal_exposes_no_manifest(
    tmp_path: Path,
) -> None:
    args = _zone_args(tmp_path)
    receipt = rehearsal.rehearse_zone(args)
    assert receipt["overall_zone_rehearsal_passed"] is True
    assert "frozen_manifest_payload_sha256" not in receipt
    assert "manual_training_attested" not in receipt
    assert "excluded_source_pilot_attested" not in receipt
    result = rehearsal.verify_zone_receipt(
        argparse.Namespace(receipt=args.receipt, candidate_id="sar")
    )
    assert result["status"] == "zone_rehearsal_passed"


def test_staged_manifest_verification_is_separate_from_zone(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest = tmp_path / "manifest.json"
    manifest.write_text("{}\n", encoding="utf-8")
    receipt_path = tmp_path / "manifest-receipt.json"
    monkeypatch.setattr(
        rehearsal,
        "verify_frozen_manifest",
        lambda _manifest, expected_sha256: expected_sha256,
    )
    receipt = rehearsal.verify_manifest(
        argparse.Namespace(
            manifest=manifest,
            expected_sha256=EXPECTED,
            candidate_id="sar",
            receipt=receipt_path,
        )
    )
    assert receipt["frozen_manifest_verified"] is True
    assert "overall_zone_rehearsal_passed" not in receipt
    result = rehearsal.verify_manifest_receipt(
        argparse.Namespace(
            receipt=receipt_path,
            candidate_id="sar",
            expected_sha256=EXPECTED,
        )
    )
    assert result["status"] == "manifest_verified"


def test_synthetic_rehearsal_creates_private_hashed_zone_and_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        rehearsal,
        "verify_frozen_manifest",
        lambda _manifest, expected_sha256: expected_sha256,
    )
    args = _args(tmp_path, all_attested=True)
    receipt = rehearsal.rehearse(args)
    assert receipt["overall_activation_passed"] is True
    assert (args.zone.stat().st_mode & 0o077) == 0
    assert (args.zone / "access-log.jsonl").is_file()
    assert (args.zone / "rehearsal/recovery/record-001.json").is_file()
    result = rehearsal.verify_receipt(
        argparse.Namespace(
            receipt=args.receipt,
            candidate_id="sar",
            expected_sha256=EXPECTED,
        )
    )
    assert result["status"] == "activation_passed"


def test_rehearsal_remains_incomplete_without_human_attestations(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        rehearsal,
        "verify_frozen_manifest",
        lambda _manifest, expected_sha256: expected_sha256,
    )
    receipt = rehearsal.rehearse(_args(tmp_path, all_attested=False))
    assert receipt["overall_activation_passed"] is False
    assert receipt["manual_training_attested"] is False
    assert receipt["excluded_source_pilot_attested"] is False


def test_rehearsal_rejects_zone_inside_implementation_repository(
    tmp_path: Path,
) -> None:
    manifest = tmp_path / "manifest.json"
    manifest.write_text("{}\n", encoding="utf-8")
    with pytest.raises(rehearsal.RehearsalError, match="outside"):
        rehearsal.rehearse(
            argparse.Namespace(
                zone=Path(".tmp-forbidden-label-zone"),
                candidate_id="sar",
                manifest=manifest,
                expected_sha256=EXPECTED,
                receipt=tmp_path / "receipt.json",
                implementation_denial_attested=False,
                training_attested=False,
                pilot_attested=False,
                duties_attested=False,
            )
        )


def test_receipt_tampering_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        rehearsal,
        "verify_frozen_manifest",
        lambda _manifest, expected_sha256: expected_sha256,
    )
    args = _args(tmp_path, all_attested=True)
    rehearsal.rehearse(args)
    receipt = json.loads(args.receipt.read_text())
    receipt["manual_training_attested"] = False
    args.receipt.write_text(json.dumps(receipt), encoding="utf-8")
    with pytest.raises(rehearsal.RehearsalError, match="hash"):
        rehearsal.verify_receipt(
            argparse.Namespace(
                receipt=args.receipt,
                candidate_id="sar",
                expected_sha256=EXPECTED,
            )
        )
