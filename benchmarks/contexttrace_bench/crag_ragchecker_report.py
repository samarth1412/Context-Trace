from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any


RAGCHECKER_METRICS = (
    "precision",
    "recall",
    "f1",
    "claim_recall",
    "context_precision",
    "context_utilization",
    "faithfulness",
    "hallucination",
    "noise_sensitivity_in_irrelevant",
    "noise_sensitivity_in_relevant",
    "self_knowledge",
)


def build_crag_ragchecker_report(
    contexttrace_result: dict[str, Any],
    ragchecker_candidate: dict[str, Any],
    ragchecker_raw: dict[str, Any],
) -> dict[str, Any]:
    contexttrace_rows = [row for row in contexttrace_result.get("rows") or [] if isinstance(row, dict)]
    candidate_rows = [
        row for row in ragchecker_candidate.get("predictions") or [] if isinstance(row, dict)
    ]
    raw_rows = [row for row in ragchecker_raw.get("rows") or [] if isinstance(row, dict)]
    if not contexttrace_rows:
        raise ValueError("ContextTrace CRAG result must contain rows.")
    if str(ragchecker_candidate.get("system") or "").lower() != "ragchecker":
        raise ValueError("Candidate system must be RAGChecker.")

    scopes = {
        str(_upstream_metadata(row).get("crag_label_scope") or "")
        for row in contexttrace_rows
    }
    if scopes != {"unreviewed_gold_answer_proxy"}:
        raise ValueError("CRAG RAGChecker comparison requires unreviewed_gold_answer_proxy rows.")
    reference = ragchecker_raw.get("reference") or {}
    if reference.get("mode") != "reference_file" or reference.get("uses_response_as_gt") is not False:
        raise ValueError("RAGChecker raw results must prove use of a real reference sidecar.")
    input_provenance = ragchecker_raw.get("input") or {}

    contexttrace_by_id = _unique_index(contexttrace_rows, "id", name="ContextTrace")
    candidate_by_id = _unique_index(candidate_rows, "id", name="RAGChecker candidate")
    raw_by_id = _unique_index(raw_rows, "query_id", name="RAGChecker raw")
    reference_ids = set(contexttrace_by_id)
    if set(candidate_by_id) != reference_ids or set(raw_by_id) != reference_ids:
        raise ValueError("ContextTrace, RAGChecker candidate, and raw IDs must match exactly.")
    errors = [row for row in raw_rows if row.get("error")]
    if errors:
        raise ValueError("RAGChecker raw results contain %s errored rows." % len(errors))

    both_accept = []
    both_flag = []
    contexttrace_accept_ragchecker_flag = []
    contexttrace_flag_ragchecker_accept = []
    for case_id in contexttrace_by_id:
        contexttrace_accepts = _accepted(contexttrace_by_id[case_id])
        ragchecker_accepts = _accepted(candidate_by_id[case_id])
        if contexttrace_accepts and ragchecker_accepts:
            both_accept.append(case_id)
        elif not contexttrace_accepts and not ragchecker_accepts:
            both_flag.append(case_id)
        elif contexttrace_accepts:
            contexttrace_accept_ragchecker_flag.append(case_id)
        else:
            contexttrace_flag_ragchecker_accept.append(case_id)

    total = len(reference_ids)
    if reference.get("reference_count") != total:
        raise ValueError("RAGChecker reference count must match the compared IDs exactly.")
    if input_provenance.get("rows") != total or len(str(input_provenance.get("sha256") or "")) != 64:
        raise ValueError("RAGChecker input provenance must cover the compared IDs.")
    contexttrace_accepted = len(both_accept) + len(contexttrace_accept_ragchecker_flag)
    ragchecker_accepted = len(both_accept) + len(contexttrace_flag_ragchecker_accept)
    agreement = len(both_accept) + len(both_flag)
    means = {
        metric: _mean_metric(raw_rows, metric)
        for metric in RAGCHECKER_METRICS
    }
    complete_metric_rows = sum(
        all(metric in (row.get("metrics") or {}) for metric in RAGCHECKER_METRICS)
        for row in raw_rows
    )
    if complete_metric_rows != total:
        raise ValueError("Every RAGChecker row must contain all requested metrics.")
    return {
        "report": "CRAG ContextTrace-RAGChecker gold-answer grounding comparison",
        "report_version": 1,
        "dataset": contexttrace_result.get("case_pack_dataset") or "CRAG-Task1-v5",
        "label_scope": "unreviewed_gold_answer_proxy",
        "publishable": False,
        "systems": {
            "contexttrace": {
                "mode": contexttrace_result.get("mode"),
                "proxy_accepted_cases": contexttrace_accepted,
                "proxy_acceptance_rate": round(contexttrace_accepted / total, 3),
                "flagged_cases": total - contexttrace_accepted,
            },
            "ragchecker": {
                "version": ragchecker_candidate.get("version"),
                "extractor_name": ragchecker_raw.get("extractor_name"),
                "checker_name": ragchecker_raw.get("checker_name"),
                "proxy_accepted_cases": ragchecker_accepted,
                "proxy_acceptance_rate": round(ragchecker_accepted / total, 3),
                "flagged_cases": total - ragchecker_accepted,
                "complete_metric_rows": complete_metric_rows,
                "mean_metrics": means,
            },
        },
        "coverage": {
            "reference_cases": total,
            "contexttrace_rows": len(contexttrace_rows),
            "ragchecker_candidate_rows": len(candidate_rows),
            "ragchecker_raw_rows": len(raw_rows),
            "ragchecker_error_rows": len(errors),
            "matched_ids": total,
        },
        "agreement": {
            "cases": agreement,
            "rate": round(agreement / total, 3),
            "cohen_kappa": _cohen_kappa(
                total=total,
                both_accept=len(both_accept),
                both_flag=len(both_flag),
                contexttrace_accepted=contexttrace_accepted,
                ragchecker_accepted=ragchecker_accepted,
            ),
            "mcnemar_exact_p_value": _mcnemar_exact_p_value(
                len(contexttrace_accept_ragchecker_flag),
                len(contexttrace_flag_ragchecker_accept),
            ),
            "both_accept": len(both_accept),
            "both_flag": len(both_flag),
            "contexttrace_accept_ragchecker_flag": len(contexttrace_accept_ragchecker_flag),
            "contexttrace_flag_ragchecker_accept": len(contexttrace_flag_ragchecker_accept),
        },
        "disagreement_case_ids": {
            "contexttrace_accept_ragchecker_flag": contexttrace_accept_ragchecker_flag,
            "contexttrace_flag_ragchecker_accept": contexttrace_flag_ragchecker_accept,
        },
        "reference": dict(reference),
        "input": dict(input_provenance),
        "source_sha256": {
            "contexttrace_result": _json_sha256(contexttrace_result),
            "ragchecker_candidate": _json_sha256(ragchecker_candidate),
            "ragchecker_raw": _json_sha256(ragchecker_raw),
        },
        "limitations": [
            (
                "The compared response is the official CRAG gold answer. This isolates grounding behavior "
                "but is not a generated-RAG answer-quality comparison."
            ),
            (
                "CRAG correctness references do not independently prove that every gold-answer claim is "
                "supported by the supplied pages."
            ),
            (
                "Acceptance rates, agreement, kappa, and McNemar statistics measure evaluator behavior on "
                "an unreviewed proxy; they are not verifier accuracy or a public SOTA result."
            ),
            "Rows with truncated contexts may create legitimate evaluator disagreement.",
        ],
    }


