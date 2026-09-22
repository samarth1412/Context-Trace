"""Freeze and verify the external five-way confirmation case pack."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from benchmarks.external_fiveway_confirmation.adapter import LABELS


class FreezeError(RuntimeError):
    """Raised when a confirmation freeze fails integrity checks."""


def sha256(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def create_manifest(
    *,
    cases_path: str | Path,
    adapter_path: str | Path,
    runner_path: str | Path,
    cascade_policy_path: str | Path,
) -> dict[str, Any]:
    cases_file = Path(cases_path)
    payload = json.loads(cases_file.read_text(encoding="utf-8"))
    rows = payload.get("cases")
    if not isinstance(rows, list) or not rows:
        raise FreezeError("Case pack is empty.")
    ids = [str(row.get("id") or "") for row in rows]
    if any(not value for value in ids) or len(ids) != len(set(ids)):
        raise FreezeError("Case ids must be non-empty and unique.")
    counts = Counter(str(row.get("expected_verdict")) for row in rows)
    if set(counts) != set(LABELS) or len(set(counts.values())) != 1:
        raise FreezeError("Case pack must be balanced across exactly five verdicts.")
    policy = json.loads(Path(cascade_policy_path).read_text(encoding="utf-8"))
    return {
        "schema_version": "external-fiveway-freeze-1.0",
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
        "code": {
            "adapter": {"path": str(adapter_path), "sha256": sha256(adapter_path)},
            "shared_input_runner": {"path": str(runner_path), "sha256": sha256(runner_path)},
        },
        "frozen_cascade_policy": {
            "path": str(cascade_policy_path),
            "file_sha256": sha256(cascade_policy_path),
            "policy_id": policy.get("policy_id"),
            "selection_split": policy.get("selection_split"),
        },
        "source_files": payload.get("sources"),
    }


def verify_manifest(manifest_path: str | Path) -> dict[str, Any]:
    manifest_file = Path(manifest_path)
    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    checked = []
    records = [manifest["case_pack"], *manifest["code"].values(), manifest["frozen_cascade_policy"]]
    for record in records:
        path = Path(record["path"])
        expected = record.get("sha256") or record.get("file_sha256")
        actual = sha256(path)
        if actual != expected:
            raise FreezeError("%s changed after freeze: %s != %s" % (path, actual, expected))
        checked.append(str(path))
    return {"valid": True, "checked": checked, "manifest_sha256": sha256(manifest_file)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    create = subparsers.add_parser("create")
    create.add_argument("--cases", required=True)
    create.add_argument("--adapter", required=True)
    create.add_argument("--runner", required=True)
    create.add_argument("--cascade-policy", required=True)
    create.add_argument("--output", required=True)
    verify = subparsers.add_parser("verify")
    verify.add_argument("--manifest", required=True)
    args = parser.parse_args(argv)
    if args.command == "create":
        output = Path(args.output)
        manifest = create_manifest(
            cases_path=args.cases,
            adapter_path=args.adapter,
            runner_path=args.runner,
            cascade_policy_path=args.cascade_policy,
        )
        output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps({"manifest": str(output), "sha256": sha256(output)}, indent=2))
    else:
        print(json.dumps(verify_manifest(args.manifest), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

