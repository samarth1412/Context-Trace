"""High-precision relationship checks for the experimental hybrid verifier."""

from __future__ import annotations

import csv
from dataclasses import dataclass, replace
import io
import json
import re
from typing import Any

from contexttrace.verify.citations import CITATION_OK, CITED_SOURCE_DOES_NOT_SUPPORT
from contexttrace.verify.schema import RAGTrace


@dataclass(frozen=True)
class RelationSignal:
    verdict: str
    basis: str
    context_id: str
    evidence: str


def refine_relational_verifications(
    verifications: list[Any],
    trace: RAGTrace,
    mode: str,
) -> list[Any]:
    """Refine only relations that can be read deterministically from a source."""
    if mode != "semantic":
        return verifications
    refined = []
    for verification in verifications:
        signal = assess_relation(trace.query, verification.claim, trace)
        if signal is None:
            refined.append(verification)
            continue
        citation_status = verification.citation_status
        cited_ids = {
            citation.source_id
            for citation in trace.citations
            if citation.claim == verification.claim
        }
        if signal.context_id in cited_ids:
            citation_status = CITATION_OK if signal.verdict == "supported" else CITED_SOURCE_DOES_NOT_SUPPORT
        reason = (
            f"The experimental relationship check {signal.basis} found that the cited evidence "
            f"{'supports' if signal.verdict == 'supported' else 'conflicts with'} the claim."
        )
        refined.append(
            replace(
                verification,
                verdict=signal.verdict,
                confidence=max(float(verification.confidence), 0.94),
                evidence=signal.evidence,
                matched_facts=[verification.claim] if signal.verdict == "supported" else [],
                missing_facts=[],
                conflicting_facts=[] if signal.verdict == "supported" else [verification.claim],
                required_fact_details=[],
                matched_fact_details=[],
                missing_fact_details=[],
                conflicting_fact_details=[],
                reason=reason,
                citation_status=citation_status,
            )
        )
    return refined


def assess_relation(query: str, claim: str, trace: RAGTrace) -> RelationSignal | None:
    for context in trace.contexts:
        checks = (
            _structured_signal(query, claim, context.id, context.text),
            _prohibited_order_signal(claim, context.id, context.text),
            _conditional_exception_signal(claim, context.id, context.text),
            _exclusive_scope_signal(query, claim, context.id, context.text),
        )
        for signal in checks:
            if signal is not None:
                return signal
    return None


def _structured_signal(query: str, claim: str, context_id: str, text: str) -> RelationSignal | None:
    json_signal = _json_signal(query, claim, context_id, text)
    if json_signal is not None:
        return json_signal
    table = _parse_table(text)
    if table is None:
        return None
    headers, rows = table
    query_text = _normalized(query)
    target_rows = [row for row in rows if _contains(query_text, row[0])]
    if len(target_rows) != 1:
        return None
    target = target_rows[0]
    for column in range(1, len(headers)):
        if not (_contains(query_text, headers[column]) or _contains(_normalized(claim), headers[column])):
            continue
        expected = target[column]
        if _contains(_normalized(claim), expected):
            return RelationSignal("supported", "structured_row_binding", context_id, text)
        competing = [row[column] for row in rows if row is not target and len(row) > column]
        if any(_contains(_normalized(claim), value) for value in competing):
            return RelationSignal("contradicted", "structured_row_binding", context_id, text)
    return None


def _json_signal(query: str, claim: str, context_id: str, text: str) -> RelationSignal | None:
    try:
        value = json.loads(text)
    except (TypeError, json.JSONDecodeError):
        return None
    if not isinstance(value, dict):
        return None
    query_tokens = set(_tokens(query))
    relevant = []
    for key, item in value.items():
        if isinstance(item, (dict, list)):
            continue
        key_tokens = set(_tokens(str(key).replace("_", " ")))
        if query_tokens & key_tokens:
            relevant.append(str(item))
    if len(relevant) != 1:
        return None
    expected = relevant[0]
    normalized_claim = _normalized(claim)
    if _contains(normalized_claim, expected):
        return RelationSignal("supported", "json_field_binding", context_id, text)
    if _numbers(claim) and _numbers(expected) and set(_numbers(claim)) != set(_numbers(expected)):
        return RelationSignal("contradicted", "json_field_binding", context_id, text)
    return None


