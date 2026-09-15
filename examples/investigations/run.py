#!/usr/bin/env python3
"""Run the public ContextTrace investigation regression artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from contexttrace.verify import verify_trace_file


ROOT = Path(__file__).resolve().parent


def nested(payload: dict[str, Any], path: str) -> Any:
    value: Any = payload
    for part in path.split("."):
        value = value[int(part)] if isinstance(value, list) else value[part]
    return value


def run_case(case_dir: Path) -> dict[str, Any]:
    spec = json.loads((case_dir / "regression.json").read_text(encoding="utf-8"))
    result: dict[str, Any] = {"case_id": spec["case_id"], "checks": [], "passed": True}
    for state in ("broken", "fixed"):
        verification = verify_trace_file(case_dir / spec[f"{state}_trace"])
        for field, expected in spec[f"{state}_assertions"].items():
            actual = nested(verification, field)
            passed = actual == expected
            result["checks"].append({
                "state": state, "field": field, "expected": expected,
                "actual": actual, "passed": passed,
            })
            result["passed"] = result["passed"] and passed
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--case", help="Investigation directory name")
    group.add_argument("--all", action="store_true", help="Run every investigation")
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args()

    directories = (
        sorted(path.parent for path in ROOT.glob("*/regression.json"))
        if args.all
        else [ROOT / args.case]
    )
    if not directories or any(not (path / "regression.json").exists() for path in directories):
        parser.error("No matching investigation regression artifact was found.")

    cases = [run_case(path) for path in directories]
    payload = {
        "schema_version": "contexttrace-growth-run-v1",
        "summary": {
            "case_count": len(cases),
            "trace_count": len(cases) * 2,
            "check_count": sum(len(case["checks"]) for case in cases),
            "passed": all(case["passed"] for case in cases),
        },
        "cases": cases,
    }
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))
    return 0 if payload["summary"]["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
