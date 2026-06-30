from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STATUS = REPO_ROOT / "benchmarks" / "contexttrace_bench" / "ARR_PRE_REVIEW_STATUS.json"
DEFAULT_TEX_DIR = Path(__file__).with_name("tables")
DEFAULT_MD_DIR = Path(__file__).with_name("tables_md")


def generate_paper_tables(
    *,
    status_path: str | Path = DEFAULT_STATUS,
    tex_dir: str | Path = DEFAULT_TEX_DIR,
    markdown_dir: str | Path = DEFAULT_MD_DIR,
    rq4_results_path: str | Path | None = None,
) -> dict[str, str]:
    status = _load_object(Path(status_path))
    rq4 = _load_object(Path(rq4_results_path)) if rq4_results_path else None
    tex_destination = Path(tex_dir)
    markdown_destination = Path(markdown_dir)
    tex_destination.mkdir(parents=True, exist_ok=True)
    markdown_destination.mkdir(parents=True, exist_ok=True)

    tables = {
        "table1_main_results": _main_results(status),
        "table2_baselines": _baselines(status),
        "table3_ablations": _ablations(status),
        "table4_rq4_actionability": _rq4(rq4),
        "table5_error_analysis": _error_analysis(status),
        "table6_reproducibility": _reproducibility(status),
    }
    outputs = {}
    for name, rows in tables.items():
        tex_path = tex_destination / (name + ".tex")
        md_path = markdown_destination / (name + ".md")
        tex_path.write_text(_render_tex(name, rows), encoding="utf-8")
        md_path.write_text(_render_markdown(name, rows), encoding="utf-8")
        outputs[name + "_tex"] = str(tex_path)
        outputs[name + "_markdown"] = str(md_path)
    return outputs


