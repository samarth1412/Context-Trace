from __future__ import annotations

import argparse
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

try:
    from benchmarks.contexttrace_bench.simulated_review.common import AGENTS, FAILURE_LABELS, read_jsonl, write_jsonl
except ModuleNotFoundError:  # pragma: no cover - direct execution
    from common import AGENTS, FAILURE_LABELS, read_jsonl, write_jsonl  # type: ignore


REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CORRECTIONS_DIR = REPO_ROOT / "benchmarks" / "contexttrace_bench" / "out" / "corrections"
SETTING_FILES = {
    "raw_trace": "setting_a_raw_trace.jsonl",
    "score_only": "setting_b_score_only.jsonl",
    "contexttrace": "setting_c_contexttrace.jsonl",
}


def score_annotation_review(
    *,
    dataset: str,
    review_dir: str | Path,
    key_path: str | Path,
    corrections_dir: str | Path = DEFAULT_CORRECTIONS_DIR,
) -> dict[str, Any]:
    directory = Path(review_dir)
    key = _load_json(Path(key_path))
    key_index = {str(row["blind_id"]): row for row in key.get("cases") or []}
    reviews: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for agent_id, config in AGENTS.items():
        for row in read_jsonl(directory / str(config["file"])):
            reviews[str(row["case_id"])][agent_id] = row

    combined = []
    suggestions = []
    complete_vote_sets = []
    pairwise_matches: dict[str, list[bool]] = defaultdict(list)
    for case_id in sorted(key_index):
        key_row = key_index[case_id]
        by_agent = reviews.get(case_id) or {}
        votes = [str(by_agent[agent]["failure_label"]) for agent in AGENTS if agent in by_agent]
        roots = [str(by_agent[agent]["root_cause"]) for agent in AGENTS if agent in by_agent]
        majority_label, majority_count = _majority(votes)
        majority_root, root_count = _majority(roots)
        frozen_label = simplify_expected_failure(key_row.get("expected") or key_row.get("expected_labels") or [])
        unanimous = len(votes) == len(AGENTS) and len(set(votes)) == 1
        ambiguous = len(votes) == len(AGENTS) and majority_count < 2
        disagrees = majority_label not in {None, "unsure"} and majority_label != frozen_label
        high_risk = disagrees and any(
            row.get("dangerous_false_green_risk") == "high" for row in by_agent.values()
        )
        status = None
        if disagrees:
            status = "high_priority_author_review" if unanimous else "medium_priority_author_review"
        elif ambiguous:
            status = "ambiguous"
        row = {
            "dataset": dataset,
            "case_id": case_id,
            "original_id": key_row.get("original_id"),
            "frozen_labels": key_row.get("expected") or key_row.get("expected_labels") or [],
            "frozen_failure_label": frozen_label,
            "agent_votes": {
                agent: {
                    "failure_label": review.get("failure_label"),
                    "root_cause": review.get("root_cause"),
                    "confidence": review.get("confidence"),
                    "dangerous_false_green_risk": review.get("dangerous_false_green_risk"),
                }
                for agent, review in sorted(by_agent.items())
            },
            "majority_failure_label": majority_label,
            "majority_failure_votes": majority_count,
            "majority_root_cause": majority_root,
            "majority_root_votes": root_count,
            "unanimous": unanimous,
            "ambiguous": ambiguous,
            "disagrees_with_frozen_label": disagrees,
            "high_risk_disagreement": high_risk,
            "review_status": status or "no_correction_suggested",
        }
        combined.append(row)
        if len(votes) == len(AGENTS):
            complete_vote_sets.append(votes)
            agent_names = list(AGENTS)
            for left in range(len(agent_names)):
                for right in range(left + 1, len(agent_names)):
                    name = "%s__%s" % (agent_names[left], agent_names[right])
                    pairwise_matches[name].append(
                        by_agent[agent_names[left]]["failure_label"]
                        == by_agent[agent_names[right]]["failure_label"]
                    )
        if status and disagrees:
            supporting = [value for value in by_agent.values() if value.get("failure_label") == majority_label]
            evidence = max(supporting, key=lambda value: float(value.get("confidence") or 0)) if supporting else {}
            suggestions.append(
                {
                    "dataset": dataset,
                    "case_id": case_id,
                    "original_id": key_row.get("original_id"),
                    "old_label": key_row.get("expected") or key_row.get("expected_labels") or [],
                    "new_suggested_label": majority_label,
                    "new_suggested_root_cause": majority_root,
                    "evidence_span": evidence.get("evidence_span"),
                    "reason": " | ".join(
                        "%s: %s" % (agent, value.get("rationale"))
                        for agent, value in sorted(by_agent.items())
                    ),
                    "source_agent_votes": {
                        agent: value.get("failure_label") for agent, value in sorted(by_agent.items())
                    },
                    "applied": False,
                    "status": "suggested_for_author_review",
                    "priority": status,
                    "independent_human_review": False,
                }
            )

    agreement = {
        "schema_version": 1,
        "dataset": dataset,
        "pilot_type": "llm_simulated_review_not_human_validation",
        "case_count": len(key_index),
        "complete_three_agent_cases": len(complete_vote_sets),
        "unanimous_cases": sum(len(set(votes)) == 1 for votes in complete_vote_sets),
        "disagreement_cases": sum(len(set(votes)) > 1 for votes in complete_vote_sets),
        "high_risk_disagreement_cases": sum(bool(row["high_risk_disagreement"]) for row in combined),
        "frozen_label_disagreement_cases": sum(bool(row["disagrees_with_frozen_label"]) for row in combined),
        "recommended_corrections": len(suggestions),
        "ambiguous_cases": sum(bool(row["ambiguous"]) for row in combined),
        "pairwise_exact_agreement": {
            pair: round(sum(values) / len(values), 6) if values else None
            for pair, values in sorted(pairwise_matches.items())
        },
        "fleiss_kappa": _fleiss_kappa(complete_vote_sets),
        "human_review": False,
        "paper_result_eligible": False,
        "sota_gate_eligible": False,
    }
    write_jsonl(directory / "combined_review.jsonl", combined)
    (directory / "agreement.json").write_text(
        json.dumps(agreement, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (directory / "review_summary.md").write_text(
        render_annotation_summary(agreement), encoding="utf-8"
    )
    _merge_correction_suggestions(Path(corrections_dir), dataset=dataset, suggestions=suggestions)
    return agreement


def render_annotation_summary(agreement: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# %s LLM-simulated review" % agreement["dataset"],
            "",
            "Status: controlled LLM-simulated pilot; not independent human review and not paper-result eligible.",
            "",
            "- Cases: `%s`" % agreement["case_count"],
            "- Complete three-agent cases: `%s`" % agreement["complete_three_agent_cases"],
            "- Unanimous cases: `%s`" % agreement["unanimous_cases"],
            "- Agent-disagreement cases: `%s`" % agreement["disagreement_cases"],
            "- Frozen-label disagreement cases: `%s`" % agreement["frozen_label_disagreement_cases"],
            "- High-risk disagreements: `%s`" % agreement["high_risk_disagreement_cases"],
            "- Suggested corrections: `%s`" % agreement["recommended_corrections"],
            "- Ambiguous cases: `%s`" % agreement["ambiguous_cases"],
            "- Fleiss kappa: `%s`" % _display(agreement["fleiss_kappa"]),
            "",
            "Suggested corrections remain unapplied until an author decision or independent human review.",
            "",
        ]
    )


def score_rq4_simulated(
    *, review_dir: str | Path, key_path: str | Path
) -> dict[str, Any]:
    directory = Path(review_dir)
    key = _load_json(Path(key_path))
    key_index = {str(row["blind_id"]): row for row in key.get("cases") or []}
    run_manifest = _load_json(directory / "run_manifest.json")
    settings: dict[str, Any] = {}
    for setting, filename in SETTING_FILES.items():
        rows = read_jsonl(directory / filename)
        scored = [_score_rq4_row(row, key_index[str(row["case_id"])]) for row in rows]
        settings[setting] = _aggregate_rq4(scored, expected=len(key_index) * len(AGENTS))
        settings[setting]["by_agent"] = {
            agent: _aggregate_rq4(
                [row for row in scored if row["agent_id"] == agent], expected=len(key_index)
            )
            for agent in AGENTS
        }
        usage = (run_manifest.get("groups") or {}).get(setting) or {}
        settings[setting]["input_tokens"] = usage.get("input_tokens")
        settings[setting]["output_tokens"] = usage.get("output_tokens")
        settings[setting]["estimated_cost_usd"] = usage.get("estimated_cost_usd")

    improvements = {
        "score_only_minus_raw": _rq4_delta(settings["score_only"], settings["raw_trace"]),
        "contexttrace_minus_score_only": _rq4_delta(settings["contexttrace"], settings["score_only"]),
        "contexttrace_minus_raw": _rq4_delta(settings["contexttrace"], settings["raw_trace"]),
    }
    treatment_improved = (
        improvements["contexttrace_minus_score_only"]["root_cause_accuracy"] > 0
        and improvements["contexttrace_minus_score_only"]["fix_correctness_proxy"] > 0
        and improvements["contexttrace_minus_raw"]["actionability_score"] > 0
    )
    report = {
        "schema_version": 1,
        "pilot_type": "controlled_llm_simulated_actionability_not_human_validation",
        "model": run_manifest.get("model"),
        "case_count": len(key_index),
        "simulated_reviewer_agents": len(AGENTS),
        "settings": settings,
        "improvements": improvements,
        "treatment_improved_preregistered_proxies": treatment_improved,
        "fix_correctness_definition": (
            "Proxy equals exact normalized root-cause match, actionability score >=4, and a non-empty fix recommendation."
        ),
        "human_review": False,
        "paper_result_eligible": False,
        "sota_gate_eligible": False,
    }
    (directory / "rq4_results.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (directory / "rq4_results.md").write_text(render_rq4_summary(report), encoding="utf-8")
    return report


def render_rq4_summary(report: dict[str, Any]) -> str:
    lines = [
        "# RQ4 controlled LLM-simulated actionability pilot",
        "",
        "This pilot does not replace independent human validation and is not paper-result or SOTA-gate eligible.",
        "",
        "| Setting | Rows | Root-cause accuracy | Fix correctness proxy | Actionability | False green | Confidence | Parse failure | Cost USD |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    labels = {
        "raw_trace": "A: raw trace",
        "score_only": "B: score only",
        "contexttrace": "C: evidence chain",
    }
    for setting in ("raw_trace", "score_only", "contexttrace"):
        row = report["settings"][setting]
        lines.append(
            "| %s | %s | %s | %s | %s | %s | %s | %s | %s |"
            % (
                labels[setting],
                row["completed_rows"],
                _display(row["root_cause_accuracy"]),
                _display(row["fix_correctness_proxy"]),
                _display(row["actionability_score"]),
                _display(row["dangerous_false_green_rate"]),
                _display(row["confidence"]),
                _display(row["parse_failure_rate"]),
                _display(row.get("estimated_cost_usd")),
            )
        )
    lines.extend(["", "## Interpretation", ""])
    if report["treatment_improved_preregistered_proxies"]:
        lines.append(
            "In this controlled LLM-simulated pilot, evidence-chain reports improved the registered root-cause, "
            "fix-selection proxy, and actionability measures over raw traces and score-only output."
        )
    else:
        lines.append(
            "The evidence-chain setting did not improve every registered proxy; no improvement claim is supported."
        )
    lines.extend(
        [
            "",
            "The fix-correctness measure is an operational proxy, not a human judgment: %s"
            % report["fix_correctness_definition"],
            "",
        ]
    )
    return "\n".join(lines)


def generate_sensitivity_analysis(
    *,
    corrections_path: str | Path,
    result_paths: list[str | Path],
    output_json: str | Path,
    output_md: str | Path,
) -> dict[str, Any]:
    corrections = [row for row in read_jsonl(corrections_path) if not row.get("applied")]
    correction_index = {
        str(row.get("original_id")): str(row.get("new_suggested_label"))
        for row in corrections
        if row.get("original_id") and row.get("new_suggested_label") in FAILURE_LABELS
    }
    rows: list[dict[str, Any]] = []
    for path in result_paths:
        payload = _load_json(Path(path))
        rows.extend(payload.get("rows") or [])
    expected_current = []
    expected_simulated = []
    expected_best = []
    expected_worst = []
    predicted = []
    affected = 0
    for row in rows:
        case_id = str(row.get("id") or "")
        current = simplify_expected_failure(row.get("expected") or [])
        prediction = simplify_expected_failure(row.get("predicted") or [])
        suggested = correction_index.get(case_id, current)
        if case_id in correction_index:
            affected += 1
        expected_current.append(current)
        expected_simulated.append(suggested)
        expected_best.append(prediction if case_id in correction_index else current)
        expected_worst.append(
            _different_label(prediction) if case_id in correction_index else current
        )
        predicted.append(prediction)
    report = {
        "schema_version": 1,
        "analysis_type": "simulated_label_sensitivity_not_corrected_results",
        "cases": len(rows),
        "suggested_correction_cases": affected,
        "corrections_applied": 0,
        "scenarios": {
            "frozen_labels": _classification_metrics(expected_current, predicted),
            "simulated_majority_suggestions": _classification_metrics(expected_simulated, predicted),
            "best_case_flagged_labels": _classification_metrics(expected_best, predicted),
            "worst_case_flagged_labels": _classification_metrics(expected_worst, predicted),
        },
        "paper_result_eligible": False,
        "sota_gate_eligible": False,
        "warning": "Simulated suggestions are not applied labels and do not replace independent review.",
    }
    output_json_path = Path(output_json)
    output_json_path.parent.mkdir(parents=True, exist_ok=True)
    output_json_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    Path(output_md).write_text(render_sensitivity(report), encoding="utf-8")
    return report


def render_sensitivity(report: dict[str, Any]) -> str:
    lines = [
        "# Simulated-label sensitivity analysis",
        "",
        "Status: sensitivity only; no simulated suggestion was applied as a benchmark correction.",
        "",
        "Cases: `%s`; suggested-correction cases: `%s`." % (report["cases"], report["suggested_correction_cases"]),
        "",
        "| Scenario | Accuracy | Macro F1 |",
        "| --- | ---: | ---: |",
    ]
    for name, row in report["scenarios"].items():
        lines.append("| %s | %s | %s |" % (name, _display(row["accuracy"]), _display(row["macro_f1"])))
    lines.extend(["", str(report["warning"]), ""])
    return "\n".join(lines)


def simplify_expected_failure(labels: Any) -> str:
    if isinstance(labels, str):
        values = {labels}
    elif isinstance(labels, list):
        values = {str(value) for value in labels}
    else:
        values = set()
    if values.intersection({"contradicted", "contradicted_answer", "conflicting_contexts"}):
        return "contradicted"
    if values.intersection({"partial_support", "partially_supported", "answer_overreach"}):
        return "partially_supported"
    if values.intersection({"should_have_abstained", "retrieval_failure", "corpus_gap", "unverifiable"}):
        return "unverifiable"
    if values.intersection({"unsupported", "unsupported_answer"}):
        return "unsupported"
    if values.intersection({"no_failure_detected", "supported"}):
        return "supported"
    return "unsure"


def normalize_root_cause(value: Any) -> str:
    root = str(value or "unsure")
    aliases = {
        "wrong_source_cited": "citation_mismatch",
        "citation_alignment": "citation_mismatch",
        "insufficient_retrieval": "retrieval_miss",
        "retrieval_failure": "retrieval_miss",
        "unsupported_answer": "answer_overreach",
    }
    return aliases.get(root, root)


def _score_rq4_row(row: dict[str, Any], key_row: dict[str, Any]) -> dict[str, Any]:
    expected_failure = simplify_expected_failure(key_row.get("expected") or key_row.get("expected_labels") or [])
    expected_root = normalize_root_cause(key_row.get("expected_primary_root_cause"))
    predicted_root = normalize_root_cause(row.get("root_cause"))
    root_correct = predicted_root == expected_root
    actionability = int(row.get("actionability_score") or 0)
    fix_proxy = root_correct and actionability >= 4 and bool(str(row.get("fix_recommendation") or "").strip())
    false_green = expected_failure != "supported" and row.get("failure_label") == "supported"
    return {
        "agent_id": row.get("agent_id"),
        "root_cause_correct": root_correct,
        "fix_correctness_proxy": fix_proxy,
        "actionability_score": actionability,
        "dangerous_false_green": false_green,
        "confidence": float(row.get("confidence") or 0),
    }


def _aggregate_rq4(rows: list[dict[str, Any]], *, expected: int) -> dict[str, Any]:
    count = len(rows)
    return {
        "expected_rows": expected,
        "completed_rows": count,
        "root_cause_accuracy": _mean([row["root_cause_correct"] for row in rows]),
        "fix_correctness_proxy": _mean([row["fix_correctness_proxy"] for row in rows]),
        "actionability_score": _mean([row["actionability_score"] for row in rows]),
        "dangerous_false_green_rate": _mean([row["dangerous_false_green"] for row in rows]),
        "confidence": _mean([row["confidence"] for row in rows]),
        "parse_failure_rate": (expected - count) / expected if expected else None,
    }


def _rq4_delta(treatment: dict[str, Any], control: dict[str, Any]) -> dict[str, float]:
    fields = (
        "root_cause_accuracy",
        "fix_correctness_proxy",
        "actionability_score",
        "dangerous_false_green_rate",
        "confidence",
    )
    return {field: round(float(treatment[field]) - float(control[field]), 6) for field in fields}


def _merge_correction_suggestions(directory: Path, *, dataset: str, suggestions: list[dict[str, Any]]) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "suggested_corrections.jsonl"
    existing = [row for row in read_jsonl(path) if row.get("dataset") != dataset]
    merged = sorted(existing + suggestions, key=lambda row: (str(row.get("dataset")), str(row.get("case_id"))))
    write_jsonl(path, merged)
    applied_path = directory / "applied_corrections.jsonl"
    if not applied_path.exists():
        write_jsonl(applied_path, [])
    by_dataset = Counter(str(row.get("dataset")) for row in merged)
    lines = [
        "# Correction summary",
        "",
        "Status: simulated suggestions only; no labels were changed.",
        "",
        "- Suggested corrections: `%s`" % len(merged),
        "- Applied corrections: `0`",
    ]
    lines.extend("- %s suggestions: `%s`" % item for item in sorted(by_dataset.items()))
    lines.extend(["", "Independent human review or an explicit author decision is required before application.", ""])
    (directory / "correction_summary.md").write_text("\n".join(lines), encoding="utf-8")


def _majority(values: list[str]) -> tuple[str | None, int]:
    if not values:
        return None, 0
    counts = Counter(values)
    label, count = counts.most_common(1)[0]
    if list(counts.values()).count(count) > 1:
        return None, count
    return label, count


def _fleiss_kappa(vote_sets: list[list[str]]) -> float | None:
    if not vote_sets:
        return None
    labels = sorted({label for votes in vote_sets for label in votes})
    n = len(vote_sets[0])
    if n < 2 or any(len(votes) != n for votes in vote_sets):
        return None
    observed = []
    totals = Counter()
    for votes in vote_sets:
        counts = Counter(votes)
        totals.update(votes)
        observed.append((sum(count * count for count in counts.values()) - n) / (n * (n - 1)))
    p_bar = sum(observed) / len(observed)
    total_votes = len(vote_sets) * n
    p_e = sum((totals[label] / total_votes) ** 2 for label in labels)
    if math.isclose(1 - p_e, 0):
        return 1.0 if math.isclose(p_bar, 1) else None
    return round((p_bar - p_e) / (1 - p_e), 6)


def _classification_metrics(expected: list[str], predicted: list[str]) -> dict[str, float | int]:
    if len(expected) != len(predicted):
        raise ValueError("Expected and predicted arrays must align.")
    labels = sorted((set(expected) | set(predicted)) - {"unsure"})
    accuracy = sum(left == right for left, right in zip(expected, predicted)) / len(expected) if expected else 0.0
    f1_values = []
    for label in labels:
        tp = sum(left == label and right == label for left, right in zip(expected, predicted))
        fp = sum(left != label and right == label for left, right in zip(expected, predicted))
        fn = sum(left == label and right != label for left, right in zip(expected, predicted))
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1_values.append(2 * precision * recall / (precision + recall) if precision + recall else 0.0)
    return {
        "cases": len(expected),
        "accuracy": round(accuracy, 6),
        "macro_f1": round(sum(f1_values) / len(f1_values), 6) if f1_values else 0.0,
    }


def _different_label(label: str) -> str:
    for candidate in ("supported", "unsupported", "contradicted", "partially_supported", "unverifiable"):
        if candidate != label:
            return candidate
    return "unsure"


def _mean(values: list[Any]) -> float | None:
    return round(sum(float(value) for value in values) / len(values), 6) if values else None


def _display(value: Any) -> str:
    if value is None:
        return "N/A"
    if isinstance(value, float):
        return "%.3f" % value
    return str(value)


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError("%s must contain a JSON object." % path)
    return value


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Score controlled LLM-simulated review pilots.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    annotation = subparsers.add_parser("annotation")
    annotation.add_argument("--dataset", required=True)
    annotation.add_argument("--review-dir", required=True)
    annotation.add_argument("--key", required=True)
    annotation.add_argument("--corrections-dir", default=str(DEFAULT_CORRECTIONS_DIR))
    rq4 = subparsers.add_parser("rq4")
    rq4.add_argument("--review-dir", required=True)
    rq4.add_argument("--key", required=True)
    sensitivity = subparsers.add_parser("sensitivity")
    sensitivity.add_argument("--corrections", required=True)
    sensitivity.add_argument("--results", nargs="+", required=True)
    sensitivity.add_argument("--output-json", required=True)
    sensitivity.add_argument("--output-md", required=True)
    return parser


def main() -> int:
    args = _parser().parse_args()
    if args.command == "annotation":
        report = score_annotation_review(
            dataset=args.dataset,
            review_dir=args.review_dir,
            key_path=args.key,
            corrections_dir=args.corrections_dir,
        )
        print("%s simulated review: %s complete cases" % (args.dataset, report["complete_three_agent_cases"]))
        print("Suggested corrections: %s" % report["recommended_corrections"])
    elif args.command == "rq4":
        report = score_rq4_simulated(review_dir=args.review_dir, key_path=args.key)
        print("RQ4 simulated rows: %s" % sum(row["completed_rows"] for row in report["settings"].values()))
        print("Treatment improved proxies: %s" % report["treatment_improved_preregistered_proxies"])
    else:
        report = generate_sensitivity_analysis(
            corrections_path=args.corrections,
            result_paths=args.results,
            output_json=args.output_json,
            output_md=args.output_md,
        )
        print("Sensitivity cases: %s" % report["cases"])
        print("Suggested-correction cases: %s" % report["suggested_correction_cases"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
