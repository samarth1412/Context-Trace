from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from ragtruth_adapter import DEFAULT_VERDICT_COUNTS


REVIEWED_STATUSES = {"reviewed", "accepted", "approved"}


def build_review_queue(
    case_pack: dict[str, Any],
    *,
    include_supported: bool = False,
    suggest_source_spans: bool = False,
    max_suggestions: int = 3,
) -> list[dict[str, Any]]:
    rows = []
    for case in case_pack.get("cases") or []:
        if not isinstance(case, dict):
            continue
        spans = ((case.get("ragtruth_metadata") or {}).get("answer_hallucination_spans") or [])
        if not include_supported and not spans:
            continue
        rows.append(
            _review_row(
                case,
                spans,
                suggest_source_spans=suggest_source_spans,
                max_suggestions=max_suggestions,
            )
        )
    return rows


def apply_review_mappings(
    case_pack: dict[str, Any],
    review_rows: list[dict[str, Any]],
    *,
    require_reviewed: bool = False,
    review_file: str | Path | None = None,
) -> dict[str, Any]:
    reviews_by_case = {
        str(row.get("case_id") or row.get("id")): row
        for row in review_rows
        if isinstance(row, dict) and (row.get("case_id") or row.get("id"))
    }
    updated_cases = []
    reviewed_count = 0
    required_review_count = 0
    for case in case_pack.get("cases") or []:
        if not isinstance(case, dict):
            continue
        case_id = str(case.get("id") or "")
        requires_review = bool(((case.get("ragtruth_metadata") or {}).get("answer_hallucination_spans") or []))
        if requires_review:
            required_review_count += 1
        review = reviews_by_case.get(case_id)
        if review is None:
            if require_reviewed and requires_review:
                raise ValueError("Missing review row for case %s." % case_id)
            updated_cases.append(dict(case))
            continue
        reviewed = str(review.get("review_status") or "").lower() in REVIEWED_STATUSES
        if require_reviewed and not reviewed:
            raise ValueError("Case %s is not marked reviewed." % case_id)
        if not reviewed:
            updated_cases.append(dict(case))
            continue
        updated_cases.append(_case_with_review(case, review, reviewed=reviewed))
        reviewed_count += 1

    output = dict(case_pack)
    output["cases"] = updated_cases
    output["review"] = {
        "status": "reviewed" if reviewed_count >= required_review_count else "partial",
        "reviewed_cases": reviewed_count,
        "required_review_cases": required_review_count,
        "total_cases": len(updated_cases),
        "review_file": str(review_file) if review_file else "",
        "applied_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
    }
    limitations = [
        str(item)
        for item in output.get("limitations") or []
        if str(item).strip()
    ]
    limitations.append(
        "RAGTruth evidence spans are human review artifacts derived from answer-side annotations and source passages."
    )
    output["limitations"] = _dedupe(limitations)
    return output


def load_case_pack(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError("Case pack must be a JSON object.")
    return payload


def load_jsonl(path: str | Path) -> list[dict[str, Any]]:
    rows = []
    for line in Path(path).read_text(encoding="utf-8-sig").splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        if isinstance(item, dict):
            rows.append(item)
    return rows


def write_jsonl(rows: list[dict[str, Any]], path: str | Path) -> str:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        "\n".join(json.dumps(row, sort_keys=True) for row in rows) + ("\n" if rows else ""),
        encoding="utf-8",
    )
    return str(output_path)


def write_json(payload: dict[str, Any], path: str | Path) -> str:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return str(output_path)


def write_text(payload: str, path: str | Path) -> str:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(payload, encoding="utf-8")
    return str(output_path)