def render_crag_ragchecker_markdown(report: dict[str, Any]) -> str:
    contexttrace = (report.get("systems") or {}).get("contexttrace") or {}
    ragchecker = (report.get("systems") or {}).get("ragchecker") or {}
    coverage = report.get("coverage") or {}
    agreement = report.get("agreement") or {}
    lines = [
        "# CRAG ContextTrace-RAGChecker Grounding Comparison",
        "",
        "- Status: `review_pending`",
        "- Publishable: `%s`" % str(report.get("publishable")).lower(),
        "- Label scope: `%s`" % report.get("label_scope"),
        "- Matched IDs: `%s / %s`" % (coverage.get("matched_ids"), coverage.get("reference_cases")),
        "- RAGChecker errors: `%s`" % coverage.get("ragchecker_error_rows"),
        "",
        "| System | Proxy Accepted | Acceptance Rate | Flagged |",
        "| --- | ---: | ---: | ---: |",
        "| ContextTrace | %s | %s | %s |"
        % (
            contexttrace.get("proxy_accepted_cases"),
            _percent(contexttrace.get("proxy_acceptance_rate")),
            contexttrace.get("flagged_cases"),
        ),
        "| RAGChecker | %s | %s | %s |"
        % (
            ragchecker.get("proxy_accepted_cases"),
            _percent(ragchecker.get("proxy_acceptance_rate")),
            ragchecker.get("flagged_cases"),
        ),
        "",
        "## Agreement",
        "",
        "| Metric | Value |",
        "| --- | ---: |",
        "| Agreement | %s / %s (%s) |"
        % (agreement.get("cases"), coverage.get("reference_cases"), _percent(agreement.get("rate"))),
        "| Cohen's kappa | %s |" % _number(agreement.get("cohen_kappa")),
        "| Exact McNemar p-value | %s |" % _number(agreement.get("mcnemar_exact_p_value")),
        "| Both accept | %s |" % agreement.get("both_accept"),
        "| Both flag | %s |" % agreement.get("both_flag"),
        "| ContextTrace accepts, RAGChecker flags | %s |"
        % agreement.get("contexttrace_accept_ragchecker_flag"),
        "| ContextTrace flags, RAGChecker accepts | %s |"
        % agreement.get("contexttrace_flag_ragchecker_accept"),
        "",
        "## RAGChecker Mean Diagnostics",
        "",
        "| Metric | Mean |",
        "| --- | ---: |",
    ]
    lines.extend(
        "| `%s` | %s |" % (metric, _number(value))
        for metric, value in sorted((ragchecker.get("mean_metrics") or {}).items())
    )
    lines.extend(["", "## Limitations", ""])
    lines.extend("- %s" % item for item in report.get("limitations") or [])
    lines.append("")
    return "\n".join(lines)


