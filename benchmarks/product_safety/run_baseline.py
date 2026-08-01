"""Run the repeatable, development-only semantic-core product safety baseline."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any

from contexttrace.verify.schema import RAGTrace, load_trace
from contexttrace.verify.semantic_core_v2.profile import DETERMINISTIC_ONLY_V2_PROFILE
from contexttrace.verify.semantic_core_v2.runner import verify_trace_v2

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
CONTROLLED_CASES = HERE / "controlled_cases.json"
PUBLIC_HOLDOUT = (
    REPO_ROOT
    / "packages"
    / "contexttrace"
    / "contexttrace"
    / "verify"
    / "public_holdout_cases.json"
)

TARGETS = {
    "controlled_exact_match_rate": {"operator": ">=", "value": 0.9},
    "public_verdict_match_rate": {"operator": ">=", "value": 0.75},
    "public_clean_supported_rate": {"operator": ">=", "value": 0.9},
    "public_dangerous_false_green_rate": {"operator": "<=", "value": 0.02},
    "public_abstention_requirement_recall": {"operator": ">=", "value": 0.9},
    "public_unresolved_route_rate": {"operator": "<=", "value": 0.4},
    "public_p95_latency_ms": {"operator": "<=", "value": 250.0},
    "runtime_failures": {"operator": "==", "value": 0},
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", type=Path, help="Write the JSON result to this path."
    )
    parser.add_argument(
        "--enforce",
        action="store_true",
        help="Exit non-zero when a target is missed.",
    )
    args = parser.parse_args(argv)

    result = run_baseline()
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        sys.stdout.write(rendered)
    if args.enforce and not result["targets"]["all_passed"]:
        return 1
    return 0


def run_baseline() -> dict[str, Any]:
    controlled_payload = _read_json(CONTROLLED_CASES)
    public_payload = _read_json(PUBLIC_HOLDOUT)
    controlled = _run_controlled(list(controlled_payload["cases"]))
    public = _run_public(list(public_payload["cases"]))
    measured = {
        "controlled_exact_match_rate": controlled["exact_match_rate"],
        "public_verdict_match_rate": public["verdict_match_rate"],
        "public_clean_supported_rate": public["clean_supported_rate"],
        "public_dangerous_false_green_rate": public["dangerous_false_green_rate"],
        "public_abstention_requirement_recall": public["abstention_requirement_recall"],
        "public_unresolved_route_rate": public["unresolved_route_rate"],
        "public_p95_latency_ms": public["latency_ms"]["p95"],
        "runtime_failures": controlled["runtime_failures"] + public["runtime_failures"],
    }
    return {
        "schema_version": "1.0",
        "benchmark_id": "contexttrace-product-safety-dev-v1",
        "evidence_class": "development_only_not_independent_research_evidence",
        "profile_id": DETERMINISTIC_ONLY_V2_PROFILE.id,
        "profile_sha256": DETERMINISTIC_ONLY_V2_PROFILE.sha256,
        "inputs": {
            "controlled_cases": {
                "count": len(controlled_payload["cases"]),
                "sha256": _file_sha256(CONTROLLED_CASES),
            },
            "public_holdout": {
                "count": len(public_payload["cases"]),
                "sha256": _file_sha256(PUBLIC_HOLDOUT),
            },
        },
        "controlled": controlled,
        "public_holdout": public,
        "targets": _score_targets(measured),
        "interpretation": [
            "These labels are visible during development and cannot support untouched-evaluation claims.",
            "A missed target identifies product work; it is not a confirmatory research result.",
            "The deterministic-only profile measures which claims require a later selective model route without making model calls.",
        ],
    }


def _run_controlled(items: list[dict[str, Any]]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    runtime_failures = 0
    for item in items:
        try:
            result, latency_ms = _verify(item, source="controlled safety fixture")
            actual = _projection(result)
            expected = dict(item["expected"])
            mismatches = {
                key: {"expected": value, "actual": actual.get(key)}
                for key, value in expected.items()
                if actual.get(key) != value
            }
            rows.append(
                {
                    "id": item["id"],
                    "passed": not mismatches,
                    "mismatches": mismatches,
                    "latency_ms": latency_ms,
                }
            )
        except Exception as exc:  # noqa: BLE001  # pragma: no cover
            runtime_failures += 1
            rows.append(
                {
                    "id": item.get("id"),
                    "passed": False,
                    "runtime_error": type(exc).__name__,
                }
            )
    passed = sum(bool(row["passed"]) for row in rows)
    return {
        "cases": len(rows),
        "passed": passed,
        "exact_match_rate": _ratio(passed, len(rows)),
        "runtime_failures": runtime_failures,
        "failures": [row for row in rows if not row["passed"]],
    }


def _run_public(items: list[dict[str, Any]]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    runtime_failures = 0
    claim_routes: Counter[str] = Counter()
    latencies: list[float] = []
    for item in items:
        try:
            result, latency_ms = _verify(item, source="public development holdout")
            latencies.append(latency_ms)
            summary = dict(result["summary"])
            predicted_counts = dict(summary["claim_verdicts"])
            expected_counts = dict(item.get("expected_verdict_counts") or {})
            verdict_match = _counts_match(expected_counts, predicted_counts)
            clean = set(item.get("expected_labels") or []) == {"no_failure_detected"}
            clean_supported = bool(
                clean
                and summary["total_claims"] > 0
                and set(predicted_counts) == {"supported"}
            )
            unsafe = _expected_unsafe(item)
            false_green = bool(unsafe and summary["green_claims"] > 0)
            requires_abstention = any(
                claim["abstention_requirement"] == "must_abstain"
                for claim in result["claims"]
            )
            for claim in result["claims"]:
                claim_routes[str(claim["route"])] += 1
            rows.append(
                {
                    "id": item["id"],
                    "verdict_match": verdict_match,
                    "clean": clean,
                    "clean_supported": clean_supported,
                    "expected_unsafe": unsafe,
                    "dangerous_false_green": false_green,
                    "expected_should_abstain": bool(
                        item.get("expected_should_abstain")
                    ),
                    "requires_abstention": requires_abstention,
                    "expected_verdict_counts": expected_counts,
                    "predicted_verdict_counts": predicted_counts,
                }
            )
        except Exception as exc:  # noqa: BLE001  # pragma: no cover
            runtime_failures += 1
            rows.append(
                {
                    "id": item.get("id"),
                    "runtime_error": type(exc).__name__,
                }
            )

    valid = [row for row in rows if "runtime_error" not in row]
    clean_rows = [row for row in valid if row["clean"]]
    unsafe_rows = [row for row in valid if row["expected_unsafe"]]
    abstain_rows = [row for row in valid if row["expected_should_abstain"]]
    total_claims = sum(claim_routes.values())
    return {
        "cases": len(rows),
        "runtime_failures": runtime_failures,
        "verdict_match_rate": _ratio(
            sum(bool(row["verdict_match"]) for row in valid), len(valid)
        ),
        "clean_supported_rate": _ratio(
            sum(bool(row["clean_supported"]) for row in clean_rows),
            len(clean_rows),
        ),
        "dangerous_false_green_rate": _ratio(
            sum(bool(row["dangerous_false_green"]) for row in unsafe_rows),
            len(unsafe_rows),
        ),
        "abstention_requirement_recall": _ratio(
            sum(bool(row["requires_abstention"]) for row in abstain_rows),
            len(abstain_rows),
        ),
        "unresolved_route_rate": _ratio(claim_routes["unresolved"], total_claims),
        "route_counts": dict(sorted(claim_routes.items())),
        "latency_ms": {
            "p50": round(statistics.median(latencies), 3) if latencies else 0.0,
            "p95": _percentile(latencies, 0.95),
        },
        "verdict_miss_ids": [row["id"] for row in valid if not row["verdict_match"]],
        "dangerous_false_green_ids": [
            row["id"] for row in unsafe_rows if row["dangerous_false_green"]
        ],
    }


def _verify(item: dict[str, Any], *, source: str) -> tuple[dict[str, Any], float]:
    contexts = [
        {
            "id": context["id"],
            "text": context["text"],
            "metadata": {
                **dict(context.get("metadata") or {}),
                **({"source": context["source"]} if context.get("source") else {}),
                **(
                    {"source_url": context["source_url"]}
                    if context.get("source_url")
                    else {}
                ),
            },
        }
        for context in item.get("contexts") or []
    ]
    metadata = {"case_id": item["id"], **dict(item.get("metadata") or {})}
    trace: RAGTrace = load_trace(
        {
            "query": item["query"],
            "answer": item["answer"],
            "contexts": contexts,
            "citations": item.get("citations") or [],
            "metadata": metadata,
        },
        source=f"{source} {item['id']}",
    )
    started = time.perf_counter()
    result = verify_trace_v2(trace, profile=DETERMINISTIC_ONLY_V2_PROFILE)
    latency_ms = round((time.perf_counter() - started) * 1000, 3)
    return result, latency_ms


def _projection(result: dict[str, Any]) -> dict[str, Any]:
    claims = list(result["claims"])
    return {
        "claim_verdicts": dict(result["summary"]["claim_verdicts"]),
        "green_claims": result["summary"]["green_claims"],
        "diagnostic_abstentions": result["summary"]["diagnostic_abstentions"],
        "source_conditions": [claim["source_condition"] for claim in claims],
        "citation_states": [claim["citation_state"] for claim in claims],
        "failure_labels": [claim["failure_label"] for claim in claims],
        "root_causes": [claim["primary_root_cause"] for claim in claims],
        "truncation_applied": bool(result["truncation"]["applied"]),
    }


def _expected_unsafe(item: dict[str, Any]) -> bool:
    counts = dict(item.get("expected_verdict_counts") or {})
    return bool(
        item.get("expected_should_abstain") is True
        or counts.get("contradicted", 0)
        or counts.get("unsupported", 0)
        or counts.get("unverifiable", 0)
    )


def _counts_match(expected: dict[str, int], predicted: dict[str, int]) -> bool:
    keys = set(expected) | set(predicted)
    return all(int(expected.get(key, 0)) == int(predicted.get(key, 0)) for key in keys)


def _score_targets(measured: dict[str, int | float]) -> dict[str, Any]:
    rows: dict[str, Any] = {}
    for name, target in TARGETS.items():
        actual = measured[name]
        operator = target["operator"]
        threshold = target["value"]
        passed = (
            actual >= threshold
            if operator == ">="
            else actual <= threshold
            if operator == "<="
            else actual == threshold
        )
        rows[name] = {
            "actual": actual,
            "operator": operator,
            "target": threshold,
            "passed": passed,
        }
    return {"all_passed": all(row["passed"] for row in rows.values()), "rows": rows}


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _ratio(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 6) if denominator else 0.0


def _percentile(values: list[float], quantile: float) -> float:
    if not values:
        return 0.0
    index = max(0, math.ceil(quantile * len(values)) - 1)
    return round(sorted(values)[index], 3)


if __name__ == "__main__":
    raise SystemExit(main())
