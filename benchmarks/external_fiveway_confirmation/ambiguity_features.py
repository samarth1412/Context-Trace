"""Evaluate decomposed TypeSafe ambiguity features on development data only."""

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

from benchmarks.external_fiveway_confirmation.ambiguity_gate import (
    GateError,
    THRESHOLDS,
    _load_env,
    _nonnegative_int,
    _probability_map,
    _unit_float,
)
from benchmarks.jev_claim_verification.experiment import (
    LABEL_CRITERIA,
    VERDICT_INSTRUCTIONS,
    enforce_remote_policy,
)
from benchmarks.jev_v2_verification.run import load_case_pack, shared_input
from contexttrace.config import load_config


FEATURES = {
    "lexical": {
        "instructions": (
            "Does a word or phrase in `claim` or `selected_evidence` have multiple plausible "
            "senses that change whether the evidence supports or contradicts the claim?"
        ),
        "true": "A specific word or phrase has competing ordinary meanings that change the verdict.",
        "false": "No plausible lexical-sense choice changes the verdict.",
    },
    "reference": {
        "instructions": (
            "Can a pronoun, name, omitted subject, or other referring expression in `claim` or "
            "`selected_evidence` plausibly refer to different entities in ways that change the verdict?"
        ),
        "true": "At least two plausible referents produce different evidence verdicts.",
        "false": "References are clear enough that alternative referents do not change the verdict.",
    },
    "structure_scope": {
        "instructions": (
            "Can syntax, attachment, coordination, negation, quantifier, modality, or temporal scope "
            "in `claim` or `selected_evidence` be read in multiple ways that change the verdict?"
        ),
        "true": "At least two plausible structural or scope readings produce different verdicts.",
        "false": "The relevant structure and scope have one clear reading for verification.",
    },
    "pragmatic": {
        "instructions": (
            "Does interpreting an implication, comparison, presupposition, intention, degree, time, "
            "or causal wording in `claim` or `selected_evidence` allow multiple plausible readings "
            "that change the verdict?"
        ),
        "true": "Different plausible pragmatic readings change the evidence verdict.",
        "false": "Pragmatic context does not create verdict-changing alternative readings.",
    },
    "verdict_instability": {
        "instructions": (
            "Because of alternative plausible readings of the supplied wording, could careful readers "
            "reasonably assign at least two different labels among supported, partially supported, "
            "unsupported, contradicted, and unverifiable?"
        ),
        "true": "Wording ambiguity itself makes two or more different verdicts reasonable.",
        "false": (
            "One verdict best fits; missing evidence, difficult reasoning, or uncertainty without "
            "alternative readings does not count."
        ),
    },
}
AGGREGATIONS = ("maximum", "top_two_mean", "mean")
MAX_FALSE_SUPPORT_RATE = 0.05