def build_review_packet(
    review_rows: list[dict[str, Any]],
    *,
    title: str = "RAGTruth Human Evidence Review Packet",
    generated_at: str | None = None,
    context_char_limit: int = 6000,
) -> str:
    generated = generated_at or datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    context_limit = max(0, int(context_char_limit))
    rows = [row for row in review_rows if isinstance(row, dict)]
    lines = [
        "# %s" % _markdown_text(title),
        "",
        "- Generated at: `%s`" % _markdown_text(generated),
        "- Review rows: `%s`" % len(rows),
        "",
        "## Reviewer Instructions",
        "",
        "For each case, inspect the answer-side hallucination spans against the source contexts. "
        "Copy only minimal source text that supports, contradicts, or bounds the labeled answer span into "
        "`source_evidence_spans` in the JSONL review file. Do not accept machine suggestions unless the "
        "source text actually supports the mapping.",
        "",
        "Use `review_status: reviewed`, `accepted`, or `approved` only after checking the source text. "
        "Use `taxonomy_override` when the adapted label or root cause does not match the evidence.",
        "",
        "## Reviewer Checklist",
        "",
        "- Confirm the source context belongs to the same RAGTruth `source_id` as the response.",
        "- Verify each answer hallucination span against source text, not against the model answer alone.",
        "- Prefer the shortest source evidence span that preserves the needed meaning.",
        "- Leave `source_evidence_spans` empty and add `review_notes` if no source span can fairly support the mapping.",
        "- Check whether `expected_labels`, `expected_primary_root_cause`, or `expected_verdict_counts` need a taxonomy override.",
        "- Record reviewer identity and review date before applying the reviewed JSONL.",
        "",
    ]
    for index, row in enumerate(rows, start=1):
        lines.extend(_review_packet_case(row, index=index, context_char_limit=context_limit))
    return "\n".join(lines).rstrip() + "\n"


def validate_review_mappings(
    case_pack: dict[str, Any],
    review_rows: list[dict[str, Any]],
    *,
    require_reviewed: bool = False,
    require_source_spans: bool = False,
) -> dict[str, Any]:
    cases_by_id = {
        str(case.get("id") or ""): case
        for case in case_pack.get("cases") or []
        if isinstance(case, dict) and case.get("id")
    }
    required_case_ids = {
        case_id
        for case_id, case in cases_by_id.items()
        if ((case.get("ragtruth_metadata") or {}).get("answer_hallucination_spans") or [])
    }
    seen_case_ids: set[str] = set()
    errors: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    row_results: list[dict[str, Any]] = []

    for index, row in enumerate(review_rows, start=1):
        if not isinstance(row, dict):
            errors.append(_validation_item("", "row_type", "Review row %s is not a JSON object." % index))
            continue
        case_id = str(row.get("case_id") or row.get("id") or "")
        row_errors: list[str] = []
        row_warnings: list[str] = []
        if not case_id:
            row_errors.append("Missing case_id.")
        elif case_id in seen_case_ids:
            row_errors.append("Duplicate review row for case_id %s." % case_id)
        else:
            seen_case_ids.add(case_id)

        case = cases_by_id.get(case_id)
        if case_id and case is None:
            row_errors.append("Review row case_id is not present in the case pack.")

        status = str(row.get("review_status") or "").strip().lower()
        reviewed = status in REVIEWED_STATUSES
        if require_reviewed and not reviewed:
            row_errors.append("Review status must be one of %s." % ", ".join(sorted(REVIEWED_STATUSES)))
        if reviewed:
            if not str(row.get("reviewer") or "").strip():
                row_errors.append("Reviewed row must include reviewer.")
            if not str(row.get("reviewed_at") or "").strip():
                row_errors.append("Reviewed row must include reviewed_at.")

        answer_spans = _answer_spans_for_validation(row, case)
        source_spans = [str(span) for span in row.get("source_evidence_spans") or [] if str(span).strip()]
        if reviewed and require_source_spans and answer_spans and not source_spans:
            row_errors.append("Reviewed row with answer hallucination spans must include source_evidence_spans.")
        if source_spans:
            context_texts = _source_context_texts_for_validation(row, case)
            for span in source_spans:
                if not _span_in_contexts(span, context_texts):
                    row_errors.append("source_evidence_spans entry is not found in the source contexts: %s" % span)
        elif reviewed and answer_spans:
            row_warnings.append("Reviewed hallucination row has no source_evidence_spans.")

        for message in row_errors:
            errors.append(_validation_item(case_id, "row", message))
        for message in row_warnings:
            warnings.append(_validation_item(case_id, "row", message))

        row_results.append(
            {
                "case_id": case_id,
                "reviewed": reviewed,
                "answer_hallucination_span_count": len(answer_spans),
                "source_evidence_span_count": len(source_spans),
                "error_count": len(row_errors),
                "warning_count": len(row_warnings),
            }
        )

    missing_required = sorted(required_case_ids - seen_case_ids)
    for case_id in missing_required:
        item = _validation_item(case_id, "missing_review", "Missing review row for hallucination case.")
        if require_reviewed:
            errors.append(item)
        else:
            warnings.append(item)

    reviewed_rows = sum(1 for row in row_results if row["reviewed"])
    source_span_rows = sum(1 for row in row_results if row["source_evidence_span_count"] > 0)
    return {
        "valid": not errors,
        "review_rows": len(row_results),
        "reviewed_rows": reviewed_rows,
        "required_review_rows": len(required_case_ids),
        "missing_required_review_rows": missing_required,
        "source_span_rows": source_span_rows,
        "errors": errors,
        "warnings": warnings,
        "rows": row_results,
        "requirements": {
            "require_reviewed": require_reviewed,
            "require_source_spans": require_source_spans,
        },
    }


