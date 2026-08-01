"""Compare frozen v2 and v2.1 exact evidence attribution."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from contexttrace.verify.schema import RAGTrace, TraceContext
from contexttrace.verify.semantic_core_v2 import verify_trace_v2
from contexttrace.verify.semantic_core_v2_1 import verify_trace_v2_1

try:
    from benchmarks.product_safety.build_evidence_attribution_corpus import (
        DEFAULT_OUTPUT,
        build_corpus,
    )
except ModuleNotFoundError:
    from build_evidence_attribution_corpus import DEFAULT_OUTPUT, build_corpus

HERE = Path(__file__).resolve().parent
DEFAULT_REPORT = HERE / "evidence-attribution-benchmark-v1.json"


def run() -> dict[str, Any]:
    corpus = json.loads(DEFAULT_OUTPUT.read_text(encoding="utf-8"))
    if corpus != build_corpus():
        raise ValueError("Evidence-attribution development corpus is stale.")
    rows = []
    for case in corpus["cases"]:
        trace = RAGTrace(
            query=str(case["query"]),
            answer=str(case["answer"]),
            contexts=[TraceContext(**context) for context in case["contexts"]],
        )
        frozen = verify_trace_v2(trace)
        candidate = verify_trace_v2_1(trace)
        rows.append(
            {
                "id": case["id"],
                "split": case["split"],
                "expected": case["expected_spans"],
                "contexts": {context.id: context.text for context in trace.contexts},
                "answer": trace.answer,
                "frozen_v2": _claim_record(frozen),
                "candidate_v2_1": _claim_record(candidate),
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
            "All spans come from synthetic development fixtures.",
            "Held-out development families are not an untouched research test.",
            "Exact span metrics do not establish semantic correctness outside the templates.",
        ],
    }


def _claim_record(result: dict[str, Any]) -> dict[str, Any]:
    if len(result["claims"]) != 1:
        return {"runtime_failure": True, "spans": [], "answer_span": None}
    claim = result["claims"][0]
    return {
        "runtime_failure": False,
        "spans": [
            {
                "context_id": span["context_id"],
                "start_char": span["start_char"],
                "end_char": span["end_char"],
                "text": span["text"],
                "role": span["role"],
            }
            for span in claim["evidence_spans"]
        ],
        "answer_span": {
            "start_char": claim["start_char"],
            "end_char": claim["end_char"],
            "text": claim["text"],
        },
    }


def _metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "cases": len(rows),
        "frozen_v2": _system_metrics(rows, "frozen_v2"),
        "candidate_v2_1": _system_metrics(rows, "candidate_v2_1"),
    }


def _system_metrics(rows: list[dict[str, Any]], system: str) -> dict[str, Any]:
    true_positive = 0
    predicted_total = 0
    expected_total = 0
    role_correct = 0
    role_comparable = 0
    exact_source_offsets = 0
    answer_offsets = 0
    char_intersection = 0
    char_union = 0
    complete_ids = []
    mismatch_ids = []
    runtime_failures = []
    for row in rows:
        record = row[system]
        if record["runtime_failure"]:
            runtime_failures.append(row["id"])
        expected = {_span_key(span) for span in row["expected"]}
        predicted = {_span_key(span) for span in record["spans"]}
        matches = expected & predicted
        true_positive += len(matches)
        predicted_total += len(predicted)
        expected_total += len(expected)
        if predicted == expected:
            complete_ids.append(row["id"])
        else:
            mismatch_ids.append(row["id"])
        expected_positions = _char_positions(row["id"], row["expected"])
        predicted_positions = _char_positions(row["id"], record["spans"])
        char_intersection += len(expected_positions & predicted_positions)
        char_union += len(expected_positions | predicted_positions)
        expected_without_role = {
            _span_key(span, include_role=False): span["role"]
            for span in row["expected"]
        }
        for span in record["spans"]:
            key = _span_key(span, include_role=False)
            if key in expected_without_role:
                role_comparable += 1
                role_correct += span["role"] == expected_without_role[key]
            context = row["contexts"].get(span["context_id"], "")
            exact_source_offsets += (
                context[span["start_char"] : span["end_char"]] == span["text"]
            )
        answer_span = record["answer_span"]
        if answer_span:
            answer_offsets += (
                row["answer"][answer_span["start_char"] : answer_span["end_char"]]
                == answer_span["text"]
            )
    precision = _raw_ratio(true_positive, predicted_total)
    recall = _raw_ratio(true_positive, expected_total)
    return {
        "span_exact_precision": round(precision, 6),
        "span_exact_recall": round(recall, 6),
        "span_exact_f1": round(
            _raw_ratio(2 * precision * recall, precision + recall), 6
        ),
        "character_iou": round(_raw_ratio(char_intersection, char_union), 6),
        "complete_case_rate": round(_raw_ratio(len(complete_ids), len(rows)), 6),
        "over_attribution_rate": round(
            _raw_ratio(predicted_total - true_positive, predicted_total), 6
        ),
        "role_accuracy": round(_raw_ratio(role_correct, role_comparable), 6),
        "source_offset_integrity": round(
            _raw_ratio(exact_source_offsets, predicted_total), 6
        ),
        "answer_offset_integrity": round(_raw_ratio(answer_offsets, len(rows)), 6),
        "runtime_failure_ids": runtime_failures,
        "mismatch_ids": mismatch_ids,
    }


def _span_key(span: dict[str, Any], *, include_role: bool = True) -> tuple[Any, ...]:
    values: tuple[Any, ...] = (
        span["context_id"],
        int(span["start_char"]),
        int(span["end_char"]),
        str(span["text"]),
    )
    return (*values, span["role"]) if include_role else values


def _char_positions(
    case_id: str, spans: list[dict[str, Any]]
) -> set[tuple[str, str, str, int]]:
    return {
        (case_id, str(span["context_id"]), str(span["role"]), position)
        for span in spans
        for position in range(int(span["start_char"]), int(span["end_char"]))
    }


def _raw_ratio(numerator: float, denominator: float) -> float:
    return numerator / denominator if denominator else 0.0


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
