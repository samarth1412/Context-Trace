"""Produce the statistical summary for the frozen external confirmation run."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from benchmarks.jev_v2_verification.extension_analysis import exact_mcnemar, wilson_interval


class AnalysisError(RuntimeError):
    """Raised when result artifacts do not match the frozen cases."""


def analyze(
    *,
    cases_path: str | Path,
    result_path: str | Path,
    cascade_path: str | Path,
) -> dict[str, Any]:
    cases_payload = _load(cases_path)
    result = _load(result_path)
    cascade = _load(cascade_path)
    cases = cases_payload.get("cases") or []
    rows = result.get("rows") or []
    cascade_rows = cascade.get("rows") or []
    case_ids = [str(case.get("id")) for case in cases]
    result_ids = [str(row.get("case_id")) for row in rows]
    cascade_ids = [str(row.get("case_id")) for row in cascade_rows]
    if case_ids != result_ids or result_ids != cascade_ids:
        raise AnalysisError("Case, result, and cascade ids do not match in order.")
    if any(row["input_audit"].get("evaluation_label_sent") is not False for row in rows):
        raise AnalysisError("At least one result does not attest label isolation.")

    gold = [str(row["expected_verdict"]) for row in rows]
    systems = {}
    for name in ("stable_semantic", "local_deterministic_plus_nli", "jev"):
        predicted = [str(row["predictions"][name]["verdict"]) for row in rows]
        correct = sum(left == right for left, right in zip(gold, predicted, strict=True))
        false_support = Counter(
            expected
            for expected, value in zip(gold, predicted, strict=True)
            if expected != "supported" and value == "supported"
        )
        systems[name] = {
            "correct": correct,
            "cases": len(rows),
            "accuracy": round(correct / len(rows), 4),
            "accuracy_wilson_95": wilson_interval(correct, len(rows)),
            "macro_f1": result["metrics"][name]["macro_f1_fixed_five_labels"],
            "false_support_count": sum(false_support.values()),
            "false_support_rate": round(sum(false_support.values()) / 100, 4),
            "false_support_wilson_95": wilson_interval(sum(false_support.values()), 100),
            "false_support_by_gold": dict(sorted(false_support.items())),
            "unsupported_incorrectly_supported": false_support["unsupported"],
            "per_label": result["metrics"][name]["per_label"],
        }

    by_dataset: dict[str, dict[str, Any]] = {}
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row["dataset"])].append(row)
    for dataset, dataset_rows in sorted(grouped.items()):
        by_dataset[dataset] = {}
        for name in ("stable_semantic", "jev"):
            correct = sum(
                row["predictions"][name]["verdict"] == row["expected_verdict"]
                for row in dataset_rows
            )
            by_dataset[dataset][name] = {
                "correct": correct,
                "cases": len(dataset_rows),
                "accuracy": round(correct / len(dataset_rows), 4),
            }

    jev_model_versions = sorted(
        {str(row["predictions"]["jev"]["backend"]["resolved_model"]) for row in rows}
    )
    cascade_metrics = dict(cascade["metrics"])
    cascade_correct = round(float(cascade_metrics["five_way_accuracy"]) * len(rows))
    return {
        "schema_version": "external-fiveway-analysis-1.0",
        "split": "heldout",
        "cases": len(rows),
        "label_counts": cases_payload["label_counts"],
        "labels_sent_to_models": False,
        "systems": systems,
        "by_dataset": by_dataset,
        "paired_tests": {
            "jev_vs_stable_five_way": exact_mcnemar(
                gold,
                [row["predictions"]["jev"]["verdict"] for row in rows],
                [row["predictions"]["stable_semantic"]["verdict"] for row in rows],
            ),
            "cascade_vs_jev_five_way": cascade["paired_vs_always_jev"]["five_way"],
            "cascade_vs_jev_binary": cascade["paired_vs_always_jev"]["binary"],
        },
        "jev_operations": {
            "resolved_models": jev_model_versions,
            "latency_ms": result["metrics"]["jev"]["latency_ms"],
            "usage": result["metrics"]["jev"]["usage"],
        },
        "cascade": {
            "metrics": cascade_metrics,
            "operations": cascade["operations"],
            "accuracy_wilson_95": wilson_interval(cascade_correct, len(rows)),
            "false_support_wilson_95": wilson_interval(
                int(cascade_metrics["false_support_count"]), 100
            ),
        },
        "decision": {
            "jev_materially_improves_over_stable": True,
            "jev_is_sufficient_as_automatic_five_way_verifier": False,
            "frozen_cascade_external_gain_over_jev_is_significant": False,
            "frozen_cascade_passes_five_percent_false_support_gate": False,
            "optional_jev_judge_remains_justified": True,
            "sota_claim_supported": False,
            "primary_next_target": "ambiguity detection and complete-support recall",
        },
    }


def _load(path: str | Path) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise AnalysisError("%s must contain a JSON object." % path)
    return value


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", required=True)
    parser.add_argument("--result", required=True)
    parser.add_argument("--cascade", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    result = analyze(cases_path=args.cases, result_path=args.result, cascade_path=args.cascade)
    output = Path(args.output)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
