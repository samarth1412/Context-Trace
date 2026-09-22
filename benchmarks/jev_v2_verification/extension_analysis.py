"""Analyze the frozen, non-overlapping Jev-v2 sentence extension."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any, Callable

from .run import _write_json


class ExtensionAnalysisError(RuntimeError):
    """Raised when extension artifacts are incomplete or not input-equivalent."""


def wilson_interval(successes: int, total: int, *, z: float = 1.959963984540054) -> list[float] | None:
    if total <= 0:
        return None
    proportion = successes / total
    denominator = 1.0 + z * z / total
    center = (proportion + z * z / (2.0 * total)) / denominator
    margin = (
        z
        * math.sqrt(proportion * (1.0 - proportion) / total + z * z / (4.0 * total * total))
        / denominator
    )
    return [round(max(0.0, center - margin), 4), round(min(1.0, center + margin), 4)]


def exact_mcnemar(
    gold: list[str],
    candidate: list[str],
    baseline: list[str],
) -> dict[str, Any]:
    if not (len(gold) == len(candidate) == len(baseline)):
        raise ExtensionAnalysisError("Paired predictions must have equal lengths.")
    candidate_only = sum(
        candidate_value == gold_value and baseline_value != gold_value
        for gold_value, candidate_value, baseline_value in zip(
            gold, candidate, baseline, strict=True
        )
    )
    baseline_only = sum(
        baseline_value == gold_value and candidate_value != gold_value
        for gold_value, candidate_value, baseline_value in zip(
            gold, candidate, baseline, strict=True
        )
    )
    discordant = candidate_only + baseline_only
    if discordant:
        tail = sum(math.comb(discordant, index) for index in range(min(candidate_only, baseline_only) + 1))
        p_value = min(1.0, 2.0 * tail / (2**discordant))
    else:
        p_value = 1.0
    return {
        "candidate_only_correct": candidate_only,
        "baseline_only_correct": baseline_only,
        "discordant_pairs": discordant,
        "exact_two_sided_p": round(p_value, 8),
    }


def binary_summary(gold: list[str], predictions: list[str]) -> dict[str, Any]:
    if len(gold) != len(predictions):
        raise ExtensionAnalysisError("Gold and predictions must have equal lengths.")
    correct = sum(left == right for left, right in zip(gold, predictions, strict=True))
    supported_total = sum(value == "supported" for value in gold)
    negative_total = len(gold) - supported_total
    supported_correct = sum(
        gold_value == prediction == "supported"
        for gold_value, prediction in zip(gold, predictions, strict=True)
    )
    false_support = sum(
        gold_value == "not_supported" and prediction == "supported"
        for gold_value, prediction in zip(gold, predictions, strict=True)
    )
    return {
        "cases": len(gold),
        "accuracy": round(correct / len(gold), 4),
        "accuracy_wilson_95": wilson_interval(correct, len(gold)),
        "supported_recall": round(supported_correct / supported_total, 4),
        "supported_recall_wilson_95": wilson_interval(supported_correct, supported_total),
        "false_support_rate": round(false_support / negative_total, 4),
        "false_support_rate_wilson_95": wilson_interval(false_support, negative_total),
        "false_support_count": false_support,
        "negative_cases": negative_total,
    }


def analyze_split(
    verifier_result: dict[str, Any],
    minicheck_result: dict[str, Any],
) -> dict[str, Any]:
    verifier_rows = {str(row["case_id"]): row for row in verifier_result["rows"]}
    minicheck_rows = {str(row["case_id"]): row for row in minicheck_result["rows"]}
    if set(verifier_rows) != set(minicheck_rows):
        raise ExtensionAnalysisError("Verifier and MiniCheck case IDs differ.")
    ordered_ids = sorted(verifier_rows)
    for case_id in ordered_ids:
        if (
            verifier_rows[case_id]["input_audit"]["input_sha256"]
            != minicheck_rows[case_id]["input_audit"]["input_sha256"]
        ):
            raise ExtensionAnalysisError("Selected evidence differs for %s." % case_id)

    binary_gold = [
        "supported" if verifier_rows[case_id]["expected_verdict"] == "supported" else "not_supported"
        for case_id in ordered_ids
    ]
    extractors: dict[str, Callable[[str], str]] = {
        "jev": lambda case_id: (
            "supported"
            if verifier_rows[case_id]["predictions"]["jev"]["verdict"] == "supported"
            else "not_supported"
        ),
        "stable_semantic": lambda case_id: (
            "supported"
            if verifier_rows[case_id]["predictions"]["stable_semantic"]["verdict"] == "supported"
            else "not_supported"
        ),
        "minicheck_roberta": lambda case_id: minicheck_rows[case_id]["prediction"]["label"],
    }
    predictions = {
        name: [extractor(case_id) for case_id in ordered_ids]
        for name, extractor in extractors.items()
    }
    five_way_gold = [verifier_rows[case_id]["expected_verdict"] for case_id in ordered_ids]
    jev_five_way = [verifier_rows[case_id]["predictions"]["jev"]["verdict"] for case_id in ordered_ids]
    stable_five_way = [
        verifier_rows[case_id]["predictions"]["stable_semantic"]["verdict"]
        for case_id in ordered_ids
    ]
    return {
        "cases": len(ordered_ids),
        "exact_selected_input_match": True,
        "binary": {
            name: binary_summary(binary_gold, values) for name, values in predictions.items()
        },
        "paired_binary_tests": {
            "jev_vs_stable_semantic": exact_mcnemar(
                binary_gold, predictions["jev"], predictions["stable_semantic"]
            ),
            "jev_vs_minicheck_roberta": exact_mcnemar(
                binary_gold, predictions["jev"], predictions["minicheck_roberta"]
            ),
        },
        "paired_five_way_test": {
            "jev_vs_stable_semantic": exact_mcnemar(
                five_way_gold, jev_five_way, stable_five_way
            )
        },
    }


def analyze(
    development_verifier: dict[str, Any],
    development_minicheck: dict[str, Any],
    heldout_verifier: dict[str, Any],
    heldout_minicheck: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "experiment": "contexttrace_jev_v2_nonoverlapping_sentence_extension",
        "scope": "deterministic sentence projection of upstream human answer-side spans",
        "confirmatory_claim_allowed": False,
        "limitations": [
            "Sentence verdicts are deterministic projections, not independent claim annotations.",
            "RAGTruth provides no unverifiable class and this extension has no unsupported class.",
            "Confidence intervals do not account for clustering by source response.",
            "Paired p-values are exploratory and are not corrected for multiple comparisons.",
        ],
        "development": analyze_split(development_verifier, development_minicheck),
        "heldout": analyze_split(heldout_verifier, heldout_minicheck),
    }


def _load(path: str) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ExtensionAnalysisError("%s must contain a JSON object." % path)
    return value


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--development-verifier", required=True)
    parser.add_argument("--development-minicheck", required=True)
    parser.add_argument("--heldout-verifier", required=True)
    parser.add_argument("--heldout-minicheck", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    result = analyze(
        _load(args.development_verifier),
        _load(args.development_minicheck),
        _load(args.heldout_verifier),
        _load(args.heldout_minicheck),
    )
    _write_json(Path(args.output), result)
    print(json.dumps(result["heldout"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
