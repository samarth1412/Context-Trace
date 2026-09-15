from __future__ import annotations

import re
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any, Callable

from contexttrace.contracts import (
    CLAIM_VERIFICATION_SCHEMA_VERSION,
    artifact_provenance,
    verification_profile_id,
)

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
from contexttrace.verify.evidence import (
    extract_numbers,
    find_best_evidence,
    lexical_score,
    score_claim_against_context,
    unique_important_tokens,
)
from contexttrace.verify.judges import ClaimJudge, JudgeVerdict, build_judge_provider
from contexttrace.verify.local_nli import LocalNLIError, build_nli_provider
from contexttrace.verify.root_cause import (
    attach_root_causes,
    primary_root_cause,
    root_cause_summary,
)
from contexttrace.verify.schema import RAGTrace, TraceContext, load_trace_file
from contexttrace.verify.semantic_normalization import semantic_normalization
from contexttrace.verify.source_trust import attach_source_assessments
from contexttrace.verify.statuses import attach_grounding_statuses
from contexttrace.verify.verdicts import classify_claim


@dataclass(frozen=True)
class VerificationProfile:
    citation_alignment: bool = True
    contradiction_checks: bool = True
    abstention_logic: bool = True
    source_assessment: bool = True
    root_cause_inference: bool = True
    evidence_span_localization: bool = True
    semantic_normalization: bool = True

    def to_dict(self) -> dict[str, bool]:
        return asdict(self)


FULL_VERIFICATION_PROFILE = VerificationProfile()


@dataclass(frozen=True)
class VerificationLimits:
    """Optional explicit bounds for production verification workloads."""

    max_contexts: int | None = None
    max_context_chars: int | None = None
    max_answer_chars: int | None = None

    def __post_init__(self) -> None:
        for name in ("max_contexts", "max_context_chars", "max_answer_chars"):
            value = getattr(self, name)
            if value is not None and value < 0:
                raise ValueError("%s must be zero or greater." % name)


def verify_trace_file(
    path: str | Path,
    *,
    mode: str = "lexical",
    judge: ClaimJudge | None = None,
    nli: ClaimJudge | None = None,
    profile: VerificationProfile | None = None,
    limits: VerificationLimits | None = None,
) -> dict[str, Any]:
    return verify_trace(
        load_trace_file(path),
        mode=mode,
        judge=judge,
        nli=nli,
        profile=profile,
        limits=limits,
    )


def verify_trace(
    trace: RAGTrace,
    *,
    mode: str = "lexical",
    judge: ClaimJudge | None = None,
    nli: ClaimJudge | None = None,
    profile: VerificationProfile | None = None,
    limits: VerificationLimits | None = None,
) -> dict[str, Any]:
    mode = _normalize_mode(mode)
    profile = profile or FULL_VERIFICATION_PROFILE
    trace, truncation = _apply_limits(trace, limits)
    with semantic_normalization(profile.semantic_normalization):
        result = _verify_trace_with_profile(trace, mode=mode, judge=judge, nli=nli, profile=profile)
    result["truncation"] = truncation
    return result


def verify_traces(
    traces: list[RAGTrace],
    *,
    mode: str = "lexical",
    judge: ClaimJudge | None = None,
    nli: ClaimJudge | None = None,
    profile: VerificationProfile | None = None,
    limits: VerificationLimits | None = None,
) -> list[dict[str, Any]]:
    """Verify a batch with one stable profile and explicit workload limits."""

    return [
        verify_trace(
            trace,
            mode=mode,
            judge=judge,
            nli=nli,
            profile=profile,
            limits=limits,
        )
        for trace in traces
    ]


def _apply_limits(
    trace: RAGTrace,
    limits: VerificationLimits | None,
) -> tuple[RAGTrace, dict[str, Any]]:
    original_context_count = len(trace.contexts)
    original_context_chars = sum(len(context.text) for context in trace.contexts)
    original_answer_chars = len(trace.answer)
    if limits is None:
        return trace, {
            "applied": False,
            "contexts_original": original_context_count,
            "contexts_used": original_context_count,
            "context_chars_original": original_context_chars,
            "context_chars_used": original_context_chars,
            "answer_chars_original": original_answer_chars,
            "answer_chars_used": original_answer_chars,
        }

    contexts = list(trace.contexts)
    if limits.max_contexts is not None:
        contexts = contexts[: limits.max_contexts]
    if limits.max_context_chars is not None:
        remaining = limits.max_context_chars
        bounded: list[TraceContext] = []
        for context in contexts:
            if remaining <= 0:
                break
            text = context.text[:remaining]
            metadata = dict(context.metadata)
            if len(text) < len(context.text):
                metadata["contexttrace_truncated"] = True
            if text:
                bounded.append(replace(context, text=text, metadata=metadata))
            remaining -= len(text)
        contexts = bounded
    answer = trace.answer
    if limits.max_answer_chars is not None:
        answer = answer[: limits.max_answer_chars]
    limited = replace(trace, contexts=contexts, answer=answer)
    used_context_chars = sum(len(context.text) for context in contexts)
    return limited, {
        "applied": True,
        "contexts_original": original_context_count,
        "contexts_used": len(contexts),
        "context_chars_original": original_context_chars,
        "context_chars_used": used_context_chars,
        "answer_chars_original": original_answer_chars,
        "answer_chars_used": len(answer),
        "contexts_truncated": len(contexts) < original_context_count or used_context_chars < original_context_chars,
        "answer_truncated": len(answer) < original_answer_chars,
    }


