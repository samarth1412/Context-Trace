"""Run a fair shared-claim/shared-evidence comparison of local judges and Jev."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import statistics
import time
from pathlib import Path
from typing import Any

from benchmarks.jev_claim_verification.experiment import (
    LABELS,
    ExperimentalJevJudge,
    create_live_judge,
    enforce_remote_policy,
)
from contexttrace.config import load_config
from contexttrace.verify.claims import Claim
from contexttrace.verify.evidence import find_best_evidence
from contexttrace.verify.local_quality import (
    LocalQualityJudge,
    select_local_evidence,
)
from contexttrace.verify.schema import TraceContext
from contexttrace.verify.semantic_core_v2.nli import build_pinned_nli, verify_nli_artifact
from contexttrace.verify.verdicts import classify_claim


class FairExperimentError(RuntimeError):
    """Raised when the fair comparison cannot preserve its input contract."""


def load_case_pack(path: str | Path, *, expected_split: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    source = Path(path)
    payload = json.loads(source.read_text(encoding="utf-8"))
    if payload.get("split") != expected_split:
        raise FairExperimentError("Expected %s split in %s." % (expected_split, source))
    cases = payload.get("cases")
    if not isinstance(cases, list) or not cases:
        raise FairExperimentError("The case pack must contain cases.")
    seen: set[str] = set()
    for row in cases:
        case_id = str(row.get("id") or "")
        if not case_id or case_id in seen:
            raise FairExperimentError("Case ids must be non-empty and unique.")
        seen.add(case_id)
        if row.get("expected_verdict") not in LABELS:
            raise FairExperimentError("Case %s has an invalid expected verdict." % case_id)
    metadata = {
        key: value
        for key, value in payload.items()
        if key != "cases"
    }
    metadata["path"] = str(source)
    metadata["sha256"] = _sha256(source)
    return metadata, cases


def shared_input(case: dict[str, Any], *, max_spans: int = 8) -> tuple[list[TraceContext], dict[str, Any]]:
    source_contexts = [
        TraceContext(id=str(item["id"]), text=str(item["text"]))
        for item in case["contexts"]
    ]
    spans = select_local_evidence(
        query=str(case["query"]),
        claim=str(case["claim"]),
        contexts=source_contexts,
        limit=max_spans,
    )
    contexts = [
        TraceContext(
            id="%s:%s:%s" % (span.context_id, span.start_char, span.end_char),
            text=span.text,
        )
        for span in spans
    ]
    state = {
        "query": str(case["query"]),
        "claim": str(case["claim"]),
        "selected_evidence": [
            {"id": context.id, "text": context.text}
            for context in contexts
        ],
    }
    encoded = json.dumps(state, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return contexts, {
        "input_sha256": hashlib.sha256(encoded.encode("utf-8")).hexdigest(),
        "evaluation_label_sent": False,
        "sent_fields": ["query", "claim", "selected_evidence"],
        "exact_shared_input": state,
        "source_context_count": len(source_contexts),
        "selected_span_count": len(contexts),
        "selected_spans": [
            {
                "id": context.id,
                "text_sha256": hashlib.sha256(context.text.encode("utf-8")).hexdigest(),
                "characters": len(context.text),
            }
            for context in contexts
        ],
    }


def stable_prediction(case: dict[str, Any], contexts: list[TraceContext]) -> dict[str, Any]:
    started = time.perf_counter()
    match = find_best_evidence(
        str(case["claim"]),
        contexts,
        mode="semantic",
        localize_spans=False,
    )
    result = classify_claim(
        Claim(id=str(case["id"]), text=str(case["claim"])),
        match,
        has_contexts=bool(contexts),
        mode="semantic",
    )
    confidence = float(result.confidence)
    review = result.verdict == "unverifiable" or confidence < 0.80
    return {
        "verdict": result.verdict,
        "confidence": confidence,
        "confidence_semantics": "stable_verifier_score",
        "review_required": review,
        "latency_ms": round((time.perf_counter() - started) * 1000.0, 3),
        "backend": {"provider": "contexttrace_stable", "mode": "semantic"},
    }


def local_prediction(
    case: dict[str, Any],
    contexts: list[TraceContext],
    judge: LocalQualityJudge,
) -> dict[str, Any]:
    started = time.perf_counter()
    result = judge.verify_claim(
        query=str(case["query"]),
        claim=str(case["claim"]),
        contexts=contexts,
    )
    return {
        "verdict": result.verdict,
        "confidence": result.confidence,
        "confidence_semantics": result.raw["confidence_semantics"],
        "review_required": bool(result.raw["review_required"]),
        "latency_ms": round((time.perf_counter() - started) * 1000.0, 3),
        "backend": dict(result.raw["backend"]),
        "reason_code": result.raw["reason_code"],
        "atomic_claims": list(result.raw["atomic_claims"]),
    }


def jev_prediction(
    case: dict[str, Any],
    contexts: list[TraceContext],
    judge: ExperimentalJevJudge,
    *,
    review_threshold: float,
) -> dict[str, Any]:
    result = judge.verify_claim(
        query=str(case["query"]),
        claim=str(case["claim"]),
        contexts=contexts,
    )
    probabilities = dict(result.raw["probabilities"])
    top_probability = max(probabilities.values())
    return {
        "verdict": result.verdict,
        "confidence": result.confidence,
        "confidence_semantics": "typesafe_choice_distribution_concentration",
        "top_probability": top_probability,
        "review_threshold": review_threshold,
        "review_required": result.verdict == "unverifiable" or top_probability < review_threshold,
        "probabilities": probabilities,
        "latency_ms": result.raw["latency_ms"],
        "backend": {
            "provider": result.provider,
            "requested_model": result.raw["requested_model"],
            "resolved_model": result.raw["resolved_model"],
        },
        "usage": dict(result.raw["usage"]),
        "reason": None,
        "matched_facts": [],
        "missing_facts": [],
        "conflicting_facts": [],
    }


def run(
    cases: list[dict[str, Any]],
    *,
    split_metadata: dict[str, Any],
    nli: object | None = None,
    nli_metadata: dict[str, Any] | None = None,
    jev: ExperimentalJevJudge | None = None,
    jev_review_threshold: float = 0.60,
    checkpoint: str | Path | None = None,
) -> dict[str, Any]:
    deterministic = LocalQualityJudge()
    with_nli = LocalQualityJudge(nli=nli) if nli is not None else None
    rows: list[dict[str, Any]] = []
    result: dict[str, Any] = {}
    for case in cases:
        contexts, audit = shared_input(case)
        predictions = {
            "stable_semantic": stable_prediction(case, contexts),
            "local_deterministic": local_prediction(case, contexts, deterministic),
        }
        if with_nli is not None:
            predictions["local_deterministic_plus_nli"] = local_prediction(case, contexts, with_nli)
        if jev is not None:
            predictions["jev"] = jev_prediction(
                case,
                contexts,
                jev,
                review_threshold=jev_review_threshold,
            )
        rows.append(
            {
                "case_id": case["id"],
                "dataset": case.get("dataset"),
                "label_scope": case.get("label_scope"),
                "expected_verdict": case["expected_verdict"],
                "input_audit": audit,
                "predictions": predictions,
            }
        )
        result = _result(
            rows,
            split_metadata=split_metadata,
            nli_metadata=nli_metadata,
            jev_enabled=jev is not None,
            jev_review_threshold=jev_review_threshold,
        )
        if checkpoint is not None:
            _write_json(Path(checkpoint), result)
    return result


def _result(
    rows: list[dict[str, Any]],
    *,
    split_metadata: dict[str, Any],
    nli_metadata: dict[str, Any] | None,
    jev_enabled: bool,
    jev_review_threshold: float,
) -> dict[str, Any]:
    variants = list(rows[0]["predictions"]) if rows else []
    return {
        "experiment": "contexttrace_jev_v2_shared_input",
        "schema_version": "1.0",
        "comparison_scope": "%s_shared_selector_shared_claim_shared_evidence"
        % split_metadata.get("label_scope", "unknown_scope"),
        "stable_defaults_changed": False,
        "split": split_metadata,
        "cases_completed": len(rows),
        "input_equivalence": {
            "claim_equal_across_variants": True,
            "selected_evidence_equal_across_variants": True,
            "evaluation_labels_sent": False,
            "note": "Each system receives the same claim and selected span texts; internal decision procedures differ.",
        },
        "nli": nli_metadata,
        "jev": {
            "enabled": jev_enabled,
            "review_policy": "review when top Choice probability is below the development-set threshold or verdict is unverifiable",
            "review_threshold": jev_review_threshold,
            "raw_probabilities_are_not_claimed_as_final_verdict_correctness_probabilities": True,
        },
        "hardware": {
            "platform": platform.platform(),
            "machine": platform.machine(),
            "python": platform.python_version(),
        },
        "metrics": {variant: metrics(rows, variant) for variant in variants},
        "disagreements": disagreements(rows, variants),
        "rows": rows,
    }


def metrics(rows: list[dict[str, Any]], variant: str) -> dict[str, Any]:
    usable = [row for row in rows if variant in row["predictions"]]
    confusion = {gold: {pred: 0 for pred in LABELS} for gold in LABELS}
    reviews = auto_total = auto_correct = 0
    false_supported: list[str] = []
    false_alarms: list[str] = []
    latencies = []
    for row in usable:
        gold = str(row["expected_verdict"])
        prediction = row["predictions"][variant]
        predicted = str(prediction["verdict"])
        confusion[gold][predicted] += 1
        latencies.append(float(prediction["latency_ms"]))
        if prediction["review_required"]:
            reviews += 1
        else:
            auto_total += 1
            auto_correct += predicted == gold
        if gold != "supported" and predicted == "supported":
            false_supported.append(str(row["case_id"]))
        if gold == "supported" and predicted != "supported":
            false_alarms.append(str(row["case_id"]))
    per_label = {}
    observed_gold = {str(row["expected_verdict"]) for row in usable}
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
    f1_values = [float(per_label[label]["f1"]) for label in observed_gold]
    correct = sum(confusion[label][label] for label in LABELS)
    non_supported = sum(row["expected_verdict"] != "supported" for row in usable)
    supported = len(usable) - non_supported
    output = {
        "cases": len(usable),
        "accuracy": round(correct / len(usable), 4) if usable else None,
        "macro_f1_observed_gold_labels": round(statistics.fmean(f1_values), 4) if f1_values else None,
        "macro_f1_fixed_five_labels": round(statistics.fmean(float(per_label[x]["f1"]) for x in LABELS), 4),
        "per_label": per_label,
        "confusion": confusion,
        "incorrect_supported": {
            "count": len(false_supported),
            "denominator_non_supported": non_supported,
            "rate": round(len(false_supported) / non_supported, 4) if non_supported else None,
            "case_ids": false_supported,
        },
        "false_alarms_on_supported": {
            "count": len(false_alarms),
            "denominator_supported": supported,
            "rate": round(len(false_alarms) / supported, 4) if supported else None,
            "case_ids": false_alarms,
        },
        "review": {
            "count": reviews,
            "rate": round(reviews / len(usable), 4) if usable else None,
            "automatically_handled": auto_total,
            "automatically_handled_accuracy": round(auto_correct / auto_total, 4) if auto_total else None,
        },
        "latency_ms": {
            "p50": _percentile(latencies, 50),
            "p95": _percentile(latencies, 95),
            "mean": round(statistics.fmean(latencies), 3) if latencies else None,
        },
    }
    probability_rows = [
        (str(row["expected_verdict"]), row["predictions"][variant]["probabilities"])
        for row in usable
        if "probabilities" in row["predictions"][variant]
    ]
    if probability_rows:
        output["probability_quality"] = {
            "multiclass_brier": _brier(probability_rows),
            "top_label_ece_10_bins": _ece(probability_rows, bins=10),
        }
        output["usage"] = _usage(usable, variant)
    return output


def disagreements(rows: list[dict[str, Any]], variants: list[str]) -> list[dict[str, Any]]:
    output = []
    for row in rows:
        verdicts = {
            variant: row["predictions"][variant]["verdict"]
            for variant in variants
            if variant in row["predictions"]
        }
        if len(set(verdicts.values())) > 1:
            output.append(
                {
                    "case_id": row["case_id"],
                    "expected_verdict": row["expected_verdict"],
                    "verdicts": verdicts,
                    "dangerous_supported_by": [
                        name
                        for name, verdict in verdicts.items()
                        if row["expected_verdict"] != "supported" and verdict == "supported"
                    ],
                }
            )
    return output


def calibrate_review_threshold(result: dict[str, Any], *, min_coverage: float = 0.60) -> dict[str, Any]:
    rows = [row for row in result.get("rows") or [] if "jev" in row.get("predictions", {})]
    candidates = [round(value / 100, 2) for value in range(50, 96, 5)]
    scored = []
    for threshold in candidates:
        automatic = [
            row
            for row in rows
            if row["predictions"]["jev"]["verdict"] != "unverifiable"
            and float(row["predictions"]["jev"]["top_probability"]) >= threshold
        ]
        coverage = len(automatic) / len(rows) if rows else 0.0
        accuracy = (
            sum(row["predictions"]["jev"]["verdict"] == row["expected_verdict"] for row in automatic)
            / len(automatic)
            if automatic
            else 0.0
        )
        scored.append({"threshold": threshold, "coverage": round(coverage, 4), "automatic_accuracy": round(accuracy, 4)})
    eligible = [row for row in scored if row["coverage"] >= min_coverage]
    chosen = max(eligible, key=lambda row: (row["automatic_accuracy"], row["coverage"], row["threshold"])) if eligible else min(scored, key=lambda row: row["threshold"])
    return {
        "selection_split": "development",
        "objective": "maximize automatic accuracy subject to minimum coverage, then coverage, then threshold",
        "minimum_coverage": min_coverage,
        "chosen_threshold": chosen["threshold"],
        "candidates": scored,
    }


def _brier(rows: list[tuple[str, dict[str, float]]]) -> float:
    values = []
    for gold, probabilities in rows:
        values.append(sum((float(probabilities.get(label, 0.0)) - float(label == gold)) ** 2 for label in LABELS))
    return round(statistics.fmean(values), 6)


def _ece(rows: list[tuple[str, dict[str, float]]], *, bins: int) -> float:
    buckets: list[list[tuple[float, bool]]] = [[] for _ in range(bins)]
    for gold, probabilities in rows:
        predicted, confidence = max(probabilities.items(), key=lambda item: float(item[1]))
        index = min(bins - 1, int(float(confidence) * bins))
        buckets[index].append((float(confidence), predicted == gold))
    total = len(rows)
    value = 0.0
    for bucket in buckets:
        if not bucket:
            continue
        confidence = statistics.fmean(item[0] for item in bucket)
        accuracy = statistics.fmean(float(item[1]) for item in bucket)
        value += len(bucket) / total * abs(accuracy - confidence)
    return round(value, 6)


def _usage(rows: list[dict[str, Any]], variant: str) -> dict[str, int]:
    input_tokens = sum(int(row["predictions"][variant]["usage"]["input_tokens"]) for row in rows)
    output_tokens = sum(int(row["predictions"][variant]["usage"]["output_tokens"]) for row in rows)
    return {"input_tokens": input_tokens, "output_tokens": output_tokens, "total_tokens": input_tokens + output_tokens}


def _percentile(values: list[float], percentile: int) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    rank = (len(ordered) - 1) * percentile / 100
    lower = int(rank)
    upper = min(len(ordered) - 1, lower + 1)
    return round(ordered[lower] + (ordered[upper] - ordered[lower]) * (rank - lower), 3)


def _load_env_file(path: str | Path) -> None:
    for raw_line in Path(path).read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key not in {"TYPESAFE_API_KEY", "TYPESAFE_ENDPOINT"}:
            continue
        os.environ.setdefault(key, value.strip().strip("\"'"))


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", required=True)
    parser.add_argument("--split", choices=("development", "heldout"), required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--model-path")
    parser.add_argument("--run-jev", action="store_true")
    parser.add_argument("--allow-remote", action="store_true")
    parser.add_argument("--env-file")
    parser.add_argument("--jev-model", default="jev-latest")
    parser.add_argument("--jev-review-threshold", type=float, default=0.60)
    parser.add_argument("--write-threshold-calibration")
    args = parser.parse_args(argv)
    if not 0.0 <= args.jev_review_threshold <= 1.0:
        raise FairExperimentError("--jev-review-threshold must be between 0 and 1.")
    split_metadata, cases = load_case_pack(args.cases, expected_split=args.split)
    nli = nli_metadata = None
    if args.model_path:
        os.environ.setdefault("HF_HUB_OFFLINE", "1")
        os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
        artifact = verify_nli_artifact(args.model_path)
        nli = build_pinned_nli(args.model_path)
        nli_metadata = {
            **artifact,
            "model_path_name": Path(args.model_path).name,
            "automatic_download": False,
            "remote_inference": False,
        }
    jev = client = None
    if args.run_jev:
        if args.env_file:
            _load_env_file(args.env_file)
        enforce_remote_policy(
            local_only=load_config().local_only,
            allow_remote=args.allow_remote,
        )
        jev, client = create_live_judge(model=args.jev_model)
    try:
        result = run(
            cases,
            split_metadata=split_metadata,
            nli=nli,
            nli_metadata=nli_metadata,
            jev=jev,
            jev_review_threshold=args.jev_review_threshold,
            checkpoint=args.output,
        )
    finally:
        close = getattr(client, "close", None)
        if callable(close):
            close()
    _write_json(Path(args.output), result)
    if args.write_threshold_calibration:
        if args.split != "development" or not args.run_jev:
            raise FairExperimentError("Threshold calibration requires a Jev development run.")
        _write_json(Path(args.write_threshold_calibration), calibrate_review_threshold(result))
    print(json.dumps(result["metrics"], indent=2, sort_keys=True))
    print("wrote %s" % args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
