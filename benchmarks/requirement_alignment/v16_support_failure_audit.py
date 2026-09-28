"""Audit V15 support misses and false supports on V13 development only."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import statistics
from collections import Counter
from pathlib import Path
from typing import Any

from benchmarks.requirement_alignment.v14_fiveway_policy import (
    DEVELOPMENT_SPLIT,
    LABELS,
    _sha256_json,
    policy_metrics,
)
from benchmarks.requirement_alignment.v9_router import _lexical_features


EXPERIMENT = "contexttrace_v16_support_failure_audit"
TARGET_LABELS = {"supported", "partially_supported"}
SUPPORT_RECALL_TARGET = 0.50
FALSE_SUPPORT_RATE_CAP = 0.05
COMPLEX_CLAIM_RE = re.compile(
    r"\b(?:and|but|while|whereas|which|who|whose|including|as well as)\b|;",
    flags=re.IGNORECASE,
)


class V16AuditError(RuntimeError):
    """Raised when V16 audit inputs violate the development-only contract."""


def audit(
    development: dict[str, Any],
    relation_scores: dict[str, Any],
    atomic_scores: dict[str, Any],
    v14_report: dict[str, Any],
    v15_report: dict[str, Any],
) -> dict[str, Any]:
    aligned = _aligned(
        development, relation_scores, atomic_scores, v14_report, v15_report
    )
    rows = [
        _diagnostic_row(
            example=example,
            relation=relation,
            atomic=atomic,
            v14=v14,
            v15=v15,
        )
        for example, relation, atomic, v14, v15 in zip(
            aligned["examples"],
            aligned["relations"],
            aligned["atomic"],
            aligned["v14"],
            aligned["v15"],
            strict=True,
        )
    ]
    missed = [
        row
        for row in rows
        if row["expected_verdict"] == "supported"
        and row["v15_prediction"] != "supported"
    ]
    correct_support = [
        row
        for row in rows
        if row["expected_verdict"] == row["v15_prediction"] == "supported"
    ]
    false_support = [
        row
        for row in rows
        if row["expected_verdict"] != "supported"
        and row["v15_prediction"] == "supported"
    ]
    if len(missed) != 15 or len(correct_support) != 10 or len(false_support) != 4:
        raise V16AuditError(
            "V16 inputs do not reproduce the selected V15 support boundary."
        )
    false_support_budget = int(
        FALSE_SUPPORT_RATE_CAP
        * sum(row["expected_verdict"] != "supported" for row in rows)
    )
    required_true_supports = math.ceil(
        SUPPORT_RECALL_TARGET
        * sum(row["expected_verdict"] == "supported" for row in rows)
    )
    additional_true_supports = required_true_supports - len(correct_support)
    remaining_false_supports = false_support_budget - len(false_support)
    frontier = _exact_frontier(rows)
    categories = Counter(row["primary_diagnostic"] for row in missed)
    flags = Counter(
        flag
        for row in missed
        for flag, enabled in row["diagnostic_flags"].items()
        if enabled
    )
    return {
        "schema_version": "contexttrace-v16-support-failure-audit-1.0",
        "experiment": EXPERIMENT,
        "status": "diagnostic_complete",
        "protocol": {
            "split": DEVELOPMENT_SPLIT,
            "heldout_loaded": False,
            "heldout_used": False,
            "model_training_performed": False,
            "threshold_selection_performed": False,
            "diagnostic_categories_are_rule_based_hypotheses": True,
        },
        "inputs": {
            "development_sha256": _sha256_json(development),
            "relation_rows_sha256": _sha256_json(relation_scores["rows"]),
            "atomic_feature_rows_sha256": _sha256_json(
                [
                    {key: value for key, value in row.items() if key != "latency_ms"}
                    for row in atomic_scores["rows"]
                ]
            ),
            "v14_rows_sha256": _sha256_json(v14_report["rows"]),
            "v15_rows_sha256": _sha256_json(v15_report["rows"]),
        },
        "support_boundary": {
            "supported_cases": len(missed) + len(correct_support),
            "correctly_supported": len(correct_support),
            "missed_supported": len(missed),
            "false_supports": len(false_support),
            "false_support_budget": false_support_budget,
            "additional_true_supports_needed": additional_true_supports,
            "remaining_false_support_budget": remaining_false_supports,
            "minimum_precision_for_next_promotions": round(
                additional_true_supports
                / (additional_true_supports + remaining_false_supports),
                4,
            ),
        },
        "missed_support_diagnostics": {
            "primary_counts": dict(sorted(categories.items())),
            "flag_counts": dict(sorted(flags.items())),
            "signal_comparison": {
                "missed_supported": _signal_summary(missed),
                "correctly_supported": _signal_summary(correct_support),
                "false_supported": _signal_summary(false_support),
            },
            "rows": missed,
        },
        "false_support_guard_cases": false_support,
        "exact_threshold_frontier": frontier,
        "decision": "improve_atomic_decomposition_and_cross_span_coverage_before_v17_classifier",
        "recommended_next_work": [
            "split materially coordinated supported claims into complete requirements",
            "score requirements over evidence combinations instead of isolated spans",
            "preserve V14 contradiction and ambiguity routing as hard guards",
            "require at least 75 percent precision on newly promoted support cases",
        ],
        "remote_inference_used": False,
        "stable_defaults_changed": False,
        "remote_provider_default_enabled": False,
        "local_only_network_calls": 0,
    }


def _diagnostic_row(
    *,
    example: dict[str, Any],
    relation: dict[str, Any],
    atomic: dict[str, Any],
    v14: dict[str, Any],
    v15: dict[str, Any],
) -> dict[str, Any]:
    per_evidence = [row["probabilities"] for row in relation["per_evidence"]]
    requirements = list(atomic["requirements"])
    atomic_entailment = [float(row["nli_scores"]["entailment"]) for row in requirements]
    lexical = _lexical_features(example)
    claim = str(example["input"]["claim"])
    requirement_count = len(requirements)
    maximum_entailment = max(float(row["entailment"]) for row in per_evidence)
    flags = {
        "v14_non_target_route": v14["prediction"] not in TARGET_LABELS,
        "single_requirement_complex_claim": bool(
            requirement_count == 1 and COMPLEX_CLAIM_RE.search(claim)
        ),
        "atomic_all_covered": atomic["atomic_verdict"] == "supported",
        "atomic_entailment_below_0_70": min(atomic_entailment) < 0.70,
        "full_claim_entailment_below_v11_threshold": maximum_entailment
        < 0.5347484350204468,
        "selected_evidence_low_claim_coverage": lexical[0] < 0.60,
        "selected_evidence_low_best_span_coverage": lexical[2] < 0.50,
        "selected_evidence_missing_number": lexical[9] > 0.0,
        "cross_span_gain": max(atomic_entailment) - maximum_entailment >= 0.15,
        "v15_completeness_below_threshold": float(v15["complete_support_probability"])
        < 0.80,
    }
    primary = _primary_diagnostic(flags, atomic=atomic, lexical=lexical)
    return {
        "case_id": str(example["id"]),
        "claim_sha256": hashlib.sha256(claim.encode("utf-8")).hexdigest(),
        "expected_verdict": str(example["target"]["verdict"]),
        "v14_prediction": str(v14["prediction"]),
        "v15_prediction": str(v15["prediction"]),
        "complete_support_probability": float(v15["complete_support_probability"]),
        "v14_probabilities": {
            label: float(v14["probabilities"][label]) for label in LABELS
        },
        "signals": {
            "atomic_requirement_count": requirement_count,
            "atomic_verdict": str(atomic["atomic_verdict"]),
            "atomic_minimum_entailment": min(atomic_entailment),
            "atomic_mean_entailment": statistics.fmean(atomic_entailment),
            "full_claim_maximum_entailment": maximum_entailment,
            "claim_coverage": float(lexical[0]),
            "best_span_claim_coverage": float(lexical[2]),
            "number_coverage": float(lexical[8]),
        },
        "diagnostic_flags": flags,
        "primary_diagnostic": primary,
    }


def _primary_diagnostic(
    flags: dict[str, bool], *, atomic: dict[str, Any], lexical: list[float]
) -> str:
    if flags["v14_non_target_route"]:
        return "v14_non_target_route"
    if flags["single_requirement_complex_claim"]:
        return "atomic_under_decomposition_candidate"
    if flags["atomic_all_covered"] and flags["v15_completeness_below_threshold"]:
        return "completeness_ranker_false_negative"
    if (
        flags["selected_evidence_low_claim_coverage"]
        or flags["selected_evidence_low_best_span_coverage"]
    ):
        return "selected_evidence_coverage_risk"
    if atomic["atomic_verdict"] != "supported" and lexical[0] >= 0.60:
        return "relation_scoring_false_negative_candidate"
    return "mixed_signal"


def _signal_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {"cases": 0}
    signal_names = (
        "atomic_requirement_count",
        "atomic_minimum_entailment",
        "atomic_mean_entailment",
        "full_claim_maximum_entailment",
        "claim_coverage",
        "best_span_claim_coverage",
        "number_coverage",
    )
    return {
        "cases": len(rows),
        "means": {
            name: round(statistics.fmean(row["signals"][name] for row in rows), 4)
            for name in signal_names
        },
        "complete_support_probability_mean": round(
            statistics.fmean(row["complete_support_probability"] for row in rows), 4
        ),
    }


def _exact_frontier(rows: list[dict[str, Any]]) -> dict[str, Any]:
    eligible = [row["v14_prediction"] in TARGET_LABELS for row in rows]
    completeness = [float(row["complete_support_probability"]) for row in rows]
    contradiction = [float(row["v14_probabilities"]["contradicted"]) for row in rows]
    unverifiable = [float(row["v14_probabilities"]["unverifiable"]) for row in rows]
    thresholds = sorted(
        {
            0.0,
            1.0,
            *(value for value, use in zip(completeness, eligible, strict=True) if use),
        }
    )
    contradiction_caps = sorted(
        {
            0.0,
            1.0,
            *(value for value, use in zip(contradiction, eligible, strict=True) if use),
        }
    )
    ambiguity_caps = sorted(
        {
            0.0,
            1.0,
            *(value for value, use in zip(unverifiable, eligible, strict=True) if use),
        }
    )
    targets = [str(row["expected_verdict"]) for row in rows]
    best_safe: dict[str, Any] | None = None
    support_target: list[dict[str, Any]] = []
    passing = 0
    for threshold in thresholds:
        complete_mask = [
            use and value >= threshold
            for use, value in zip(eligible, completeness, strict=True)
        ]
        for contradiction_cap in contradiction_caps:
            guarded = [
                use and value <= contradiction_cap
                for use, value in zip(complete_mask, contradiction, strict=True)
            ]
            for ambiguity_cap in ambiguity_caps:
                predictions = [
                    (
                        "supported"
                        if use and ambiguity <= ambiguity_cap
                        else "partially_supported"
                    )
                    if eligible[index]
                    else str(row["v14_prediction"])
                    for index, (row, use, ambiguity) in enumerate(
                        zip(rows, guarded, unverifiable, strict=True)
                    )
                ]
                metrics = policy_metrics(targets, predictions)
                policy = {
                    "complete_support_probability_minimum": threshold,
                    "contradiction_probability_maximum": contradiction_cap,
                    "unverifiable_probability_maximum": ambiguity_cap,
                    "metrics": metrics,
                }
                if metrics["gates"]["all_met"]:
                    passing += 1
                safe_review = all(
                    metrics["gates"][name]
                    for name in (
                        "false_support_rate",
                        "zero_contradiction_false_supports",
                        "partial_or_ambiguous_review_recall",
                        "review_rate",
                    )
                )
                if safe_review and (
                    best_safe is None
                    or _frontier_key(policy) > _frontier_key(best_safe)
                ):
                    best_safe = policy
                if metrics["support_recall"] >= SUPPORT_RECALL_TARGET:
                    support_target.append(policy)
    best_target = (
        min(
            support_target,
            key=lambda row: (
                row["metrics"]["false_support_rate"],
                row["metrics"]["contradiction_false_supports"],
                -row["metrics"]["partial_or_ambiguous_review_recall"],
                row["metrics"]["review_rate"],
                -row["metrics"]["macro_f1"],
            ),
        )
        if support_target
        else None
    )
    return {
        "candidate_count": len(thresholds)
        * len(contradiction_caps)
        * len(ambiguity_caps),
        "all_gate_candidate_count": passing,
        "best_policy_preserving_other_four_gates": best_safe,
        "lowest_false_support_policy_reaching_support_target": best_target,
    }


def _frontier_key(row: dict[str, Any]) -> tuple[Any, ...]:
    metrics = row["metrics"]
    return (
        metrics["support_recall"],
        -metrics["false_support_rate"],
        metrics["macro_f1"],
        metrics["partial_or_ambiguous_review_recall"],
        -metrics["review_rate"],
    )


def _aligned(
    development: dict[str, Any],
    relation_scores: dict[str, Any],
    atomic_scores: dict[str, Any],
    v14_report: dict[str, Any],
    v15_report: dict[str, Any],
) -> dict[str, Any]:
    if any(
        value.get("split") != DEVELOPMENT_SPLIT
        for value in (development, relation_scores, atomic_scores)
    ):
        raise V16AuditError("V16 accepts only V13 development artifacts.")
    for report in (v14_report, v15_report):
        protocol = report.get("protocol") or {}
        if (
            protocol.get("selection_split") != DEVELOPMENT_SPLIT
            or protocol.get("heldout_loaded") is not False
            or protocol.get("heldout_used_for_selection") is not False
        ):
            raise V16AuditError("V16 input does not attest development-only selection.")
    examples = {str(row["id"]): row for row in development.get("examples") or []}
    relations = {str(row["case_id"]): row for row in relation_scores.get("rows") or []}
    atomic = {str(row["case_id"]): row for row in atomic_scores.get("rows") or []}
    v14 = {str(row["case_id"]): row for row in v14_report.get("rows") or []}
    v15 = {str(row["case_id"]): row for row in v15_report.get("rows") or []}
    if not examples or not set(examples) == set(relations) == set(atomic) == set(
        v14
    ) == set(v15):
        raise V16AuditError("V16 case IDs are empty or misaligned.")
    case_ids = sorted(examples)
    return {
        "examples": [examples[case_id] for case_id in case_ids],
        "relations": [relations[case_id] for case_id in case_ids],
        "atomic": [atomic[case_id] for case_id in case_ids],
        "v14": [v14[case_id] for case_id in case_ids],
        "v15": [v15[case_id] for case_id in case_ids],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--development", required=True)
    parser.add_argument("--relation-scores", required=True)
    parser.add_argument("--atomic-scores", required=True)
    parser.add_argument("--v14-report", required=True)
    parser.add_argument("--v15-report", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)

    def load(path: str) -> dict[str, Any]:
        return json.loads(Path(path).read_text(encoding="utf-8"))

    report = audit(
        load(args.development),
        load(args.relation_scores),
        load(args.atomic_scores),
        load(args.v14_report),
        load(args.v15_report),
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "support_boundary": report["support_boundary"],
                "primary_counts": report["missed_support_diagnostics"][
                    "primary_counts"
                ],
                "frontier": report["exact_threshold_frontier"],
                "decision": report["decision"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
