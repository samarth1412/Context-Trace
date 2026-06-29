from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any


GROUP_FIELDS = (
    ("domain", "crag_domain"),
    ("question_type", "crag_question_type"),
    ("static_or_dynamic", "crag_static_or_dynamic"),
    ("split", "crag_split"),
)


def build_crag_calibration_report(result: dict[str, Any]) -> dict[str, Any]:
    rows = [row for row in result.get("rows") or [] if isinstance(row, dict)]
    if not rows:
        raise ValueError("CRAG calibration results must contain rows.")
    scopes = Counter(_upstream_metadata(row).get("crag_label_scope") or "missing" for row in rows)
    if set(scopes) != {"unreviewed_gold_answer_proxy"}:
        raise ValueError("CRAG calibration report requires unreviewed_gold_answer_proxy rows only.")

    accepted_rows = [row for row in rows if _accepted(row)]
    flagged_rows = [row for row in rows if not _accepted(row)]
    predicted_labels = Counter(
        label
        for row in rows
        for label in (row.get("predicted") or [])
    )
    contexts = [
        context
        for row in rows
        for context in ((row.get("trace") or {}).get("contexts") or [])
        if isinstance(context, dict)
    ]
    truncated_contexts = sum(str(context.get("text") or "").rstrip().endswith(" ...") for context in contexts)
    return {
        "report": "CRAG gold-answer grounding calibration",
        "report_version": 1,
        "dataset": result.get("case_pack_dataset") or "CRAG-Task1-v5",
        "case_set": result.get("case_set"),
        "mode": result.get("mode"),
        "label_scope": "unreviewed_gold_answer_proxy",
        "publishable": False,
        "summary": {
            "cases": len(rows),
            "proxy_accepted_cases": len(accepted_rows),
            "proxy_acceptance_rate": round(len(accepted_rows) / len(rows), 3),
            "flagged_for_grounding_review_cases": len(flagged_rows),
            "flagged_for_grounding_review_rate": round(len(flagged_rows) / len(rows), 3),
            "contexts": len(contexts),
            "truncated_contexts": truncated_contexts,
            "truncated_context_rate": round(truncated_contexts / len(contexts), 3) if contexts else None,
        },
        "predicted_label_counts": dict(sorted(predicted_labels.items())),
        "by_group": {
            name: _group_summary(rows, metadata_field)
            for name, metadata_field in GROUP_FIELDS
        },
        "flagged_case_ids": [str(row.get("id") or "") for row in flagged_rows],
        "source_result_sha256": _result_sha256(result),
        "limitations": [
            (
                "CRAG gold answers are correctness references, not independent labels that every answer "
                "claim is grounded by the supplied web pages."
            ),
            (
                "Proxy acceptance means ContextTrace emitted only no_failure_detected for a gold answer; "
                "it is not failure-detection accuracy."
            ),
            (
                "Flagged rows require independent source-grounding review before labels, spans, or public "
                "claims are valid."
            ),
            "Truncated page contexts can create legitimate grounding-review flags.",
        ],
    }


def render_crag_calibration_markdown(report: dict[str, Any]) -> str:
    summary = report.get("summary") or {}
    lines = [
        "# CRAG Gold-Answer Grounding Calibration",
        "",
        "- Status: `review_pending`",
        "- Publishable: `%s`" % str(report.get("publishable")).lower(),
        "- Label scope: `%s`" % report.get("label_scope"),
        "- Cases: `%s`" % summary.get("cases"),
        "- Proxy accepted: `%s` (`%s`)"
        % (summary.get("proxy_accepted_cases"), _rate(summary.get("proxy_acceptance_rate"))),
        "- Flagged for grounding review: `%s` (`%s`)"
        % (
            summary.get("flagged_for_grounding_review_cases"),
            _rate(summary.get("flagged_for_grounding_review_rate")),
        ),
        "- Truncated contexts: `%s / %s` (`%s`)"
        % (
            summary.get("truncated_contexts"),
            summary.get("contexts"),
            _rate(summary.get("truncated_context_rate")),
        ),
        "",
        "These are gold-answer grounding-review statistics, not failure-detection accuracy.",
        "",
        "## Predicted Labels",
        "",
        "| Label | Cases |",
        "| --- | ---: |",
    ]
    lines.extend(
        "| `%s` | %s |" % (label, count)
        for label, count in sorted((report.get("predicted_label_counts") or {}).items())
    )
    for group_name, values in (report.get("by_group") or {}).items():
        lines.extend(
            [
                "",
                "## By %s" % group_name.replace("_", " ").title(),
                "",
                "| Value | Cases | Accepted | Acceptance Rate |",
                "| --- | ---: | ---: | ---: |",
            ]
        )
        for value, metrics in sorted(values.items()):
            lines.append(
                "| `%s` | %s | %s | %s |"
                % (value, metrics["cases"], metrics["accepted"], _rate(metrics["acceptance_rate"]))
            )
    lines.extend(["", "## Limitations", ""])
    lines.extend("- %s" % item for item in report.get("limitations") or [])
    lines.append("")
    return "\n".join(lines)


def write_crag_calibration_report(
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
    markdown_output.write_text(render_crag_calibration_markdown(report), encoding="utf-8")
    return {"json": str(json_output), "markdown": str(markdown_output)}


def _accepted(row: dict[str, Any]) -> bool:
    return set(row.get("predicted") or []) == {"no_failure_detected"}


def _upstream_metadata(row: dict[str, Any]) -> dict[str, Any]:
    case_pack_metadata = row.get("case_pack_metadata") or {}
    dataset_metadata = case_pack_metadata.get("dataset_metadata") or {}
    metadata = dataset_metadata.get("upstream_metadata") or {}
    return metadata if isinstance(metadata, dict) else {}


def _group_summary(rows: list[dict[str, Any]], field: str) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        raw_value = _upstream_metadata(row).get(field)
        value = "missing" if raw_value is None or str(raw_value) == "" else str(raw_value)
        grouped.setdefault(value, []).append(row)
    return {
        value: {
            "cases": len(group_rows),
            "accepted": sum(_accepted(row) for row in group_rows),
            "acceptance_rate": round(sum(_accepted(row) for row in group_rows) / len(group_rows), 3),
        }
        for value, group_rows in sorted(grouped.items())
    }


def _result_sha256(result: dict[str, Any]) -> str:
    payload = json.dumps(result, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _rate(value: Any) -> str:
    return "N/A" if value is None else "%.1f%%" % (float(value) * 100)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build a non-publishable CRAG grounding calibration report.")
    parser.add_argument("--results", required=True, help="ContextTrace case-pack result JSON.")
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--output-markdown", required=True)
    args = parser.parse_args(argv)

    result = json.loads(Path(args.results).read_text(encoding="utf-8"))
    report = build_crag_calibration_report(result)
    paths = write_crag_calibration_report(
        report,
        json_path=args.output_json,
        markdown_path=args.output_markdown,
    )
    print("CRAG calibration JSON: %s" % paths["json"])
    print("CRAG calibration Markdown: %s" % paths["markdown"])
    print("Proxy acceptance rate: %s" % report["summary"]["proxy_acceptance_rate"])
    print("Publishable: false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
