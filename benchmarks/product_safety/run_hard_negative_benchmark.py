"""Compare pinned generic NLI with the observable-conflict checker."""

from __future__ import annotations

import argparse
import json
import math
import statistics
import time
from importlib.metadata import version
from pathlib import Path
from typing import Any

from build_hard_negatives import (
    DEFAULT_OUTPUT,
    build_corpus,
)
from contexttrace.verify.judges import ClaimJudge
from contexttrace.verify.schema import TraceContext
from contexttrace.verify.semantic_core_v2 import build_pinned_nli, verify_nli_artifact
from contexttrace.verify.semantic_core_v2_1 import (
    OBSERVABLE_CONFLICT_GUARD_VERSION,
    ObservableConflictGuard,
)

ACCEPTED_ENTAILMENT_THRESHOLD = 0.80


def run_benchmark(model_path: Path) -> dict[str, Any]:
    expected_corpus = build_corpus()
    stored_corpus = json.loads(DEFAULT_OUTPUT.read_text(encoding="utf-8"))
    if stored_corpus != expected_corpus:
        raise ValueError("Hard-negative corpus is stale; rebuild it first.")
    lock = verify_nli_artifact(model_path)
    base = build_pinned_nli(model_path)
    generic = _score_cases(list(stored_corpus["cases"]), base)
    dedicated = _score_cases(
        list(stored_corpus["cases"]),
        ObservableConflictGuard(base),
    )
    gates = {
        "dedicated_accuracy_at_least_0_95": dedicated["accuracy"] >= 0.95,
        "dedicated_false_entailment_rate_zero": (
            dedicated["accepted_false_entailment_rate"] == 0.0
        ),
        "dedicated_positive_recall_at_least_0_95": (
            dedicated["positive_recall"] >= 0.95
        ),
        "no_positive_regression": (
            dedicated["positive_recall"] >= generic["positive_recall"]
        ),
    }
    return {
        "schema_version": "1.0",
        "benchmark_id": "contexttrace-observable-conflict-hard-negatives-v1",
        "evidence_class": "synthetic_development_only_not_research_evidence",
        "corpus": {
            "case_count": stored_corpus["case_count"],
            "payload_sha256": stored_corpus["payload_sha256"],
            "seed_sha256": stored_corpus["seed_sha256"],
        },
        "model_lock": {
            "model_id": lock["model_id"],
            "model_revision": lock["model_revision"],
            "artifact_manifest_sha256": lock["artifact_manifest_sha256"],
            "runtime_versions": {
                "torch": version("torch"),
                "transformers": version("transformers"),
            },
        },
        "accepted_entailment_threshold": ACCEPTED_ENTAILMENT_THRESHOLD,
        "generic_nli": generic,
        "dedicated_checker": {
            **dedicated,
            "guard_version": OBSERVABLE_CONFLICT_GUARD_VERSION,
        },
        "gates": {"all_passed": all(gates.values()), "rows": gates},
        "limitations": [
            "This is synthetic development evidence and cannot establish SOTA.",
            "The guard handles only explicit observable conflicts and is not a general truth model.",
            "External and untouched evaluation remain required after the checker is frozen.",
        ],
    }


def _score_cases(cases: list[dict[str, Any]], judge: ClaimJudge) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    latencies: list[float] = []
    for case in cases:
        started = time.perf_counter()
        verdict = judge.verify_claim(
            query=str(case["query"]),
            claim=str(case["claim"]),
            contexts=[
                TraceContext(
                    id=str(case["id"]),
                    text=str(case["premise"]),
                )
            ],
        )
        latencies.append((time.perf_counter() - started) * 1000.0)
        accepted_supported = bool(
            verdict.verdict == "supported"
            and verdict.confidence >= ACCEPTED_ENTAILMENT_THRESHOLD
        )
        expected_supported = case["expected"] == "supported"
        rows.append(
            {
                "id": case["id"],
                "category": case["category"],
                "expected": case["expected"],
                "verdict": verdict.verdict,
                "confidence": verdict.confidence,
                "accepted_supported": accepted_supported,
                "correct": accepted_supported == expected_supported,
                "guard_intervened": bool(verdict.raw.get("observable_conflict_guard")),
            }
        )

    positives = [row for row in rows if row["expected"] == "supported"]
    negatives = [row for row in rows if row["expected"] == "not_supported"]
    false_entailments = [row for row in negatives if row["accepted_supported"]]
    interventions = [row for row in rows if row["guard_intervened"]]
    return {
        "cases": len(rows),
        "accuracy": _ratio(sum(bool(row["correct"]) for row in rows), len(rows)),
        "positive_recall": _ratio(
            sum(bool(row["accepted_supported"]) for row in positives),
            len(positives),
        ),
        "accepted_false_entailment_rate": _ratio(
            len(false_entailments),
            len(negatives),
        ),
        "accepted_false_entailment_ids": [row["id"] for row in false_entailments],
        "guard_intervention_ids": [row["id"] for row in interventions],
        "guard_intervention_categories": sorted(
            {str(row["category"]) for row in interventions}
        ),
        "latency_ms": {
            "p50": round(statistics.median(latencies), 3) if latencies else 0.0,
            "p95": _percentile(latencies, 0.95),
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-path", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--enforce", action="store_true")
    args = parser.parse_args(argv)
    result = run_benchmark(args.model_path)
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    if args.enforce and not result["gates"]["all_passed"]:
        return 1
    return 0


def _ratio(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 6) if denominator else 0.0


def _percentile(values: list[float], quantile: float) -> float:
    if not values:
        return 0.0
    index = max(0, math.ceil(quantile * len(values)) - 1)
    return round(sorted(values)[index], 3)


if __name__ == "__main__":
    raise SystemExit(main())
