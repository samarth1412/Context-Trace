from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

from contexttrace.evidence_integrity import audit_evidence_integrity
from contexttrace.verify.schema import load_trace


ISSUE_TYPES = (
    "linked_part_dropped",
    "material_span_dropped",
    "selected_text_not_in_source",
)
EXPECTED_KEYS = {"status", "issue_types", "unknown_contexts"}


class IntegrityBenchmarkError(ValueError):
    """Raised when a benchmark artifact violates the frozen data contract."""


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_manifest(manifest_path: Path) -> dict[str, Any]:
    manifest = _read_json(manifest_path)
    files = manifest.get("files")
    if not isinstance(files, dict) or not files:
        raise IntegrityBenchmarkError("manifest files must be a non-empty object")
    for relative, expected_hash in files.items():
        path = manifest_path.parent / str(relative)
        actual_hash = sha256_file(path)
        if actual_hash != expected_hash:
            raise IntegrityBenchmarkError(
                f"hash mismatch for {relative}: expected {expected_hash}, got {actual_hash}"
            )
    return manifest


def load_cases(path: Path, *, expected_split: str | None = None) -> list[dict[str, Any]]:
    payload = _read_json(path)
    split = payload.get("split")
    if expected_split is not None and split != expected_split:
        raise IntegrityBenchmarkError(
            f"{path} contains split {split!r}; expected {expected_split!r}"
        )
    cases = payload.get("cases")
    if not isinstance(cases, list) or not cases:
        raise IntegrityBenchmarkError(f"{path} cases must be a non-empty list")
    seen: set[str] = set()
    validated: list[dict[str, Any]] = []
    for index, case in enumerate(cases):
        if not isinstance(case, dict):
            raise IntegrityBenchmarkError(f"case {index} must be an object")
        case_id = str(case.get("id") or "").strip()
        if not case_id or case_id in seen:
            raise IntegrityBenchmarkError(f"case {index} has a missing or duplicate id")
        seen.add(case_id)
        expected = case.get("expected")
        if not isinstance(expected, dict) or set(expected) != EXPECTED_KEYS:
            raise IntegrityBenchmarkError(
                f"{case_id} expected must contain exactly {sorted(EXPECTED_KEYS)}"
            )
        if expected["status"] not in {"complete", "issues_found", "partial", "not_captured"}:
            raise IntegrityBenchmarkError(f"{case_id} has an invalid expected status")
        if not isinstance(expected["unknown_contexts"], int):
            raise IntegrityBenchmarkError(f"{case_id} unknown_contexts must be an integer")
        issue_types = expected["issue_types"]
        if not isinstance(issue_types, list) or any(item not in ISSUE_TYPES for item in issue_types):
            raise IntegrityBenchmarkError(f"{case_id} has an invalid expected issue type")
        trace = case.get("trace")
        if not isinstance(trace, dict):
            raise IntegrityBenchmarkError(f"{case_id} trace must be an object")
        if _contains_key(trace, "expected") or _contains_key(trace, "label"):
            raise IntegrityBenchmarkError(f"{case_id} trace contains an evaluation label")
        validated.append(case)
    return validated


def assert_disjoint(*case_sets: Iterable[dict[str, Any]]) -> None:
    seen: set[str] = set()
    for cases in case_sets:
        current = {str(case["id"]) for case in cases}
        overlap = seen & current
        if overlap:
            raise IntegrityBenchmarkError(
                "development and held-out ids overlap: %s" % ", ".join(sorted(overlap))
            )
        seen.update(current)