def _review_row(
    case: dict[str, Any],
    spans: list[dict[str, Any]],
    *,
    suggest_source_spans: bool,
    max_suggestions: int,
) -> dict[str, Any]:
    source_contexts = [
        {
            "id": context.get("id"),
            "text": context.get("text"),
            "source_id": context.get("source_id") or (context.get("metadata") or {}).get("source_id"),
        }
        for context in case.get("contexts") or []
        if isinstance(context, dict)
    ]
    return {
        "case_id": str(case.get("id") or ""),
        "review_status": "needs_review",
        "reviewer": "",
        "reviewed_at": "",
        "review_notes": "",
        "source": case.get("source"),
        "query": case.get("query"),
        "answer": case.get("answer"),
        "expected_labels": list(case.get("expected_labels") or []),
        "expected_primary_root_cause": case.get("expected_primary_root_cause"),
        "expected_verdict_counts": dict(case.get("expected_verdict_counts") or {}),
        "answer_hallucination_spans": spans,
        "source_contexts": source_contexts,
        "source_evidence_span_suggestions": (
            _source_span_suggestions(case, spans, source_contexts, max_suggestions=max_suggestions)
            if suggest_source_spans
            else []
        ),
        "source_evidence_spans": [],
        "taxonomy_override": {
            "expected_labels": [],
            "expected_primary_root_cause": "",
            "expected_verdict_counts": {},
        },
    }


def _case_with_review(case: dict[str, Any], review: dict[str, Any], *, reviewed: bool) -> dict[str, Any]:
    updated = dict(case)
    source_spans = [str(span) for span in review.get("source_evidence_spans") or [] if str(span).strip()]
    if source_spans:
        updated["expected_evidence_spans"] = source_spans

    override = review.get("taxonomy_override") if isinstance(review.get("taxonomy_override"), dict) else {}
    labels = _labels_from_review(review, override)
    if labels:
        updated["expected_labels"] = labels
        updated["expected_verdict_counts"] = _verdict_counts_from_review(review, override, labels)
    root_cause = str(override.get("expected_primary_root_cause") or review.get("expected_primary_root_cause") or "").strip()
    if root_cause:
        updated["expected_primary_root_cause"] = root_cause

    updated["review_metadata"] = {
        "review_status": str(review.get("review_status") or ""),
        "reviewed": reviewed,
        "reviewer": str(review.get("reviewer") or ""),
        "reviewed_at": str(review.get("reviewed_at") or ""),
        "review_notes": str(review.get("review_notes") or ""),
        "source_evidence_span_count": len(source_spans),
    }
    return updated


def _labels_from_review(review: dict[str, Any], override: dict[str, Any]) -> list[str]:
    labels = override.get("expected_labels") or review.get("expected_labels") or []
    if isinstance(labels, str):
        labels = [labels]
    return sorted({str(label) for label in labels if str(label).strip()})


def _verdict_counts_from_review(
    review: dict[str, Any],
    override: dict[str, Any],
    labels: list[str],
) -> dict[str, int]:
    raw_counts = override.get("expected_verdict_counts") or review.get("expected_verdict_counts") or {}
    counts = {verdict: int(raw_counts.get(verdict) or 0) for verdict in DEFAULT_VERDICT_COUNTS}
    if any(counts.values()):
        return counts
    labels_set = set(labels)
    if "contradicted_answer" in labels_set:
        counts["contradicted"] = 1
    elif "partial_support" in labels_set:
        counts["partially_supported"] = 1
    elif "unsupported_answer" in labels_set or "should_have_abstained" in labels_set:
        counts["unsupported"] = 1
    else:
        counts["supported"] = 1
    return counts


