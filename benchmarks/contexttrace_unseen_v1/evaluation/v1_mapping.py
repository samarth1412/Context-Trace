"""Pure frozen compatibility mapping for semantic_v1_calibrated claims."""

from __future__ import annotations

import re
from typing import Any, Mapping


ROOT_MAP = {
    "no_failure_detected": "none",
    "retrieval_miss": "retrieval_miss",
    "answer_overreach": "answer_overreach",
    "partial_context_support": "insufficient_selected_context",
    "wrong_source_cited": "citation_mismatch",
    "missing_cited_source": "citation_mismatch",
    "conflicting_contexts": "conflicting_contexts",
    "stale_context": "stale_or_superseded_source",
    "low_authority_source": "noncanonical_or_low_authority_source",
    "insufficient_context": "insufficient_selected_context",
    "corpus_gap": "corpus_gap",
    "should_have_abstained": "failure_to_abstain",
}

CITATION_MAP = {
    "citation_ok": "correct",
    "claim_has_no_citation": "not_applicable",
    "claim_supported_by_different_source": "wrong_source",
    "cited_source_missing": "malformed",
    "cited_source_does_not_support_claim": "wrong_source",
    "citation_partial": "partial",
}

SOURCE_MAP = {
    "current_canonical": "current_canonical",
    "grounded_by_current_canonical_source": "current_canonical",
    "grounded_by_low_authority_source": "low_authority",
    "grounded_but_stale": "stale",
    "stale_source": "stale",
    "stale_or_version_conflicted": "superseded",
    "grounded_but_conflicted": "conflicting_authorities",
    "conflicting_source": "conflicting_authorities",
    "freshness_unknown": "unknown",
}


def _failure_label(
    *,
    verdict: str,
    citation: str,
    source: str,
    root: str,
    should_abstain: bool,
) -> str:
    if (
        source
        in {
            "current_noncanonical",
            "stale",
            "superseded",
            "low_authority",
            "conflicting_authorities",
        }
        and verdict == "supported"
    ):
        return "source_condition_failure"
    if citation in {"partial", "wrong_source", "missing", "malformed"}:
        return "citation_mismatch"
    if should_abstain:
        return "should_have_abstained"
    if root == "retrieval_miss":
        return "retrieval_miss"
    if root in {
        "reranking_failure",
        "chunking_issue",
        "insufficient_selected_context",
    }:
        return "context_selection_error"
    if verdict == "contradicted":
        return "contradiction"
    if verdict == "partially_supported" or root == "answer_overreach":
        return "answer_overreach"
    if verdict in {"unsupported", "unverifiable"}:
        return "insufficient_evidence"
    return "none"


def map_v1_claim(
    claim: Mapping[str, Any],
    *,
    trace_abstention: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    trace_abstention = trace_abstention or {}
    root_record = claim.get("root_cause")
    root_label = (
        str(root_record.get("label") or "")
        if isinstance(root_record, Mapping)
        else str(root_record or "")
    )
    root = ROOT_MAP.get(root_label, "not_observable")
    verdict = str(claim.get("verdict") or "unverifiable")
    citation = CITATION_MAP.get(
        str(claim.get("citation_status") or ""), "not_applicable"
    )
    source = SOURCE_MAP.get(str(claim.get("source_status") or ""), "unknown")
    should_abstain = bool(trace_abstention.get("should_abstain"))
    failure = _failure_label(
        verdict=verdict,
        citation=citation,
        source=source,
        root=root,
        should_abstain=should_abstain,
    )
    raw_spans = claim.get("supporting_spans") or []
    if not raw_spans and isinstance(claim.get("evidence_span"), Mapping):
        raw_spans = [claim["evidence_span"]]
    spans = [
        {
            "context_id": span.get("context_id") or claim.get("best_context_id"),
            "start_char": span.get("start_char", span.get("start")),
            "end_char": span.get("end_char", span.get("end")),
            "text": span.get("text") or span.get("evidence") or "",
            "role": "contradicting" if verdict == "contradicted" else "supporting",
        }
        for span in raw_spans
        if isinstance(span, Mapping)
    ]
    return {
        "claim_id": str(claim.get("claim_id") or ""),
        "text": str(claim.get("claim") or ""),
        "start_char": claim.get("start_char"),
        "end_char": claim.get("end_char"),
        "claim_verdict": verdict,
        "failure_label": failure,
        "primary_root_cause": root,
        "citation_state": citation,
        "source_condition": source,
        "abstention_requirement": ("must_abstain" if should_abstain else "must_answer"),
        "diagnostic_abstention": should_abstain,
        "diagnostic_confidence": claim.get("confidence"),
        "confidence_semantics": "ranking_score_only",
        "route": "deterministic",
        "green": bool(
            verdict == "supported"
            and failure == "none"
            and citation in {"correct", "not_applicable"}
            and source in {"current_canonical", "unknown"}
            and not should_abstain
        ),
        "qualification_required": source == "unknown",
        "evidence_spans": spans,
    }


def map_v1_output(output: Mapping[str, Any]) -> dict[str, Any]:
    raw = output.get("raw_output")
    if not isinstance(raw, Mapping):
        raise ValueError("semantic_v1_calibrated output has no raw_output object.")
    abstention = raw.get("abstention")
    abstention = abstention if isinstance(abstention, Mapping) else {}
    claims = raw.get("claims")
    if not isinstance(claims, list):
        raise ValueError("semantic_v1_calibrated output has no claims list.")
    answer = str(raw.get("answer") or "")
    mapped: list[dict[str, Any]] = []
    cursor = 0
    for claim in claims:
        if not isinstance(claim, Mapping):
            continue
        item = map_v1_claim(claim, trace_abstention=abstention)
        start, end = _locate_claim(answer, item["text"], cursor)
        item["start_char"] = start
        item["end_char"] = end
        if end is not None:
            cursor = end
        mapped.append(item)
    return {
        "case_id": output.get("case_id"),
        "claims": mapped,
        "latency_ms": output.get("latency_ms"),
    }


def _locate_claim(
    answer: str, claim_text: str, cursor: int
) -> tuple[int | None, int | None]:
    candidates = [claim_text, claim_text.rstrip().rstrip(".!?")]
    for candidate in candidates:
        if not candidate:
            continue
        position = answer.find(candidate, cursor)
        if position < 0:
            position = answer.casefold().find(candidate.casefold(), cursor)
        if position >= 0:
            return position, position + len(candidate)
    words = [re.escape(word) for word in claim_text.split()]
    if words:
        match = re.search(
            r"\s+".join(words),
            answer[cursor:],
            flags=re.IGNORECASE,
        )
        if match:
            return cursor + match.start(), cursor + match.end()
    return None, None