def run_cases(cases: list[dict[str, Any]], *, split: str, dataset_sha256: str) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    expected_counts: Counter[str] = Counter()
    predicted_counts: Counter[str] = Counter()
    true_positive_counts: Counter[str] = Counter()
    framework_totals: Counter[str] = Counter()
    framework_correct: Counter[str] = Counter()

    for case in cases:
        case_id = str(case["id"])
        framework = str(case.get("framework") or "generic")
        trace = load_trace(case["trace"], source=f"benchmark case {case_id}")
        result = audit_evidence_integrity(trace)
        expected = case["expected"]
        expected_issues = list(expected["issue_types"])
        predicted_issues = [str(issue["type"]) for issue in result["issues"]]
        expected_counter = Counter(expected_issues)
        predicted_counter = Counter(predicted_issues)
        exact = (
            result["status"] == expected["status"]
            and predicted_counter == expected_counter
            and result["summary"]["unknown_contexts"] == expected["unknown_contexts"]
        )
        expected_counts.update(expected_counter)
        predicted_counts.update(predicted_counter)
        true_positive_counts.update(expected_counter & predicted_counter)
        framework_totals[framework] += 1
        framework_correct[framework] += int(exact)
        rows.append(
            {
                "id": case_id,
                "framework": framework,
                "expected": expected,
                "actual": {
                    "status": result["status"],
                    "issue_types": predicted_issues,
                    "unknown_contexts": result["summary"]["unknown_contexts"],
                    "network_calls": result["network_calls"],
                    "model_calls": result["model_calls"],
                },
                "exact": exact,
            }
        )

    per_issue: dict[str, dict[str, float | int]] = {}
    for issue_type in ISSUE_TYPES:
        tp = true_positive_counts[issue_type]
        fp = predicted_counts[issue_type] - tp
        fn = expected_counts[issue_type] - tp
        per_issue[issue_type] = _classification_metrics(tp=tp, fp=fp, fn=fn)

    expected_issue_rows = [row for row in rows if row["expected"]["issue_types"]]
    false_green_ids = [
        str(row["id"])
        for row in expected_issue_rows
        if not row["actual"]["issue_types"]
    ]
    unknown_rows = [row for row in rows if row["expected"]["unknown_contexts"] > 0]
    exact_count = sum(int(row["exact"]) for row in rows)
    summary = {
        "cases": len(rows),
        "exact_cases": exact_count,
        "exact_case_accuracy": exact_count / len(rows),
        "dangerous_false_green_count": len(false_green_ids),
        "dangerous_false_green_rate": (
            len(false_green_ids) / len(expected_issue_rows) if expected_issue_rows else 0.0
        ),
        "dangerous_false_green_case_ids": false_green_ids,
        "unknown_cases": len(unknown_rows),
        "unknown_exact_cases": sum(int(row["exact"]) for row in unknown_rows),
        "unknown_accuracy": (
            sum(int(row["exact"]) for row in unknown_rows) / len(unknown_rows)
            if unknown_rows
            else 1.0
        ),
        "network_calls": sum(int(row["actual"]["network_calls"]) for row in rows),
        "model_calls": sum(int(row["actual"]["model_calls"]) for row in rows),
        "per_issue": per_issue,
        "framework_slices": {
            framework: {
                "cases": framework_totals[framework],
                "exact_cases": framework_correct[framework],
                "accuracy": framework_correct[framework] / framework_totals[framework],
            }
            for framework in sorted(framework_totals)
        },
    }
    accepted = (
        summary["exact_case_accuracy"] == 1.0
        and summary["dangerous_false_green_count"] == 0
        and summary["unknown_accuracy"] == 1.0
        and summary["network_calls"] == 0
        and summary["model_calls"] == 0
    )
    return {
        "schema_version": "1.0",
        "benchmark": "contexttrace_evidence_integrity",
        "split": split,
        "dataset_sha256": dataset_sha256,
        "evaluation_labels_sent_to_a_model": False,
        "acceptance": {
            "passed": accepted,
            "requirements": {
                "exact_case_accuracy": 1.0,
                "dangerous_false_green_count": 0,
                "unknown_accuracy": 1.0,
                "network_calls": 0,
                "model_calls": 0,
            },
        },
        "summary": summary,
        "rows": rows,
    }


def _classification_metrics(*, tp: int, fp: int, fn: int) -> dict[str, float | int]:
    precision = tp / (tp + fp) if tp + fp else 1.0
    recall = tp / (tp + fn) if tp + fn else 1.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"tp": tp, "fp": fp, "fn": fn, "precision": precision, "recall": recall, "f1": f1}


def _contains_key(value: Any, key: str) -> bool:
    if isinstance(value, dict):
        return key in value or any(_contains_key(item, key) for item in value.values())
    if isinstance(value, list):
        return any(_contains_key(item, key) for item in value)
    return False


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise IntegrityBenchmarkError(f"could not read {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise IntegrityBenchmarkError(f"{path} must contain a JSON object")
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, required=True)
    parser.add_argument("--split", choices=("development", "heldout"), required=True)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)

    if args.manifest:
        verify_manifest(args.manifest)
    cases = load_cases(args.cases, expected_split=args.split)
    report = run_cases(cases, split=args.split, dataset_sha256=sha256_file(args.cases))
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0 if report["acceptance"]["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
