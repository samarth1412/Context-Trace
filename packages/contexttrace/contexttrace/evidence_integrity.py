from __future__ import annotations

import re
import unicodedata
from typing import Any, Iterable

from contexttrace.verify.schema import RAGTrace, TraceContext


EVIDENCE_METADATA_KEY = "contexttrace_evidence"

LINKED_PART_DROPPED = "linked_part_dropped"
MATERIAL_SPAN_DROPPED = "material_span_dropped"
SELECTED_TEXT_NOT_IN_SOURCE = "selected_text_not_in_source"
INVALID_LINEAGE = "invalid_lineage"


def build_evidence_lineage(
    *,
    source_unit_id: str,
    source_text: str,
    linked_parts: Iterable[dict[str, Any]] | None = None,
    material_spans: Iterable[dict[str, Any]] | None = None,
    transformation: str | None = None,
) -> dict[str, Any]:
    """Build namespaced metadata for deterministic source-to-selection checks."""

    unit_id = _required_text(source_unit_id, "source_unit_id")
    text = _required_text(source_text, "source_text")
    lineage: dict[str, Any] = {
        "schema_version": "1.0",
        "source_unit_id": unit_id,
        "source_text": text,
    }
    if linked_parts is not None:
        lineage["linked_parts"] = _build_parts(linked_parts, text, "linked_parts")
    if material_spans is not None:
        lineage["material_spans"] = _build_parts(material_spans, text, "material_spans")
    if transformation is not None:
        lineage["transformation"] = _required_text(transformation, "transformation")
    return {EVIDENCE_METADATA_KEY: lineage}


def audit_evidence_integrity(trace: RAGTrace) -> dict[str, Any]:
    """Report observed evidence loss from explicitly captured lineage metadata."""

    assessments = [_assess_context(context) for context in trace.contexts]
    captured = [item for item in assessments if item["capture_status"] == "captured"]
    unknown = [item for item in assessments if item["capture_status"] != "captured"]
    issues = [issue for item in captured for issue in item["issues"]]
    if not captured:
        status = "not_captured"
    elif issues:
        status = "issues_found"
    elif unknown:
        status = "partial"
    else:
        status = "complete"
    counts: dict[str, int] = {}
    for issue in issues:
        issue_type = str(issue["type"])
        counts[issue_type] = counts.get(issue_type, 0) + 1
    return {
        "schema_version": "1.0",
        "status": status,
        "summary": {
            "total_contexts": len(trace.contexts),
            "assessed_contexts": len(captured),
            "unknown_contexts": len(unknown),
            "issue_count": len(issues),
            "issue_types": counts,
        },
        "issues": issues,
        "contexts": assessments,
        "network_calls": 0,
        "model_calls": 0,
    }


def _assess_context(context: TraceContext) -> dict[str, Any]:
    raw = context.metadata.get(EVIDENCE_METADATA_KEY)
    if raw is None:
        return {
            "selected_context_id": context.id,
            "capture_status": "not_captured",
            "reason": "No contexttrace_evidence lineage metadata was captured.",
            "issues": [],
        }
    if not isinstance(raw, dict):
        return _invalid_context(context.id, "contexttrace_evidence must be an object.")
    source_unit_id = _clean(raw.get("source_unit_id"))
    source_text = _clean(raw.get("source_text"))
    if not source_unit_id or not source_text:
        return _invalid_context(
            context.id,
            "Captured lineage must include non-empty source_unit_id and source_text.",
        )

    selected = _normalize(context.text)
    source = _normalize(source_text)
    linked_parts, invalid_parts = _parts(raw.get("linked_parts"), source_text, "linked_parts")
    material_spans, invalid_spans = _parts(
        raw.get("material_spans"), source_text, "material_spans"
    )
    if invalid_parts or invalid_spans:
        return _invalid_context(context.id, "; ".join(invalid_parts + invalid_spans))

    issues: list[dict[str, Any]] = []
    if selected not in source:
        issues.append(
            _issue(
                issue_type=SELECTED_TEXT_NOT_IN_SOURCE,
                severity="high",
                context_id=context.id,
                source_unit_id=source_unit_id,
                observed="Selected text is not a normalized verbatim span of the captured source unit.",
            )
        )
    else:
        present_parts = [
            part
            for part in linked_parts
            if part["required"] and _normalize(part["text"]) in selected
        ]
        for part in linked_parts:
            if not part["required"] or _normalize(part["text"]) in selected:
                continue
            if present_parts:
                issues.append(
                    _issue(
                        issue_type=LINKED_PART_DROPPED,
                        severity="high",
                        context_id=context.id,
                        source_unit_id=source_unit_id,
                        observed="A required linked part is present in the source unit but absent from the selected text.",
                        item=part,
                    )
                )
        for span in material_spans:
            if span["required"] and _normalize(span["text"]) not in selected:
                issues.append(
                    _issue(
                        issue_type=MATERIAL_SPAN_DROPPED,
                        severity="high",
                        context_id=context.id,
                        source_unit_id=source_unit_id,
                        observed="A declared material span is present in the source unit but absent from the selected text.",
                        item=span,
                    )
                )

    return {
        "selected_context_id": context.id,
        "source_unit_id": source_unit_id,
        "transformation": _clean(raw.get("transformation")) or None,
        "capture_status": "captured",
        "issues": issues,
    }


