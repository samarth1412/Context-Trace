"""Custodian-side synthetic label-zone and recovery rehearsal.

This utility never receives or creates production annotations. It must be run
by the independent custodian outside the ContextTrace repository.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from benchmarks.contexttrace_unseen_v1.freeze_manifest import (
    FreezeError,
    verify_frozen_manifest,
)


TOOL_VERSION = "contexttrace-label-zone-rehearsal-v1"
STAGED_TOOL_VERSION = "contexttrace-label-zone-rehearsal-v2"
CANDIDATE_ID = re.compile(r"^[a-z0-9][a-z0-9_-]{1,63}$")
LAYOUT = (
    "assignments",
    "raw/annotator-a",
    "raw/annotator-b",
    "validation-receipts",
    "agreement",
    "disagreement-packets",
    "adjudication-ledger",
    "gold",
    "correction-ledger",
    "receipts-read-only",
    "rehearsal/backup",
    "rehearsal/recovery",
)
RECEIPT_KEYS = frozenset(
    {
        "schema_version",
        "record_kind",
        "tool_version",
        "candidate_id",
        "rehearsed_at",
        "frozen_manifest_payload_sha256",
        "frozen_manifest_verified",
        "directory_layout_passed",
        "private_mode_passed",
        "append_only_log_rehearsal_passed",
        "synthetic_seal_backup_recovery_passed",
        "implementation_account_denial_attested",
        "manual_training_attested",
        "excluded_source_pilot_attested",
        "duties_and_disclosure_attested",
        "overall_activation_passed",
        "receipt_payload_sha256",
    }
)
ZONE_RECEIPT_KEYS = frozenset(
    {
        "schema_version",
        "record_kind",
        "tool_version",
        "candidate_id",
        "rehearsed_at",
        "directory_layout_passed",
        "private_mode_passed",
        "append_only_log_rehearsal_passed",
        "synthetic_seal_backup_recovery_passed",
        "implementation_account_denial_attested",
        "duties_and_disclosure_attested",
        "overall_zone_rehearsal_passed",
        "receipt_payload_sha256",
    }
)
MANIFEST_RECEIPT_KEYS = frozenset(
    {
        "schema_version",
        "record_kind",
        "tool_version",
        "candidate_id",
        "verified_at",
        "frozen_manifest_payload_sha256",
        "frozen_manifest_verified",
        "receipt_payload_sha256",
    }
)


class RehearsalError(RuntimeError):
    """The synthetic custodian rehearsal failed closed."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


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
        raise RehearsalError(f"Could not load {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise RehearsalError(f"{path} must contain a JSON object.")
    return value


def atomic_json(path: Path, value: Any, *, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(
        json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.chmod(temporary, mode)
    os.replace(temporary, path)


def _outside_repository(path: Path, *, label: str) -> Path:
    resolved = path.resolve()
    repository = Path(__file__).resolve().parents[2]
    if resolved == repository or repository in resolved.parents:
        raise RehearsalError(f"{label} must be outside the ContextTrace repository.")
    return resolved


def _prepare_zone(zone: Path) -> None:
    if zone.exists():
        if not zone.is_dir() or any(zone.iterdir()):
            raise RehearsalError("Rehearsal zone must be absent or empty.")
    else:
        zone.mkdir(parents=True, mode=0o700)
    os.chmod(zone, 0o700)
    for relative in LAYOUT:
        directory = zone / relative
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(directory, 0o700)


def _append_chained_event(
    path: Path,
    *,
    previous_sha256: str | None,
    action: str,
    candidate_id: str,
) -> str:
    event: dict[str, Any] = {
        "schema_version": "1.0",
        "event_id": f"synthetic-event-{action}",
        "timestamp": utc_now(),
        "actor_id": candidate_id,
        "role": "label_custodian",
        "purpose": "synthetic_rehearsal_only",
        "action": action,
        "artifact_sha256": "0" * 64,
        "previous_event_sha256": previous_sha256,
    }
    event["event_sha256"] = sha256_bytes(
        canonical_json(event).encode("utf-8")
    )
    with path.open("a", encoding="utf-8") as handle:
        handle.write(canonical_json(event) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.chmod(path, 0o600)
    return str(event["event_sha256"])


def _verify_log_chain(path: Path) -> bool:
    previous: str | None = None
    events = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if len(events) != 2:
        return False
    for event in events:
        digest = event.pop("event_sha256", None)
        if event.get("previous_event_sha256") != previous:
            return False
        expected = sha256_bytes(canonical_json(event).encode("utf-8"))
        if digest != expected:
            return False
        previous = digest
    return True


def _synthetic_recovery(zone: Path) -> bool:
    source = zone / "raw/annotator-a/record-001.json"
    payload = {
        "schema_version": "synthetic-1.0",
        "record_kind": "synthetic_rehearsal_record",
        "synthetic_case_id": "training-only-001",
        "field_a": "alpha",
        "field_b": ["beta"],
        "production_data": False,
    }
    atomic_json(source, payload, mode=0o400)
    original_hash = sha256_file(source)
    backup = zone / "rehearsal/backup/record-001.json"
    recovery = zone / "rehearsal/recovery/record-001.json"
    shutil.copyfile(source, backup)
    os.chmod(backup, 0o400)
    shutil.copyfile(backup, recovery)
    os.chmod(recovery, 0o400)
    return (
        sha256_file(backup) == original_hash
        and sha256_file(recovery) == original_hash
        and load_json(recovery) == payload
    )


def _private_modes_pass(zone: Path) -> bool:
    paths = [zone, *(zone / relative for relative in LAYOUT)]
    return all((path.stat().st_mode & 0o077) == 0 for path in paths)


def _receipt_payload_hash(receipt: Mapping[str, Any]) -> str:
    payload = dict(receipt)
    payload.pop("receipt_payload_sha256", None)
    return sha256_bytes(canonical_json(payload).encode("utf-8"))


def _write_receipt(receipt_path: Path, receipt: dict[str, Any]) -> None:
    receipt["receipt_payload_sha256"] = _receipt_payload_hash(receipt)
    atomic_json(receipt_path, receipt, mode=0o600)
    sidecar = receipt_path.with_suffix(receipt_path.suffix + ".sha256")
    sidecar.write_text(
        f"{sha256_file(receipt_path)}  {receipt_path.name}\n",
        encoding="utf-8",
    )
    os.chmod(sidecar, 0o600)


def _validate_candidate_id(candidate_id: str) -> None:
    if not CANDIDATE_ID.fullmatch(candidate_id):
        raise RehearsalError("Candidate ID format is invalid.")


def rehearse_zone(args: argparse.Namespace) -> dict[str, Any]:
    """Run the synthetic zone checks before any untouched manifest is shared."""

    _validate_candidate_id(args.candidate_id)
    zone = _outside_repository(args.zone, label="Label zone")
    receipt_path = _outside_repository(args.receipt, label="Receipt")
    _prepare_zone(zone)
    log_path = zone / "access-log.jsonl"
    first = _append_chained_event(
        log_path,
        previous_sha256=None,
        action="zone_created",
        candidate_id=args.candidate_id,
    )
    _append_chained_event(
        log_path,
        previous_sha256=first,
        action="synthetic_recovery_verified",
        candidate_id=args.candidate_id,
    )
    receipt: dict[str, Any] = {
        "schema_version": "1.0",
        "record_kind": "contexttrace_label_zone_rehearsal_receipt",
        "tool_version": STAGED_TOOL_VERSION,
        "candidate_id": args.candidate_id,
        "rehearsed_at": utc_now(),
        "directory_layout_passed": all(
            (zone / relative).is_dir() for relative in LAYOUT
        ),
        "private_mode_passed": _private_modes_pass(zone),
        "append_only_log_rehearsal_passed": _verify_log_chain(log_path),
        "synthetic_seal_backup_recovery_passed": _synthetic_recovery(zone),
        "implementation_account_denial_attested": bool(
            args.implementation_denial_attested
        ),
        "duties_and_disclosure_attested": bool(args.duties_attested),
    }
    receipt["overall_zone_rehearsal_passed"] = all(
        value is True
        for key, value in receipt.items()
        if key.endswith("_passed") or key.endswith("_attested")
    )
    _write_receipt(receipt_path, receipt)
    return receipt


def verify_manifest(args: argparse.Namespace) -> dict[str, Any]:
    """Verify the real frozen manifest only after training and pilot gates pass."""

    _validate_candidate_id(args.candidate_id)
    receipt_path = _outside_repository(args.receipt, label="Receipt")
    manifest = load_json(args.manifest)
    verified = verify_frozen_manifest(
        manifest, expected_sha256=args.expected_sha256
    )
    receipt: dict[str, Any] = {
        "schema_version": "1.0",
        "record_kind": "contexttrace_frozen_manifest_verification_receipt",
        "tool_version": STAGED_TOOL_VERSION,
        "candidate_id": args.candidate_id,
        "verified_at": utc_now(),
        "frozen_manifest_payload_sha256": verified,
        "frozen_manifest_verified": True,
    }
    _write_receipt(receipt_path, receipt)
    return receipt


def rehearse(args: argparse.Namespace) -> dict[str, Any]:
    _validate_candidate_id(args.candidate_id)
    zone = _outside_repository(args.zone, label="Label zone")
    receipt_path = _outside_repository(args.receipt, label="Receipt")
    manifest = load_json(args.manifest)
    verified = verify_frozen_manifest(
        manifest, expected_sha256=args.expected_sha256
    )
    _prepare_zone(zone)
    log_path = zone / "access-log.jsonl"
    first = _append_chained_event(
        log_path,
        previous_sha256=None,
        action="zone_created",
        candidate_id=args.candidate_id,
    )
    _append_chained_event(
        log_path,
        previous_sha256=first,
        action="synthetic_recovery_verified",
        candidate_id=args.candidate_id,
    )
    recovery_passed = _synthetic_recovery(zone)
    receipt: dict[str, Any] = {
        "schema_version": "1.0",
        "record_kind": "contexttrace_label_custodian_activation_receipt",
        "tool_version": TOOL_VERSION,
        "candidate_id": args.candidate_id,
        "rehearsed_at": utc_now(),
        "frozen_manifest_payload_sha256": verified,
        "frozen_manifest_verified": True,
        "directory_layout_passed": all(
            (zone / relative).is_dir() for relative in LAYOUT
        ),
        "private_mode_passed": _private_modes_pass(zone),
        "append_only_log_rehearsal_passed": _verify_log_chain(log_path),
        "synthetic_seal_backup_recovery_passed": recovery_passed,
        "implementation_account_denial_attested": bool(
            args.implementation_denial_attested
        ),
        "manual_training_attested": bool(args.training_attested),
        "excluded_source_pilot_attested": bool(args.pilot_attested),
        "duties_and_disclosure_attested": bool(args.duties_attested),
    }
    receipt["overall_activation_passed"] = all(
        value is True
        for key, value in receipt.items()
        if key.endswith("_passed") or key.endswith("_attested")
    )
    _write_receipt(receipt_path, receipt)
    return receipt


def _verify_receipt_fields(
    receipt: Mapping[str, Any],
    *,
    allowed_keys: frozenset[str],
    record_kind: str,
    tool_version: str,
    candidate_id: str,
) -> None:
    if set(receipt) != allowed_keys:
        raise RehearsalError("Receipt fields are missing or exceed the allowlist.")
    if (
        receipt["record_kind"] != record_kind
        or receipt["tool_version"] != tool_version
        or receipt["candidate_id"] != candidate_id
        or receipt["receipt_payload_sha256"] != _receipt_payload_hash(receipt)
    ):
        raise RehearsalError("Receipt identity or hash is invalid.")


def verify_receipt(args: argparse.Namespace) -> dict[str, Any]:
    receipt = load_json(args.receipt)
    _verify_receipt_fields(
        receipt,
        allowed_keys=RECEIPT_KEYS,
        record_kind="contexttrace_label_custodian_activation_receipt",
        tool_version=TOOL_VERSION,
        candidate_id=args.candidate_id,
    )
    if (
        receipt["frozen_manifest_payload_sha256"] != args.expected_sha256
    ):
        raise RehearsalError("Activation receipt manifest hash is invalid.")
    return {
        "status": (
            "activation_passed"
            if receipt["overall_activation_passed"]
            else "activation_incomplete"
        ),
        "candidate_id": receipt["candidate_id"],
        "frozen_manifest_payload_sha256": receipt[
            "frozen_manifest_payload_sha256"
        ],
        "receipt_payload_sha256": receipt["receipt_payload_sha256"],
    }


def verify_zone_receipt(args: argparse.Namespace) -> dict[str, Any]:
    receipt = load_json(args.receipt)
    _verify_receipt_fields(
        receipt,
        allowed_keys=ZONE_RECEIPT_KEYS,
        record_kind="contexttrace_label_zone_rehearsal_receipt",
        tool_version=STAGED_TOOL_VERSION,
        candidate_id=args.candidate_id,
    )
    return {
        "status": (
            "zone_rehearsal_passed"
            if receipt["overall_zone_rehearsal_passed"]
            else "zone_rehearsal_incomplete"
        ),
        "candidate_id": receipt["candidate_id"],
        "receipt_payload_sha256": receipt["receipt_payload_sha256"],
    }


def verify_manifest_receipt(args: argparse.Namespace) -> dict[str, Any]:
    receipt = load_json(args.receipt)
    _verify_receipt_fields(
        receipt,
        allowed_keys=MANIFEST_RECEIPT_KEYS,
        record_kind="contexttrace_frozen_manifest_verification_receipt",
        tool_version=STAGED_TOOL_VERSION,
        candidate_id=args.candidate_id,
    )
    if (
        receipt["frozen_manifest_payload_sha256"] != args.expected_sha256
        or receipt["frozen_manifest_verified"] is not True
    ):
        raise RehearsalError("Manifest receipt hash or verification state is invalid.")
    return {
        "status": "manifest_verified",
        "candidate_id": receipt["candidate_id"],
        "frozen_manifest_payload_sha256": receipt[
            "frozen_manifest_payload_sha256"
        ],
        "receipt_payload_sha256": receipt["receipt_payload_sha256"],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    rehearsal = subparsers.add_parser("rehearse")
    rehearsal.add_argument("--zone", type=Path, required=True)
    rehearsal.add_argument("--candidate-id", required=True)
    rehearsal.add_argument("--manifest", type=Path, required=True)
    rehearsal.add_argument("--expected-sha256", required=True)
    rehearsal.add_argument("--receipt", type=Path, required=True)
    rehearsal.add_argument(
        "--implementation-denial-attested", action="store_true"
    )
    rehearsal.add_argument("--training-attested", action="store_true")
    rehearsal.add_argument("--pilot-attested", action="store_true")
    rehearsal.add_argument("--duties-attested", action="store_true")

    zone_rehearsal = subparsers.add_parser("rehearse-zone")
    zone_rehearsal.add_argument("--zone", type=Path, required=True)
    zone_rehearsal.add_argument("--candidate-id", required=True)
    zone_rehearsal.add_argument("--receipt", type=Path, required=True)
    zone_rehearsal.add_argument(
        "--implementation-denial-attested", action="store_true"
    )
    zone_rehearsal.add_argument("--duties-attested", action="store_true")

    manifest = subparsers.add_parser("verify-manifest")
    manifest.add_argument("--manifest", type=Path, required=True)
    manifest.add_argument("--expected-sha256", required=True)
    manifest.add_argument("--candidate-id", required=True)
    manifest.add_argument("--receipt", type=Path, required=True)

    verify = subparsers.add_parser("verify-receipt")
    verify.add_argument("--receipt", type=Path, required=True)
    verify.add_argument("--candidate-id", required=True)
    verify.add_argument("--expected-sha256", required=True)

    verify_zone = subparsers.add_parser("verify-zone-receipt")
    verify_zone.add_argument("--receipt", type=Path, required=True)
    verify_zone.add_argument("--candidate-id", required=True)

    verify_manifest_result = subparsers.add_parser("verify-manifest-receipt")
    verify_manifest_result.add_argument("--receipt", type=Path, required=True)
    verify_manifest_result.add_argument("--candidate-id", required=True)
    verify_manifest_result.add_argument("--expected-sha256", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        commands = {
            "rehearse": rehearse,
            "rehearse-zone": rehearse_zone,
            "verify-manifest": verify_manifest,
            "verify-receipt": verify_receipt,
            "verify-zone-receipt": verify_zone_receipt,
            "verify-manifest-receipt": verify_manifest_receipt,
        }
        result = commands[args.command](args)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except (FreezeError, RehearsalError, OSError, ValueError) as exc:
        print(f"Custodian rehearsal stopped: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
