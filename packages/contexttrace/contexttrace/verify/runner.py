from __future__ import annotations

from pathlib import Path
from typing import Any

from contexttrace.verify.abstention import judge_abstention
from contexttrace.verify.citations import (
    CITATION_OK,
    CLAIM_HAS_NO_CITATION,
    CLAIM_SUPPORTED_BY_DIFFERENT_SOURCE,
    CITED_SOURCE_DOES_NOT_SUPPORT,
    CITED_SOURCE_MISSING,
    attach_citation_statuses,
    find_citation_for_claim,
)
from contexttrace.verify.claims import extract_claims
from contexttrace.verify.evidence import find_best_evidence, score_claim_against_context
from contexttrace.verify.judges import ClaimJudge, JudgeVerdict, build_judge_provider
from contexttrace.verify.local_nli import LocalNLIError, build_nli_provider
from contexttrace.verify.root_cause import (
    attach_root_causes,
    primary_root_cause,
    root_cause_summary,
)
from contexttrace.verify.schema import RAGTrace, TraceContext, load_trace_file
from contexttrace.verify.source_trust import attach_source_assessments
from contexttrace.verify.statuses import attach_grounding_statuses
from contexttrace.verify.verdicts import classify_claim


def verify_trace_file(
    path: str | Path,
    *,
    mode: str = "lexical",
    judge: ClaimJudge | None = None,
    nli: ClaimJudge | None = None,
) -> dict[str, Any]:
    return verify_trace(load_trace_file(path), mode=mode, judge=judge, nli=nli)


def verify_trace(
    trace: RAGTrace,
    *,
    mode: str = "lexical",
    judge: ClaimJudge | None = None,
    nli: ClaimJudge | None = None,
) -> dict[str, Any]:
    mode = _normalize_mode(mode)
    evidence_mode = _evidence_mode(mode)
    judge = _resolve_judge(mode=mode, judge=judge)
    nli = _resolve_nli(mode=mode, nli=nli)
    claims = extract_claims(trace.answer)
    verifications = []
    for claim in claims:
        match = find_best_evidence(claim.text, trace.contexts, mode=evidence_mode)
        verifications.append(
            classify_claim(claim, match, has_contexts=bool(trace.contexts), mode=evidence_mode)
        )

    if judge is not None:
        verifications = _apply_judge_verdicts(trace, claims, verifications, judge)
    elif nli is not None:
        verifications = _apply_judge_verdicts(trace, claims, verifications, nli)

    verifications = attach_citation_statuses(claims, verifications, trace, mode=evidence_mode)
    if judge is not None:
        verifications = _apply_judge_citation_statuses(trace, claims, verifications, judge, mode=evidence_mode)
    elif nli is not None:
        verifications = _apply_judge_citation_statuses(trace, claims, verifications, nli, mode=evidence_mode)
    abstention = judge_abstention(
        query=trace.query,
        claims=claims,
        contexts=trace.contexts,
        verifications=verifications,
        mode=evidence_mode,
    )
    claim_results = attach_source_assessments(
        [verification.to_dict() for verification in verifications],
        trace,
        mode=evidence_mode,
    )
    claim_results = attach_root_causes(claim_results, abstention)
    claim_results = attach_grounding_statuses(claim_results, trace)
    summary = _summary(verifications, abstention)
    summary["root_causes"] = root_cause_summary(claim_results)
    summary["primary_root_cause"] = primary_root_cause(claim_results)
    summary["source_status"] = _source_status_summary(claim_results)
    diagnostics = _diagnostics(verifications, abstention)
    diagnostics = _augment_diagnostics_with_source_status(diagnostics, claim_results)
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
    normalized = str(mode or "lexical").strip().lower().replace("-", "_")
    if normalized not in {"lexical", "semantic", "local_ml", "judge", "nli"}:
        raise ValueError("Verification mode must be lexical, semantic, local_ml, judge, or nli.")
    return normalized


def _evidence_mode(mode: str) -> str:
    return "semantic" if mode in {"judge", "nli"} else mode


def _resolve_judge(*, mode: str, judge: ClaimJudge | None) -> ClaimJudge | None:
    if mode != "judge":
        return None
    resolved = judge or build_judge_provider()
    if resolved is None:
        raise ValueError(
            "mode='judge' requires a judge provider. Pass judge=..., set "
            "CONTEXTTRACE_JUDGE_PROVIDER=ollama for local judging, or use mode='semantic'."
        )
    return resolved


