from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


DEFAULT_VERDICT_COUNTS = {
    "supported": 0,
    "partially_supported": 0,
    "unsupported": 0,
    "contradicted": 0,
    "unverifiable": 0,
}


def adapt_ragtruth_rows(
    response_rows: list[dict[str, Any]],
    *,
    source_rows: list[dict[str, Any]] | None = None,
    split: str | None = None,
    quality: str | None = "good",
    limit: int | None = None,
) -> dict[str, Any]:
    """Convert RAGTruth response/source exports into a ContextTrace case pack.

    RAGTruth labels answer-side hallucination spans. ContextTrace-Bench scores
    source-side evidence localization, so this adapter intentionally leaves
    `expected_evidence_spans` empty until a human curator maps answer spans to
    source evidence spans.
    """

    sources = _source_index(source_rows or [])
    cases = []
    skipped_missing_source = 0
    skipped_filtered = 0
    for index, row in enumerate(response_rows):
        if split and str(row.get("split") or "") != split:
            skipped_filtered += 1
            continue
        if quality is not None and str(row.get("quality") or "good") != quality:
            skipped_filtered += 1
            continue
        source_row = sources.get(str(row.get("source_id") or ""))
        case = _case_from_response(row, source_row, index=index)
        if not case["contexts"]:
            skipped_missing_source += 1
            continue
        cases.append(case)
        if limit is not None and len(cases) >= int(limit):
            break

    return {
        "description": (
            "RAGTruth case pack adapted for ContextTrace external validation. "
            "These cases are scaffolding until answer-side hallucination spans "
            "are human-mapped to source-side evidence spans."
        ),
        "dataset": "RAGTruth",
        "adapter": "ragtruth_contexttrace_case_pack",
        "source_files": {
            "responses": "response.jsonl",
            "sources": "source_info.jsonl",
        },
        "cases": cases,
        "stats": {
            "input_responses": len(response_rows),
            "output_cases": len(cases),
            "skipped_filtered": skipped_filtered,
            "skipped_missing_source": skipped_missing_source,
        },
        "notes": [
            "RAGTruth publishes response.jsonl and source_info.jsonl separately, joined by source_id.",
            "labels are answer-side hallucination spans; expected_evidence_spans require human curation before span-overlap claims.",
            "good-quality rows without hallucination spans map to no_failure_detected; span-labeled rows map to partial_support or contradicted_answer.",
        ],
    }


def load_rows(path: str | Path) -> list[dict[str, Any]]:
    input_path = Path(path)
    if input_path.suffix.lower() == ".jsonl":
        return [
            item
            for item in (
                json.loads(line)
                for line in input_path.read_text(encoding="utf-8-sig").splitlines()
                if line.strip()
            )
            if isinstance(item, dict)
        ]
    payload = json.loads(input_path.read_text(encoding="utf-8-sig"))
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for key in ("responses", "source_info", "rows", "cases"):
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
    raise ValueError("Could not find rows in %s." % input_path)


def write_case_pack(case_pack: dict[str, Any], path: str | Path) -> str:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(case_pack, indent=2, sort_keys=True), encoding="utf-8")
    return str(output_path)


def _case_from_response(
    row: dict[str, Any],
    source_row: dict[str, Any] | None,
    *,
    index: int,
) -> dict[str, Any]:
    response_id = str(row.get("id") or index)
    source_id = str(row.get("source_id") or "")
    source_info = _first_value(source_row or {}, ["source_info"])
    query = _query_text(row, source_row or {}, source_info, source_id=source_id)
    context_text = _context_text(source_info)
    expected_labels, expected_verdict_counts, root_cause = _expected_outcome(row.get("labels") or [])
    answer_spans = _answer_spans(row.get("labels") or [])
    context = (
        [
            {
                "id": "ragtruth_source_%s" % (source_id or response_id),
                "source": "RAGTruth",
                "source_id": source_id,
                "task_type": str((source_row or {}).get("task_type") or ""),
                "text": context_text,
            }
        ]
        if context_text
        else []
    )
    task_type = str((source_row or {}).get("task_type") or "unknown")
    upstream_source = str((source_row or {}).get("source") or "unknown")
    return {
        "id": "ragtruth_%s" % response_id,
        "source": "RAGTruth/%s/%s" % (task_type, upstream_source),
        "note": (
            "Adapted from RAGTruth response %s. Human review is required before "
            "using source-evidence span metrics because RAGTruth labels answer-side spans."
        )
        % response_id,
        "query": query,
        "answer": str(row.get("response") or row.get("answer") or ""),
        "contexts": context,
        "citations": [],
        "expected_labels": expected_labels,
        "expected_verdict_counts": expected_verdict_counts,
        "expected_citation_statuses": [],
        "expected_should_abstain": False,
        "expected_primary_root_cause": root_cause,
        "expected_evidence_spans": [],
        "ragtruth_metadata": {
            "response_id": response_id,
            "source_id": source_id,
            "model": str(row.get("model") or ""),
            "split": str(row.get("split") or ""),
            "quality": str(row.get("quality") or ""),
            "answer_hallucination_spans": answer_spans,
        },
    }


