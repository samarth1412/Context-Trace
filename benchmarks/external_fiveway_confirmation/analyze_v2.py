"""Analyze the frozen second-confirmation learned-gate result."""

from __future__ import annotations

import argparse
import json
import math
import statistics
from pathlib import Path
from typing import Any

from benchmarks.external_fiveway_confirmation.ambiguity_features import evaluate_rows
from benchmarks.external_fiveway_confirmation.freeze_v2 import sha256, verify_manifest


def analyze(
    source: dict[str, Any],
    applied: dict[str, Any],
    *,
    manifest_path: str | Path,
) -> dict[str, Any]:
    verification = verify_manifest(manifest_path)
    source_rows = source.get("rows") or []
    applied_rows = applied.get("rows") or []
    if len(source_rows) != len(applied_rows) or not source_rows:
        raise ValueError("Source and applied results must contain the same nonempty rows.")
    base = evaluate_rows(source_rows, policy=None)
    gated = applied["metrics"]
    paired = {"both_correct": 0, "gate_only_correct": 0, "base_only_correct": 0, "both_wrong": 0}
    overrides = []
    for raw, final in zip(source_rows, applied_rows, strict=True):
        if raw["case_id"] != final["case_id"]:
            raise ValueError("Source and applied row order differs.")
        gold = str(raw["expected_verdict"])
        base_verdict = str(raw["signals"]["base_verdict"])
        gate_verdict = str(final["learned_gate"]["final_verdict"])
        base_correct = base_verdict == gold
        gate_correct = gate_verdict == gold
        key = (
            "both_correct"
            if base_correct and gate_correct
            else "gate_only_correct"
            if gate_correct
            else "base_only_correct"
            if base_correct
            else "both_wrong"
        )
        paired[key] += 1
        if base_verdict != gate_verdict:
            overrides.append(
                {
                    "case_id": raw["case_id"],
                    "dataset": raw["dataset"],
                    "expected_verdict": gold,
                    "base_verdict": base_verdict,
                    "gate_verdict": gate_verdict,
                    "ambiguity_probability": final["learned_gate"][
                        "ambiguity_probability"
                    ],
                    "base_correct": base_correct,
                    "gate_correct": gate_correct,
                }
            )
    discordant = paired["gate_only_correct"] + paired["base_only_correct"]
    latencies = [float(row["request"]["latency_ms"]) for row in source_rows]
    input_tokens = sum(int(row["request"]["usage"]["input_tokens"]) for row in source_rows)
    output_tokens = sum(int(row["request"]["usage"]["output_tokens"]) for row in source_rows)
    non_supported = sum(row["expected_verdict"] != "supported" for row in source_rows)
    ambiguity_cases = sum(row["expected_verdict"] == "unverifiable" for row in source_rows)
    return {
        "schema_version": "external-fiveway-confirmation-v2-analysis-1.0",
        "freeze_manifest_sha256": verification["manifest_sha256"],
        "policy_id": applied["policy_id"],
        "cases": len(source_rows),
        "base_jev": base,
        "frozen_learned_gate": gated,
        "delta": {
            "accuracy_percentage_points": round(
                100 * (gated["accuracy"] - base["accuracy"]), 2
            ),
            "macro_f1_percentage_points": round(
                100 * (gated["macro_f1"] - base["macro_f1"]), 2
            ),
            "unverifiable_recall_percentage_points": round(
                100
                * (
                    gated["per_label_recall"]["unverifiable"]
                    - base["per_label_recall"]["unverifiable"]
                ),
                2,
            ),
            "false_support_percentage_points": round(
                100 * (gated["false_support_rate"] - base["false_support_rate"]), 2
            ),
        },
        "paired_comparison": {
            **paired,
            "discordant_cases": discordant,
            "exact_two_sided_mcnemar_p": _mcnemar_exact(
                paired["gate_only_correct"], paired["base_only_correct"]
            ),
        },
        "intervals_95_wilson": {
            "base_accuracy": _wilson(round(base["accuracy"] * len(source_rows)), len(source_rows)),
            "gate_accuracy": _wilson(round(gated["accuracy"] * len(source_rows)), len(source_rows)),
            "base_false_support": _wilson(base["false_support_count"], non_supported),
            "gate_false_support": _wilson(gated["false_support_count"], non_supported),
            "gate_unverifiable_recall": _wilson(
                round(gated["per_label_recall"]["unverifiable"] * ambiguity_cases),
                ambiguity_cases,
            ),
        },
        "overrides": overrides,
        "operations": {
            "resolved_models": sorted(
                {str(row["request"]["resolved_model"]) for row in source_rows}
            ),
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
            "latency_ms": {
                "mean": round(statistics.fmean(latencies), 1),
                "p50": round(statistics.median(latencies), 1),
                "p95": round(sorted(latencies)[int(0.95 * (len(latencies) - 1))], 1),
            },
            "additional_gate_remote_requests": 0,
        },
        "stable_defaults_changed": False,
        "remote_provider_default_enabled": False,
        "limitations": [
            "This balanced confirmation contains only seven cases per verdict.",
            "The paired improvement is not significant at 0.05 in this small sample.",
            "Public-test pretraining contamination cannot be ruled out.",
        ],
    }


def _mcnemar_exact(first_only: int, second_only: int) -> float:
    n = first_only + second_only
    if n == 0:
        return 1.0
    tail = sum(math.comb(n, index) for index in range(min(first_only, second_only) + 1))
    return round(min(1.0, 2.0 * tail / (2**n)), 8)


def _wilson(successes: int, total: int) -> list[float]:
    if total <= 0:
        return [0.0, 0.0]
    z = 1.959963984540054
    observed = successes / total
    denominator = 1 + z * z / total
    center = (observed + z * z / (2 * total)) / denominator
    margin = (
        z
        * math.sqrt(observed * (1 - observed) / total + z * z / (4 * total * total))
        / denominator
    )
    return [round(center - margin, 4), round(center + margin, 4)]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True)
    parser.add_argument("--applied", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    result = analyze(
        json.loads(Path(args.source).read_text(encoding="utf-8")),
        json.loads(Path(args.applied).read_text(encoding="utf-8")),
        manifest_path=args.manifest,
    )
    Path(args.output).write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    print("analysis_sha256=%s" % sha256(args.output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