def _resolve_nli(*, mode: str, nli: ClaimJudge | None) -> ClaimJudge | None:
    if mode != "nli":
        return None
    try:
        resolved = nli or build_nli_provider()
    except LocalNLIError as exc:
        raise ValueError(str(exc)) from exc
    if resolved is None:
        raise ValueError(
            "mode='nli' requires CONTEXTTRACE_NLI_MODEL_PATH or nli=LocalNLIJudge(...). "
            "ContextTrace never downloads NLI models automatically."
        )
    return resolved


def _apply_judge_verdicts(
    trace: RAGTrace,
    claims: list[Any],
    verifications: list[Any],
    judge: ClaimJudge,
) -> list[Any]:
    updated = []
    for claim, verification in zip(claims, verifications):
        verdict = judge.verify_claim(
            query=trace.query,
            claim=claim.text,
            contexts=_selected_span_contexts(verification),
        )
        updated.append(_verification_with_judge(verification, verdict))
    return updated


def _apply_judge_citation_statuses(
    trace: RAGTrace,
    claims: list[Any],
    verifications: list[Any],
    judge: ClaimJudge,
    *,
    mode: str,
) -> list[Any]:
    contexts_by_id = {context.id: context for context in trace.contexts}
    updated = []
    for claim, verification in zip(claims, verifications):
        citation = find_citation_for_claim(claim.text, trace.citations, mode=mode)
        if citation is None:
            updated.append(verification.with_citation(status=CLAIM_HAS_NO_CITATION, source_id=None))
            continue
        cited_context = contexts_by_id.get(citation.source_id)
        if cited_context is None:
            updated.append(verification.with_citation(status=CITED_SOURCE_MISSING, source_id=citation.source_id))
            continue

        cited_match = score_claim_against_context(claim.text, cited_context, mode=mode)
        cited_verdict = judge.verify_claim(
            query=trace.query,
            claim=claim.text,
            contexts=_span_contexts_from_match(cited_match),
        )
        if cited_verdict.verdict == "supported":
            status = CITATION_OK
        elif verification.verdict == "supported" and verification.best_context_id != citation.source_id:
            status = CLAIM_SUPPORTED_BY_DIFFERENT_SOURCE
        else:
            status = CITED_SOURCE_DOES_NOT_SUPPORT
        updated.append(verification.with_citation(status=status, source_id=citation.source_id))
    return updated


def _verification_with_judge(verification: Any, verdict: JudgeVerdict) -> Any:
    return verification.with_judge(
        verdict=verdict.verdict,
        confidence=verdict.confidence,
        reason="Judge verdict: %s" % verdict.reason,
        matched_facts=verdict.matched_facts or list(verification.matched_facts),
        missing_facts=verdict.missing_facts or ([] if verdict.verdict == "supported" else list(verification.missing_facts)),
        conflicting_facts=verdict.conflicting_facts or ([] if verdict.verdict != "contradicted" else list(verification.conflicting_facts)),
        judge={
            "provider": verdict.provider,
            "model": verdict.model,
            "verdict": verdict.verdict,
            "confidence": verdict.confidence,
            "reason": verdict.reason,
            "scope": "selected_evidence_spans",
            "raw": dict(verdict.raw),
        },
    )


def _selected_span_contexts(verification: Any) -> list[TraceContext]:
    contexts = _span_contexts(list(getattr(verification, "supporting_spans", []) or []))
    if contexts:
        return contexts
    evidence_span = getattr(verification, "evidence_span", None)
    if isinstance(evidence_span, dict):
        return _span_contexts([evidence_span])
    return []


def _span_contexts_from_match(match: Any) -> list[TraceContext]:
    contexts = _span_contexts(list(getattr(match, "supporting_spans", []) or []))
    if contexts:
        return contexts
    span = match.span_dict() if hasattr(match, "span_dict") else None
    if isinstance(span, dict):
        return _span_contexts([span])
    return []