def _verify_trace_with_profile(
    trace: RAGTrace,
    *,
    mode: str,
    judge: ClaimJudge | None,
    nli: ClaimJudge | None,
    profile: VerificationProfile,
    reasoning_mode: str = "legacy",
    verification_refiner: Callable[[list[Any], RAGTrace, str], list[Any]] | None = None,
) -> dict[str, Any]:
    hybrid_reasoning = reasoning_mode == "hybrid_v2"
    evidence_mode = _evidence_mode(mode)
    judge = _resolve_judge(mode=mode, judge=judge)
    nli = _resolve_nli(mode=mode, nli=nli)
    claims = extract_claims(trace.answer)
    verifications = []
    for claim in claims:
        match = find_best_evidence(
            claim.text,
            trace.contexts,
            mode=evidence_mode,
            localize_spans=profile.evidence_span_localization,
        )
        verifications.append(
            classify_claim(
                claim,
                match,
                has_contexts=bool(trace.contexts),
                mode=evidence_mode,
                contradiction_checks=profile.contradiction_checks,
            )
        )

    if judge is not None:
        verifications = _apply_judge_verdicts(trace, claims, verifications, judge)
    elif nli is not None:
        verifications = _apply_judge_verdicts(trace, claims, verifications, nli)

    if profile.citation_alignment:
        verifications = attach_citation_statuses(claims, verifications, trace, mode=evidence_mode)
        if judge is not None:
            verifications = _apply_judge_citation_statuses(trace, claims, verifications, judge, mode=evidence_mode)
        elif nli is not None:
            verifications = _apply_judge_citation_statuses(trace, claims, verifications, nli, mode=evidence_mode)
    if verification_refiner is not None:
        verifications = verification_refiner(verifications, trace, evidence_mode)
    if hybrid_reasoning:
        verifications = _refine_context_gaps(verifications, trace, mode=evidence_mode)
    else:
        verifications = _refine_authoritative_corpus_gaps(verifications, trace)
    abstention = (
        judge_abstention(
            query=trace.query,
            claims=claims,
            contexts=trace.contexts,
            verifications=verifications,
            mode=evidence_mode,
            localize_spans=profile.evidence_span_localization,
        )
        if profile.abstention_logic
        else {
            "should_abstain": False,
            "reason": "Abstention logic disabled by the verification profile.",
        }
    )
    base_claim_results = [verification.to_dict() for verification in verifications]
    if hybrid_reasoning:
        base_claim_results = _attach_evidence_relevance(
            base_claim_results,
            trace,
            mode=evidence_mode,
        )
    if profile.source_assessment:
        claim_results = attach_source_assessments(
            base_claim_results,
            trace,
            mode=evidence_mode,
            metadata_free_reasoning=hybrid_reasoning,
        )
    else:
        claim_results = [
            {
                **claim,
                "source_status": "freshness_unknown",
                "source_assessment": {},
            }
            for claim in base_claim_results
        ]
    abstention = _augment_abstention_with_source_status(
        abstention,
        claim_results,
        metadata_free_reasoning=hybrid_reasoning,
    )
    if profile.root_cause_inference:
        claim_results = attach_root_causes(claim_results, abstention)
    claim_results = attach_grounding_statuses(claim_results, trace)
    summary = _summary(verifications, abstention)
    summary["root_causes"] = root_cause_summary(claim_results) if profile.root_cause_inference else {}
    summary["primary_root_cause"] = primary_root_cause(claim_results) if profile.root_cause_inference else ""
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
        **artifact_provenance(
            schema_version=CLAIM_VERIFICATION_SCHEMA_VERSION,
            profile_id=verification_profile_id(profile.to_dict()),
        ),
        "query": trace.query,
        "answer": trace.answer,
        "summary": summary,
        "claims": claim_results,
        "abstention": abstention,
        "diagnostics": diagnostics,
        "metadata": dict(trace.metadata),
        "verification_profile": profile.to_dict(),
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
    partial_answer = bool(abstention.get("partial_answer"))
    if abstention.get("should_abstain"):
        failure_types.append("should_have_abstained")
    if any(item.verdict == "contradicted" for item in verifications):
        failure_types.append("contradicted_answer")
    if any(item.verdict == "unsupported" for item in verifications) and not partial_answer:
        failure_types.append("unsupported_answer")
    if partial_answer or any(item.verdict == "partially_supported" for item in verifications):
        failure_types.append("partial_support")
    if any(item.verdict == "unverifiable" for item in verifications) and not partial_answer:
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
        if any(_has_direct_polarity_conflict(claim) for claim in claims):
            failure_types.append("contradicted_answer")
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