def _parts(value: Any, source_text: str, field: str) -> tuple[list[dict[str, Any]], list[str]]:
    if value is None:
        return [], []
    if not isinstance(value, list):
        return [], ["%s must be a list." % field]
    parts: list[dict[str, Any]] = []
    invalid: list[str] = []
    for index, item in enumerate(value):
        try:
            part = _part(item, index, field)
        except ValueError as exc:
            invalid.append(str(exc))
            continue
        if _normalize(part["text"]) not in _normalize(source_text):
            invalid.append("%s[%s].text is not present in source_text." % (field, index))
        parts.append(part)
    return parts, invalid


def _build_parts(
    values: Iterable[dict[str, Any]], source_text: str, field: str
) -> list[dict[str, Any]]:
    parts = [_part(value, index, field) for index, value in enumerate(values)]
    for index, part in enumerate(parts):
        if _normalize(part["text"]) not in _normalize(source_text):
            raise ValueError("%s[%s].text must be present in source_text." % (field, index))
    return parts


def _part(value: Any, index: int, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("%s[%s] must be an object." % (field, index))
    required = value.get("required", True)
    if not isinstance(required, bool):
        raise ValueError("%s[%s].required must be a boolean." % (field, index))
    return {
        "id": _required_text(value.get("id"), "%s[%s].id" % (field, index)),
        "role": _required_text(value.get("role"), "%s[%s].role" % (field, index)),
        "text": _required_text(value.get("text"), "%s[%s].text" % (field, index)),
        "required": required,
    }


def _issue(
    *,
    issue_type: str,
    severity: str,
    context_id: str,
    source_unit_id: str,
    observed: str,
    item: dict[str, Any] | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "type": issue_type,
        "status": "observed",
        "severity": severity,
        "selected_context_id": context_id,
        "source_unit_id": source_unit_id,
        "observed": observed,
    }
    if item is not None:
        result.update(
            {
                "item_id": item["id"],
                "item_role": item["role"],
                "missing_text": item["text"],
            }
        )
    return result


def _invalid_context(context_id: str, reason: str) -> dict[str, Any]:
    return {
        "selected_context_id": context_id,
        "capture_status": INVALID_LINEAGE,
        "reason": reason,
        "issues": [],
    }


def _required_text(value: Any, field: str) -> str:
    if not isinstance(value, str):
        raise ValueError("%s must be a non-empty string." % field)
    text = value.strip()
    if not text:
        raise ValueError("%s must be a non-empty string." % field)
    return text


def _clean(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _normalize(value: str) -> str:
    text = unicodedata.normalize("NFKC", value)
    text = text.translate(str.maketrans("“”‘’", "\"\"''"))
    return re.sub(r"\s+", " ", text).strip().casefold()
