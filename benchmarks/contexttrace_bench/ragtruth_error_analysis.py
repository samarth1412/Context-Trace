from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


DEFAULT_RESULTS_PATH = Path(__file__).with_name("out") / "ragtruth_release" / "scored" / "contexttrace_bench_results.json"
DEFAULT_CASE_PACK_PATH = Path(__file__).with_name("out") / "ragtruth_release" / "ragtruth_reviewed_case_pack.json"
DEFAULT_OUTPUT_DIR = Path(__file__).with_name("out") / "ragtruth_release" / "scored"
DEFAULT_SPAN_OVERLAP_THRESHOLD = 0.75


def load_json(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError("%s must contain a JSON object." % path)
    return payload


def build_ragtruth_error_analysis(
    result: dict[str, Any],
    case_pack: dict[str, Any],
    *,
    max_cases: int = 25,
    span_overlap_threshold: float = DEFAULT_SPAN_OVERLAP_THRESHOLD,
) -> dict[str, Any]:
    rows = [row for row in result.get("rows") or [] if isinstance(row, dict)]
    cases = {
        str(case.get("id") or ""): case
        for case in case_pack.get("cases") or []
        if isinstance(case, dict) and case.get("id")
    }
    enriched = [_enriched_row(row, cases.get(str(row.get("id") or "")) or {}, span_overlap_threshold=span_overlap_threshold) for row in rows]
    misses = [item for item in enriched if item["miss_flags"]["any_miss"]]
    targets = {
        "dangerous_false_greens": _target_cases(
            [item for item in enriched if item["miss_flags"]["dangerous_false_green"]],
            max_cases=max_cases,
        ),
        "partial_support_misses": _target_cases(
            [item for item in enriched if item["miss_flags"]["partial_support_miss"]],
            max_cases=max_cases,
        ),
        "contradicted_answer_misses": _target_cases(
            [item for item in enriched if item["miss_flags"]["contradicted_answer_miss"]],
            max_cases=max_cases,
        ),
        "source_span_bad_localization": _target_cases(
            [item for item in enriched if item["miss_flags"]["source_span_bad_localization"]],
            max_cases=max_cases,
        ),
        "root_cause_misses": _target_cases(
            [item for item in enriched if item["miss_flags"]["root_cause_miss"]],
            max_cases=max_cases,
        ),
    }
    return {
        "benchmark": "RAGTruth error analysis",
        "case_count": len(enriched),
        "summary": {
            "cases": len(enriched),
            "misses": len(misses),
            "miss_rate": _rate(len(misses), len(enriched)),
            "label_misses": sum(1 for item in enriched if item["miss_flags"]["label_miss"]),
            "root_cause_misses": sum(1 for item in enriched if item["miss_flags"]["root_cause_miss"]),
            "verdict_misses": sum(1 for item in enriched if item["miss_flags"]["verdict_miss"]),
            "dangerous_false_greens": sum(1 for item in enriched if item["miss_flags"]["dangerous_false_green"]),
            "span_localization_misses": sum(1 for item in enriched if item["miss_flags"]["span_localization_miss"]),
            "source_span_bad_localization": sum(1 for item in enriched if item["miss_flags"]["source_span_bad_localization"]),
            "span_overlap_threshold": float(span_overlap_threshold),
            "failure_label_macro_f1": (result.get("summary") or {}).get("failure_label_macro_f1"),
            "root_cause_accuracy": (result.get("summary") or {}).get("root_cause_accuracy"),
            "evidence_span_overlap": (result.get("summary") or {}).get("evidence_span_overlap"),
            "dangerous_false_green_rate": (result.get("summary") or {}).get("dangerous_false_green_rate"),
        },
        "groups": {
            "task_type": _facet_groups(enriched, "task_type"),
            "source_dataset": _facet_groups(enriched, "source_dataset"),
            "model": _facet_groups(enriched, "model"),
            "label_type": _multi_facet_groups(enriched, "label_types"),
            "expected_label": _multi_facet_groups(enriched, "expected"),
            "root_cause_confusion": _root_cause_confusion(enriched),
        },
        "calibration_targets": targets,
        "notes": [
            "RAGTruth labels answer-side hallucination spans; this analysis joins reviewed source-evidence mappings where available.",
            "Calibration targets are engineering priorities, not publishable SOTA claims.",
            "Assisted or source-span-missing reviews should remain calibration_only until independently signed off.",
        ],
    }


def write_ragtruth_error_analysis(
    result: dict[str, Any],
    case_pack: dict[str, Any],
    *,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    max_cases: int = 25,
    span_overlap_threshold: float = DEFAULT_SPAN_OVERLAP_THRESHOLD,
) -> dict[str, str]:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    analysis = build_ragtruth_error_analysis(
        result,
        case_pack,
        max_cases=max_cases,
        span_overlap_threshold=span_overlap_threshold,
    )
    json_path = output_path / "ragtruth_error_analysis.json"
    md_path = output_path / "ragtruth_error_analysis.md"
    json_path.write_text(json.dumps(analysis, indent=2, sort_keys=True), encoding="utf-8")
    md_path.write_text(render_ragtruth_error_analysis_markdown(analysis), encoding="utf-8")
    return {
        "ragtruth_error_analysis_json": str(json_path),
        "ragtruth_error_analysis_md": str(md_path),
    }


def render_ragtruth_error_analysis_markdown(analysis: dict[str, Any]) -> str:
    summary = analysis.get("summary") or {}
    lines = [
        "# RAGTruth Error Analysis",
        "",
        "This report turns the RAGTruth calibration result into concrete engineering targets. It is not a publishable SOTA claim by itself.",
        "",
        "## Summary",
        "",
        "| Metric | Value |",
        "| --- | ---: |",
        "| Cases | %s |" % summary.get("cases"),
        "| Misses | %s |" % summary.get("misses"),
        "| Miss rate | %s |" % _format_float(summary.get("miss_rate")),
        "| Failure macro-F1 | %s |" % _format_float(summary.get("failure_label_macro_f1")),
        "| Root-cause accuracy | %s |" % _format_float(summary.get("root_cause_accuracy")),
        "| Evidence span overlap | %s |" % _format_float(summary.get("evidence_span_overlap")),
        "| Dangerous false greens | %s |" % summary.get("dangerous_false_greens"),
        "| Span localization misses | %s |" % summary.get("span_localization_misses"),
        "",
        "## Top Calibration Targets",
        "",
    ]
    target_titles = {
        "dangerous_false_greens": "Dangerous False Greens",
        "partial_support_misses": "Partial-Support Misses",
        "contradicted_answer_misses": "Contradicted-Answer Misses",
        "source_span_bad_localization": "Source-Spans With Bad Localization",
        "root_cause_misses": "Root-Cause Misses",
    }
    for key, title in target_titles.items():
        lines.extend(_target_table(title, (analysis.get("calibration_targets") or {}).get(key) or []))

    groups = analysis.get("groups") or {}
    lines.extend(["## Miss Groups", ""])
    lines.extend(_group_table("By Task Type", groups.get("task_type") or []))
    lines.extend(_group_table("By Source Dataset", groups.get("source_dataset") or []))
    lines.extend(_group_table("By Model", groups.get("model") or []))
    lines.extend(_group_table("By RAGTruth Label Type", groups.get("label_type") or []))
    lines.extend(_group_table("By Expected Label", groups.get("expected_label") or []))

    lines.extend(["## Root Cause Confusion", "", "| Expected | Predicted | Count |", "| --- | --- | ---: |"])
    for row in (groups.get("root_cause_confusion") or [])[:20]:
        lines.append("| `%s` | `%s` | %s |" % (row.get("expected"), row.get("predicted"), row.get("count")))
    lines.append("")
    return "\n".join(lines)


def _enriched_row(row: dict[str, Any], case: dict[str, Any], *, span_overlap_threshold: float) -> dict[str, Any]:
    metadata = _case_metadata(case)
    expected = sorted(str(label) for label in row.get("expected") or [])
    predicted = sorted(str(label) for label in row.get("predicted") or [])
    expected_root = str(row.get("expected_primary_root_cause") or "")
    predicted_root = str(row.get("predicted_primary_root_cause") or "")
    expected_spans = [str(span) for span in row.get("expected_evidence_spans") or [] if str(span).strip()]
    predicted_spans = [str(span) for span in row.get("predicted_evidence_spans") or [] if str(span).strip()]
    span_overlap = row.get("evidence_span_overlap")
    span_miss = bool(expected_spans) and (span_overlap is None or float(span_overlap) < float(span_overlap_threshold))
    flags = {
        "label_miss": set(expected) != set(predicted),
        "root_cause_miss": bool(expected_root) and expected_root != predicted_root,
        "verdict_miss": row.get("verdict_match") is False,
        "dangerous_false_green": set(expected) != {"no_failure_detected"} and set(predicted) == {"no_failure_detected"},
        "partial_support_miss": "partial_support" in expected and set(expected) != set(predicted),
        "contradicted_answer_miss": "contradicted_answer" in expected and set(expected) != set(predicted),
        "span_localization_miss": span_miss,
        "source_span_bad_localization": bool(expected_spans) and bool(predicted_spans) and span_miss,
    }
    flags["any_miss"] = any(flags.values()) or row.get("benchmark_pass") is False
    return {
        "id": str(row.get("id") or ""),
        "expected": expected,
        "predicted": predicted,
        "expected_primary_root_cause": expected_root,
        "predicted_primary_root_cause": predicted_root,
        "expected_evidence_spans": expected_spans,
        "predicted_evidence_spans": predicted_spans[:5],
        "evidence_span_overlap": span_overlap,
        "benchmark_pass": bool(row.get("benchmark_pass")),
        "miss_flags": flags,
        **metadata,
    }


def _case_metadata(case: dict[str, Any]) -> dict[str, Any]:
    ragtruth = case.get("ragtruth_metadata") or {}
    review = case.get("review_metadata") or {}
    source = str(case.get("source") or "")
    source_parts = source.split("/", 2)
    first_context = (case.get("contexts") or [{}])[0]
    if not isinstance(first_context, dict):
        first_context = {}
    task_type = str(first_context.get("task_type") or (source_parts[1] if len(source_parts) > 1 else "unknown"))
    source_dataset = str(source_parts[2] if len(source_parts) > 2 else "unknown")
    answer_spans = [span for span in ragtruth.get("answer_hallucination_spans") or [] if isinstance(span, dict)]
    label_types = sorted({str(span.get("label_type") or "unknown") for span in answer_spans}) or ["no_hallucination_span"]
    return {
        "task_type": task_type or "unknown",
        "source_dataset": source_dataset or "unknown",
        "model": str(ragtruth.get("model") or "unknown"),
        "source_id": str(ragtruth.get("source_id") or ""),
        "response_id": str(ragtruth.get("response_id") or ""),
        "label_types": label_types,
        "answer_hallucination_span_count": len(answer_spans),
        "source_evidence_span_count": int(review.get("source_evidence_span_count") or len(case.get("expected_evidence_spans") or [])),
        "review_status": str(review.get("review_status") or ""),
        "reviewer": str(review.get("reviewer") or ""),
        "review_notes": str(review.get("review_notes") or "")[:300],
    }


def _facet_groups(items: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in items:
        buckets[str(item.get(key) or "unknown")].append(item)
    return _bucket_rows(buckets)


def _multi_facet_groups(items: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in items:
        values = item.get(key) or ["unknown"]
        for value in values:
            buckets[str(value or "unknown")].append(item)
    return _bucket_rows(buckets)


def _bucket_rows(buckets: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    rows = []
    for value, items in buckets.items():
        misses = [item for item in items if item["miss_flags"]["any_miss"]]
        rows.append(
            {
                "value": value,
                "cases": len(items),
                "misses": len(misses),
                "miss_rate": _rate(len(misses), len(items)),
                "dangerous_false_greens": sum(1 for item in items if item["miss_flags"]["dangerous_false_green"]),
                "root_cause_misses": sum(1 for item in items if item["miss_flags"]["root_cause_miss"]),
                "span_localization_misses": sum(1 for item in items if item["miss_flags"]["span_localization_miss"]),
            }
        )
    return sorted(rows, key=lambda row: (-row["misses"], -row["miss_rate"], row["value"]))


def _root_cause_confusion(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counter = Counter((item["expected_primary_root_cause"], item["predicted_primary_root_cause"]) for item in items)
    return [
        {"expected": expected, "predicted": predicted, "count": count}
        for (expected, predicted), count in sorted(counter.items(), key=lambda item: (-item[1], item[0]))
    ]


def _target_cases(items: list[dict[str, Any]], *, max_cases: int) -> list[dict[str, Any]]:
    ranked = sorted(
        items,
        key=lambda item: (
            item["miss_flags"]["dangerous_false_green"],
            item["source_evidence_span_count"],
            -(item["evidence_span_overlap"] or 0),
        ),
        reverse=True,
    )
    return [_case_item(item) for item in ranked[:max_cases]]


def _case_item(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": item["id"],
        "task_type": item["task_type"],
        "source_dataset": item["source_dataset"],
        "model": item["model"],
        "label_types": item["label_types"],
        "expected": item["expected"],
        "predicted": item["predicted"],
        "expected_primary_root_cause": item["expected_primary_root_cause"],
        "predicted_primary_root_cause": item["predicted_primary_root_cause"],
        "evidence_span_overlap": item["evidence_span_overlap"],
        "source_evidence_span_count": item["source_evidence_span_count"],
        "review_notes": item["review_notes"],
    }


def _target_table(title: str, rows: list[dict[str, Any]]) -> list[str]:
    lines = ["### %s" % title, ""]
    if not rows:
        return [*lines, "No cases in this bucket.", ""]
    lines.extend(["| Case | Task | Source | Expected | Predicted | Root Cause | Span Overlap |", "| --- | --- | --- | --- | --- | --- | ---: |"])
    for row in rows[:10]:
        lines.append(
            "| `%s` | `%s` | `%s` | `%s` | `%s` | `%s -> %s` | %s |"
            % (
                row.get("id"),
                row.get("task_type"),
                row.get("source_dataset"),
                ",".join(row.get("expected") or []),
                ",".join(row.get("predicted") or []),
                row.get("expected_primary_root_cause"),
                row.get("predicted_primary_root_cause"),
                _format_float(row.get("evidence_span_overlap")),
            )
        )
    lines.append("")
    return lines


def _group_table(title: str, rows: list[dict[str, Any]]) -> list[str]:
    lines = ["### %s" % title, "", "| Value | Cases | Misses | Miss Rate | False Greens | Root Misses | Span Misses |", "| --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for row in rows[:15]:
        lines.append(
            "| `%s` | %s | %s | %s | %s | %s | %s |"
            % (
                row.get("value"),
                row.get("cases"),
                row.get("misses"),
                _format_float(row.get("miss_rate")),
                row.get("dangerous_false_greens"),
                row.get("root_cause_misses"),
                row.get("span_localization_misses"),
            )
        )
    lines.append("")
    return lines


def _rate(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round(float(numerator) / float(denominator), 6)


def _format_float(value: Any) -> str:
    if value is None:
        return "N/A"
    if isinstance(value, float):
        return "%.3f" % value
    return str(value)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build RAGTruth calibration error-analysis reports.")
    parser.add_argument("--results", default=str(DEFAULT_RESULTS_PATH))
    parser.add_argument("--case-pack", default=str(DEFAULT_CASE_PACK_PATH))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--max-cases", type=int, default=25)
    parser.add_argument("--span-overlap-threshold", type=float, default=DEFAULT_SPAN_OVERLAP_THRESHOLD)
    args = parser.parse_args(argv)

    paths = write_ragtruth_error_analysis(
        load_json(args.results),
        load_json(args.case_pack),
        output_dir=args.output_dir,
        max_cases=args.max_cases,
        span_overlap_threshold=args.span_overlap_threshold,
    )
    print("RAGTruth error analysis: %s" % paths["ragtruth_error_analysis_md"])
    print("RAGTruth error analysis JSON: %s" % paths["ragtruth_error_analysis_json"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
