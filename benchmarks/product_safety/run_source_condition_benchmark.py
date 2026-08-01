"""Compare frozen v2 and candidate v2.1 source-condition reasoning."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from contexttrace.verify.schema import RAGTrace, TraceContext
from contexttrace.verify.semantic_core_v2 import verify_trace_v2
from contexttrace.verify.semantic_core_v2_1 import verify_trace_v2_1

try:
    from benchmarks.product_safety.build_source_condition_corpus import (
        DEFAULT_OUTPUT,
        build_corpus,
    )
except ModuleNotFoundError:
    from build_source_condition_corpus import DEFAULT_OUTPUT, build_corpus

HERE = Path(__file__).resolve().parent
DEFAULT_REPORT = HERE / "source-condition-benchmark-v1.json"


def run() -> dict[str, Any]:
    corpus = json.loads(DEFAULT_OUTPUT.read_text(encoding="utf-8"))
    if corpus != build_corpus():
        raise ValueError("Source-condition development corpus is stale.")
    rows = []
    for case in corpus["cases"]:
        trace = RAGTrace(
            query=str(case["query"]),
            answer=str(case["answer"]),
            contexts=[TraceContext(**context) for context in case["contexts"]],
        )
        frozen = verify_trace_v2(trace)["claims"][0]
        candidate = verify_trace_v2_1(trace)["claims"][0]
        rows.append(
            {
                "id": case["id"],
                "split": case["split"],
                "expected": case["expected_source_condition"],
                "frozen_v2": frozen["source_condition"],
                "candidate_v2_1": candidate["source_condition"],
                "frozen_green": frozen["green"],
                "candidate_green": candidate["green"],
            }
        )
    return {
        "schema_version": "1.0",
        "evidence_class": "synthetic_development_only_not_research_evidence",
        "corpus_payload_sha256": corpus["payload_sha256"],
        "all_cases": _metrics(rows),
        "heldout_development": _metrics(
            [row for row in rows if row["split"] == "heldout_development"]
        ),
        "limitations": [
            "All cases are synthetic development fixtures.",
            "Held-out development families are not an untouched research test.",
            "The corpus measures metadata and relation handling, not independent truth.",
        ],
    }


def _metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    labels = [str(row["expected"]) for row in rows]
    unsafe = {
        "current_noncanonical",
        "stale",
        "superseded",
        "low_authority",
        "conflicting_authorities",
    }
    return {
        "cases": len(rows),
        "frozen_v2": _system_metrics(rows, labels, "frozen_v2", "frozen_green", unsafe),
        "candidate_v2_1": _system_metrics(
            rows,
            labels,
            "candidate_v2_1",
            "candidate_green",
            unsafe,
        ),
    }


def _system_metrics(
    rows: list[dict[str, Any]],
    labels: list[str],
    prediction_key: str,
    green_key: str,
    unsafe: set[str],
) -> dict[str, Any]:
    predictions = [str(row[prediction_key]) for row in rows]
    dangerous = [row for row in rows if row["expected"] in unsafe]
    return {
        "accuracy": _ratio(
            sum(
                prediction == label
                for prediction, label in zip(predictions, labels, strict=True)
            ),
            len(labels),
        ),
        "macro_f1": _macro_f1(labels, predictions),
        "dangerous_false_green_rate": _ratio(
            sum(bool(row[green_key]) for row in dangerous),
            len(dangerous),
        ),
        "mismatch_ids": [
            str(row["id"]) for row in rows if row[prediction_key] != row["expected"]
        ],
        "dangerous_false_green_ids": [
            str(row["id"]) for row in dangerous if bool(row[green_key])
        ],
        "prediction_counts": dict(sorted(Counter(predictions).items())),
    }


def _macro_f1(labels: list[str], predictions: list[str]) -> float:
    values = sorted(set(labels) | set(predictions))
    scores = []
    for value in values:
        true_positive = sum(
            label == value and prediction == value
            for label, prediction in zip(labels, predictions, strict=True)
        )
        false_positive = sum(
            label != value and prediction == value
            for label, prediction in zip(labels, predictions, strict=True)
        )
        false_negative = sum(
            label == value and prediction != value
            for label, prediction in zip(labels, predictions, strict=True)
        )
        precision = _raw_ratio(true_positive, true_positive + false_positive)
        recall = _raw_ratio(true_positive, true_positive + false_negative)
        scores.append(_raw_ratio(2 * precision * recall, precision + recall))
    return round(sum(scores) / len(scores), 6) if scores else 0.0


def _raw_ratio(numerator: float, denominator: float) -> float:
    return numerator / denominator if denominator else 0.0


def _ratio(numerator: int, denominator: int) -> float:
    return round(_raw_ratio(numerator, denominator), 6)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args(argv)
    args.output.write_text(
        json.dumps(run(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
