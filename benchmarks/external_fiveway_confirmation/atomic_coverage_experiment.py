"""Evaluate experimental local atomic coverage on disjoint WiCE development cohorts."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import statistics
import time
from collections import Counter
from pathlib import Path
from typing import Any

from contexttrace.verify.atomic_coverage import AtomicCoverageJudge
from contexttrace.verify.schema import TraceContext
from contexttrace.verify.semantic_core_v2.nli import build_pinned_nli
from contexttrace.verify.semantic_core_v2.nli import verify_nli_artifact


LABELS = ("supported", "partially_supported")
THRESHOLDS = tuple(round(value / 100, 2) for value in range(5, 100, 5))
MAX_PARTIAL_TO_SUPPORTED_RATE = 0.05
MIN_SUPPORTED_RECALL = 0.50
MIN_PARTIAL_RECALL = 0.70


class AtomicExperimentError(RuntimeError):
    """Raised when the local atomic experiment contract is violated."""


def load_cohort(path: str | Path, *, cohort: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    source = Path(path)
    payload = json.loads(source.read_text(encoding="utf-8"))
    if payload.get("split") != "development":
        raise AtomicExperimentError("Atomic coverage accepts development packs only.")
    cases = payload.get("cases")
    if not isinstance(cases, list) or not cases:
        raise AtomicExperimentError("Atomic coverage needs a nonempty case pack.")
    rows = []
    for case in cases:
        if case.get("expected_verdict") not in LABELS:
            raise AtomicExperimentError("Atomic coverage has an invalid evaluation label.")
        copied = dict(case)
        copied["atomic_cohort"] = cohort
        rows.append(copied)
    metadata = {key: value for key, value in payload.items() if key != "cases"}
    metadata.update(
        {
            "path": str(source),
            "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
            "atomic_cohort": cohort,
            "cases": len(rows),
        }
    )
    return metadata, rows


def run_cases(
    cases: list[dict[str, Any]],
    *,
    judge: AtomicCoverageJudge,
) -> list[dict[str, Any]]:
    rows = []
    for case in cases:
        contexts = [
            TraceContext(id=str(item["id"]), text=str(item["text"]))
            for item in case["contexts"]
        ]
        started = time.perf_counter()
        verdict = judge.verify_claim(
            query=str(case.get("query") or ""),
            claim=str(case["claim"]),
            contexts=contexts,
        )
        latency_ms = round((time.perf_counter() - started) * 1000.0, 3)
        requirements = list(verdict.raw["requirements"])
        rows.append(
            {
                "case_id": str(case["id"]),
                "dataset": str(case["dataset"]),
                "cohort": str(case["atomic_cohort"]),
                "expected_verdict": str(case["expected_verdict"]),
                "claim_sha256": hashlib.sha256(
                    str(case["claim"]).encode("utf-8")
                ).hexdigest(),
                "prediction": {
                    "verdict": verdict.verdict,
                    "confidence": verdict.confidence,
                    "reason_code": verdict.reason,
                    "verifier_version": verdict.raw["verifier_version"],
                    "profile": dict(verdict.raw["profile"]),
                    "latency_ms": latency_ms,
                    "requirements": requirements,
                },
                "input_audit": {
                    "evaluation_label_sent_to_verifier": False,
                    "verifier_input_fields": ["query", "claim", "contexts"],
                    "local_only": True,
                    "remote_inference": False,
                    "nli_received_selected_evidence_only": True,
                    "selected_evidence_context_ids": [
                        context_id
                        for requirement in requirements
                        for context_id in requirement["evidence_context_ids"]
                    ],
                    "selected_evidence_text_sha256": [
                        hashlib.sha256(text.encode("utf-8")).hexdigest()
                        for requirement in requirements
                        for text in requirement["evidence_texts"]
                    ],
                },
            }
        )
    return rows


def threshold_prediction(row: dict[str, Any], threshold: float) -> str:
    requirements = row["prediction"]["requirements"]
    if not requirements:
        return "partially_supported"
    complete = all(
        float(requirement["nli_scores"]["entailment"]) >= threshold
        for requirement in requirements
    )
    return "supported" if complete else "partially_supported"


def metrics(rows: list[dict[str, Any]], *, threshold: float) -> dict[str, Any]:
    expected = [str(row["expected_verdict"]) for row in rows]
    predicted = [threshold_prediction(row, threshold) for row in rows]
    correct = sum(gold == guess for gold, guess in zip(expected, predicted, strict=True))
    recalls = {}
    f1s = []
    for label in LABELS:
        true_positive = sum(
            gold == guess == label
            for gold, guess in zip(expected, predicted, strict=True)
        )
        false_positive = sum(
            gold != label and guess == label
            for gold, guess in zip(expected, predicted, strict=True)
        )
        false_negative = sum(
            gold == label and guess != label
            for gold, guess in zip(expected, predicted, strict=True)
        )
        precision = (
            true_positive / (true_positive + false_positive)
            if true_positive + false_positive
            else 0.0
        )
        recall = (
            true_positive / (true_positive + false_negative)
            if true_positive + false_negative
            else 0.0
        )
        recalls[label] = round(recall, 4)
        f1s.append(
            2 * precision * recall / (precision + recall)
            if precision + recall
            else 0.0
        )
    partial_total = sum(label == "partially_supported" for label in expected)
    false_support = sum(
        gold == "partially_supported" and guess == "supported"
        for gold, guess in zip(expected, predicted, strict=True)
    )
    return {
        "cases": len(rows),
        "accuracy": round(correct / len(rows), 4),
        "macro_f1": round(statistics.fmean(f1s), 4),
        "per_label_recall": recalls,
        "partial_incorrectly_supported_count": false_support,
        "partial_incorrectly_supported_rate": round(false_support / partial_total, 4),
        "confusion": {
            label: dict(
                sorted(
                    Counter(
                        guess
                        for gold, guess in zip(expected, predicted, strict=True)
                        if gold == label
                    ).items()
                )
            )
            for label in LABELS
        },
    }


def select_threshold(calibration: list[dict[str, Any]]) -> dict[str, Any]:
    candidates = []
    for threshold in THRESHOLDS:
        result = metrics(calibration, threshold=threshold)
        safety = result["partial_incorrectly_supported_rate"] <= MAX_PARTIAL_TO_SUPPORTED_RATE
        candidates.append(
            {
                "threshold": threshold,
                "meets_safety_constraint": safety,
                "metrics": result,
            }
        )
    safe = [candidate for candidate in candidates if candidate["meets_safety_constraint"]]
    if not safe:
        raise AtomicExperimentError("No atomic threshold meets the false-support limit.")
    selected = max(
        safe,
        key=lambda candidate: (
            candidate["metrics"]["macro_f1"],
            candidate["metrics"]["accuracy"],
            candidate["metrics"]["per_label_recall"]["supported"],
            candidate["threshold"],
        ),
    )
    return {
        "selection_cohort": "calibration",
        "selection_rule": (
            "maximize macro_f1, accuracy, supported recall, then threshold among "
            "thresholds with partial-to-supported rate <= 0.05"
        ),
        "threshold": selected["threshold"],
        "calibration_metrics": selected["metrics"],
        "candidates": candidates,
    }


def analyze(rows: list[dict[str, Any]]) -> dict[str, Any]:
    calibration = [row for row in rows if row["cohort"] == "calibration"]
    validation = [row for row in rows if row["cohort"] == "validation"]
    if not calibration or not validation:
        raise AtomicExperimentError("Both calibration and validation cohorts are required.")
    policy = select_threshold(calibration)
    threshold = float(policy["threshold"])
    validation_metrics = metrics(validation, threshold=threshold)
    meets_success = bool(
        validation_metrics["per_label_recall"]["supported"] >= MIN_SUPPORTED_RECALL
        and validation_metrics["per_label_recall"]["partially_supported"]
        >= MIN_PARTIAL_RECALL
        and validation_metrics["partial_incorrectly_supported_rate"]
        <= MAX_PARTIAL_TO_SUPPORTED_RATE
    )
    return {
        "schema_version": "atomic-coverage-analysis-1.0",
        "policy": policy,
        "validation_metrics": validation_metrics,
        "prespecified_success_requirements": {
            "minimum_supported_recall": MIN_SUPPORTED_RECALL,
            "minimum_partial_recall": MIN_PARTIAL_RECALL,
            "maximum_partial_incorrectly_supported_rate": MAX_PARTIAL_TO_SUPPORTED_RATE,
        },
        "meets_prespecified_success_requirements": meets_success,
        "heldout_created": False,
        "heldout_queried": False,
        "promotion_recommendation": "continue_research" if not meets_success else "eligible_for_heldout",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--calibration-cases", required=True)
    parser.add_argument("--validation-cases", required=True)
    parser.add_argument("--model-path", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--analysis-output", required=True)
    args = parser.parse_args(argv)

    calibration_metadata, calibration_cases = load_cohort(
        args.calibration_cases, cohort="calibration"
    )
    validation_metadata, validation_cases = load_cohort(
        args.validation_cases, cohort="validation"
    )
    calibration_ids = {str(case["id"]) for case in calibration_cases}
    validation_ids = {str(case["id"]) for case in validation_cases}
    if calibration_ids & validation_ids:
        raise AtomicExperimentError("Calibration and validation case ids overlap.")

    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
    artifact = verify_nli_artifact(args.model_path)
    judge = AtomicCoverageJudge(nli=build_pinned_nli(args.model_path))
    rows = run_cases(calibration_cases + validation_cases, judge=judge)
    result = {
        "schema_version": "atomic-coverage-run-1.0",
        "experiment": "contexttrace_local_atomic_complete_support",
        "cohorts": [calibration_metadata, validation_metadata],
        "inference_contract": {
            "provider": "local_atomic_coverage",
            "local_only": True,
            "remote_inference": False,
            "evaluation_labels_used_as_model_input": False,
            "automatic_download": False,
        },
        "model_artifact": artifact,
        "rows": rows,
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    analysis = analyze(rows)
    analysis["run_sha256"] = hashlib.sha256(output.read_bytes()).hexdigest()
    analysis_output = Path(args.analysis_output)
    analysis_output.parent.mkdir(parents=True, exist_ok=True)
    analysis_output.write_text(
        json.dumps(analysis, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(analysis, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