def _refine_authoritative_corpus_gaps(
    verifications: list[Any],
    trace: RAGTrace,
) -> list[Any]:
    """Preserve the frozen v1 metadata-backed evidence-gap behavior."""

    contexts = {context.id: context for context in trace.contexts}
    refined = []
    for verification in verifications:
        context = contexts.get(verification.best_context_id)
        metadata = dict(getattr(context, "metadata", {}) or {})
        freshness = str(
            metadata.get("freshness")
            or metadata.get("freshness_status")
            or metadata.get("source_status")
            or ""
        ).strip().lower()
        explicitly_incomplete = freshness == "incomplete" or metadata.get("source_status") == "incomplete"
        is_gap = bool(
            verification.verdict == "unsupported"
            and float(verification.best_score or 0.0) >= 0.15
            and verification.matched_terms
            and metadata.get("canonical") is True
            and not metadata.get("stale")
            and (freshness in {"current", "fresh", "active", "latest"} or explicitly_incomplete)
            and verification.missing_facts
        )
        if is_gap:
            refined.append(
                replace(
                    verification,
                    verdict="unverifiable",
                    confidence=round(max(0.55, float(verification.best_score or 0.0)), 3),
                    reason=(
                        "A current canonical context is topically relevant, but it does not contain "
                        "the requested fact; absence is not evidence that the claim is false."
                    ),
                )
            )
        else:
            refined.append(verification)
    return refined


def _refine_context_gaps(
    verifications: list[Any],
    trace: RAGTrace,
    *,
    mode: str,
) -> list[Any]:
    """Separate relevant-but-insufficient evidence from unrelated retrieval misses."""
    contexts = {context.id: context for context in trace.contexts}
    query_match = find_best_evidence(trace.query, trace.contexts, mode=mode)
    query_relevant = bool(
        query_match.context_id
        and query_match.score >= 0.30
        and len(query_match.matched_terms) >= 2
    )
    has_grounded_claim = any(
        verification.verdict in {"supported", "partially_supported"}
        for verification in verifications
    )
    refined = []
    for verification in verifications:
        _claim_query_score, claim_query_terms = lexical_score(
            verification.claim,
            trace.query,
            mode=mode,
        )
        context = contexts.get(verification.best_context_id)
        metadata = dict(getattr(context, "metadata", {}) or {})
        freshness = str(
            metadata.get("freshness")
            or metadata.get("freshness_status")
            or metadata.get("source_status")
            or ""
        ).strip().lower()
        explicitly_incomplete = freshness == "incomplete" or metadata.get("source_status") == "incomplete"
        citation = find_citation_for_claim(verification.claim, trace.citations, mode=mode)
        citation_relevant = bool(
            citation
            and query_match.context_id
            and citation.source_id == query_match.context_id
        )
        authoritative_gap = bool(
            verification.verdict == "unsupported"
            and float(verification.best_score or 0.0) >= 0.15
            and verification.matched_terms
            and metadata.get("canonical") is True
            and not metadata.get("stale")
            and (freshness in {"current", "fresh", "active", "latest"} or explicitly_incomplete)
            and verification.missing_facts
        )
        relevant_context_gap = bool(
            verification.verdict == "unsupported"
            and verification.missing_facts
            and query_relevant
            and (
                citation_relevant
                or (
                    bool(claim_query_terms)
                    and (
                        not has_grounded_claim
                        or _claim_addresses_query_focus(verification.claim, trace.query, mode=mode)
                    )
                )
            )
            and not _has_competing_numeric_value(verification.claim, query_match.context_text)
        )
        if authoritative_gap or relevant_context_gap:
            relevance_reason = (
                "A current canonical context is topically relevant"
                if authoritative_gap
                else "A retrieved context is relevant to the user's question"
            )
            refined.append(
                replace(
                    verification,
                    verdict="unverifiable",
                    confidence=round(
                        max(0.55, float(verification.best_score or 0.0), float(query_match.score or 0.0)),
                        3,
                    ),
                    reason=(
                        "%s, but it does not contain the claimed fact; absence is not evidence "
                        "that the claim is false." % relevance_reason
                    ),
                )
            )
        else:
            refined.append(verification)
    return refined