def run_features(
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
            )
        }
        for name, definition in FEATURES.items():
            questions["ambiguity_%s" % name] = noul_factory(  # type: ignore[operator]
                instructions=definition["instructions"],
                criteria=noul_criteria_factory(  # type: ignore[operator]
                    true=definition["true"], false=definition["false"]
                ),
            )
        started = time.perf_counter()
        response = client.system_one(state=state, questions=questions, model=model)  # type: ignore[attr-defined]
        latency_ms = round((time.perf_counter() - started) * 1000.0, 3)
        answers = getattr(response, "answers", None)
        if not isinstance(answers, Mapping):
            raise GateError("TypeSafe feature response omitted answers.")
        verdict_answer = answers.get("verdict")
        if verdict_answer is None:
            raise GateError("TypeSafe feature response omitted verdict.")
        base_verdict = str(getattr(verdict_answer, "choice", "")).strip().casefold()
        probabilities = _probability_map(getattr(verdict_answer, "probabilities", None))
        if base_verdict not in LABEL_CRITERIA or set(probabilities) != set(LABEL_CRITERIA):
            raise GateError("TypeSafe returned an invalid five-way verdict distribution.")
        feature_values = {}
        for name in FEATURES:
            answer = answers.get("ambiguity_%s" % name)
            if answer is None:
                raise GateError("TypeSafe feature response omitted %s." % name)
            feature_values[name] = _unit_float(getattr(answer, "noul", None), name)
        usage = getattr(response, "usage", None)
        if usage is None:
            raise GateError("TypeSafe feature response omitted usage.")
        state_json = json.dumps(state, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        rows.append(
            {
                "case_id": case["id"],
                "dataset": case["dataset"],
                "expected_verdict": case["expected_verdict"],
                "development_partition": case.get("development_partition"),
                "input_audit": {
                    **input_audit,
                    "remote_sent_fields": ["claim", "selected_evidence"],
                    "remote_state_sha256": hashlib.sha256(state_json.encode("utf-8")).hexdigest(),
                    "query_sent": False,
                    "evaluation_label_sent": False,
                },
                "signals": {
                    "base_verdict": base_verdict,
                    "base_probabilities": probabilities,
                    "base_confidence": _unit_float(
                        getattr(verdict_answer, "confidence", None), "verdict confidence"
                    ),
                    "ambiguity_features": feature_values,
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
            _write(
                Path(checkpoint),
                _result(rows, split_metadata=split_metadata or {}, model=model),
            )
    return _result(rows, split_metadata=split_metadata or {}, model=model)


def ambiguity_score(features: dict[str, Any], aggregation: str) -> float:
    values = sorted((float(value) for value in features.values()), reverse=True)
    if aggregation == "maximum":
        return values[0]
    if aggregation == "top_two_mean":
        return statistics.fmean(values[:2])
    if aggregation == "mean":
        return statistics.fmean(values)
    raise GateError("Unknown ambiguity aggregation %s." % aggregation)


def feature_verdict(signals: dict[str, Any], *, policy: dict[str, Any]) -> str:
    score = ambiguity_score(
        signals["ambiguity_features"], str(policy["ambiguity_aggregation"])
    )
    if score >= float(policy["ambiguity_threshold"]):
        return "unverifiable"
    return str(signals["base_verdict"])


def calibrate(result: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    rows = result.get("rows") or []
    calibration_rows = [row for row in rows if row["development_partition"] == "calibration"]
    validation_rows = [row for row in rows if row["development_partition"] == "validation"]
    candidates = []
    for aggregation in AGGREGATIONS:
        for threshold in THRESHOLDS:
            policy = {
                "ambiguity_aggregation": aggregation,
                "ambiguity_threshold": threshold,
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
        raise GateError("No decomposed ambiguity policy meets false-support constraints.")
    selected = max(
        qualified,
        key=lambda candidate: (
            candidate["metrics"]["macro_f1"],
            candidate["metrics"]["accuracy"],
            candidate["metrics"]["per_label_recall"]["unverifiable"],
            candidate["policy"]["ambiguity_threshold"],
        ),
    )
    policy_core = dict(selected["policy"])
    policy_id = hashlib.sha256(
        json.dumps(policy_core, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    policy = {
        "schema_version": "jev-decomposed-ambiguity-policy-1.0",
        "policy_id": policy_id,
        "selection_split": "development.calibration",
        "validation_split": "development.validation",
        "heldout_used_for_selection": False,
        "stable_defaults_changed": False,
        "remote_provider_default_enabled": False,
        "policy": policy_core,
    }
    analysis = {
        "schema_version": "jev-decomposed-ambiguity-analysis-1.0",
        "base_calibration": evaluate_rows(calibration_rows, policy=None),
        "base_validation": evaluate_rows(validation_rows, policy=None),
        "selected_calibration": selected,
        "selected_validation": evaluate_rows(validation_rows, policy=policy_core),
        "candidate_count": len(candidates),
        "qualifying_candidate_count": len(qualified),
        "feature_distribution": feature_distribution(rows),
        "policy_id": policy_id,
        "candidates": candidates,
    }
    return policy, analysis


def evaluate_rows(
    rows: list[dict[str, Any]], *, policy: dict[str, Any] | None
) -> dict[str, Any]:
    labels = tuple(LABEL_CRITERIA)
    gold = [str(row["expected_verdict"]) for row in rows]
    predicted = [
        str(row["signals"]["base_verdict"])
        if policy is None
        else feature_verdict(row["signals"], policy=policy)
        for row in rows
    ]
    correct = sum(g == p for g, p in zip(gold, predicted, strict=True))
    f1_scores = []
    recalls = {}
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
    false_support = sum(
        g != "supported" and p == "supported"
        for g, p in zip(gold, predicted, strict=True)
    )
    non_supported = sum(g != "supported" for g in gold)
    return {
        "cases": len(rows),
        "accuracy": round(correct / len(rows), 4),
        "macro_f1": round(statistics.fmean(f1_scores), 4),
        "false_support_count": false_support,
        "false_support_rate": round(false_support / non_supported, 4),
        "unsupported_incorrectly_supported": sum(
            g == "unsupported" and p == "supported"
            for g, p in zip(gold, predicted, strict=True)
        ),
        "per_label_recall": recalls,
        "confusion": {
            label: dict(
                sorted(Counter(p for g, p in zip(gold, predicted, strict=True) if g == label).items())
            )
            for label in labels
        },
    }


def feature_distribution(rows: list[dict[str, Any]]) -> dict[str, Any]:
    output = {}
    for feature in FEATURES:
        output[feature] = {}
        for label in LABEL_CRITERIA:
            values = [
                float(row["signals"]["ambiguity_features"][feature])
                for row in rows
                if row["expected_verdict"] == label
            ]
            output[feature][label] = {
                "mean": round(statistics.fmean(values), 4),
                "median": round(statistics.median(values), 4),
                "minimum": min(values),
                "maximum": max(values),
            }
    return output


def _result(
    rows: list[dict[str, Any]], *, split_metadata: dict[str, Any], model: str
) -> dict[str, Any]:
    return {
        "schema_version": "jev-decomposed-ambiguity-signals-1.0",
        "experiment": "contexttrace_jev_decomposed_ambiguity",
        "split": split_metadata,
        "requested_model": model,
        "stable_defaults_changed": False,
        "remote_provider_default_enabled": False,
        "labels_sent_to_model": False,
        "generated_explanations": False,
        "cases_completed": len(rows),
        "rows": rows,
    }


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
    run_parser.add_argument("--expected-split", default="development")
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
            raise GateError("typesafe-sdk is required for ambiguity features.") from exc
        api_key = os.environ.get("TYPESAFE_API_KEY", "").strip()
        if not api_key:
            raise GateError("TYPESAFE_API_KEY is not set.")
        metadata, cases = load_case_pack(args.cases, expected_split=args.expected_split)
        client = TypeSafeClient(
            api_key=api_key,
            base_url=os.environ.get("TYPESAFE_ENDPOINT") or None,
            timeout=120.0,
        )
        try:
            result = run_features(
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
