from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path
from typing import Any


def finalize_after_review(
    *,
    output_dir: str | Path,
    sensitivity_json: str | Path,
    sensitivity_md: str | Path,
    simulated_status: str | Path,
) -> dict[str, Any]:
    destination = Path(output_dir)
    manifest_path = destination / "manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError("Full frozen-label manifest is missing: %s" % manifest_path)
    manifest = _load(manifest_path)
    sensitivity_json_path = Path(sensitivity_json)
    sensitivity_md_path = Path(sensitivity_md)
    status_path = Path(simulated_status)
    for source in (sensitivity_json_path, sensitivity_md_path, status_path):
        if not source.is_file():
            raise FileNotFoundError("Required review artifact is missing: %s" % source)
    copied = []
    for source, name in (
        (sensitivity_json_path, "sensitivity_analysis.json"),
        (sensitivity_md_path, "sensitivity_analysis.md"),
        (status_path, "simulated_review_status.json"),
    ):
        target = destination / name
        shutil.copyfile(source, target)
        copied.append({"path": name, "bytes": target.stat().st_size, "sha256": _sha256(target)})
    manifest["after_review_status"] = {
        "review_kind": "llm_simulated_pilot",
        "human_review_complete": False,
        "independent_review_complete": False,
        "corrections_applied": 0,
        "frozen_labels_preserved": True,
        "paper_result_eligible": False,
        "sota_gate_eligible": False,
        "sensitivity_only": True,
        "artifacts": copied,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest["after_review_status"]


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError("%s must contain a JSON object." % path)
    return value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description="Finalize frozen-label ARR outputs after simulated review.")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--sensitivity-json", required=True)
    parser.add_argument("--sensitivity-md", required=True)
    parser.add_argument("--simulated-status", required=True)
    args = parser.parse_args()
    status = finalize_after_review(
        output_dir=args.output_dir,
        sensitivity_json=args.sensitivity_json,
        sensitivity_md=args.sensitivity_md,
        simulated_status=args.simulated_status,
    )
    print("Frozen labels preserved: %s" % status["frozen_labels_preserved"])
    print("Corrections applied: %s" % status["corrections_applied"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