def _expected_outcome(labels: Any) -> tuple[list[str], dict[str, int], str]:
    span_labels = [label for label in labels if isinstance(label, dict)] if isinstance(labels, list) else []
    counts = dict(DEFAULT_VERDICT_COUNTS)
    if not span_labels:
        counts["supported"] = 1
        return ["no_failure_detected"], counts, "no_failure_detected"

    label_types = [str(label.get("label_type") or "").lower() for label in span_labels]
    if any("conflict" in label_type or "contradict" in label_type for label_type in label_types):
        counts["contradicted"] = 1
        return ["contradicted_answer"], counts, "conflicting_contexts"

    counts["partially_supported"] = 1
    return ["partial_support"], counts, "answer_overreach"


def _answer_spans(labels: Any) -> list[dict[str, Any]]:
    if not isinstance(labels, list):
        return []
    spans = []
    for label in labels:
        if not isinstance(label, dict):
            continue
        spans.append(
            {
                "text": str(label.get("text") or ""),
                "start": label.get("start"),
                "end": label.get("end"),
                "label_type": str(label.get("label_type") or ""),
                "due_to_null": bool(label.get("due_to_null")) if "due_to_null" in label else None,
                "implicit_true": bool(label.get("implicit_true")) if "implicit_true" in label else None,
            }
        )
    return spans


def _source_index(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        str(row.get("source_id")): row
        for row in rows
        if row.get("source_id") is not None
    }


def _query_text(
    response_row: dict[str, Any],
    source_row: dict[str, Any],
    source_info: Any,
    *,
    source_id: str,
) -> str:
    if isinstance(source_info, dict) and source_info.get("question"):
        return str(source_info["question"])
    prompt = _first_value(source_row, ["prompt"]) or _first_value(response_row, ["prompt", "instruction", "query"])
    if prompt:
        return str(prompt)
    return "Evaluate the RAGTruth response for source %s." % (source_id or "unknown")


def _context_text(source_info: Any) -> str:
    if source_info is None:
        return ""
    if isinstance(source_info, str):
        return source_info.strip()
    if isinstance(source_info, dict):
        for field in ("passages", "context", "document", "source", "source_text"):
            value = source_info.get(field)
            if isinstance(value, str) and value.strip():
                return value.strip()
            if isinstance(value, list):
                text = "\n\n".join(str(item) for item in value if str(item).strip())
                if text.strip():
                    return text.strip()
        return json.dumps(source_info, sort_keys=True)
    return str(source_info).strip()


def _first_value(row: dict[str, Any], fields: list[str]) -> Any:
    for field in fields:
        value = row.get(field)
        if value is not None and value != "":
            return value
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Adapt RAGTruth exports into a ContextTrace case pack.")
    parser.add_argument("--response", required=True, help="RAGTruth response.jsonl or equivalent JSON rows.")
    parser.add_argument("--source-info", required=True, help="RAGTruth source_info.jsonl or equivalent JSON rows.")
    parser.add_argument("--output", required=True, help="ContextTrace case-pack JSON to write.")
    parser.add_argument("--split", default=None, help="Optional RAGTruth split filter, such as train or test.")
    parser.add_argument("--quality", default="good", help="Quality filter. Use 'any' to keep all rows.")
    parser.add_argument("--limit", default=None, type=int, help="Optional maximum number of output cases.")
    args = parser.parse_args(argv)

    quality = None if str(args.quality).lower() == "any" else args.quality
    case_pack = adapt_ragtruth_rows(
        load_rows(args.response),
        source_rows=load_rows(args.source_info),
        split=args.split,
        quality=quality,
        limit=args.limit,
    )
    written = write_case_pack(case_pack, args.output)
    print("Wrote %s" % written)
    print("Cases: %s" % len(case_pack["cases"]))
    print("Skipped missing source: %s" % case_pack["stats"]["skipped_missing_source"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