def _dedupe(values: list[str]) -> list[str]:
    seen = set()
    output = []
    for value in values:
        normalized = " ".join(str(value).split())
        if normalized and normalized not in seen:
            seen.add(normalized)
            output.append(normalized)
    return output


def _source_span_suggestions(
    case: dict[str, Any],
    spans: list[dict[str, Any]],
    source_contexts: list[dict[str, Any]],
    *,
    max_suggestions: int,
) -> list[dict[str, Any]]:
    if not spans or not source_contexts or max_suggestions <= 0:
        return []
    answer = str(case.get("answer") or "")
    candidates = []
    for span in spans:
        label_text = str(span.get("text") or "")
        query = _suggestion_query(answer, span)
        for context in source_contexts:
            for sentence in _sentence_windows(str(context.get("text") or "")):
                score = _overlap_score(query, sentence)
                if score <= 0.0:
                    continue
                candidates.append(
                    {
                        "context_id": context.get("id"),
                        "source_id": context.get("source_id"),
                        "text": sentence,
                        "score": score,
                        "answer_span_text": label_text,
                        "label_type": str(span.get("label_type") or ""),
                    }
                )
    candidates = sorted(
        candidates,
        key=lambda item: (
            -float(item["score"]),
            str(item["context_id"] or ""),
            str(item["text"]),
        ),
    )
    deduped = []
    seen = set()
    for candidate in candidates:
        key = (candidate.get("context_id"), " ".join(str(candidate.get("text") or "").split()).lower())
        if key in seen:
            continue
        seen.add(key)
        deduped.append(candidate)
        if len(deduped) >= max_suggestions:
            break
    return deduped


def _suggestion_query(answer: str, span: dict[str, Any]) -> str:
    label_text = str(span.get("text") or "")
    start = _int_or_none(span.get("start"))
    end = _int_or_none(span.get("end"))
    if start is None or end is None or not answer:
        return label_text
    left = max(start - 120, 0)
    right = min(end + 120, len(answer))
    return "%s %s" % (label_text, answer[left:right])


def _sentence_windows(text: str) -> list[str]:
    sentences: list[str] = []
    current = []
    for char in text:
        current.append(char)
        if char in ".!?\n":
            sentence = "".join(current).strip()
            if sentence:
                sentences.append(sentence)
            current = []
    tail = "".join(current).strip()
    if tail:
        sentences.append(tail)

    windows = []
    for index, sentence in enumerate(sentences):
        windows.append(sentence)
        if index + 1 < len(sentences):
            windows.append("%s %s" % (sentence, sentences[index + 1]))
    return _dedupe(windows)


def _overlap_score(left: str, right: str) -> float:
    left_tokens = _important_tokens(left)
    right_tokens = _important_tokens(right)
    if not left_tokens or not right_tokens:
        return 0.0
    overlap = len(set(left_tokens) & set(right_tokens))
    if not overlap:
        return 0.0
    precision = overlap / len(set(right_tokens))
    recall = overlap / len(set(left_tokens))
    return round((2 * precision * recall / (precision + recall)), 3) if precision + recall else 0.0


def _important_tokens(value: str) -> list[str]:
    stopwords = {
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "but",
        "by",
        "for",
        "from",
        "in",
        "is",
        "it",
        "of",
        "on",
        "or",
        "that",
        "the",
        "this",
        "to",
        "was",
        "were",
        "with",
    }
    tokens = []
    for raw in str(value or "").split():
        token = raw.strip(".,:;!?()[]{}\"'").lower()
        if len(token) < 3 or token in stopwords:
            continue
        tokens.append(token)
    return tokens


