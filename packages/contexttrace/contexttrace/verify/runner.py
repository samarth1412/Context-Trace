from __future__ import annotations

from pathlib import Path
from typing import Any

from contexttrace.verify.abstention import judge_abstention
from contexttrace.verify.citations import (
    CITATION_OK,
    CLAIM_HAS_NO_CITATION,
    attach_citation_statuses,
)
from contexttrace.verify.claims import extract_claims
from contexttrace.verify.evidence import find_best_evidence
from contexttrace.verify.schema import RAGTrace, load_trace_file
from contexttrace.verify.verdicts import classify_claim


def verify_trace_file(path: str | Path, *, mode: str = "lexical") -> dict[str, Any]:
    return verify_trace(load_trace_file(path), mode=mode)


def verify_trace(trace: RAGTrace, *, mode: str = "lexical") -> dict[str, Any]:
    mode = _normalize_mode(mode)
    claims = extract_claims(trace.answer)
    verifications = []
    for claim in claims:
        match = find_best_evidence(claim.text, trace.contexts, mode=mode)
        verifications.append(
            classify_claim(claim, match, has_contexts=bool(trace.contexts))
        )

    verifications = attach_citation_statuses(claims, verifications, trace, mode=mode)
    claim_results = [verification.to_dict() for verification in verifications]
    abstention = judge_abstention(
        query=trace.query,
        claims=claims,
        contexts=trace.contexts,
        verifications=verifications,
        mode=mode,
    )
    summary = _summary(verifications, abstention)
    diagnostics = _diagnostics(verifications, abstention)
    summary.update(
        {
            "failure_type": diagnostics["failure_type"],
            "failure_types": diagnostics["failure_types"],
            "suggested_fix": diagnostics["suggested_fix"],
            "mode": mode,
        }
    )
    return {
        "query": trace.query,
        "answer": trace.answer,
        "summary": summary,
        "claims": claim_results,
        "abstention": abstention,
        "diagnostics": diagnostics,
        "metadata": dict(trace.metadata),
    }


def _normalize_mode(mode: str) -> str:
    normalized = str(mode or "lexical").strip().lower()
    if normalized not in {"lexical", "semantic"}:
        raise ValueError("Verification mode must be lexical or semantic.")
    return normalized


def _summary(verifications: list[Any], abstention: dict[str, object]) -> dict[str, object]:
    total = len(verifications)
    counts = {
        "supported": len([item for item in verifications if item.verdict == "supported"]),
        "partially_supported": len([item for item in verifications if item.verdict == "partially_supported"]),
        "unsupported": len([item for item in verifications if item.verdict == "unsupported"]),
        "contradicted": len([item for item in verifications if item.verdict == "contradicted"]),
        "unverifiable": len([item for item in verifications if item.verdict == "unverifiable"]),
    }
    citation_mismatches = len(
        [item for item in verifications if item.citation_status != CITATION_OK]
    )
    unsupported_like = (
        counts["partially_supported"]
        + counts["unsupported"]
        + counts["contradicted"]
        + counts["unverifiable"]
    )
    return {
        "total_claims": total,
        **counts,
        "support_rate": round(counts["supported"] / total, 3) if total else 1.0,
        "unsupported_claim_rate": round(unsupported_like / total, 3) if total else 0.0,
        "citation_mismatches": citation_mismatches,
        "should_abstain": bool(abstention.get("should_abstain")),
    }


def _diagnostics(verifications: list[Any], abstention: dict[str, object]) -> dict[str, object]:
    failure_types: list[str] = []
    if abstention.get("should_abstain"):
        failure_types.append("should_have_abstained")
    if any(item.verdict == "contradicted" for item in verifications):
        failure_types.append("contradicted_answer")
    if any(item.verdict == "unsupported" for item in verifications):
        failure_types.append("unsupported_answer")
    if any(item.verdict == "partially_supported" for item in verifications):
        failure_types.append("partial_support")
    if any(item.verdict == "unverifiable" for item in verifications):
        failure_types.append("insufficient_context")
    if any(
        item.citation_status not in {CITATION_OK, CLAIM_HAS_NO_CITATION}
        for item in verifications
    ):
        failure_types.append("citation_mismatch")
    if not failure_types:
        failure_types.append("no_failure_detected")

    failure_type = failure_types[0]
    return {
        "failure_type": failure_type,
        "failure_types": failure_types,
        "suggested_fix": _suggested_fix(failure_types),
    }


def _suggested_fix(failure_types: list[str]) -> str:
    if "should_have_abstained" in failure_types:
        return (
            "Add an abstention rule: when retrieved contexts do not support the requested fact, "
            "say the information is unavailable instead of generating a factual answer."
        )
    if "contradicted_answer" in failure_types:
        return "Filter stale or conflicting sources and require the final answer to match the highest-priority evidence."
    if "unsupported_answer" in failure_types:
        return "Constrain generation to retrieved evidence or retrieve a source that explicitly states the missing claim before answering."
    if "partial_support" in failure_types:
        return "Split compound claims and either remove unsupported details or retrieve evidence that supports each detail explicitly."
    if "citation_mismatch" in failure_types:
        return "Select citations at the claim level and only cite source IDs whose text directly supports that claim."
    if "insufficient_context" in failure_types:
        return "Retrieve more specific context or mark the claim as unavailable when evidence is ambiguous."
    return "No fix is needed for this trace based on the local verifier."
