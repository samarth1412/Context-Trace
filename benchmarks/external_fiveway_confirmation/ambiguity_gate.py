"""Run and calibrate development-only Jev ambiguity and complete-support gates."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import statistics
import time
from collections import Counter
from pathlib import Path
from typing import Any, Mapping

from benchmarks.jev_claim_verification.experiment import (
    LABEL_CRITERIA,
    VERDICT_INSTRUCTIONS,
    enforce_remote_policy,
)
from benchmarks.jev_v2_verification.run import load_case_pack, shared_input
from contexttrace.config import load_config


AMBIGUITY_INSTRUCTIONS = (
    "Considering only `claim` and `selected_evidence`, can their wording or references be "
    "reasonably interpreted in multiple materially different ways that produce different "
    "support, contradiction, or undecidable verdicts?"
)
AMBIGUITY_CRITERIA = {
    "true": (
        "At least two plausible readings of the supplied wording change the evidence verdict. "
        "Lexical, syntactic, scope, reference, or pragmatic ambiguity counts."
    ),
    "false": (
        "The materially relevant reading is clear. Missing evidence, weak evidence, ordinary "
        "uncertainty, or a difficult inference alone does not count as linguistic ambiguity."
    ),
}
COMPLETE_SUPPORT_INSTRUCTIONS = (
    "Considering only `claim` and `selected_evidence`, does the evidence directly establish "
    "every material part of the claim under one clear reading?"
)
COMPLETE_SUPPORT_CRITERIA = {
    "true": (
        "Every required entity, relation, qualifier, number, date, and attribution is directly "
        "supported, with no material omission or conflict."
    ),
    "false": (
        "At least one material part is missing, conflicting, ambiguous, or supported only by "
        "topical overlap or outside knowledge."
    ),
}
THRESHOLDS = tuple(round(value / 100, 2) for value in range(35, 96, 5))
MAX_FALSE_SUPPORT_RATE = 0.05


class GateError(RuntimeError):
    """Raised when the development gate experiment violates its contract."""


def run_signals(
    cases: list[dict[str, Any]],
    *,
    client: object,
    choice_factory: object,
    noul_factory: object,
    noul_criteria_factory: object,
    model: str,
    checkpoint: str | Path | None = None,
    split_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    rows = []
    for case in cases:
        contexts, input_audit = shared_input(case)
        state = {
            "claim": str(case["claim"]),
            "selected_evidence": [
                {"id": context.id, "text": context.text} for context in contexts
            ],
        }
        questions = {
            "verdict": choice_factory(  # type: ignore[operator]
                instructions=VERDICT_INSTRUCTIONS,
                criteria=LABEL_CRITERIA,
            ),
            "linguistic_ambiguity": noul_factory(  # type: ignore[operator]
                instructions=AMBIGUITY_INSTRUCTIONS,
                criteria=noul_criteria_factory(**AMBIGUITY_CRITERIA),  # type: ignore[operator]
            ),
            "complete_support": noul_factory(  # type: ignore[operator]
                instructions=COMPLETE_SUPPORT_INSTRUCTIONS,
                criteria=noul_criteria_factory(**COMPLETE_SUPPORT_CRITERIA),  # type: ignore[operator]
            ),
        }
        started = time.perf_counter()
        response = client.system_one(state=state, questions=questions, model=model)  # type: ignore[attr-defined]
        latency_ms = round((time.perf_counter() - started) * 1000.0, 3)
        answers = getattr(response, "answers", None)
        if not isinstance(answers, Mapping):
            raise GateError("TypeSafe response did not contain answers.")
        verdict_answer = answers.get("verdict")
        ambiguity_answer = answers.get("linguistic_ambiguity")
        support_answer = answers.get("complete_support")
        if verdict_answer is None or ambiguity_answer is None or support_answer is None:
            raise GateError("TypeSafe response omitted one or more gate answers.")
        verdict = str(getattr(verdict_answer, "choice", "")).strip().casefold()
        probabilities = _probability_map(getattr(verdict_answer, "probabilities", None))
        if verdict not in LABEL_CRITERIA or set(probabilities) != set(LABEL_CRITERIA):
            raise GateError("TypeSafe returned an invalid five-way verdict distribution.")
        ambiguity = _unit_float(getattr(ambiguity_answer, "noul", None), "ambiguity")
        complete_support = _unit_float(
            getattr(support_answer, "noul", None), "complete_support"
        )
        usage = getattr(response, "usage", None)
        if usage is None:
            raise GateError("TypeSafe response omitted usage.")
        state_json = json.dumps(state, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        rows.append(
            {
                "case_id": case["id"],
                "dataset": case["dataset"],
                "expected_verdict": case["expected_verdict"],
                "development_partition": case["development_partition"],
                "input_audit": {
                    **input_audit,
                    "remote_sent_fields": ["claim", "selected_evidence"],
                    "remote_state_sha256": hashlib.sha256(state_json.encode("utf-8")).hexdigest(),
                    "query_sent": False,
                    "evaluation_label_sent": False,
                },
                "signals": {
                    "base_verdict": verdict,
                    "base_probabilities": probabilities,
                    "base_confidence": _unit_float(
                        getattr(verdict_answer, "confidence", None), "verdict confidence"
                    ),
                    "linguistic_ambiguity": ambiguity,
                    "complete_support": complete_support,
                },
                "request": {
                    "requested_model": model,
                    "resolved_model": str(getattr(response, "model", "")),
                    "latency_ms": latency_ms,
                    "usage": {
                        "input_tokens": _nonnegative_int(
                            getattr(usage, "input_tokens", None), "input_tokens"
                        ),
                        "output_tokens": _nonnegative_int(
                            getattr(usage, "output_tokens", None), "output_tokens"
                        ),
                    },
                    "generated_explanation": None,
                    "generated_evidence_spans": [],
                    "generated_matched_facts": [],
                },
            }
        )
        if checkpoint is not None:
            _write_result(
                Path(checkpoint),
                rows,
                split_metadata=split_metadata or {},
                model=model,
            )
    return _result(rows, split_metadata=split_metadata or {}, model=model)


def calibrate(result: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    rows = result.get("rows") or []
    calibration_rows = [row for row in rows if row["development_partition"] == "calibration"]
    validation_rows = [row for row in rows if row["development_partition"] == "validation"]
    if len(calibration_rows) != 75 or len(validation_rows) != 50:
        raise GateError("Expected 75 calibration and 50 validation rows.")
    candidates = []
    for ambiguity_threshold in THRESHOLDS:
        for support_threshold in THRESHOLDS:
            policy = {
                "ambiguity_threshold": ambiguity_threshold,
                "complete_support_threshold": support_threshold,
                "max_false_support_rate": MAX_FALSE_SUPPORT_RATE,
            }
            metrics = evaluate_rows(calibration_rows, policy=policy)
            qualifies = bool(
                metrics["false_support_rate"] <= MAX_FALSE_SUPPORT_RATE
                and metrics["unsupported_incorrectly_supported"] == 0
            )
            candidates.append({"policy": policy, "qualifies": qualifies, "metrics": metrics})
    qualified = [candidate for candidate in candidates if candidate["qualifies"]]
    if not qualified:
        raise GateError("No gate policy meets the development false-support constraints.")
    selected = max(
        qualified,
        key=lambda candidate: (
            candidate["metrics"]["macro_f1"],
            candidate["metrics"]["accuracy"],
            candidate["metrics"]["per_label_recall"]["unverifiable"],
            candidate["metrics"]["per_label_recall"]["supported"],
            candidate["policy"]["ambiguity_threshold"],
            candidate["policy"]["complete_support_threshold"],
        ),
    )
    policy_core = dict(selected["policy"])
    policy_id = _hash_json(policy_core)
    policy_manifest = {
        "schema_version": "jev-ambiguity-support-gate-policy-1.0",
        "policy_id": policy_id,
        "selection_split": "development.calibration",
        "validation_split": "development.validation",
        "heldout_used_for_selection": False,
        "stable_defaults_changed": False,
        "remote_provider_default_enabled": False,
        "policy": policy_core,
        "decision_order": [
            "If linguistic_ambiguity is at or above threshold, return unverifiable.",
            "Otherwise, use complete_support to choose supported versus partially_supported when the base verdict is either.",
            "Otherwise, retain the base Jev verdict.",
            "Require review for every supported or unverifiable verdict and for signals within 0.10 of a threshold.",
        ],
    }
    analysis = {
        "schema_version": "jev-ambiguity-support-gate-analysis-1.0",
        "candidate_count": len(candidates),
        "qualifying_candidate_count": len(qualified),
        "base_calibration": evaluate_rows(calibration_rows, policy=None),
        "base_validation": evaluate_rows(validation_rows, policy=None),
        "selected_calibration": selected,
        "selected_validation": evaluate_rows(validation_rows, policy=policy_core),
        "policy_id": policy_id,
        "candidates": candidates,
    }
    return policy_manifest, analysis


def evaluate_rows(
    rows: list[dict[str, Any]], *, policy: dict[str, Any] | None
) -> dict[str, Any]:
    gold = [str(row["expected_verdict"]) for row in rows]
    predicted = [
        str(row["signals"]["base_verdict"])
        if policy is None
        else gated_verdict(row["signals"], policy=policy)
        for row in rows
    ]
    labels = tuple(LABEL_CRITERIA)
    correct = sum(left == right for left, right in zip(gold, predicted, strict=True))
    false_support = sum(
        expected != "supported" and value == "supported"
        for expected, value in zip(gold, predicted, strict=True)
    )
    non_supported = sum(value != "supported" for value in gold)
    recalls = {}
    f1_scores = []
    for label in labels:
        tp = sum(g == p == label for g, p in zip(gold, predicted, strict=True))
        fp = sum(g != label and p == label for g, p in zip(gold, predicted, strict=True))
        fn = sum(g == label and p != label for g, p in zip(gold, predicted, strict=True))
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1_scores.append(
            2 * precision * recall / (precision + recall) if precision + recall else 0.0
        )
        recalls[label] = round(recall, 4)
    return {
        "cases": len(rows),
        "accuracy": round(correct / len(rows), 4),
        "macro_f1": round(statistics.fmean(f1_scores), 4),
        "false_support_count": false_support,
        "false_support_rate": round(false_support / non_supported, 4),
        "unsupported_incorrectly_supported": sum(
            expected == "unsupported" and value == "supported"
            for expected, value in zip(gold, predicted, strict=True)
        ),
        "per_label_recall": recalls,
        "confusion": {
            label: dict(
                sorted(Counter(p for g, p in zip(gold, predicted, strict=True) if g == label).items())
            )
            for label in labels
        },
    }


def gated_verdict(signals: dict[str, Any], *, policy: dict[str, Any]) -> str:
    if float(signals["linguistic_ambiguity"]) >= float(policy["ambiguity_threshold"]):
        return "unverifiable"
    base = str(signals["base_verdict"])
    if base in {"supported", "partially_supported"}:
        return (
            "supported"
            if float(signals["complete_support"])
            >= float(policy["complete_support_threshold"])
            else "partially_supported"
        )
    return base


def review_reasons(signals: dict[str, Any], *, policy: dict[str, Any]) -> list[str]:
    verdict = gated_verdict(signals, policy=policy)
    reasons = []
    if verdict in {"supported", "unverifiable"}:
        reasons.append("sensitive_verdict")
    if abs(float(signals["linguistic_ambiguity"]) - float(policy["ambiguity_threshold"])) < 0.10:
        reasons.append("ambiguity_near_threshold")
    if (
        str(signals["base_verdict"]) in {"supported", "partially_supported"}
        and abs(
            float(signals["complete_support"])
            - float(policy["complete_support_threshold"])
        )
        < 0.10
    ):
        reasons.append("complete_support_near_threshold")
    return reasons


def _result(
    rows: list[dict[str, Any]], *, split_metadata: dict[str, Any], model: str
) -> dict[str, Any]:
    return {
        "schema_version": "jev-ambiguity-support-signals-1.0",
        "experiment": "contexttrace_jev_ambiguity_support_gate",
        "split": split_metadata,
        "requested_model": model,
        "stable_defaults_changed": False,
        "remote_provider_default_enabled": False,
        "labels_sent_to_model": False,
        "generated_explanations": False,
        "cases_completed": len(rows),
        "rows": rows,
    }


def _write_result(
    path: Path,
    rows: list[dict[str, Any]],
    *,
    split_metadata: dict[str, Any],
    model: str,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_result(rows, split_metadata=split_metadata, model=model), indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )


def _load_env(path: str | Path) -> None:
    for raw in Path(path).read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key.strip() in {"TYPESAFE_API_KEY", "TYPESAFE_ENDPOINT"}:
            os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


def _probability_map(value: object) -> dict[str, float]:
    if not isinstance(value, Mapping):
        raise GateError("Verdict probabilities are missing.")
    return {str(key): _unit_float(item, "probability") for key, item in value.items()}


def _unit_float(value: object, field: str) -> float:
    try:
        number = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError) as exc:
        raise GateError("%s is not numeric." % field) from exc
    if not 0.0 <= number <= 1.0:
        raise GateError("%s is outside [0, 1]." % field)
    return number


def _nonnegative_int(value: object, field: str) -> int:
    try:
        number = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError) as exc:
        raise GateError("%s is not an integer." % field) from exc
    if number < 0:
        raise GateError("%s is negative." % field)
    return number


def _hash_json(value: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    run_parser = subparsers.add_parser("run")
    run_parser.add_argument("--cases", required=True)
    run_parser.add_argument("--output", required=True)
    run_parser.add_argument("--env-file")
    run_parser.add_argument("--allow-remote", action="store_true")
    run_parser.add_argument("--model", default="jev-latest")
    calibrate_parser = subparsers.add_parser("calibrate")
    calibrate_parser.add_argument("--result", required=True)
    calibrate_parser.add_argument("--policy-output", required=True)
    calibrate_parser.add_argument("--analysis-output", required=True)
    args = parser.parse_args(argv)
    if args.command == "run":
        if args.env_file:
            _load_env(args.env_file)
        enforce_remote_policy(
            local_only=load_config().local_only,
            allow_remote=args.allow_remote,
        )
        try:
            from typesafe_sdk import Choice, Noul, NoulCriteria, TypeSafeClient
        except ImportError as exc:
            raise GateError("typesafe-sdk is required for the ambiguity gate.") from exc
        api_key = os.environ.get("TYPESAFE_API_KEY", "").strip()
        if not api_key:
            raise GateError("TYPESAFE_API_KEY is not set.")
        metadata, cases = load_case_pack(args.cases, expected_split="development")
        client = TypeSafeClient(
            api_key=api_key,
            base_url=os.environ.get("TYPESAFE_ENDPOINT") or None,
            timeout=120.0,
        )
        try:
            result = run_signals(
                cases,
                client=client,
                choice_factory=Choice,
                noul_factory=Noul,
                noul_criteria_factory=NoulCriteria,
                model=args.model,
                checkpoint=args.output,
                split_metadata=metadata,
            )
        finally:
            client.close()
        _write(Path(args.output), result)
        print(json.dumps({"cases": len(result["rows"])}, indent=2))
    else:
        result = json.loads(Path(args.result).read_text(encoding="utf-8"))
        policy, analysis = calibrate(result)
        _write(Path(args.policy_output), policy)
        _write(Path(args.analysis_output), analysis)
        print(
            json.dumps(
                {
                    "policy": policy,
                    "calibration": analysis["selected_calibration"]["metrics"],
                    "validation": analysis["selected_validation"],
                },
                indent=2,
                sort_keys=True,
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