def _main_results(status: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for row in status.get("external_results") or []:
        summary = row.get("summary") or {}
        rows.append(
            {
                "Dataset": row.get("dataset"),
                "Review status": row.get("review_status"),
                "Cases": summary.get("cases"),
                "Failure F1": _metric(summary.get("failure_label_macro_f1")),
                "Root cause": _metric(summary.get("root_cause_accuracy")),
                "Citation F1": _metric(summary.get("citation_error_f1")),
                "Span overlap": _metric(summary.get("evidence_span_overlap")),
                "False green": _metric(summary.get("dangerous_false_green_rate")),
            }
        )
    return rows


def _baselines(status: dict[str, Any]) -> list[dict[str, Any]]:
    ragtruth = next(
        (row for row in status.get("external_results") or [] if row.get("dataset_id") == "ragtruth_primary"),
        {},
    )
    rows = [_baseline_row("ContextTrace", ragtruth, "assisted_review_pending_independent")]
    for row in status.get("baseline_results") or []:
        rows.append(_baseline_row(str(row.get("system") or "baseline"), row, "same-ID cached baseline"))
    return rows


def _baseline_row(system: str, row: dict[str, Any], review_status: str) -> dict[str, Any]:
    summary = row.get("summary") or {}
    return {
        "System": system,
        "Review status": review_status,
        "Cases": summary.get("cases"),
        "Failure F1": _metric(summary.get("failure_label_macro_f1")),
        "Claim F1": _metric(summary.get("claim_verdict_macro_f1")),
        "Root cause": _metric(summary.get("root_cause_accuracy")),
        "Citation F1": _metric(summary.get("citation_error_f1")),
        "Span overlap": _metric(summary.get("evidence_span_overlap")),
        "False green": _metric(summary.get("dangerous_false_green_rate")),
    }


def _ablations(status: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for row in status.get("ablation_results") or []:
        summary = row.get("summary") or {}
        rows.append(
            {
                "Variant": row.get("label"),
                "Availability": row.get("availability"),
                "Review status": "engineering regression benchmark",
                "Failure F1": _metric(summary.get("failure_label_macro_f1")),
                "Root cause": _metric(summary.get("root_cause_accuracy")),
                "Citation F1": _metric(summary.get("citation_error_f1")),
                "Span overlap": _metric(summary.get("evidence_span_overlap")),
                "False green": _metric(summary.get("dangerous_false_green_rate")),
                "p95 ms": _metric(summary.get("latency_p95_ms")),
                "Cost / 100": _metric(summary.get("cost_per_100_traces_usd")),
            }
        )
    return rows


def _rq4(result: dict[str, Any] | None) -> list[dict[str, Any]]:
    if result is None:
        return [
            {
                "Study": "Preregistered paired actionability study",
                "Review status": "pending three independent reviewers",
                "Cases": 40,
                "Reviewers / agents": "0/3 humans",
                "Root cause": "N/A",
                "Fix proxy": "N/A",
                "Actionability": "N/A",
                "False green": "N/A",
            }
        ]
    if result.get("pilot_type") == "controlled_llm_simulated_actionability_not_human_validation":
        rows = _rq4(None)
        labels = {
            "raw_trace": "Simulated A: raw trace",
            "score_only": "Simulated B: score only",
            "contexttrace": "Simulated C: evidence chain",
        }
        for setting in ("raw_trace", "score_only", "contexttrace"):
            summary = (result.get("settings") or {}).get(setting) or {}
            rows.append(
                {
                    "Study": labels[setting],
                    "Review status": "LLM-simulated pilot; not human validation",
                    "Cases": result.get("case_count"),
                    "Reviewers / agents": result.get("simulated_reviewer_agents"),
                    "Root cause": _metric(summary.get("root_cause_accuracy")),
                    "Fix proxy": _metric(summary.get("fix_correctness_proxy")),
                    "Actionability": _metric(summary.get("actionability_score")),
                    "False green": _metric(summary.get("dangerous_false_green_rate")),
                }
            )
        return rows
    summary = result.get("summary") or result
    return [
        {
            "Study": "Preregistered paired actionability study",
            "Review status": "human study" if result.get("paper_result_eligible") else "incomplete human study",
            "Cases": summary.get("case_count") or result.get("case_count"),
            "Reviewers / agents": len(result.get("reviewers") or []),
            "Root cause": "N/A",
            "Fix proxy": "N/A",
            "Actionability": _metric(summary.get("repair_actionable_delta")),
            "False green": "N/A",
        }
    ]


def _error_analysis(status: dict[str, Any]) -> list[dict[str, Any]]:
    error = status.get("error_analysis") or {}
    cases = error.get("cases_to_review") or []
    confusion = error.get("confusion") or []
    root_confusion = error.get("root_cause_confusion") or []
    baseline = (status.get("baseline_results") or [{}])[0].get("summary") or {}

    overflag = sum(
        int(row.get("count") or 0)
        for row in confusion
        if row.get("expected") == "no_failure_detected" and row.get("predicted") != "no_failure_detected"
    )
    contradiction_missed = sum(
        int(row.get("count") or 0)
        for row in confusion
        if row.get("expected") == "contradicted_answer" and row.get("predicted") != "contradicted_answer"
    )
    root_missed = sum(
        int(row.get("count") or 0)
        for row in root_confusion
        if row.get("expected_root_cause") != row.get("predicted_root_cause")
    )
    baseline_false_green = round(
        float(baseline.get("dangerous_false_green_rate") or 0.0) * int(baseline.get("cases") or 0)
    )
    return [
        _cluster("Supported claim overflagged", overflag, _example(cases, "no_failure_detected"), "Support threshold or label boundary", "Independent adjudication and calibrated claim decomposition", True),
        _cluster("Contradiction missed", contradiction_missed, _example(cases, "contradicted_answer"), "Taxonomy boundary or implicit contradiction", "Adjudicate labels; add contradiction regression cases", True),
        _cluster("Evidence span too broad", "not_measured", "N/A", "No dedicated breadth annotation", "Add span-boundary error tags during review", "unknown"),
        _cluster("Multi-span evidence failure", "not_measured", "N/A", "Distributed evidence is not separately tagged", "Add multi-span annotations and recall metric", "unknown"),
        _cluster("Root cause confused", root_missed, _root_example(cases), "Failure label and upstream cause are difficult to separate", "Adjudicate root causes and report agreement", True),
        _cluster("Numeric/date normalization error", "not_measured", "N/A", "No dedicated numeric/date error tag", "Add typed normalization error labels", "unknown"),
        _cluster("Citation mismatch ambiguity", 0, "N/A", "No citation mismatch was observed in the primary errors", "Retain citation-specific regression coverage", False),
        _cluster("Stale/source-trust limitation", "not_measured", "N/A", "RAGTruth does not independently label source freshness", "Evaluate on a temporally labeled dataset", "unknown"),
        _cluster("Score-only baseline false-green", baseline_false_green, "aggregate", "Score-only output lacks diagnostic coverage", "Report same-ID false-green rate and N/A fields", True, "same-ID cached baseline"),
        _cluster("Judge parse failure", "not_run", "N/A", "Judge-only mode is unavailable without a frozen provider", "Pin provider/model/cache/cost before running", "unknown", "not_run"),
    ]


def _cluster(
    name: str,
    count: Any,
    example: Any,
    cause: str,
    fix: str,
    affects: Any,
    review_status: str = "assisted_review_pending_independent",
) -> dict[str, Any]:
    return {
        "Cluster": name,
        "Review status": review_status,
        "Count": count,
        "Example": example,
        "What happened / likely cause": cause,
        "Planned fix": fix,
        "Affects broad claim": affects,
    }


def _example(cases: list[dict[str, Any]], expected: str) -> str:
    for case in cases:
        if expected in (case.get("expected") or []):
            return str(case.get("id") or "N/A")
    return "N/A"


def _root_example(cases: list[dict[str, Any]]) -> str:
    for case in cases:
        if case.get("expected_primary_root_cause") != case.get("predicted_primary_root_cause"):
            return str(case.get("id") or "N/A")
    return "N/A"


def _reproducibility(status: dict[str, Any]) -> list[dict[str, Any]]:
    reproduction = status.get("reproduction") or {}
    cost = reproduction.get("cost") or {}
    return [
        {"Item": "Source revision", "Review status": "pre_review_paper_candidate", "Value": status.get("source_commit"), "Status": "frozen"},
        {"Item": "Command", "Review status": "pre_review_paper_candidate", "Value": reproduction.get("command"), "Status": "full"},
        {"Item": "Python", "Review status": "pre_review_paper_candidate", "Value": (reproduction.get("python") or {}).get("version"), "Status": "recorded"},
        {"Item": "Runtime seconds", "Review status": "pre_review_paper_candidate", "Value": reproduction.get("runtime_seconds"), "Status": "recorded"},
        {"Item": "Bootstrap", "Review status": "pre_review_paper_candidate", "Value": "%s / %s" % (status.get("bootstrap_samples"), status.get("bootstrap_seed")), "Status": "frozen"},
        {"Item": "ContextTrace API cost", "Review status": "pre_review_paper_candidate", "Value": cost.get("contexttrace_api_cost_usd"), "Status": "local"},
        {"Item": "Candidate cost", "Review status": "same-ID cached baseline", "Value": "N/A" if cost.get("candidate_total_cost_usd") is None else cost.get("candidate_total_cost_usd"), "Status": "cached/unreported"},
        {"Item": "Paper result eligible", "Review status": "pending independent review", "Value": status.get("paper_result_eligible"), "Status": "pending review"},
    ]


def _render_markdown(name: str, rows: list[dict[str, Any]]) -> str:
    title = name.replace("_", " ").title()
    if not rows:
        return "# %s\n\nNo rows.\n" % title
    headers = list(rows[0])
    lines = ["# %s" % title, "", "| %s |" % " | ".join(headers), "| %s |" % " | ".join("---" for _ in headers)]
    for row in rows:
        lines.append("| %s |" % " | ".join(_md_cell(row.get(header)) for header in headers))
    lines.extend(["", "All rows expose review status; `N/A`, `not_run`, and `not_measured` are never imputed.", ""])
    return "\n".join(lines)


def _render_tex(name: str, rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "% No rows for %s\n" % name
    headers = list(rows[0])
    columns = "l" * len(headers)
    lines = [
        "% Generated by paper/generate_tables.py; do not edit manually.",
        "\\begin{table*}[t]",
        "\\centering",
        "\\scriptsize",
        "\\resizebox{\\textwidth}{!}{%",
        "\\begin{tabular}{%s}" % columns,
        "\\toprule",
        " %s \\\\" % " & ".join(_tex_cell(header) for header in headers),
        "\\midrule",
    ]
    for row in rows:
        lines.append(" %s \\\\" % " & ".join(_tex_cell(row.get(header)) for header in headers))
    lines.extend(
        [
            "\\bottomrule",
            "\\end{tabular}%",
            "}",
            "\\caption{%s. Review status and unavailable measurements are shown explicitly.}" % _tex_cell(name.replace("_", " ").title()),
            "\\label{tab:%s}" % name.replace("_", "-"),
            "\\end{table*}",
            "",
        ]
    )
    return "\n".join(lines)


def _metric(value: Any) -> str:
    if value is None:
        return "N/A"
    if isinstance(value, float):
        return "%.3f" % value
    return str(value)


def _md_cell(value: Any) -> str:
    return str("N/A" if value is None else value).replace("|", "\\|").replace("\n", " ")


def _tex_cell(value: Any) -> str:
    text = str("N/A" if value is None else value)
    replacements = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
    }
    return "".join(replacements.get(char, char) for char in text)


def _load_object(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError("Expected JSON object: %s" % path)
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate paper-ready ContextTrace ARR tables.")
    parser.add_argument("--status", default=str(DEFAULT_STATUS))
    parser.add_argument("--tex-dir", default=str(DEFAULT_TEX_DIR))
    parser.add_argument("--markdown-dir", default=str(DEFAULT_MD_DIR))
    parser.add_argument("--rq4-results", default=None)
    args = parser.parse_args(argv)
    outputs = generate_paper_tables(
        status_path=args.status,
        tex_dir=args.tex_dir,
        markdown_dir=args.markdown_dir,
        rq4_results_path=args.rq4_results,
    )
    print("Generated tables: %s" % (len(outputs) // 2))
    print("TeX directory: %s" % args.tex_dir)
    print("Markdown directory: %s" % args.markdown_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