def write_crag_ragchecker_report(
    report: dict[str, Any],
    *,
    json_path: str | Path,
    markdown_path: str | Path,
) -> dict[str, str]:
    json_output = Path(json_path)
    markdown_output = Path(markdown_path)
    json_output.parent.mkdir(parents=True, exist_ok=True)
    markdown_output.parent.mkdir(parents=True, exist_ok=True)
    json_output.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    markdown_output.write_text(render_crag_ragchecker_markdown(report), encoding="utf-8")
    return {"json": str(json_output), "markdown": str(markdown_output)}


def _accepted(row: dict[str, Any]) -> bool:
    return set(row.get("predicted") or []) == {"no_failure_detected"}


def _upstream_metadata(row: dict[str, Any]) -> dict[str, Any]:
    case_pack_metadata = row.get("case_pack_metadata") or {}
    dataset_metadata = case_pack_metadata.get("dataset_metadata") or {}
    metadata = dataset_metadata.get("upstream_metadata") or {}
    return metadata if isinstance(metadata, dict) else {}


def _unique_index(rows: list[dict[str, Any]], field: str, *, name: str) -> dict[str, dict[str, Any]]:
    output = {}
    for row in rows:
        case_id = str(row.get(field) or "")
        if not case_id:
            raise ValueError("%s row is missing %s." % (name, field))
        if case_id in output:
            raise ValueError("%s IDs must be unique; duplicate: %s" % (name, case_id))
        output[case_id] = row
    return output


def _mean_metric(rows: list[dict[str, Any]], metric: str) -> float | None:
    values = []
    for row in rows:
        value = (row.get("metrics") or {}).get(metric)
        try:
            values.append(float(value))
        except (TypeError, ValueError):
            continue
    return round(sum(values) / len(values), 4) if values else None


def _cohen_kappa(
    *,
    total: int,
    both_accept: int,
    both_flag: int,
    contexttrace_accepted: int,
    ragchecker_accepted: int,
) -> float | None:
    observed = (both_accept + both_flag) / total
    contexttrace_accept_rate = contexttrace_accepted / total
    ragchecker_accept_rate = ragchecker_accepted / total
    expected = (
        contexttrace_accept_rate * ragchecker_accept_rate
        + (1 - contexttrace_accept_rate) * (1 - ragchecker_accept_rate)
    )
    if expected == 1:
        return 1.0 if observed == 1 else None
    return round((observed - expected) / (1 - expected), 4)


def _mcnemar_exact_p_value(first_only: int, second_only: int) -> float:
    discordant = first_only + second_only
    if discordant == 0:
        return 1.0
    tail = sum(
        math.comb(discordant, index) * (0.5 ** discordant)
        for index in range(min(first_only, second_only) + 1)
    )
    return round(min(1.0, 2 * tail), 6)


def _json_sha256(value: dict[str, Any]) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _percent(value: Any) -> str:
    return "N/A" if value is None else "%.1f%%" % (float(value) * 100)


def _number(value: Any) -> str:
    return "N/A" if value is None else str(value)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compare ContextTrace and RAGChecker on CRAG proxy rows.")
    parser.add_argument("--contexttrace-results", required=True)
    parser.add_argument("--ragchecker-candidate", required=True)
    parser.add_argument("--ragchecker-raw", required=True)
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--output-markdown", required=True)
    args = parser.parse_args(argv)

    contexttrace_result = json.loads(Path(args.contexttrace_results).read_text(encoding="utf-8"))
    ragchecker_candidate = json.loads(Path(args.ragchecker_candidate).read_text(encoding="utf-8"))
    ragchecker_raw = json.loads(Path(args.ragchecker_raw).read_text(encoding="utf-8"))
    report = build_crag_ragchecker_report(contexttrace_result, ragchecker_candidate, ragchecker_raw)
    paths = write_crag_ragchecker_report(
        report,
        json_path=args.output_json,
        markdown_path=args.output_markdown,
    )
    print("CRAG RAGChecker JSON: %s" % paths["json"])
    print("CRAG RAGChecker Markdown: %s" % paths["markdown"])
    print("Matched IDs: %s" % report["coverage"]["matched_ids"])
    print("Publishable: false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
