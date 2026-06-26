from __future__ import annotations

import argparse
import csv
import json
import urllib.request
from pathlib import Path
from typing import Any


ARES_EXAMPLE_URLS = {
    "labeled": (
        "https://raw.githubusercontent.com/stanford-futuredata/ARES/main/"
        "datasets/example_files/nq_labeled_output.tsv"
    ),
    "unlabeled": (
        "https://raw.githubusercontent.com/stanford-futuredata/ARES/main/"
        "datasets/example_files/nq_unlabeled_output.tsv"
    ),
}


def download_ares_example(kind: str, output_dir: str | Path) -> str:
    normalized = str(kind or "").strip().lower()
    if normalized not in ARES_EXAMPLE_URLS:
        raise ValueError("kind must be one of: %s" % ", ".join(sorted(ARES_EXAMPLE_URLS)))
    output_path = Path(output_dir) / ("nq_%s_output.tsv" % normalized)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(ARES_EXAMPLE_URLS[normalized], timeout=120) as response:
        output_path.write_bytes(response.read())
    return str(output_path)


def load_ares_tsv(path: str | Path) -> list[dict[str, str]]:
    input_path = Path(path)
    with input_path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = [dict(row) for row in csv.DictReader(handle, delimiter="\t") if isinstance(row, dict)]
    return [
        row
        for row in rows
        if str(row.get("id") or "").strip()
        and str(row.get("Query") or row.get("input") or "").strip()
        and str(row.get("Answer") or "").strip()
        and str(row.get("Document") or "").strip()
    ]


def adapt_ares_rows(
    rows: list[dict[str, Any]],
    *,
    dataset: str = "ARES-NQ-example",
    source_name: str = "ARES/NQ example",
    include_context_relevance_negatives: bool = False,
) -> list[dict[str, Any]]:
    output = []
    for row in rows:
        if _context_relevance_only_negative(row) and not include_context_relevance_negatives:
            continue
        labels, root_cause, mapping_reason = _expected_from_ares_labels(row)
        answer = str(row.get("Answer") or "").strip()
        document = str(row.get("Document") or "").strip()
        evidence_spans = _evidence_spans(answer, document, labels)
        source_id = "ares_doc_%s" % _slug(row.get("id") or len(output))
        output.append(
            {
                "id": str(row.get("id") or len(output)),
                "source": source_name,
                "query": str(row.get("Query") or row.get("input") or "").strip(),
                "answer": answer,
                "contexts": [
                    {
                        "id": source_id,
                        "text": document,
                        "metadata": {
                            "wikipedia_id": str(row.get("wikipedia_id") or ""),
                            "paragraph_number": str(row.get("paragraph_number") or ""),
                        },
                    }
                ],
                "expected_label": labels,
                "expected_primary_root_cause": root_cause,
                "expected_evidence_spans": evidence_spans,
                "metadata": {
                    "dataset": dataset,
                    "ares_id": str(row.get("id") or ""),
                    "ares_input": str(row.get("input") or ""),
                    "ares_context_relevance_label": _label_value(row.get("Context_Relevance_Label")),
                    "ares_answer_faithfulness_label": _label_value(row.get("Answer_Faithfulness_Label")),
                    "ares_answer_relevance_label": _label_value(row.get("Answer_Relevance_Label")),
                    "ares_mapping_reason": mapping_reason,
                },
            }
        )
    return output


def _context_relevance_only_negative(row: dict[str, Any]) -> bool:
    return (
        _label_value(row.get("Context_Relevance_Label")) == "0.0"
        and not _label_value(row.get("Answer_Faithfulness_Label"))
        and not _label_value(row.get("Answer_Relevance_Label"))
    )


def write_jsonl_rows(rows: list[dict[str, Any]], path: str | Path) -> str:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        "\n".join(json.dumps(row, sort_keys=True) for row in rows) + ("\n" if rows else ""),
        encoding="utf-8",
    )
    return str(output_path)


def _expected_from_ares_labels(row: dict[str, Any]) -> tuple[list[str], str, str]:
    context_relevance = _label_value(row.get("Context_Relevance_Label"))
    faithfulness = _label_value(row.get("Answer_Faithfulness_Label"))
    answer_relevance = _label_value(row.get("Answer_Relevance_Label"))
    if context_relevance == "1.0" and faithfulness == "1.0" and answer_relevance == "1.0":
        return ["no_failure_detected"], "no_failure_detected", "all_ares_labels_positive"
    if context_relevance == "0.0":
        return ["should_have_abstained", "unsupported_answer"], "should_have_abstained", "ares_context_not_relevant"
    if faithfulness == "0.0":
        return ["should_have_abstained", "unsupported_answer"], "should_have_abstained", "ares_answer_not_faithful"
    if answer_relevance == "0.0":
        return ["should_have_abstained"], "should_have_abstained", "ares_answer_not_relevant"
    return (
        ["should_have_abstained", "unsupported_answer"],
        "should_have_abstained",
        "ares_partial_or_missing_component_labels",
    )


def _evidence_spans(answer: str, document: str, labels: list[str]) -> list[str]:
    if labels != ["no_failure_detected"]:
        return []
    answer_text = " ".join(answer.split())
    document_text = str(document or "")
    if not answer_text:
        return []
    index = document_text.lower().find(answer_text.lower())
    if index < 0:
        return []
    return [document_text[index : index + len(answer_text)]]


def _label_value(value: Any) -> str:
    text = str(value or "").strip()
    if text in {"1", "1.0", "1.00"}:
        return "1.0"
    if text in {"0", "0.0", "0.00"}:
        return "0.0"
    return ""


def _slug(value: object) -> str:
    text = "".join(char.lower() if char.isalnum() else "_" for char in str(value or "case"))
    text = "_".join(part for part in text.split("_") if part)
    return text or "case"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Normalize official ARES example TSV rows into generic ContextTrace external JSONL rows."
    )
    parser.add_argument("--input", help="ARES TSV file. Omit when using --download-example.")
    parser.add_argument("--output", required=True, help="Generic external JSONL rows to write.")
    parser.add_argument("--dataset", default="ARES-NQ-example")
    parser.add_argument("--source-name", default="ARES/NQ example")
    parser.add_argument(
        "--include-context-relevance-negatives",
        action="store_true",
        help=(
            "Keep ARES rows where only Context_Relevance_Label is 0.0. "
            "By default these retrieval-relevance rows are skipped for answer-grounding runs."
        ),
    )
    parser.add_argument("--download-example", choices=["labeled", "unlabeled"])
    parser.add_argument("--download-dir", default=str(Path(__file__).with_name("out") / "ares_nq_example"))
    args = parser.parse_args(argv)

    input_path = args.input
    if args.download_example:
        input_path = download_ares_example(args.download_example, args.download_dir)
    if not input_path:
        parser.error("--input or --download-example is required.")

    rows = adapt_ares_rows(
        load_ares_tsv(input_path),
        dataset=args.dataset,
        source_name=args.source_name,
        include_context_relevance_negatives=args.include_context_relevance_negatives,
    )
    written = write_jsonl_rows(rows, args.output)
    print("Wrote: %s" % written)
    print("Input: %s" % input_path)
    print("Rows: %s" % len(rows))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