def _has_competing_numeric_value(claim_text: str, context_text: str) -> bool:
    claim_numbers = set(extract_numbers(claim_text))
    context_numbers = set(extract_numbers(context_text))
    return bool(claim_numbers and context_numbers and not claim_numbers.issubset(context_numbers))


def _claim_addresses_query_focus(claim_text: str, query: str, *, mode: str) -> bool:
    """Require an insufficient-evidence claim to answer the question, not add a new topic."""
    text = str(query or "").strip()
    focus_text = ""
    fronted = re.search(
        r"^\s*(?:what|which)\s+(?!(?:does|do|did|can|is|are|was|were)\b)"
        r"(.+?)\s+(?:does|do|did|can|is|are|was|were)\b",
        text,
        flags=re.IGNORECASE,
    )
    if fronted:
        focus_text = fronted.group(1)
    else:
        remainder = re.search(
            r"^\s*(?:what|which)\s+(?:does|do|did|can|is|are|was|were)\s+(.+?)[?.!]*$",
            text,
            flags=re.IGNORECASE,
        )
        if remainder:
            tokens = unique_important_tokens(remainder.group(1), mode=mode)
            focus_text = tokens[-1] if tokens else ""
    focus_terms = set(unique_important_tokens(focus_text, mode=mode))
    if not focus_terms:
        return True
    claim_terms = set(unique_important_tokens(claim_text, mode=mode))
    return bool(focus_terms.intersection(claim_terms))


def _attach_evidence_relevance(
    claims: list[dict[str, Any]],
    trace: RAGTrace,
    *,
    mode: str,
) -> list[dict[str, Any]]:
    query_match = find_best_evidence(trace.query, trace.contexts, mode=mode)
    query_relevant = bool(
        query_match.context_id
        and query_match.score >= 0.30
        and len(query_match.matched_terms) >= 2
    )
    contexts = {context.id: context for context in trace.contexts}
    annotated = []
    for claim in claims:
        best_context = contexts.get(str(claim.get("best_context_id") or ""))
        best_metadata = dict(getattr(best_context, "metadata", {}) or {})
        authoritative = bool(
            best_metadata.get("canonical")
            or str(best_metadata.get("source_authority") or "").lower()
            in {"canonical", "official", "primary", "high", "trusted", "source_of_truth"}
        )
        if str(claim.get("verdict") or "") == "unverifiable" and query_relevant:
            basis = "query_context_overlap"
        elif str(claim.get("verdict") or "") == "unverifiable" and authoritative:
            basis = "authoritative_source_metadata"
        elif claim.get("matched_terms"):
            basis = "claim_context_overlap"
        else:
            basis = "none"
        annotated.append(
            {
                **claim,
                "evidence_relevance": {
                    "basis": basis,
                    "context_id": query_match.context_id if query_relevant else None,
                    "score": query_match.score if query_relevant else 0.0,
                    "matched_terms": list(query_match.matched_terms) if query_relevant else [],
                },
            }
        )
    return annotated


def _augment_abstention_with_source_status(
    abstention: dict[str, object],
    claims: list[dict[str, Any]],
    *,
    metadata_free_reasoning: bool = False,
) -> dict[str, object]:
    unsafe = set()
    for claim in claims:
        status = str(claim.get("source_status") or "")
        assessment = claim.get("source_assessment") if isinstance(claim.get("source_assessment"), dict) else {}
        if status == "grounded_but_conflicted":
            unsafe.add(status)
        elif status == "grounded_but_stale" and assessment.get(
            "query_requires_current_source"
            if metadata_free_reasoning
            else "query_requests_current"
        ):
            unsafe.add(status)
        best_metadata = ((assessment.get("best_source") or {}).get("metadata") or {})
        if status == "incomplete" and bool(best_metadata.get("requires_abstention")):
            unsafe.add("incomplete_context")
    if not unsafe:
        return abstention
    return {
        **abstention,
        "should_abstain": True,
        "reason": (
            "The answer is textually grounded, but the selected evidence is stale or conflicts "
            "with a stronger retrieved source."
        ),
        "source_safety_override": sorted(unsafe),
    }


def _has_direct_polarity_conflict(claim: dict[str, Any]) -> bool:
    assessment = claim.get("source_assessment") if isinstance(claim.get("source_assessment"), dict) else {}
    claim_text = str(claim.get("claim") or "").lower()
    pairs = (
        ("enable", "disable"),
        ("allow", "prohibit"),
        ("permit", "forbid"),
        ("require", "optional"),
        ("increase", "decrease"),
        ("accept", "reject"),
    )
    for signal in assessment.get("stronger_conflicting_sources") or []:
        evidence = str((signal or {}).get("evidence") or "").lower()
        if any(
            (left in claim_text and right in evidence)
            or (right in claim_text and left in evidence)
            for left, right in pairs
        ):
            return True
    return False


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
