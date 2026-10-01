from __future__ import annotations

import json
from pathlib import Path

from contexttrace import audit_evidence_integrity
from contexttrace.verify.schema import load_trace_file


ROOT = Path(__file__).resolve().parent
CASES = {
    "langchain_linked_answer_loss.json": "linked_part_dropped",
    "llamaindex_qualifier_loss.json": "material_span_dropped",
}


def main() -> int:
    results = []
    for filename, expected in CASES.items():
        result = audit_evidence_integrity(load_trace_file(ROOT / filename))
        observed = [item["type"] for item in result["issues"]]
        passed = result["status"] == "issues_found" and observed == [expected]
        results.append(
            {
                "case": filename,
                "expected": expected,
                "observed": observed,
                "passed": passed,
                "network_calls": result["network_calls"],
                "model_calls": result["model_calls"],
            }
        )
    payload = {"passed": all(item["passed"] for item in results), "cases": results}
    print(json.dumps(payload, indent=2))
    return 0 if payload["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
