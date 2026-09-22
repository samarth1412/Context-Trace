"""Freeze and verify the second confirmation pack and learned ambiguity policy."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from benchmarks.external_fiveway_confirmation.adapter import LABELS


class FreezeV2Error(RuntimeError):
    """Raised when second-confirmation integrity checks fail."""


def sha256(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def create_manifest(
    *,
    cases_path: str | Path,
    policy_path: str | Path,
    code_paths: list[str | Path],
) -> dict[str, Any]:
    cases_file = Path(cases_path)
    payload = json.loads(cases_file.read_text(encoding="utf-8"))
    rows = payload.get("cases") or []
    counts = Counter(str(row.get("expected_verdict")) for row in rows)
    if counts != Counter({label: 7 for label in LABELS}):
        raise FreezeV2Error("Expected exactly seven cases for each five-way verdict.")
    ids = [str(row.get("id") or "") for row in rows]
    if any(not case_id for case_id in ids) or len(ids) != len(set(ids)):
        raise FreezeV2Error("Case ids must be non-empty and unique.")
    policy_file = Path(policy_path)
    policy = json.loads(policy_file.read_text(encoding="utf-8"))
    if policy.get("heldout_used_for_selection") is not False:
        raise FreezeV2Error("Learned policy must declare no held-out selection.")
    return {
        "schema_version": "external-fiveway-freeze-2.0",
        "frozen_at": datetime.now(timezone.utc).isoformat(),
        "split": "heldout",
        "predictions_absent_when_frozen": True,
        "labels_used_for_policy_selection": False,
        "stable_defaults_changed": False,
        "remote_provider_default_enabled": False,
        "case_pack": {
            "path": str(cases_file),
            "sha256": sha256(cases_file),
            "cases": len(rows),
            "label_counts": dict(sorted(counts.items())),
        },
        "frozen_policy": {
            "path": str(policy_file),
            "sha256": sha256(policy_file),
            "policy_id": policy.get("policy_id"),
            "selection_split": policy.get("selection_split"),
            "validation_split": policy.get("validation_split"),
        },
        "code": [
            {"path": str(Path(path)), "sha256": sha256(path)} for path in code_paths
        ],
        "source_files": payload.get("sources"),
    }


def verify_manifest(path: str | Path) -> dict[str, Any]:
    manifest_path = Path(path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    records = [manifest["case_pack"], manifest["frozen_policy"], *manifest["code"]]
    checked = []
    for record in records:
        source = Path(record["path"])
        actual = sha256(source)
        if actual != record["sha256"]:
            raise FreezeV2Error(
                "%s changed after freeze: %s != %s"
                % (source, actual, record["sha256"])
            )
        checked.append(str(source))
    return {
        "valid": True,
        "checked": checked,
        "manifest_sha256": sha256(manifest_path),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    create = subparsers.add_parser("create")
    create.add_argument("--cases", required=True)
    create.add_argument("--policy", required=True)
    create.add_argument("--code", action="append", required=True)
    create.add_argument("--output", required=True)
    verify = subparsers.add_parser("verify")
    verify.add_argument("--manifest", required=True)
    args = parser.parse_args(argv)
    if args.command == "create":
        output = Path(args.output)
        manifest = create_manifest(
            cases_path=args.cases,
            policy_path=args.policy,
            code_paths=args.code,
        )
        output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps({"manifest": str(output), "sha256": sha256(output)}, indent=2))
    else:
        print(json.dumps(verify_manifest(args.manifest), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
