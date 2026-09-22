from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import resource
import statistics
import time
from pathlib import Path
from typing import Any

from contexttrace.verify.local_quality import LocalQualityJudge, LocalQualityProfile
from contexttrace.verify.runner import verify_trace
from contexttrace.verify.schema import RAGTrace, TraceContext
from contexttrace.verify.semantic_core_v2.constants import (
    NLI_MODEL_ID,
    NLI_MODEL_REVISION,
)
from contexttrace.verify.semantic_core_v2.nli import build_pinned_nli, verify_nli_artifact


LABELS = (
    "supported",
    "partially_supported",
    "unsupported",
    "contradicted",
    "unverifiable",
)


def load_cases(path: str | Path, *, expected_split: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    source = Path(path)
    payload = json.loads(source.read_text(encoding="utf-8"))
    if payload.get("split") != expected_split:
        raise ValueError("Expected split %s in %s." % (expected_split, source))
    rows = payload.get("cases")
    if not isinstance(rows, list) or not rows:
        raise ValueError("Case file must contain a non-empty cases list.")
    ids: set[str] = set()
    for row in rows:
        case_id = str(row.get("id") or "")
        if not case_id or case_id in ids:
            raise ValueError("Case ids must be non-empty and unique.")
        ids.add(case_id)
        if row.get("expected_verdict") not in LABELS:
            raise ValueError("Case %s has an invalid verdict." % case_id)
    metadata = {
        "path": str(source),
        "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "split": payload["split"],
        "provenance": payload.get("provenance"),
        "scenario_families": list(payload.get("scenario_families") or []),
    }
    return metadata, rows


def run_evaluation(
    cases: list[dict[str, Any]],
    *,
    split_metadata: dict[str, Any],
    nli: object | None = None,
    nli_metadata: dict[str, Any] | None = None,
    initialization: dict[str, Any] | None = None,
) -> dict[str, Any]:
    variants: list[tuple[str, LocalQualityJudge | None]] = [
        ("stable_semantic", None),
        (
            "local_decomposition_only",
            LocalQualityJudge(
                profile=LocalQualityProfile(
                    decompose_claims=True,
                    relation_rules=False,
                    require_nli=False,
                )
            ),
        ),
        (
            "local_rules_only",
            LocalQualityJudge(
                profile=LocalQualityProfile(
                    decompose_claims=False,
                    relation_rules=True,
                    require_nli=False,
                )
            ),
        ),
        ("local_deterministic", LocalQualityJudge()),
    ]
    if nli is not None:
        variants.append(("local_deterministic_plus_nli", LocalQualityJudge(nli=nli)))

    rows: list[dict[str, Any]] = []
    for case in cases:
        trace = _trace(case)
        predictions: dict[str, dict[str, Any]] = {}
        for name, judge in variants:
            started = time.perf_counter()
            prediction = _stable_prediction(trace) if judge is None else _local_prediction(case, judge)
            prediction["latency_ms"] = round((time.perf_counter() - started) * 1000.0, 3)
            predictions[name] = prediction
        rows.append(
            {
                "case_id": case["id"],
                "tags": list(case.get("tags") or []),
                "expected_verdict": case["expected_verdict"],
                "expected_evidence_context_ids": list(case.get("expected_evidence_context_ids") or []),
                "evaluation_label_sent_to_verifier": False,
                "predictions": predictions,
            }
        )
    variant_names = [name for name, _ in variants]
    return {
        "experiment": "contexttrace_local_verification_quality",
        "schema_version": "1.0",
        "split": split_metadata,
        "cases": len(rows),
        "stable_default_changed": False,
        "hosted_inference_calls": 0,
        "nli": nli_metadata,
        "initialization": initialization,
        "hardware": _hardware(),
        "metrics": {name: _metrics(rows, name) for name in variant_names},
        "rows": rows,
    }


def initialize_nli(model_path: str) -> tuple[object, dict[str, Any], dict[str, Any]]:
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
    before = _peak_rss_mb()
    started = time.perf_counter()
    artifact = verify_nli_artifact(model_path)
    nli = build_pinned_nli(model_path)
    nli.verify_claim(
        query="",
        claim="The local policy is active.",
        contexts=[TraceContext(id="warmup", text="The local policy is active.")],
    )
    elapsed = round((time.perf_counter() - started) * 1000.0, 3)
    after = _peak_rss_mb()
    metadata = {
        "provider": "local_nli",
        "backend": "transformers",
        "model_id": NLI_MODEL_ID,
        "model_revision": NLI_MODEL_REVISION,
        "artifact_manifest_sha256": artifact["artifact_manifest_sha256"],
        "model_path": str(Path(model_path).resolve()),
        "model_size_bytes": sum(int(item["bytes"]) for item in artifact["files"]),
        "license": "Apache-2.0 (from the pinned local model card)",
        "automatic_download": False,
        "remote_inference": False,
        "raw_scores_are_calibrated_correctness_probabilities": False,
    }
    initialization = {
        "model_load_and_warmup_ms": elapsed,
        "peak_rss_before_mb": before,
        "peak_rss_after_mb": after,
        "peak_rss_increase_mb": round(max(0.0, after - before), 3),
    }
    return nli, metadata, initialization


def _trace(case: dict[str, Any]) -> RAGTrace:
    return RAGTrace(
        query=str(case["query"]),
        answer=str(case["claim"]),
        contexts=[
            TraceContext(id=str(item["id"]), text=str(item["text"]))
            for item in case["contexts"]
        ],
    )


def _stable_prediction(trace: RAGTrace) -> dict[str, Any]:
    result = verify_trace(trace, mode="semantic")
    claims = list(result.get("claims") or [])
    verdict = _aggregate_verdicts([str(item.get("verdict")) for item in claims])
    confidence = _aggregate_confidence(claims, verdict)
    evidence_ids = sorted(
        {
            str(span.get("context_id"))
            for item in claims
            for span in list(item.get("supporting_spans") or [])
            if span.get("context_id")
        }
        | {
            str(item.get("best_context_id"))
            for item in claims
            if item.get("best_context_id")
        }
    )
    review = verdict == "unverifiable" or confidence < 0.80
    return {
        "verdict": verdict,
        "confidence": confidence,
        "confidence_semantics": "stable_verifier_score",
        "review_required": review,
        "automatic_supported": verdict == "supported" and not review,
        "backend": {
            "provider": "contexttrace_stable",
            "mode": "semantic",
            "verifier_version": result.get("verifier_version"),
        },
        "evidence_context_ids": evidence_ids,
        "claim_count": len(claims),
    }


def _local_prediction(case: dict[str, Any], judge: LocalQualityJudge) -> dict[str, Any]:
    verdict = judge.verify_claim(
        query=str(case["query"]),
        claim=str(case["claim"]),
        contexts=[
            TraceContext(id=str(item["id"]), text=str(item["text"]))
            for item in case["contexts"]
        ],
    )
    spans = list(verdict.raw.get("selected_evidence_spans") or [])
    return {
        "verdict": verdict.verdict,
        "confidence": verdict.confidence,
        "confidence_semantics": verdict.raw["confidence_semantics"],
        "review_required": bool(verdict.raw["review_required"]),
        "automatic_supported": bool(verdict.raw["automatic_supported"]),
        "backend": dict(verdict.raw["backend"]),
        "evidence_context_ids": sorted({str(span["context_id"]) for span in spans}),
        "evidence_spans": spans,
        "atomic_claims": list(verdict.raw["atomic_claims"]),
        "reason_code": verdict.raw["reason_code"],
    }


def _metrics(rows: list[dict[str, Any]], variant: str) -> dict[str, Any]:
    confusion = {
        expected: {predicted: 0 for predicted in LABELS}
        for expected in LABELS
    }
    latencies: list[float] = []
    auto_correct = auto_total = reviews = 0
    localization_tp = localization_fp = localization_fn = 0
    incorrect_supported: list[str] = []
    false_alarms: list[str] = []
    for row in rows:
        expected = str(row["expected_verdict"])
        prediction = row["predictions"][variant]
        predicted = str(prediction["verdict"])
        confusion[expected][predicted] += 1
        latencies.append(float(prediction["latency_ms"]))
        if prediction["review_required"]:
            reviews += 1
        else:
            auto_total += 1
            auto_correct += predicted == expected
        if expected != "supported" and predicted == "supported":
            incorrect_supported.append(str(row["case_id"]))
        if expected == "supported" and predicted != "supported":
            false_alarms.append(str(row["case_id"]))
        expected_ids = set(row["expected_evidence_context_ids"])
        predicted_ids = set(prediction["evidence_context_ids"])
        localization_tp += len(expected_ids & predicted_ids)
        localization_fp += len(predicted_ids - expected_ids)
        localization_fn += len(expected_ids - predicted_ids)

    per_label: dict[str, dict[str, float | int]] = {}
    for label in LABELS:
        tp = confusion[label][label]
        fp = sum(confusion[other][label] for other in LABELS if other != label)
        fn = sum(confusion[label][other] for other in LABELS if other != label)
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        per_label[label] = {
            "support": sum(confusion[label].values()),
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
        }
    correct = sum(confusion[label][label] for label in LABELS)
    non_supported = sum(1 for row in rows if row["expected_verdict"] != "supported")
    supported = sum(1 for row in rows if row["expected_verdict"] == "supported")
    return {
        "accuracy": round(correct / len(rows), 4),
        "macro_f1": round(statistics.fmean(float(per_label[label]["f1"]) for label in LABELS), 4),
        "per_label": per_label,
        "confusion": confusion,
        "incorrect_supported": {
            "count": len(incorrect_supported),
            "denominator_non_supported": non_supported,
            "rate": round(len(incorrect_supported) / non_supported, 4) if non_supported else 0.0,
            "case_ids": incorrect_supported,
        },
        "false_alarms_on_supported": {
            "count": len(false_alarms),
            "denominator_supported": supported,
            "rate": round(len(false_alarms) / supported, 4) if supported else 0.0,
            "case_ids": false_alarms,
        },
        "review": {
            "count": reviews,
            "rate": round(reviews / len(rows), 4),
            "automatically_handled": auto_total,
            "automatically_handled_accuracy": round(auto_correct / auto_total, 4) if auto_total else None,
        },
        "evidence_localization": {
            "precision": round(localization_tp / (localization_tp + localization_fp), 4)
            if localization_tp + localization_fp else 0.0,
            "recall": round(localization_tp / (localization_tp + localization_fn), 4)
            if localization_tp + localization_fn else 0.0,
            "true_positive_contexts": localization_tp,
            "false_positive_contexts": localization_fp,
            "false_negative_contexts": localization_fn,
        },
        "warm_latency_ms": {
            "p50": _percentile(latencies, 50),
            "p95": _percentile(latencies, 95),
            "mean": round(statistics.fmean(latencies), 3),
        },
    }


def _aggregate_verdicts(verdicts: list[str]) -> str:
    if not verdicts:
        return "unverifiable"
    if "contradicted" in verdicts:
        return "contradicted"
    if all(item == "supported" for item in verdicts):
        return "supported"
    if "supported" in verdicts or "partially_supported" in verdicts:
        return "partially_supported"
    if "unverifiable" in verdicts:
        return "unverifiable"
    return "unsupported"


def _aggregate_confidence(claims: list[dict[str, Any]], verdict: str) -> float:
    values = [
        float(item.get("confidence") or 0.0)
        for item in claims
        if item.get("verdict") == verdict
    ] or [float(item.get("confidence") or 0.0) for item in claims]
    return round(min(values), 3) if values else 0.0


def _percentile(values: list[float], percentile: int) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    rank = (len(ordered) - 1) * (percentile / 100.0)
    lower = int(rank)
    upper = min(len(ordered) - 1, lower + 1)
    fraction = rank - lower
    return round(ordered[lower] + (ordered[upper] - ordered[lower]) * fraction, 3)


def _peak_rss_mb() -> float:
    value = float(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    if platform.system() == "Darwin":
        return round(value / (1024 * 1024), 3)
    return round(value / 1024, 3)


def _hardware() -> dict[str, Any]:
    data: dict[str, Any] = {
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor() or None,
        "python": platform.python_version(),
        "peak_rss_mb_at_report": _peak_rss_mb(),
    }
    try:
        import torch

        data.update(
            {
                "torch": torch.__version__,
                "torch_threads": torch.get_num_threads(),
                "mps_available": bool(
                    getattr(torch.backends, "mps", None)
                    and torch.backends.mps.is_available()
                ),
                "cuda_available": bool(torch.cuda.is_available()),
                "inference_device": "cpu",
            }
        )
    except ImportError:
        data["torch"] = None
        data["inference_device"] = "none"
    return data


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", required=True)
    parser.add_argument("--split", choices=("development", "heldout"), required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--model-path")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    metadata, cases = load_cases(args.cases, expected_split=args.split)
    nli = nli_metadata = initialization = None
    if args.model_path:
        nli, nli_metadata, initialization = initialize_nli(args.model_path)
    result = run_evaluation(
        cases,
        split_metadata=metadata,
        nli=nli,
        nli_metadata=nli_metadata,
        initialization=initialization,
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result["metrics"], indent=2, sort_keys=True))
    print("wrote %s" % output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