def _span_contexts(spans: list[dict[str, Any]]) -> list[TraceContext]:
    contexts: list[TraceContext] = []
    seen = set()
    for span in spans:
        if not isinstance(span, dict):
            continue
        text = str(span.get("text") or "").strip()
        context_id = str(span.get("context_id") or "").strip()
        if not text or not context_id:
            continue
        key = (
            context_id,
            span.get("start_char"),
            span.get("end_char"),
            span.get("span_hash"),
        )
        if key in seen:
            continue
        seen.add(key)
        contexts.append(
            TraceContext(
                id=context_id,
                text=text,
                metadata={
                    "evidence_scope": "selected_span",
                    "source_context_id": context_id,
                    "start_char": span.get("start_char"),
                    "end_char": span.get("end_char"),
                    "span_hash": span.get("span_hash"),
                    "score": span.get("score"),
                },
            )
        )
    return contexts


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
        "grounded_claims": counts["supported"],
        "truth_status": "not_assessed",
        "source_status": "freshness_unknown",
        "truth_assessed": False,
        "source_freshness_assessed": False,
        "support_rate": round(counts["supported"] / total, 3) if total else 1.0,
        "unsupported_claim_rate": round(unsupported_like / total, 3) if total else 0.0,
        "citation_mismatches": citation_mismatches,
        "should_abstain": bool(abstention.get("should_abstain")),
    }


def _source_status_summary(claims: list[dict[str, Any]]) -> str:
    statuses = {str(claim.get("source_status") or "") for claim in claims}
    statuses.discard("")
    if not statuses:
        return "freshness_unknown"
    priority = [
        "cited_source_missing",
        "grounded_but_conflicted",
        "stale_or_version_conflicted",
        "grounded_but_stale",
        "stale_source",
        "conflicting_source",
        "grounded_by_low_authority_source",
        "no_source",
    ]
    for status in priority:
        if status in statuses:
            return status
    if len(statuses) == 1:
        return next(iter(statuses))
    return "mixed"


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


def _augment_diagnostics_with_source_status(
    diagnostics: dict[str, object],
    claims: list[dict[str, Any]],
) -> dict[str, object]:
    failure_types = [
        item
        for item in list(diagnostics.get("failure_types") or [])
        if item != "no_failure_detected"
    ]
    source_statuses = {str(claim.get("source_status") or "") for claim in claims}
    if "grounded_but_conflicted" in source_statuses:
        failure_types.append("source_conflict")
    if "grounded_but_stale" in source_statuses:
        failure_types.append("stale_source")
    if "grounded_by_low_authority_source" in source_statuses:
        failure_types.append("low_authority_source")
    if not failure_types:
        failure_types = ["no_failure_detected"]
    deduped = []
    for failure_type in failure_types:
        if failure_type not in deduped:
            deduped.append(failure_type)
    return {
        **diagnostics,
        "failure_type": deduped[0],
        "failure_types": deduped,
        "suggested_fix": _suggested_fix(deduped),
    }


def _suggested_fix(failure_types: list[str]) -> str:
    if "should_have_abstained" in failure_types:
        return (
            "Add an abstention rule: when retrieved contexts do not support the requested fact, "
            "say the information is unavailable instead of generating a factual answer."
        )
    if "contradicted_answer" in failure_types:
        return "Filter stale or conflicting sources and require the final answer to match the highest-priority evidence."
    if "source_conflict" in failure_types:
        return "Resolve conflicting retrieved sources using canonical, current, or higher-authority evidence before generation."
    if "stale_source" in failure_types:
        return "Refresh stale sources or prefer newer canonical evidence before trusting grounded claims."
    if "low_authority_source" in failure_types:
        return "Prefer canonical or higher-authority sources for this claim, or mark the answer as lower confidence."
    if "unsupported_answer" in failure_types:
        return "Constrain generation to retrieved evidence or retrieve a source that explicitly states the missing claim before answering."
    if "partial_support" in failure_types:
        return "Split compound claims and either remove unsupported details or retrieve evidence that supports each detail explicitly."
    if "citation_mismatch" in failure_types:
        return "Select citations at the claim level and only cite source IDs whose text directly supports that claim."
    if "insufficient_context" in failure_types:
        return "Retrieve more specific context or mark the claim as unavailable when evidence is ambiguous."
    return "No fix is needed for this trace based on the local verifier."