def _parse_table(text: str) -> tuple[list[str], list[list[str]]] | None:
    lines = [line.strip() for line in str(text or "").splitlines() if line.strip()]
    if len(lines) < 2:
        return None
    if all("|" in line for line in lines):
        parsed = [[cell.strip() for cell in line.strip("|").split("|")] for line in lines]
        parsed = [row for row in parsed if not all(re.fullmatch(r":?-{3,}:?", cell) for cell in row)]
    elif all("," in line for line in lines):
        parsed = [[cell.strip() for cell in row] for row in csv.reader(io.StringIO("\n".join(lines)))]
    else:
        return None
    if len(parsed) < 2 or len({len(row) for row in parsed}) != 1 or len(parsed[0]) < 2:
        return None
    return parsed[0], parsed[1:]


def _prohibited_order_signal(claim: str, context_id: str, text: str) -> RelationSignal | None:
    relation = re.search(
        r"\b(?:must|should|may|can|cannot|can't)\s+([a-z][^.]{0,90}?\bbefore\b[^.]{1,90})[.!]?$",
        _normalized(claim),
    )
    if relation is None:
        return None
    ordered = relation.group(1).strip()
    evidence = _normalized(text)
    prohibited = re.search(
        rf"\b(?:never|must\s+not|should\s+not|do\s+not|cannot)\s+{re.escape(ordered)}\b",
        evidence,
    )
    if prohibited:
        return RelationSignal("contradicted", "prohibited_operation_order", context_id, prohibited.group(0))
    return None


def _conditional_exception_signal(claim: str, context_id: str, text: str) -> RelationSignal | None:
    normalized_claim = _normalized(claim)
    permission = re.search(r"\b(.{1,80}?)\s+(?:may|can)\s+be\s+([a-z]+)", normalized_claim)
    if permission is None:
        return None
    action = permission.group(2)
    for sentence in re.split(r"(?<=[.!?])\s+", _normalized(text)):
        prohibition = re.search(
            rf"\b(.{{1,60}}?)\s+(?:cannot|may\s+not|must\s+not)\s+be\s+{re.escape(action)}"
            r"(?:\s+unless\s+(?:(?:they|it|the\s+item)\s+)?"
            r"(?:(?:are|is|arrived|arrive)\s+)?([a-z]+))?",
            sentence,
        )
        if prohibition is None:
            continue
        subject_terms = set(_tokens(permission.group(1)))
        prohibited_terms = set(_tokens(prohibition.group(1)))
        if not subject_terms & prohibited_terms:
            continue
        exception = prohibition.group(2)
        if exception and not _excludes_exception(normalized_claim, exception):
            continue
        return RelationSignal("contradicted", "conditional_exception", context_id, sentence)
    return None


def _exclusive_scope_signal(query: str, claim: str, context_id: str, text: str) -> RelationSignal | None:
    normalized = _normalized(text)
    exclusive = re.search(r"\b([a-z0-9_-]+)\s+includes\s+([^.]+?)\s+only\b", normalized)
    assigned = re.search(r"\b([a-z0-9_-]+(?:\s+[a-z0-9_-]+)?)\s+(?:is|are)\s+available\s+on\s+(?:the\s+)?([a-z0-9_-]+)", normalized)
    if exclusive is None or assigned is None:
        return None
    target, allowed = exclusive.group(1), exclusive.group(2)
    feature, owner = assigned.group(1), assigned.group(2)
    query_claim = _normalized(f"{query} {claim}")
    if not (_contains(query_claim, target) and _contains(query_claim, feature)):
        return None
    if _contains(allowed, feature) or target == owner:
        return None
    negated = bool(re.search(r"\b(?:not|no|cannot|can't|doesn't|does\s+not)\b", _normalized(claim)))
    verdict = "supported" if negated else "contradicted"
    return RelationSignal(verdict, "exclusive_feature_scope", context_id, text)


def _excludes_exception(claim: str, exception: str) -> bool:
    return bool(
        re.search(rf"\b(?:un{re.escape(exception)}|not\s+{re.escape(exception)})\b", claim)
    )


def _normalized(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def _tokens(value: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", _normalized(value))


def _numbers(value: str) -> list[str]:
    return re.findall(r"\b\d+(?:\.\d+)?\b", str(value or ""))


def _contains(text: str, value: str) -> bool:
    normalized_value = _normalized(value)
    if not normalized_value:
        return False
    flexible = re.escape(normalized_value).replace(r"\ ", r"[\s_-]+")
    return bool(re.search(rf"(?<![a-z0-9]){flexible}(?![a-z0-9])", text))