def _int_or_none(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _review_packet_case(row: dict[str, Any], *, index: int, context_char_limit: int) -> list[str]:
    case_id = str(row.get("case_id") or row.get("id") or "case_%s" % index)
    lines = [
        "## Case %s: `%s`" % (index, _markdown_text(case_id)),
        "",
        "| Field | Value |",
        "| --- | --- |",
        "| Review status | `%s` |" % _markdown_cell(row.get("review_status") or ""),
        "| Source | %s |" % _markdown_cell(row.get("source") or ""),
        "| Expected labels | `%s` |" % _markdown_cell(", ".join(str(item) for item in row.get("expected_labels") or [])),
        "| Expected root cause | `%s` |" % _markdown_cell(row.get("expected_primary_root_cause") or ""),
        "",
        "### Query",
        "",
        _code_block(row.get("query") or ""),
        "",
        "### Answer",
        "",
        _code_block(row.get("answer") or ""),
        "",
        "### Answer Hallucination Spans",
        "",
    ]
    spans = [span for span in row.get("answer_hallucination_spans") or [] if isinstance(span, dict)]
    if spans:
        lines.extend(
            [
                "| # | Label Type | Offsets | Text |",
                "| ---: | --- | --- | --- |",
            ]
        )
        for span_index, span in enumerate(spans, start=1):
            offsets = "%s-%s" % (span.get("start", ""), span.get("end", ""))
            lines.append(
                "| %s | %s | `%s` | %s |"
                % (
                    span_index,
                    _markdown_cell(span.get("label_type") or ""),
                    _markdown_cell(offsets),
                    _markdown_cell(span.get("text") or ""),
                )
            )
    else:
        lines.append("_No answer-side hallucination spans on this row._")
    lines.extend(["", "### Source Evidence Suggestions", ""])
    suggestions = [
        suggestion
        for suggestion in row.get("source_evidence_span_suggestions") or []
        if isinstance(suggestion, dict)
    ]
    if suggestions:
        lines.extend(
            [
                "| # | Score | Context | Answer Span | Suggested Source Text |",
                "| ---: | ---: | --- | --- | --- |",
            ]
        )
        for suggestion_index, suggestion in enumerate(suggestions, start=1):
            lines.append(
                "| %s | `%s` | `%s` | %s | %s |"
                % (
                    suggestion_index,
                    _markdown_cell(suggestion.get("score") or ""),
                    _markdown_cell(suggestion.get("context_id") or ""),
                    _markdown_cell(suggestion.get("answer_span_text") or ""),
                    _markdown_cell(suggestion.get("text") or ""),
                )
            )
    else:
        lines.append("_No machine suggestions were generated for this row._")

    lines.extend(["", "### Source Contexts", ""])
    contexts = [context for context in row.get("source_contexts") or [] if isinstance(context, dict)]
    if contexts:
        for context in contexts:
            context_id = str(context.get("id") or "")
            source_id = str(context.get("source_id") or "")
            text = str(context.get("text") or "")
            excerpt, truncated = _truncate_for_packet(text, context_char_limit)
            lines.extend(
                [
                    "#### Context `%s`" % _markdown_text(context_id),
                    "",
                    "- RAGTruth source id: `%s`" % _markdown_text(source_id),
                    "- Truncated in packet: `%s`" % ("yes" if truncated else "no"),
                    "",
                    _code_block(excerpt),
                    "",
                ]
            )
    else:
        lines.append("_No source contexts are available for this row._")
        lines.append("")

    lines.extend(
        [
            "### Review Output Fields",
            "",
            "Fill these fields in the JSONL row after review:",
            "",
            "- `review_status`",
            "- `reviewer`",
            "- `reviewed_at`",
            "- `review_notes`",
            "- `source_evidence_spans`",
            "- `taxonomy_override` if needed",
            "",
        ]
    )
    return lines


def _truncate_for_packet(value: str, limit: int) -> tuple[str, bool]:
    text = str(value or "")
    if limit <= 0 or len(text) <= limit:
        return text, False
    return text[:limit].rstrip() + "\n[truncated]", True


def _code_block(value: Any) -> str:
    text = str(value or "").replace("```", "` ` `")
    return "```text\n%s\n```" % text


def _markdown_cell(value: Any) -> str:
    return _markdown_text(value).replace("|", "\\|").replace("\n", "<br>")


def _markdown_text(value: Any) -> str:
    return str(value or "").replace("\r\n", "\n").replace("\r", "\n")


def _answer_spans_for_validation(row: dict[str, Any], case: dict[str, Any] | None) -> list[dict[str, Any]]:
    row_spans = row.get("answer_hallucination_spans") or []
    if row_spans:
        return [span for span in row_spans if isinstance(span, dict)]
    if case is None:
        return []
    return [
        span
        for span in ((case.get("ragtruth_metadata") or {}).get("answer_hallucination_spans") or [])
        if isinstance(span, dict)
    ]


def _source_context_texts_for_validation(row: dict[str, Any], case: dict[str, Any] | None) -> list[str]:
    row_contexts = [
        str(context.get("text") or "")
        for context in row.get("source_contexts") or []
        if isinstance(context, dict) and str(context.get("text") or "").strip()
    ]
    if row_contexts:
        return row_contexts
    if case is None:
        return []
    return [
        str(context.get("text") or "")
        for context in case.get("contexts") or []
        if isinstance(context, dict) and str(context.get("text") or "").strip()
    ]


def _span_in_contexts(span: str, context_texts: list[str]) -> bool:
    normalized_span = _normalize_review_text(span)
    if not normalized_span:
        return False
    return any(normalized_span in _normalize_review_text(context) for context in context_texts)


def _normalize_review_text(value: str) -> str:
    return " ".join(str(value or "").casefold().split())


def _validation_item(case_id: str, check: str, message: str) -> dict[str, str]:
    return {
        "case_id": case_id,
        "check": check,
        "message": message,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build or apply RAGTruth human-review mappings.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    queue_parser = subparsers.add_parser("build-queue", help="Build a JSONL review queue from a RAGTruth case pack.")
    queue_parser.add_argument("--case-pack", required=True)
    queue_parser.add_argument("--output", required=True)
    queue_parser.add_argument("--include-supported", action="store_true")
    queue_parser.add_argument("--suggest-source-spans", action="store_true", help="Prefill scored source-evidence suggestions for reviewers.")
    queue_parser.add_argument("--max-suggestions", default=3, type=int, help="Maximum source-evidence suggestions per review row.")

    apply_parser = subparsers.add_parser("apply", help="Apply reviewed source evidence spans to a RAGTruth case pack.")
    apply_parser.add_argument("--case-pack", required=True)
    apply_parser.add_argument("--review", required=True)
    apply_parser.add_argument("--output", required=True)
    apply_parser.add_argument("--require-reviewed", action="store_true")

    packet_parser = subparsers.add_parser("build-packet", help="Build a Markdown packet from a JSONL review queue.")
    packet_parser.add_argument("--review-queue", "--input", dest="review_queue", required=True)
    packet_parser.add_argument("--output", required=True)
    packet_parser.add_argument("--title", default="RAGTruth Human Evidence Review Packet")
    packet_parser.add_argument("--context-char-limit", default=6000, type=int)

    validate_parser = subparsers.add_parser("validate", help="Validate a reviewed RAGTruth JSONL file.")
    validate_parser.add_argument("--case-pack", required=True)
    validate_parser.add_argument("--review", required=True)
    validate_parser.add_argument("--output")
    validate_parser.add_argument("--require-reviewed", action="store_true")
    validate_parser.add_argument("--require-source-spans", action="store_true")

    args = parser.parse_args(argv)
    if args.command == "build-queue":
        rows = build_review_queue(
            load_case_pack(args.case_pack),
            include_supported=args.include_supported,
            suggest_source_spans=args.suggest_source_spans,
            max_suggestions=args.max_suggestions,
        )
        written = write_jsonl(rows, args.output)
        print("Wrote %s" % written)
        print("Review rows: %s" % len(rows))
        return 0

    if args.command == "build-packet":
        rows = load_jsonl(args.review_queue)
        packet = build_review_packet(
            rows,
            title=args.title,
            context_char_limit=args.context_char_limit,
        )
        written = write_text(packet, args.output)
        print("Wrote %s" % written)
        print("Review rows: %s" % len(rows))
        return 0

    if args.command == "validate":
        report = validate_review_mappings(
            load_case_pack(args.case_pack),
            load_jsonl(args.review),
            require_reviewed=args.require_reviewed,
            require_source_spans=args.require_source_spans,
        )
        if args.output:
            written = write_json(report, args.output)
            print("Wrote %s" % written)
        print("Valid: %s" % str(report["valid"]).lower())
        print("Review rows: %s" % report["review_rows"])
        print("Reviewed rows: %s" % report["reviewed_rows"])
        print("Errors: %s" % len(report["errors"]))
        print("Warnings: %s" % len(report["warnings"]))
        return 0 if report["valid"] else 1

    reviewed = apply_review_mappings(
        load_case_pack(args.case_pack),
        load_jsonl(args.review),
        require_reviewed=args.require_reviewed,
        review_file=args.review,
    )
    written = write_json(reviewed, args.output)
    print("Wrote %s" % written)
    print("Reviewed cases: %s / %s" % (reviewed["review"]["reviewed_cases"], reviewed["review"]["total_cases"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
